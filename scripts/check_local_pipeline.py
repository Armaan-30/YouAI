"""Local pipeline smoke check; denies outbound Python sockets, not system-wide networking."""
import asyncio,ipaddress,socket,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import os
os.environ['YOUAI_LLM_PROVIDER']='ollama'
os.environ['YOUAI_SPEECH_PROVIDER']='local'
from app.main import speech,answer
from app.storage import Store
from app.rag import Rag
original=socket.socket.connect
blocked=[]
def connect(sock,address):
 if isinstance(address,tuple):
  host=address[0]
  try:allowed=ipaddress.ip_address(host).is_loopback
  except ValueError:allowed=host=='localhost'
  if not allowed:blocked.append(host);raise RuntimeError('Unexpected external connection')
 return original(sock,address)
socket.socket.connect=connect
async def run():
 with tempfile.TemporaryDirectory() as folder:
  rag=Rag(Store(Path(folder)/'db'))
  await rag.import_file('offline.txt',b'Orchid launch is November 18. The owner is Mira.')
  sources=await rag.retrieve('When is the Orchid launch?')
  result=await answer('When is the Orchid launch?',[],sources)
  assert 'November 18' in result
  text=await asyncio.to_thread(speech.transcribe,Path('.runtime/wake-command.wav').read_bytes())
  assert text['text']
  assert not blocked
  print('Local embedding, retrieval, LLM and Whisper succeeded with outbound Python connections blocked.')
asyncio.run(run())
