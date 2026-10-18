"""Local document extraction, embeddings and bounded cosine retrieval."""
import asyncio
import hashlib
import io
import json
import os
import re
from pathlib import Path
import httpx
import numpy as np
from pypdf import PdfReader

MODEL = os.getenv("YOUAI_EMBED_MODEL", "nomic-embed-text")
MAX_BYTES = 10 * 1024 * 1024
MAX_CHARS = 300_000
MAX_CHUNKS = 400
INDEX_LIMIT = 4000

def extract(filename, data, ocr_languages=None, page_limit=150):
    suffix = Path(filename).suffix.lower()
    warnings = []
    if suffix == ".pdf":
        try:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                raise ValueError("Password-protected PDFs are not supported. Import an unlocked copy.")
            if len(reader.pages) > page_limit:
                raise ValueError(f"Please use a PDF with at most {page_limit} pages.")
            pages = []
            total = 0
            for number, page in enumerate(reader.pages, 1):
                # Intended for personal documents; scanned images require a separate OCR step.
                text = page.extract_text() or ""
                total += len(text)
                if total > MAX_CHARS:
                    raise ValueError("This document contains too much text. Split it into smaller documents.")
                if text.strip():
                    pages.append((number, text))
                else:
                    ocr_text = ocr_page(data, number - 1, ocr_languages)
                    total += len(ocr_text)
                    if total > MAX_CHARS:
                        raise ValueError('This document contains too much OCR text. Split it into smaller documents.')
                    if ocr_text.strip():
                        pages.append((number,ocr_text))
                        warnings.append(f"Page {number} used local OCR; check names and numbers against the original.")
                    else:
                        warnings.append(f"Page {number} has no readable text after OCR.")
        except ValueError:
            raise
        except Exception as error:
            raise ValueError("This PDF could not be read. Try an unlocked text-based PDF.") from error
    elif suffix in (".txt", ".md"):
        try:
            pages = [(1, data.decode("utf-8-sig"))]
        except UnicodeDecodeError as error:
            raise ValueError("Please save text files as UTF-8.") from error
    else:
        raise ValueError("Import a PDF, TXT or Markdown file.")
    if sum(len(text) for _, text in pages) > MAX_CHARS:
        raise ValueError("This document contains too much text. Split it into smaller documents.")
    chunks = []
    for page, text in pages:
        text = re.sub(r"\s+", " ", text).strip()
        start = 0
        while start < len(text):
            end = min(start + 1000, len(text))
            if end < len(text):
                split = text.rfind(" ", start + 700, end)
                if split > start:
                    end = split
            chunk = text[start:end].strip()
            if chunk:
                chunks.append({"page": page, "text": chunk})
            if end == len(text):
                break
            start = end - 140
    if not chunks:
        raise ValueError("No text could be extracted. Scanned PDFs need OCR before import.")
    if len(chunks) > MAX_CHUNKS:
        raise ValueError("This document needs too many chunks. Please split it.")
    return chunks, warnings

def ocr_page(data, index, ocr_languages=None):
    import pymupdf
    tessdata=Path(os.getenv('YOUAI_TESSDATA',str(Path(os.getenv('LOCALAPPDATA','.'))/'YouAI/models/tessdata')))
    languages = (ocr_languages or os.getenv('YOUAI_OCR_LANGUAGES', 'eng')).split('+')
    allowed = {'eng', 'hin', 'spa', 'fra', 'deu'}
    if not languages or any(lang not in allowed for lang in languages):
        raise ValueError('OCR languages must be eng, hin, spa, fra or deu, joined with +.')
    missing = [lang for lang in languages if not (tessdata / (lang + '.traineddata')).exists()]
    if missing:
        raise ValueError('Missing OCR languages: ' + ', '.join(missing) + '. Run scripts/setup_ocr.ps1 -Languages ' + ','.join(missing))
    with pymupdf.open(stream=data,filetype='pdf') as doc:
        page=doc[index]
        if page.rect.width*page.rect.height>4_000_000:
            raise ValueError('PDF page is too large for safe local OCR.')
        textpage=page.get_textpage_ocr(language='+'.join(languages),dpi=150,full=True,tessdata=str(tessdata))
        return page.get_text(textpage=textpage)

