import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from app.rag import Rag, ocr_page
from app.storage import Store
from app.summarize import summarize
from app import web_search


class ReleaseTests(unittest.IsolatedAsyncioTestCase):
    async def test_summary_reads_every_chunk_and_last_character(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / 'db')
            with store.connect() as db:
                ident = db.execute("INSERT INTO documents(name,sha256,model_digest,warnings) VALUES ('long','hash','model','[]')").lastrowid
                for i in range(17):
                    db.execute('INSERT INTO document_chunks(document_id,page,content,embedding) VALUES (?,?,?,?)',
                               (ident, i+1, str(i) + 'x'*950 + 'END' + str(i), b'0'))
            sources = Rag(store).summary_sources(ident)
            seen = []
            async def generate(prompt, context, passages):
                seen.extend(s['excerpt'] for s in passages)
                return 'Condensed notes [S1].'
            await summarize(sources, generate)
            self.assertEqual(len(sources), 17)
            self.assertTrue(all(s['excerpt'] in seen for s in sources))
            self.assertTrue(sources[-1]['excerpt'].endswith('END16'))

    async def test_summary_cancel_stops_remaining_calls(self):
        generate = AsyncMock(side_effect=asyncio.CancelledError)
        with self.assertRaises(asyncio.CancelledError):
            await summarize([{'excerpt':'x'*1000} for _ in range(12)], generate)
        self.assertEqual(generate.await_count, 1)

    async def test_free_search_without_key_filters_unsafe_urls(self):
        with patch.dict('os.environ', {'YOUAI_SEARCH_PROVIDER':'duckduckgo','YOUAI_BRAVE_KEY':''}), patch.object(web_search,'free_search',return_value=[
            {'href':'https://example.org','title':'Example','body':'<b>Fact</b>'},
            {'href':'javascript:alert(1)','body':'bad'}]) as provider:
            result = await web_search.search('only this question')
            provider.assert_called_once_with('only this question')
            self.assertEqual(len(result),1)
            self.assertEqual(result[0]['excerpt'],'Fact')

    async def test_free_search_failure_is_explicit(self):
        with patch.dict('os.environ', {'YOUAI_SEARCH_PROVIDER':'duckduckgo'}), patch.object(web_search,'free_search',side_effect=RuntimeError('quota')):
            with self.assertRaisesRegex(ValueError,'unavailable or rate limited'):
                await web_search.search('question')

    def test_missing_ocr_language_actionable(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict('os.environ', {'YOUAI_TESSDATA':folder}):
            with self.assertRaisesRegex(ValueError,'hin'):
                ocr_page(b'',0,'eng+hin')
            with self.assertRaisesRegex(ValueError,'OCR languages must'):
                ocr_page(b'',0,'../../bad')
