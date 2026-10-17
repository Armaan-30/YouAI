import asyncio
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

TEMP = tempfile.TemporaryDirectory()
os.environ["YOUAI_DATA_DIR"] = TEMP.name
from fastapi.testclient import TestClient
from app import main

class AppTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app, base_url="http://127.0.0.1:8765")
        self.headers = {"X-YouAI": "1"}
        main.store.clear()

    def post(self, text):
        return self.client.post("/api/chat", headers=self.headers,
                                json={"text": text, "turn_id": str(uuid4())})

    def test_note_is_executed_and_persisted_without_llm(self):
        with patch.object(main, "answer", new_callable=AsyncMock) as model:
            response = self.post("Save a note: buy notebooks")
        self.assertEqual(response.status_code, 200)
        self.assertIn("buy notebooks", response.json()["text"])
        self.assertEqual(main.store.notes()[0]["content"], "buy notebooks")
        self.assertEqual(len(main.store.history()), 2)
        model.assert_not_called()

    def test_chat_uses_history_and_commits_only_success(self):
        main.store.turn("My name is Alex.", "Hello Alex.")
        with patch.object(main, "answer", new_callable=AsyncMock, return_value="Alex") as model:
            response = self.post("What is my name?")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(model.call_args.args[1][0]["content"], "My name is Alex.")
        with patch.object(main, "answer", new_callable=AsyncMock, side_effect=ValueError("empty")):
            failed = self.post("This fails")
        self.assertEqual(failed.status_code, 503)
        self.assertEqual(len(main.store.history()), 4)

    def test_cross_site_requests_are_rejected(self):
        response = self.client.post("/api/chat", headers={"X-YouAI": "1", "Origin": "https://evil.example"},
            json={"text": "save a note: should not exist", "turn_id": str(uuid4())})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.delete("/api/history").status_code, 403)
        self.assertEqual(self.client.get("/", headers={"Host":"evil.example"}).status_code, 403)

    def test_empty_input_and_empty_audio_are_rejected(self):
        self.assertEqual(self.post("  ").status_code, 400)
        response = self.client.post("/api/transcribe", headers=self.headers, files={"audio":("empty.wav",b"","audio/wav")})
        self.assertEqual(response.status_code, 400)

    def test_identity_uses_runtime_config_even_after_false_history(self):
        with patch.object(main.httpx, "AsyncClient") as network:
            for prompt in ("Which AI are you?", "Are you Claude?", "Who are you?"):
                result = asyncio.run(main.answer(prompt, [
                    {"role": "assistant", "content": "I am Claude."}
                ]))
                self.assertIn(main.MODEL, result)
                self.assertIn("YouAI", result)
            network.assert_not_called()

    def test_model_identity_does_not_override_other_questions(self):
        response = httpx_response = unittest.mock.Mock()
        response.json.return_value = {"message": {"content": "A comparison."}}
        response.raise_for_status.return_value = None
        with patch.object(main.httpx, "AsyncClient") as factory:
            client = factory.return_value.__aenter__.return_value
            client.post = AsyncMock(return_value=httpx_response)
            result = asyncio.run(main.answer("How does Claude compare with Qwen?", []))
            self.assertEqual(result, "A comparison.")
            client.post.assert_awaited_once()

    def test_cancellation_does_not_save_answer(self):
        async def scenario():
            import httpx
            entered = asyncio.Event()
            async def slow(*_):
                entered.set()
                await asyncio.sleep(10)
                return "Too late"
            transport = httpx.ASGITransport(app=main.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8765") as client:
                key = str(uuid4())
                with patch.object(main, "answer", side_effect=slow):
                    pending = asyncio.create_task(client.post("/api/chat", headers=self.headers,
                        json={"text":"Think slowly", "turn_id":key}))
                    await entered.wait()
                    await client.post("/api/cancel/"+key, headers=self.headers)
                    response = await pending
                    self.assertEqual(response.status_code, 409)
                    self.assertEqual(main.store.history(), [])
        asyncio.run(scenario())

if __name__ == "__main__":
    unittest.main()
