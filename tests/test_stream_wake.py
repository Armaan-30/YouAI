import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
from fastapi.testclient import TestClient
from app import main
from app.wake import WakeSession
from app.storage import Store

class StreamTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        original = main.store
        main.store = Store(Path(temp.name) / "test.sqlite3")
        self.addCleanup(setattr, main, "store", original)
        self.client = TestClient(main.app, base_url="http://127.0.0.1:8765")
        main.store.clear()

    def test_stream_finishes_and_saves_one_complete_turn(self):
        async def fake(*_):
            yield "Hello "
            yield "there."
        with patch.object(main, "stream_answer", fake):
            result = self.client.post("/api/chat/stream", headers={"X-YouAI":"1"},
                json={"text":"hello", "turn_id":str(uuid4())})
        events = [json.loads(line) for line in result.text.splitlines()]
        self.assertEqual([event["type"] for event in events], ["token", "token", "done"])
        self.assertEqual(main.store.history()[-1]["content"], "Hello there.")

    def test_failed_stream_is_not_saved_as_complete(self):
        async def broken(*_):
            yield "Partial "
            raise ValueError("connection lost")
        with patch.object(main, "stream_answer", broken):
            result = self.client.post("/api/chat/stream", headers={"X-YouAI":"1"},
                json={"text":"hello", "turn_id":str(uuid4())})
        events = [json.loads(line) for line in result.text.splitlines()]
        self.assertEqual(events[-1]["type"], "error")
        self.assertEqual(main.store.history(), [])

    def test_wake_socket_rejects_foreign_origin(self):
        from starlette.websockets import WebSocketDisconnect
        with self.assertRaises(WebSocketDisconnect):
            with self.client.websocket_connect("/api/wake", headers={"Origin":"https://example.com"}):
                self.fail("Foreign origin connected")

class WakeTests(unittest.TestCase):
    def test_partial_must_be_stable_and_resets_after_wake(self):
        class Recognizer:
            resets = 0
            def AcceptWaveform(self, data): return False
            def PartialResult(self): return '{"partial":"hey you"}'
            def Reset(self): self.resets += 1
        engine = Recognizer()
        session = WakeSession(engine)
        self.assertFalse(session.feed(b"audio"))
        self.assertTrue(session.feed(b"audio"))
        self.assertEqual(engine.resets, 1)
        self.assertFalse(session.feed(b"audio"))
