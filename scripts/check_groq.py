"""Opt-in live Groq checks using an isolated database and synthetic audio only."""
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))

async def run():
    import httpx
    with tempfile.TemporaryDirectory() as folder:
        os.environ['YOUAI_DATA_DIR']=folder
        os.environ['YOUAI_LLM_PROVIDER']='groq'
        os.environ['YOUAI_SPEECH_PROVIDER']='groq'
        os.environ['YOUAI_PRELOAD']='0'
        from app import main
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),base_url='http://127.0.0.1:8765',timeout=120) as client:
            headers={'X-YouAI':'1'}
            status=(await client.get('/api/status')).json()
            if not status['llm_ready']:raise RuntimeError(status['error'])
            assert status['provider']=='groq'
            print('Groq model availability verified.')
            response=await client.post('/api/chat/stream',headers=headers,json={'text':'Say hello in one sentence.','turn_id':str(uuid4())})
            events=[json.loads(line) for line in response.text.splitlines()]
            if events[-1]['type']!='done':raise RuntimeError(events[-1].get('message','Incomplete response'))
            assert events[-1]['text']
            assert len(main.store.history())==2
            print('Streamed chat completed and persisted in isolated test storage.')
            wave=Path('.runtime/wake-command.wav')
            if wave.exists():
                response=await client.post('/api/transcribe',headers=headers,files={'audio':('voice.wav',wave.read_bytes(),'audio/wav')},data={'language':'en'})
                assert response.status_code==200, response.json().get('detail')
                assert 'remind' in response.json()['text'].lower()
                print('Synthetic WAV transcribed through Groq Whisper.')
            else:print('No synthetic WAV fixture; skipped audio check.')
            result=await main.answer('What is the launch date?',[],[{'label':'S1','name':'Synthetic fixture','page':1,'excerpt':'The Orchid launch date is November 18.'}])
            assert 'November 18' in result
            print('Groq answered correctly from a synthetic RAG passage.')

if __name__=='__main__':
    try:asyncio.run(run())
    except Exception as error:
        # Deliberately do not print transport objects, headers or environment values.
        print('Groq live check failed:',type(error).__name__)
        raise SystemExit(1)
