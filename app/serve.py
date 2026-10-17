"""Run HTTP loopback and authenticated HTTPS LAN listeners in one process."""
import asyncio
import uvicorn
from app.main import app, DATA
from app.mobile import prepare

async def serve():
    directory=DATA/"mobile"
    prepare(directory)
    local=uvicorn.Server(uvicorn.Config(app,host="127.0.0.1",port=8765))
    remote=uvicorn.Server(uvicorn.Config(app,host="0.0.0.0",port=8768,lifespan="off",
        ssl_certfile=str(directory/"server.pem"),ssl_keyfile=str(directory/"server-key.pem")))
    await asyncio.gather(local.serve(),remote.serve())

if __name__ == "__main__":
    asyncio.run(serve())
