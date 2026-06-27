import asyncio

import uvicorn

from core.auth import AuthManager
from core.observability import MemoryTraceEmitter
from web.server import create_app


async def main():
    app = create_app(None, AuthManager(), MemoryTraceEmitter())
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