class Rag:
    def __init__(self, store, base="http://127.0.0.1:11434", lexical=False):
        self.store = store
        self.lexical = lexical
        self.base = base
        self.lock = asyncio.Lock()

    async def fingerprint(self):
        if self.lexical:
            return 'keyword-retrieval-v1'
        async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
            response = await client.get(self.base + "/api/tags")
            response.raise_for_status()
            for item in response.json().get("models", []):
                if item["name"] in (MODEL, MODEL + ":latest"):
                    return item["digest"]
        raise ValueError(f"The embedding model is missing. Run: ollama pull {MODEL}")

    async def embed(self, texts, query=False):
        if self.lexical:
            # Hosted retrieval ranks actual words, so it does not need model vectors.
            return np.zeros((len(texts), 1), dtype=np.float32)
        prefix = "search_query: " if query else "search_document: "
        async with httpx.AsyncClient(timeout=120, trust_env=False) as client:
            response = await client.post(self.base + "/api/embed", json={
                "model": MODEL, "input": [prefix + text for text in texts],
                "truncate": False, "keep_alive": "5m", "options": {"num_gpu": 0}
            })
            response.raise_for_status()
            vectors = np.asarray(response.json()["embeddings"], dtype=np.float32)
        if vectors.ndim != 2 or len(vectors) != len(texts) or not np.isfinite(vectors).all():
            raise ValueError("Invalid embeddings returned by the local model.")
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        if np.any(norms == 0):
            raise ValueError("The embedding model returned an empty vector.")
        return vectors / norms

    async def import_file(self, filename, data, ocr_languages=None):
        if self.lexical and len(data) > 3 * 1024 * 1024:
            raise ValueError('Hosted uploads are limited to 3 MB per document.')
        if not data or len(data) > MAX_BYTES:
            raise ValueError("Choose a non-empty document of at most 10 MB.")
        name = Path(filename.replace("\\", "/")).name[:200]
        digest = hashlib.sha256(data).hexdigest()
        async with self.lock:
            with self.store.connect() as db:
                existing = db.execute("SELECT id,name FROM documents WHERE sha256=?", (digest,)).fetchone()
                if existing:
                    return {"id":existing["id"], "name":existing["name"], "duplicate":True, "warnings":[]}
            chunks, warnings = await asyncio.to_thread(extract, name, data, ocr_languages, 25 if self.lexical else 150)
            if self.lexical and len(chunks) > 50:
                raise ValueError('Hosted documents are limited to 50 passages. Split this document into smaller files.')
            with self.store.connect() as db:
                if db.execute("SELECT count(*) FROM document_chunks").fetchone()[0] + len(chunks) > INDEX_LIMIT:
                    raise ValueError("The local index is full. Remove documents before importing more.")
            fingerprint = await self.fingerprint()
            vectors = []
            for start in range(0, len(chunks), 16):
                vectors.extend(await self.embed([c["text"] for c in chunks[start:start + 16]]))
            if await self.fingerprint() != fingerprint:
                raise ValueError("The embedding model changed during import. Please retry.")
            with self.store.connect() as db:
                ident = db.execute("INSERT INTO documents(name,sha256,model_digest,warnings) VALUES (?,?,?,?)",
                    (name,digest,fingerprint,json.dumps(warnings))).lastrowid
                db.executemany("INSERT INTO document_chunks(document_id,page,content,embedding) VALUES (?,?,?,?)",
                    [(ident,c["page"],c["text"],v.astype("<f4").tobytes()) for c,v in zip(chunks,vectors)])
            return {"id":ident, "name":name, "chunks":len(chunks), "warnings":warnings, "duplicate":False}

    def documents(self):
        with self.store.connect() as db:
            rows = db.execute("SELECT d.*,count(c.id) AS chunks FROM documents d LEFT JOIN document_chunks c ON c.document_id=d.id GROUP BY d.id ORDER BY d.id DESC").fetchall()
        return [{"id":r["id"],"name":r["name"],"chunks":r["chunks"],
                 "warnings":json.loads(r["warnings"]),"created_at":r["created_at"]} for r in rows]

    async def delete(self, ident):
        async with self.lock:
            with self.store.connect() as db:
                return db.execute("DELETE FROM documents WHERE id=?", (ident,)).rowcount > 0

    async def retrieve(self, query, document_ids=None):
        async with self.lock:
            with self.store.connect() as db:
                rows = db.execute("SELECT c.*,d.name,d.model_digest FROM document_chunks c JOIN documents d ON d.id=c.document_id ORDER BY c.id").fetchall()
            if document_ids:
                rows = [r for r in rows if r["document_id"] in document_ids]
            if not rows:
                return []
            fingerprint = await self.fingerprint()
            if any(r["model_digest"] != fingerprint for r in rows):
                raise ValueError("Your embedding model changed. Remove and re-import documents to rebuild the index.")
            vector = (await self.embed([query], query=True))[0]
            ranked = []
            for row in rows:
                item_vector = np.frombuffer(row["embedding"], dtype="<f4")
                if len(item_vector) != len(vector):
                    raise ValueError("The index has incompatible vectors. Re-import your documents.")
                if self.lexical:
                    terms = set(re.findall(r'\w+', query.casefold())) - {'the','a','an','is','are','what','when','where','how','to','of','in','my','and','for','does','it'}
                    words = set(re.findall(r'\w+', row['content'].casefold()))
                    score = len(terms & words) / max(1, len(terms))
                else:
                    score = float(np.dot(vector, item_vector))
                if score >= (0.2 if self.lexical else 0.45):
                    ranked.append((score, row))
            ranked.sort(key=lambda pair:pair[0], reverse=True)
            selected, budget = [], 3600
            for score,row in ranked[:4]:
                excerpt = row["content"][:budget]
                if not excerpt:
                    break
                selected.append({"label":f"S{len(selected)+1}", "document_id":row["document_id"],
                    "chunk_id":row["id"], "name":row["name"], "page":row["page"], "excerpt":excerpt,
                    "score":round(score,4)})
                budget -= len(excerpt)
            return selected

    def summary_sources(self, ident):
        with self.store.connect() as db:
            rows=db.execute("SELECT c.*,d.name FROM document_chunks c JOIN documents d ON d.id=c.document_id WHERE d.id=? ORDER BY c.id",(ident,)).fetchall()
        if not rows:raise ValueError("Document not found or empty.")
        return [{"label":f"S{i+1}","document_id":ident,"name":row['name'],"page":row['page'],
            "excerpt":row['content'],"coverage":"all indexed passages"}
            for i,row in enumerate(rows)]
