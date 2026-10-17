"""Explicitly approved memory and bounded desktop actions; no model-generated commands."""
import asyncio
import os
import secrets
import subprocess
import time
from pathlib import Path
from typing import Literal
from fastapi import HTTPException, Request
from pydantic import BaseModel, Field

class MemoryInput(BaseModel):
    content: str = Field(min_length=1,max_length=1000)
    approved: Literal[True]

class PermissionInput(BaseModel):
    kind: Literal['app','folder']
    path: str = Field(min_length=1,max_length=1000)
    approved: Literal[True]

class ActionInput(BaseModel):
    permission_id: int
    operation: Literal['open','search','create','watch']
    name: str = Field(default='',max_length=200)
    content: str = Field(default='',max_length=100000)

class ConfirmInput(BaseModel):
    token: str
    approved: Literal[True]

class DesktopActions:
    def __init__(self,store):
        self.store=store
        self.pending={}

    def permissions(self):
        with self.store.connect() as db:
            return [dict(r) for r in db.execute('SELECT * FROM permissions ORDER BY id')]

    def approve(self,kind,value):
        path=Path(value).expanduser().resolve(strict=True)
        if kind=='app' and (not path.is_file() or path.suffix.lower()!='.exe'):
            raise ValueError('Choose an executable .exe file.')
        if kind=='folder' and not path.is_dir():
            raise ValueError('Choose an existing folder.')
        with self.store.connect() as db:
            db.execute('INSERT OR IGNORE INTO permissions(kind,path) VALUES (?,?)',(kind,str(path)))

    def permission(self,ident):
        with self.store.connect() as db:
            row=db.execute('SELECT * FROM permissions WHERE id=?',(ident,)).fetchone()
        if not row:raise ValueError('This permission was removed. Approve the location again.')
        return dict(row)

    def prepare(self,action):
        permission=self.permission(action.permission_id)
        root=Path(permission['path']).resolve(strict=True)
        if action.operation=='open':
            if permission['kind']!='app':raise ValueError('Select an approved application.')
            preview='Open '+str(root)+' (no command-line arguments)'
        else:
            if permission['kind']!='folder':raise ValueError('Select an approved folder.')
            if action.operation=='search':
                return {'results':self.search(root,action.name)}
            if action.operation=='watch':
                preview='Enable automatic PDF/TXT/Markdown indexing for '+str(root)+'. Scans every 60 seconds; at most 50 files per folder. Removing files from disk does not delete existing indexed documents.'
                token=secrets.token_urlsafe(24)
                self.pending[token]=(time.monotonic()+120,action,permission)
                return {'token':token,'preview':preview,'expires_in':120}
            name=action.name.strip()
            if not name or Path(name).name!=name or any(c in name for c in '/\\:') or Path(name).suffix.lower() not in ('.txt','.md'):
                raise ValueError('Choose a plain filename ending in .txt or .md, without folders.')
            target=(root/name).resolve()
            if target.parent!=root or target.exists():raise ValueError('File already exists or is outside the approved folder. Choose a new filename.')
            preview=f'Create {target}\n\n{action.content}'
        now=time.monotonic()
        self.pending={k:v for k,v in self.pending.items() if v[0]>now}
        if len(self.pending)>=20:raise ValueError('Too many pending actions. Wait a few minutes.')
        token=secrets.token_urlsafe(24)
        self.pending[token]=(now+120,action,permission)
        return {'token':token,'preview':preview,'expires_in':120}

    @staticmethod
    def search(root,query):
        if not query.strip():raise ValueError('Enter part of a filename.')
        results=[];visited=0
        for current,dirs,files in os.walk(root,followlinks=False):
            dirs[:]=[d for d in dirs if not (Path(current)/d).is_symlink() and not (hasattr(Path(current)/d,'is_junction') and (Path(current)/d).is_junction()) and d not in ('.git','node_modules','.venv')]
            for name in files:
                visited+=1
                if query.casefold() in name.casefold():
                    p=(Path(current)/name).resolve()
                    if p.is_relative_to(root):results.append(str(p))
                if len(results)>=50 or visited>=10000:return results
        return results

    def confirm(self,token):
        entry=self.pending.pop(token,None)
        if not entry or entry[0]<time.monotonic():raise ValueError('Action expired or was already used. Preview it again.')
        _,action,permission=entry
        if self.permission(action.permission_id)!=permission:raise ValueError('Permission changed.')
        root=Path(permission['path'])
        if root.resolve(strict=True)!=root:raise ValueError('The approved path changed.')
        if action.operation=='open':
            subprocess.Popen([str(root)],shell=False,close_fds=True)
            return {'message':'Opened '+root.name}
        if action.operation=='watch':
            with self.store.connect() as db:db.execute('INSERT OR IGNORE INTO watched_folders(permission_id) VALUES (?)',(action.permission_id,))
            return {'message':'Automatic indexing enabled. Revoke the folder permission to stop future scans; imported documents remain until removed.'}
        target=root/action.name.strip()
        if target.resolve().parent!=root:raise ValueError('Target is outside approved folder.')
        # Exclusive creation never overwrites an existing file; no delete/rename tool exists.
        with target.open('x',encoding='utf-8') as handle:handle.write(action.content)
        return {'message':'Created '+str(target)}

