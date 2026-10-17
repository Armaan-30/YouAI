import tempfile,unittest
from pathlib import Path
from unittest.mock import patch,AsyncMock
from fastapi.testclient import TestClient
from app import main
from app.storage import Store
from app.features import DesktopActions,ActionInput

class FeatureTests(unittest.TestCase):
 def test_memory_needs_approval_and_can_be_edited_forgotten(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(main,'store',Store(Path(folder)/'db')):
   c=TestClient(main.app,base_url='http://127.0.0.1:8765');h={'X-YouAI':'1'}
   self.assertEqual(c.post('/api/memories',headers=h,json={'content':'I prefer concise replies'}).status_code,422)
   result=c.post('/api/memories',headers=h,json={'content':'I prefer concise replies','approved':True});self.assertEqual(result.status_code,200);ident=result.json()['id']
   self.assertIn('concise',main.model_messages('Hello',[])[0]['content'])
   self.assertEqual(c.put(f'/api/memories/{ident}',headers=h,json={'content':'I like tea','approved':True}).status_code,200)
   c.delete(f'/api/memories/{ident}',headers=h)
   self.assertNotIn('I like tea',main.model_messages('Hello',[])[0]['content'])
 def test_actions_preview_confirm_no_overwrite_and_revoke(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);store=Store(root/'db');actions=DesktopActions(store);actions.approve('folder',folder)
   ident=actions.permissions()[0]['id'];action=ActionInput(permission_id=ident,operation='create',name='hello.txt',content='hello')
   preview=actions.prepare(action);self.assertFalse((root/'hello.txt').exists());actions.confirm(preview['token']);self.assertEqual((root/'hello.txt').read_text(),'hello')
   with self.assertRaises(ValueError):actions.confirm(preview['token'])
   with self.assertRaises(ValueError):actions.prepare(action)
   for name in ['../outside.txt','a/b.txt','C:bad.txt','script.ps1']:
    with self.assertRaises(ValueError):actions.prepare(ActionInput(permission_id=ident,operation='create',name=name))
   token=actions.prepare(ActionInput(permission_id=ident,operation='create',name='new.md'))['token']
   with store.connect() as db:db.execute('DELETE FROM permissions')
   with self.assertRaises(ValueError):actions.confirm(token)
 def test_history_search_does_not_change_history(self):
  with tempfile.TemporaryDirectory() as folder:
   store=Store(Path(folder)/'db');store.turn('Orchid launch','November 18')
   self.assertEqual(len(store.search_history('Orchid')),1);self.assertEqual(len(store.history()),2)
 def test_web_without_key_never_contacts_provider(self):
  import asyncio
  from app.web_search import search
  with patch.dict('os.environ',{'YOUAI_BRAVE_KEY':'','YOUAI_SEARCH_PROVIDER':'brave'}),patch('app.web_search.httpx.AsyncClient') as client:
   with self.assertRaises(ValueError):asyncio.run(search('weather'))
   client.assert_not_called()
 def test_ocr_scanned_pdf(self):
  import pymupdf
  from app.rag import extract
  import os
  tess=Path(os.getenv('LOCALAPPDATA','.'))/'YouAI/models/tessdata/eng.traineddata'
  if not tess.exists():self.skipTest('OCR data not installed')
  source=pymupdf.open();page=source.new_page();page.insert_text((60,100),'Orchid launch November 18',fontsize=24)
  scan=pymupdf.open();page=scan.new_page();page.insert_image(page.rect,stream=source[0].get_pixmap().tobytes('png'))
  chunks,warnings=extract('scan.pdf',scan.tobytes());self.assertIn('Orchid',chunks[0]['text']);self.assertTrue(warnings)
 def test_native_alert_ack_survives_restart(self):
  import time
  with tempfile.TemporaryDirectory() as folder,patch.object(main,'store',Store(Path(folder)/'db')):
   with main.store.connect() as db:db.execute("INSERT INTO reminders(content,due_at) VALUES ('Drink water',?)",(time.time()-10,))
   c=TestClient(main.app,base_url='http://127.0.0.1:8765');h={'X-YouAI':'1'}
   reminders=c.get('/api/desktop/alerts').json()['reminders'];self.assertEqual(len(reminders),1)
   c.post('/api/desktop/alerts/'+str(reminders[0]['id']),headers=h)
   self.assertEqual(c.get('/api/desktop/alerts').json()['reminders'],[])
   self.assertEqual(len(main.store.reminders()),1)
 def test_approved_folder_indexes_only_supported_files_once(self):
  import asyncio
  from app.features import watch_loop
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);(root/'facts.txt').write_text('Facts');(root/'ignore.exe').write_text('Not a document')
   store=Store(root/'db');actions=DesktopActions(store);actions.approve('folder',folder);ident=actions.permissions()[0]['id']
   actions.confirm(actions.prepare(ActionInput(permission_id=ident,operation='watch'))['token'])
   rag=AsyncMock();rag.import_file.return_value={'id':1}
   async def one_scan():
    with patch('app.features.asyncio.sleep',side_effect=asyncio.CancelledError):
     try:await watch_loop(store,rag)
     except asyncio.CancelledError:pass
   asyncio.run(one_scan());asyncio.run(one_scan());rag.import_file.assert_awaited_once_with('facts.txt',b'Facts')
