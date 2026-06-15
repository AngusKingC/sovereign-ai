"""CLI command to start the Jarvis web server."""

import asyncio
from pathlib import Path

import typer
import uvicorn

from core.auth import AuthManager
from core.observability import MemoryTraceEmitter
from web.server import create_app


def serve(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Host to bind to"),
    port: int = typer.Option(7000, "--port", "-p", help="Port to bind to"),
    reload: bool = typer.Option(False, "--reload", "-r", help="Enable auto-reload"),
) -> None:
    """Start the Jarvis web server.
    
    This command starts the FastAPI web server with REST and WebSocket endpoints.
    The server requires authentication via a bearer token.
    """
    # Instantiate AuthManager
    auth_manager = AuthManager()
    
    # Get or create token
    token = asyncio.run(auth_manager.get_or_create_token())
    
    # Print token on first run
    print(f"Jarvis auth token: {token} — save this, it won't be shown again")
    
    # Instantiate MemoryTraceEmitter
    emitter = MemoryTraceEmitter()
    
    # Import and instantiate orchestrator
    # Note: This is a placeholder - actual orchestrator instantiation depends on
    # the full dependency tree which is outside the scope of this file
    from core.orchestrator import Orchestrator
    from core.memory_router import MemoryRouter
    
    # Create a minimal orchestrator for the web server
    # In production, this would be wired with all dependencies
    memory_router = MemoryRouter()
    orchestrator = Orchestrator(memory_router=memory_router, emitter=emitter)
    
    # Create FastAPI app
    app = create_app(orchestrator, auth_manager, emitter)
    
    # Start server with uvicorn
    uvicorn.run(app, host=host, port=port, reload=reload)


if __name__ == "__main__":
    typer.run(serve)
