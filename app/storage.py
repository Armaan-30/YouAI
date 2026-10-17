import sqlite3
import json
from contextlib import contextmanager
from pathlib import Path

class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS memories (id INTEGER PRIMARY KEY, content TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS permissions (id INTEGER PRIMARY KEY, kind TEXT NOT NULL, path TEXT NOT NULL, UNIQUE(kind,path));
                CREATE TABLE IF NOT EXISTS watched_folders (permission_id INTEGER PRIMARY KEY REFERENCES permissions(id) ON DELETE CASCADE, status TEXT DEFAULT 'Waiting for scan');
                CREATE TABLE IF NOT EXISTS watched_files (permission_id INTEGER REFERENCES permissions(id) ON DELETE CASCADE, path TEXT, digest TEXT, document_id INTEGER, PRIMARY KEY(permission_id,path));
                CREATE TABLE IF NOT EXISTS alerts (reminder_id INTEGER PRIMARY KEY, delivered_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY, role TEXT NOT NULL, content TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY, content TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY, content TEXT NOT NULL, due_at REAL NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS receipts (
                    request_id TEXT PRIMARY KEY, prompt TEXT NOT NULL, answer TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY, name TEXT NOT NULL, sha256 TEXT NOT NULL UNIQUE,
                    model_digest TEXT NOT NULL, warnings TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS document_chunks (
                    id INTEGER PRIMARY KEY, document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    page INTEGER NOT NULL, content TEXT NOT NULL, embedding BLOB NOT NULL);
                CREATE TABLE IF NOT EXISTS message_sources (
                    message_id INTEGER PRIMARY KEY REFERENCES messages(id) ON DELETE CASCADE,
                    sources TEXT NOT NULL);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def history(self, limit=40):
        with self.connect() as db:
            rows = db.execute("SELECT m.*,s.sources FROM messages m LEFT JOIN message_sources s ON s.message_id=m.id ORDER BY m.id DESC LIMIT ?", (limit,)).fetchall()
        return [{**dict(row), "sources":json.loads(row["sources"] or "[]")} for row in reversed(rows)]

    def turn(self, prompt, answer, sources=None):
        with self.connect() as db:
            db.execute("INSERT INTO messages(role,content) VALUES ('user',?)", (prompt,))
            ident = db.execute("INSERT INTO messages(role,content) VALUES ('assistant',?)", (answer,)).lastrowid
            if sources:
                db.execute("INSERT INTO message_sources VALUES (?,?)", (ident,json.dumps(sources)))

    def clear(self):
        with self.connect() as db:
            db.execute("DELETE FROM messages")

    def add_note(self, content):
        with self.connect() as db:
            cursor = db.execute("INSERT INTO notes(content) VALUES (?)", (content,))
            return cursor.lastrowid

    def notes(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM notes ORDER BY id DESC LIMIT 100")]

    def search_notes(self, query):
        with self.connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT * FROM notes WHERE instr(lower(content),lower(?)) > 0 ORDER BY id DESC LIMIT 10", (query,))]

    def reminders(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT * FROM reminders WHERE status='pending' ORDER BY due_at LIMIT 100")]

    def finish_reminder(self, reminder_id):
        with self.connect() as db:
            return db.execute("UPDATE reminders SET status='done' WHERE id=? AND status='pending'",
                              (reminder_id,)).rowcount > 0

    def perform(self, request_id, prompt, operation):
        """Commit an action and its receipt atomically; retries cannot duplicate writes."""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT prompt,answer FROM receipts WHERE request_id=?", (request_id,)).fetchone()
            if row:
                if row["prompt"] != prompt:
                    raise ValueError("This request ID has already been used for another action.")
                return row["answer"]
            answer = operation(db)
            db.execute("INSERT INTO receipts VALUES (?,?,?)", (request_id, prompt, answer))
            return answer


    def memories(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT * FROM memories ORDER BY id DESC")]

    def save_memory(self, content, ident=None):
        content=content.strip()
        if not content or len(content)>1000:
            raise ValueError("Memory must contain 1–1000 characters.")
        with self.connect() as db:
            if ident is not None:
                if not db.execute("UPDATE memories SET content=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(content,ident)).rowcount:
                    raise ValueError("Memory no longer exists.")
                return ident
            if db.execute("SELECT count(*) FROM memories").fetchone()[0]>=50:
                raise ValueError("Keep at most 50 memories. Edit or delete an existing memory first.")
            return db.execute("INSERT INTO memories(content) VALUES (?)",(content,)).lastrowid

    def delete_memory(self, ident):
        with self.connect() as db:
            return bool(db.execute("DELETE FROM memories WHERE id=?",(ident,)).rowcount)

    def search_history(self, query):
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT id,role,content,created_at FROM messages WHERE instr(lower(content),lower(?))>0 ORDER BY id DESC LIMIT 50",(query,))]
