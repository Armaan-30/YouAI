"""Request-local user state for the single-process hosted deployment."""
import asyncio
from contextvars import ContextVar
from types import SimpleNamespace
from app.storage import Store
from app.rag import Rag

current = ContextVar('youai_cloud_user')

class Proxy:
    def __init__(self, name): self.name = name
    def target(self): return getattr(current.get(), self.name)
    def __getattr__(self, name): return getattr(self.target(), name)
    def __setitem__(self, key, value): self.target()[key] = value
    def __contains__(self, key): return key in self.target()
    async def __aenter__(self): return await self.target().__aenter__()
    async def __aexit__(self, *args): return await self.target().__aexit__(*args)

def user_state(path):
    store = Store(path)
    return SimpleNamespace(store=store, rag=Rag(store, lexical=True),
                           active={}, chat_lock=asyncio.Lock(), speech_lock=asyncio.Lock())
