"""Offline hosted integration acceptance checks; uses only synthetic account data."""
import asyncio
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.update(YOUAI_MODE='cloud',GROQ_API_KEY='test-not-real')
import httpx
from app.cloudapp import CloudGateway
from app import main

async def check():
    with tempfile.TemporaryDirectory() as root:
        gateway=CloudGateway(main.app,root,'https://youai.test','x'*32)
        transport=httpx.ASGITransport(app=gateway)
        options=dict(transport=transport,base_url='https://youai.test',headers={'Origin':'https://youai.test','X-YouAI':'1'})
        async with httpx.AsyncClient(**options) as alice, httpx.AsyncClient(**options) as bob:
            assert (await alice.get('/healthz')).status_code==200
            assert (await alice.get('/api/history')).status_code==401
            assert (await alice.get('/')).status_code==303
            assert (await alice.get('/login')).status_code==200
            assert (await alice.post('/api/auth/register',json={'username':'alice','password':'example-password','invite':'wrong'})).status_code==400
            for client,name in ((alice,'alice'),(bob,'bob')):
                response=await client.post('/api/auth/register',json={'username':name,'password':'example-password','invite':'x'*32})
                assert response.status_code==200,response.text
                assert 'Secure' in response.headers['set-cookie'] and 'HttpOnly' in response.headers['set-cookie']
            assert 'data-cloud="true"' in (await alice.get('/')).text
            assert (await alice.post('/api/memories',json={'content':'Alice likes tea','approved':True})).status_code==200
            assert (await bob.get('/api/memories')).json()['memories']==[]
            assert (await alice.post('/api/memories',json={'content':'bad','approved':True},headers={'Origin':'https://evil.test'})).status_code==403
            assert (await alice.get('/api/desktop/permissions')).status_code==403
            assert (await alice.get('/api/mobile/pairing')).status_code==403
            async def reply(prompt, context, sources=None):
                await asyncio.sleep(.03)
                return 'Answer for '+prompt
            with patch.object(main,'answer',side_effect=reply):
                a,b=await asyncio.gather(*[client.post('/api/chat',json={'text':name+' question','turn_id':str(uuid4())}) for client,name in ((alice,'Alice'),(bob,'Bob'))])
                assert a.status_code==b.status_code==200,(a.text,b.text)
            assert 'Alice' in str((await alice.get('/api/history')).json())
            assert 'Alice' not in str((await bob.get('/api/history')).json())
            started=asyncio.Event()
            async def slow(*args,**kwargs):
                started.set()
                await asyncio.sleep(20)
            ident=str(uuid4())
            with patch.object(main,'answer',side_effect=slow):
                running=asyncio.create_task(alice.post('/api/chat',json={'text':'A slow question','turn_id':ident}))
                await asyncio.wait_for(started.wait(),3)
                assert (await bob.post('/api/cancel/'+ident)).status_code==200
                await asyncio.sleep(.15)
                assert not running.done(), 'Another account cancelled this user\'s request'
                await alice.post('/api/cancel/'+ident)
                assert (await running).status_code==409
            doc=await alice.post('/api/documents',files={'document':('launch.txt',b'The telescope launch is November 18.','text/plain')})
            assert doc.status_code==200,doc.text
            assert (await bob.get('/api/documents')).json()['documents']==[]
            async def stream(prompt,context,sources=None):
                assert sources and 'November 18' in sources[0]['excerpt']
                yield 'The telescope launch is November 18. [S1]'
            with patch.object(main,'stream_answer',side_effect=stream):
                response=await alice.post('/api/chat/stream',json={'text':'When is the telescope launch?','turn_id':str(uuid4()),'use_documents':True})
                assert '"type": "done"' in response.text,response.text
                assert 'November 18' in response.text
            # A new gateway simulates process restart, retaining account and content on disk.
            restart=CloudGateway(main.app,root,'https://youai.test','x'*32)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=restart),base_url='https://youai.test',headers=options['headers']) as fresh:
                assert (await fresh.post('/api/auth/login',json={'username':'alice','password':'wrong-password'})).status_code==400
                assert (await fresh.post('/api/auth/login',json={'username':'alice','password':'example-password'})).status_code==200
                assert 'Alice likes tea' in (await fresh.get('/api/memories')).text
                assert 'launch.txt' in (await fresh.get('/api/documents')).text
                await fresh.post('/api/auth/logout')
                assert (await fresh.get('/api/history')).status_code==401
                assert (await alice.get('/api/history')).status_code==401
            assert gateway.rate('test-limit',1)
            assert not gateway.rate('test-limit',1)
        print('Cloud checks passed: invitation, auth, cookies, CSRF, concurrent user isolation, RAG streaming, persistence and logout.')

asyncio.run(check())
