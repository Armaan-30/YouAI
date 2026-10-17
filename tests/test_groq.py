import asyncio
import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4
import httpx
from app import main
from app.groq_provider import GroqProvider, ProviderError
from app.storage import Store

Client = httpx.AsyncClient

@contextmanager
def remote(handler):
    with patch.dict('os.environ', {'GROQ_API_KEY':'test-only-secret'}), patch(
            'app.groq_provider.httpx.AsyncClient', side_effect=lambda **kw: Client(transport=httpx.MockTransport(handler), **kw)):
        yield

class GroqTests(unittest.IsolatedAsyncioTestCase):
    async def test_server_auth_and_answer(self):
        def respond(request):
            self.assertEqual(str(request.url),'https://api.groq.com/openai/v1/chat/completions')
            self.assertEqual(request.headers['Authorization'],'Bearer test-only-secret')
            body=json.loads(request.content)
            self.assertEqual(body['model'],'qwen/qwen3.8-27b')
            self.assertEqual(body['reasoning_effort'],'none')
            self.assertNotIn('api_key',body)
            return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':'Hello'}}]})
        with remote(respond):
            self.assertEqual(await GroqProvider('qwen/qwen3.8-27b').answer([{'role':'user','content':'Hi'}]),'Hello')

    async def test_stream_ignores_reasoning_and_requires_complete_answer(self):
        events=[{'choices':[{'delta':{'reasoning':'private reasoning'}}]},
                {'choices':[{'delta':{'content':'Hello'}}]},
                {'choices':[{'delta':{},'finish_reason':'stop'}]}]
        body=''.join('data: '+json.dumps(e)+'\n\n' for e in events)+'data: [DONE]\n\n'
        with remote(lambda _:httpx.Response(200,text=body)):
            self.assertEqual([s async for s in GroqProvider('model').stream([])],['Hello'])
        with remote(lambda _:httpx.Response(200,text=body.replace('data: [DONE]\n\n',''))):
            with self.assertRaisesRegex(ProviderError,'before the answer finished'):
                _=[s async for s in GroqProvider('model').stream([])]

    async def test_errors_do_not_expose_key_or_provider_response(self):
        for code, message in [(401,'rejected'),(429,'limit'),(500,'unavailable')]:
            with remote(lambda _:httpx.Response(code,json={'error':'test-only-secret'})):
                with self.assertRaises(ProviderError) as caught:
                    await GroqProvider('model').answer([])
                self.assertIn(message,str(caught.exception))
                self.assertNotIn('test-only-secret',str(caught.exception))

    async def test_missing_key_never_connects(self):
        with patch.dict('os.environ',{'GROQ_API_KEY':''}), patch('app.groq_provider.httpx.AsyncClient') as factory:
            with self.assertRaisesRegex(ProviderError,'missing'):
                await GroqProvider('model').answer([])
            factory.return_value.__aenter__.return_value.post.assert_not_called()

    async def test_transcription_only_uploads_audio_and_selected_language(self):
        def respond(request):
            self.assertTrue(str(request.url).endswith('/audio/transcriptions'))
            self.assertIn(b'whisper-large-v3-turbo',request.content)
            self.assertIn(b'\r\nhi\r\n',request.content)
            self.assertIn(b'fixture-audio',request.content)
            self.assertNotIn(b'messages',request.content)
            return httpx.Response(200,json={'text':'Hello','language':'Hindi'})
        with remote(respond):
            self.assertEqual((await GroqProvider('model').transcribe(b'fixture-audio','hi'))['text'],'Hello')

    async def test_status_cached_and_contains_no_secret(self):
        calls=[]
        def respond(request):
            calls.append(request)
            return httpx.Response(200,json={'data':[{'id':'model'},{'id':'whisper-large-v3-turbo'}]})
        with remote(respond):
            provider=GroqProvider('model')
            self.assertTrue((await provider.status())['ready'])
            self.assertNotIn('test-only-secret',json.dumps(await provider.status()))
            self.assertEqual(len(calls),1)

    async def test_cancelled_groq_turn_does_not_save_or_retry(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(main,'store',Store(Path(folder)/'db')), patch.object(main,'PROVIDER','groq'):
            started=asyncio.Event()
            async def slow(messages):
                started.set()
                await asyncio.sleep(30)
            with patch.object(main.groq,'answer',side_effect=slow) as model:
                ident=uuid4()
                pending=asyncio.create_task(main.run_turn(main.Turn(text='Hello',turn_id=ident)))
                await started.wait()
                main.active[str(ident)].set()
                with self.assertRaises(main.HTTPException) as caught:await pending
                self.assertEqual(caught.exception.status_code,409)
                self.assertEqual(main.store.history(),[])
                self.assertEqual(model.await_count,1)

    async def test_identity_reports_hosted_provider_without_network(self):
        with patch.object(main,'PROVIDER','groq'),patch.object(main,'MODEL','qwen/qwen3.8-27b'),patch.object(main.groq,'answer',new_callable=AsyncMock) as model:
            result=await main.answer('Which AI are you?',[])
            self.assertIn('Groq',result)
            self.assertNotIn('running locally',result)
            model.assert_not_called()