def install(app,get_store):
    actions=DesktopActions(get_store())
    def local(request):
        if request.client.host not in ('127.0.0.1','::1','testclient') or request.url.hostname not in ('localhost','127.0.0.1'):
            raise HTTPException(403,'Desktop settings are only available on this laptop.')
    def checked(fn,*args):
        try:return fn(*args)
        except (ValueError,OSError) as e:raise HTTPException(400,str(e)) from e

    @app.get('/api/memories')
    def memories():return {'memories':get_store().memories()}
    @app.post('/api/memories')
    def add_memory(value:MemoryInput):return {'id':checked(get_store().save_memory,value.content)}
    @app.put('/api/memories/{ident}')
    def edit_memory(ident:int,value:MemoryInput):return {'id':checked(get_store().save_memory,value.content,ident)}
    @app.delete('/api/memories/{ident}')
    def delete_memory(ident:int):return {'ok':get_store().delete_memory(ident)}
    @app.get('/api/history/search')
    def history_search(q:str=''):return {'messages':get_store().search_history(q[:200])}
    @app.get('/api/desktop/permissions')
    def permissions(request:Request):
        local(request)
        with actions.store.connect() as db:
            watched={r['permission_id']:r['status'] for r in db.execute('SELECT * FROM watched_folders')}
        return {'permissions':[{**p,'watch_status':watched.get(p['id'])} for p in actions.permissions()]}
    @app.post('/api/desktop/permissions')
    def add_permission(request:Request,value:PermissionInput):
        local(request);checked(actions.approve,value.kind,value.path);return {'ok':True}
    @app.delete('/api/desktop/permissions/{ident}')
    def revoke(request:Request,ident:int):
        local(request)
        with actions.store.connect() as db:db.execute('DELETE FROM permissions WHERE id=?',(ident,))
        return {'ok':True}
    @app.post('/api/desktop/preview')
    async def preview(request:Request,value:ActionInput):
        local(request);return await asyncio.to_thread(checked,actions.prepare,value)
    @app.post('/api/desktop/confirm')
    def confirm(request:Request,value:ConfirmInput):local(request);return checked(actions.confirm,value.token)

    @app.get('/api/desktop/alerts')
    def alerts(request:Request):
        local(request)
        with get_store().connect() as db:
            rows=db.execute("SELECT r.* FROM reminders r LEFT JOIN alerts a ON a.reminder_id=r.id WHERE r.status='pending' AND r.due_at<=? AND a.reminder_id IS NULL ORDER BY r.due_at LIMIT 20",(time.time(),)).fetchall()
        return {'reminders':[dict(r) for r in rows]}
    @app.post('/api/desktop/alerts/{ident}')
    def ack_alert(request:Request,ident:int):
        local(request)
        with get_store().connect() as db:
            db.execute('INSERT OR IGNORE INTO alerts VALUES (?,?)',(ident,time.time()))
        return {'ok':True}


async def watch_loop(store,rag):
    import hashlib
    while True:
        with store.connect() as db:
            folders=db.execute('SELECT p.id,p.path FROM permissions p JOIN watched_folders w ON p.id=w.permission_id').fetchall()
        for folder in folders:
            status='Scan complete'
            try:
                root=Path(folder['path']).resolve(strict=True)
                def candidates():
                    paths=[];count=0
                    for current,dirs,files in os.walk(root,followlinks=False):
                        dirs[:]=[d for d in dirs if not d.startswith('.') and d!='node_modules' and not (Path(current)/d).is_symlink() and not (Path(current)/d).is_junction()]
                        for name in files:
                            count+=1;p=Path(current)/name
                            if p.suffix.lower() in ('.pdf','.txt','.md') and p.resolve().is_relative_to(root) and not p.is_symlink() and p.stat().st_size<=10*1024*1024:paths.append(p)
                            if count>=10000 or len(paths)>=50:return paths
                    return paths
                paths=await asyncio.to_thread(candidates)
                for path in paths:
                    with store.connect() as db:
                        if not db.execute('SELECT 1 FROM watched_folders WHERE permission_id=?',(folder['id'],)).fetchone():break
                        old=db.execute('SELECT * FROM watched_files WHERE permission_id=? AND path=?',(folder['id'],str(path))).fetchone()
                    data=await asyncio.to_thread(path.read_bytes);digest=hashlib.sha256(data).hexdigest()
                    if old and old['digest']==digest:continue
                    result=await rag.import_file(path.name,data)
                    with store.connect() as db:
                        if db.execute('SELECT 1 FROM watched_folders WHERE permission_id=?',(folder['id'],)).fetchone():
                            db.execute('INSERT OR REPLACE INTO watched_files VALUES (?,?,?,?)',(folder['id'],str(path),digest,result['id']))
                    # Keep prior versions rather than deleting documents another import may share.
                status=f'Scanned {len(paths)} files. Updated files create a new indexed version.'
            except Exception as error:
                status='Scan needs attention: '+str(error)[:200]
            with store.connect() as db:db.execute('UPDATE watched_folders SET status=? WHERE permission_id=?',(status,folder['id']))
        await asyncio.sleep(60)
