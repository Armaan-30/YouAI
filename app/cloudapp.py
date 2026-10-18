"""Render entry point: authenticated, isolated, single-worker web preview."""
import asyncio
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import shutil
import time
from collections import defaultdict, deque
from pathlib import Path
from http.cookies import SimpleCookie
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, RedirectResponse

os.environ['YOUAI_MODE'] = 'cloud'
from app import main
from app.cloud_runtime import current, user_state
from app.config import setting

COOKIE = '__Host-youai_session'

class CloudGateway:
    def __init__(self, backend, root=None, origin=None, invite=None):
        self.backend = backend
        self.root = Path(root or os.environ.get('YOUAI_DATA_DIR', '/var/data/youai'))
        self.origin = (origin or os.environ.get('YOUAI_PUBLIC_ORIGIN') or os.environ.get('RENDER_EXTERNAL_URL', '')).rstrip('/')
        self.invite = invite or os.environ.get('YOUAI_INVITE_CODE', '')
        if not self.origin.startswith('https://') or len(self.invite) < 32:
            raise RuntimeError('Set HTTPS YOUAI_PUBLIC_ORIGIN and YOUAI_INVITE_CODE (at least 32 characters).')
        if not setting('GROQ_API_KEY'):
            raise RuntimeError('Set GROQ_API_KEY in backend secrets.')
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = self.root / 'accounts.sqlite3'
        with self.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY, name TEXT UNIQUE, salt TEXT, password TEXT);
                CREATE TABLE IF NOT EXISTS sessions (digest TEXT PRIMARY KEY, user_id TEXT, expires REAL);
                CREATE TABLE IF NOT EXISTS usage (user_id TEXT, day INTEGER, count INTEGER, PRIMARY KEY(user_id,day));''')
        self.states = {}
        self.requests = defaultdict(deque)
        self.inflight = 0
        self.importing = False

    def connect(self):
        # Explicit closing is handled by callers: sqlite Connection's context only commits.
        from contextlib import contextmanager
        @contextmanager
        def connection():
            db = sqlite3.connect(self.db, timeout=10)
            try:
                with db: yield db
            finally: db.close()
        return connection()

    def rate(self, key, limit):
        now = time.monotonic()
        if len(self.requests) > 2048:
            self.requests = defaultdict(deque, {k:v for k,v in self.requests.items() if v and v[-1] > now-60})
            if len(self.requests) > 2048: return False
        queue = self.requests[key]
        while queue and queue[0] < now-60: queue.popleft()
        if len(queue) >= limit: return False
        queue.append(now)
        return True

    def session_user(self, scope):
        cookie = SimpleCookie()
        try:
            cookie.load(dict(scope['headers']).get(b'cookie', b'').decode())
            token = cookie[COOKIE].value
        except (KeyError, ValueError): return None
        with self.connect() as db:
            row = db.execute('SELECT user_id FROM sessions WHERE digest=? AND expires>?',
                             (hashlib.sha256(token.encode()).hexdigest(), time.time())).fetchone()
        return row[0] if row else None

    def authenticate(self, data, register):
        name, password = data.get('username', ''), data.get('password', '')
        if not isinstance(name, str) or not isinstance(password, str): return None
        name = name.strip().lower()
        if not re.fullmatch(r'[a-z0-9_]{3,40}', name) or not 12 <= len(password) <= 128: return None
        with self.connect() as db:
            if register:
                supplied = data.get('invite', '')
                if not isinstance(supplied, str) or not hmac.compare_digest(supplied, self.invite): return None
                salt = secrets.token_hex(16)
            else:
                row = db.execute('SELECT id,salt,password FROM users WHERE name=?', (name,)).fetchone()
                salt = row[1] if row else '0'*32
            digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
            if register:
                db.execute('BEGIN IMMEDIATE')
                if db.execute('SELECT count(*) FROM users').fetchone()[0] >= 100: return None
                ident = secrets.token_hex(16)
                try: db.execute('INSERT INTO users VALUES (?,?,?,?)', (ident,name,salt,digest))
                except sqlite3.IntegrityError: return None
            else:
                if not row or not hmac.compare_digest(digest, row[2]): return None
                ident = row[0]
            token = secrets.token_urlsafe(32)
            db.execute('DELETE FROM sessions WHERE expires<?', (time.time(),))
            db.execute('DELETE FROM sessions WHERE user_id=? AND digest NOT IN (SELECT digest FROM sessions WHERE user_id=? ORDER BY expires DESC LIMIT 4)', (ident,ident))
            db.execute('INSERT INTO sessions VALUES (?,?,?)',
                       (hashlib.sha256(token.encode()).hexdigest(),ident,time.time()+7*86400))
            return token

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'lifespan':
            return await self.backend(scope, receive, send)
        if scope['type'] == 'websocket':
            await send({'type':'websocket.close','code':1008})
            return
        request = Request(scope, receive)
        path = request.url.path
        async def respond(response):
            response.headers['Cache-Control'] = 'no-store'
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['Referrer-Policy'] = 'no-referrer'
            response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'"
            return await response(scope, receive, send)
        if path == '/healthz': return await respond(JSONResponse({'ok': True}))
        if request.url.netloc != self.origin.split('://',1)[1]:
            return await respond(JSONResponse({'detail':'Host not allowed.'}, status_code=403))
        if request.method not in ('GET','HEAD'):
            if request.headers.get('origin') != self.origin or request.headers.get('x-youai') != '1':
                return await respond(JSONResponse({'detail':'Origin not allowed.'}, status_code=403))
        try:
            if int(request.headers.get('content-length','0')) > 11*1024*1024:
                return await respond(JSONResponse({'detail':'Upload too large.'}, status_code=413))
        except ValueError:
            return await respond(JSONResponse({'detail':'Invalid request length.'},status_code=400))
        if path == '/login' and request.method == 'GET':
            return await respond(FileResponse(main.ROOT/'web'/'login.html'))
        if path in ('/api/auth/login','/api/auth/register') and request.method == 'POST':
            ip = scope.get('client', ('unknown',))[0]
            if not self.rate('auth:'+ip, 10) or self.inflight >= 8:
                return await respond(JSONResponse({'detail':'Too many requests. Wait a minute.'},status_code=429))
            self.inflight += 1
            try:
                body = bytearray()
                async for chunk in request.stream():
                    body.extend(chunk)
                    if len(body)>4096: raise ValueError()
                data = json.loads(body)
                if not isinstance(data,dict): raise ValueError()
                token = await asyncio.to_thread(self.authenticate, data, path.endswith('register'))
            except (ValueError, TypeError): token = None
            finally: self.inflight -= 1
            if not token: return await respond(JSONResponse({'detail':'Check username, password and invitation code. Registration may be full or the username taken.'},status_code=400))
            response = JSONResponse({'ok':True})
            response.set_cookie(COOKIE,token,secure=True,httponly=True,samesite='strict',max_age=7*86400,path='/')
            return await respond(response)
        user = self.session_user(scope)
        if path.startswith('/static/'):
            return await self.backend(scope,receive,send)
        if not user:
            return await respond(JSONResponse({'detail':'Sign in to continue.'},status_code=401) if path.startswith('/api/') else RedirectResponse('/login',status_code=303))
        if path == '/api/auth/logout' and request.method == 'POST':
            # Revoke all sessions for this account; other tabs/devices must sign in again.
            with self.connect() as db: db.execute('DELETE FROM sessions WHERE user_id=?',(user,))
            response=JSONResponse({'ok':True});response.delete_cookie(COOKIE,path='/',secure=True,httponly=True,samesite='strict')
            return await respond(response)
        if path.startswith(('/api/desktop/', '/api/mobile/', '/api/wake')):
            return await respond(JSONResponse({'detail':'This feature requires the Windows desktop app.'},status_code=403))
        if not self.rate(user, 180) or self.inflight >= 8:
            return await respond(JSONResponse({'detail':'Server busy or request limit reached. Try again shortly.'},status_code=429))
        if request.method == 'POST' and path in ('/api/chat','/api/chat/stream','/api/transcribe'):
            day = int(time.time()//86400)
            with self.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                db.execute('DELETE FROM usage WHERE day<?',(day,))
                row=db.execute('SELECT count FROM usage WHERE user_id=? AND day=?',(user,day)).fetchone()
                if row and row[0]>=200:
                    return await respond(JSONResponse({'detail':'Daily limit reached (200 chat/transcription requests).'},status_code=429))
                db.execute('INSERT INTO usage VALUES (?,?,1) ON CONFLICT(user_id,day) DO UPDATE SET count=count+1',(user,day))
        user_path = self.root/'users'/user/'youai.sqlite3'
        if request.method in ('POST','PUT') and not path.startswith('/api/cancel/'):
            if shutil.disk_usage(self.root).free < 64*1024*1024:
                return await respond(JSONResponse({'detail':'Server storage is full. Contact the app owner.'},status_code=507))
            if user_path.exists():
                db=sqlite3.connect(user_path)
                try:
                    used=(db.execute('PRAGMA page_count').fetchone()[0]-db.execute('PRAGMA freelist_count').fetchone()[0])*db.execute('PRAGMA page_size').fetchone()[0]
                finally: db.close()
                if used>5*1024*1024:
                    return await respond(JSONResponse({'detail':'Account storage limit reached. Delete documents or clear history.'},status_code=413))
        if user not in self.states: self.states[user]=user_state(user_path)
        importing = path == '/api/documents' and request.method == 'POST'
        if importing and self.importing:
            return await respond(JSONResponse({'detail':'Another document is being indexed. Try again shortly.'},status_code=429))
        if importing: self.importing = True
        context = current.set(self.states[user])
        self.inflight += 1
        received = 0
        async def bounded_receive():
            nonlocal received
            message = await receive()
            received += len(message.get('body',b''))
            if received>11*1024*1024:
                from starlette.exceptions import HTTPException
                raise HTTPException(413,'Upload too large.')
            return message
        async def secure_send(message):
            if message['type']=='http.response.start':
                message['headers'] += [(b'cache-control',b'no-store'),(b'x-content-type-options',b'nosniff'),
                    (b'referrer-policy',b'no-referrer'),
                    (b'content-security-policy',b"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; media-src 'self' blob:; frame-ancestors 'none'")]
            await send(message)
        try: await self.backend(scope,bounded_receive,secure_send)
        finally:
            if importing: self.importing = False
            self.inflight -= 1
            current.reset(context)

# Lazy construction permits importing the class in tests without production secrets.
_gateway = None
async def app(scope, receive, send):
    global _gateway
    if _gateway is None: _gateway = CloudGateway(main.app)
    await _gateway(scope,receive,send)
