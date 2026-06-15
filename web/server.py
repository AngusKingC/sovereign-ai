"""FastAPI web server for Jarvis."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from web.middleware.auth_middleware import AuthMiddleware, SecretsAudit
from core.auth import AuthManager
from core.observability import (
    MemoryTraceEmitter,
    TraceEmitter,
    TraceComponent,
    TraceEventType,
    TraceLevel,
    TraceEvent,
)

if TYPE_CHECKING:
    from core.observability import TraceEmitter
    from core.orchestrator import Orchestrator


def create_app(
    orchestrator: "Orchestrator",
    auth_manager: AuthManager,
    emitter: TraceEmitter | None = None,
) -> FastAPI:
    """Factory function to create a configured FastAPI app.

    Args:
        orchestrator: The orchestrator instance
        auth_manager: The auth manager instance
        emitter: Trace emitter for observability

    Returns:
        Configured FastAPI application
    """
    app = FastAPI()
    _emitter = emitter or MemoryTraceEmitter()

    # Wire AuthMiddleware into the app
    app.add_middleware(AuthMiddleware, auth_manager=auth_manager)

    # Startup event: run secrets audit
    @app.on_event("startup")
    async def startup_event():
        """Run secrets audit on startup."""
        try:
            audit = SecretsAudit(emitter=_emitter)
            await audit.audit()
        except Exception:
            pass  # Secrets audit failure should not crash the server

    # GET /health — no auth required
    @app.get("/health")
    async def health():
        """Health check endpoint."""
        return {"status": "ok", "version": "0.1.0"}

    # GET /api/tasks — auth required
    @app.get("/api/tasks")
    async def get_tasks():
        """Return list of recent tasks from orchestrator."""
        try:
            if hasattr(orchestrator, "list_tasks"):
                tasks = await orchestrator.list_tasks()
                return {"tasks": tasks}
            return {"tasks": []}
        except Exception:
            return {"tasks": []}

    # POST /api/tasks — auth required
    @app.post("/api/tasks")
    async def create_task(body: dict):
        """Create and submit a task to the orchestrator."""
        try:
            intent = body.get("intent", "")
            priority = body.get("priority", "medium")

            # Submit task to orchestrator
            task_id = await orchestrator.submit_task(intent, priority)

            try:
                event = TraceEvent(
                    event_type=TraceEventType.WEB_TASK_SUBMITTED,
                    component=TraceComponent.WEB,
                    level=TraceLevel.INFO,
                    message="Task submitted via web API",
                    data={"task_id": task_id, "priority": priority},
                    duration_ms=0,
                )
                await _emitter.emit(event)
            except Exception:
                pass  # Trace failure should not abort operation

            return {"task_id": task_id, "status": "queued"}
        except Exception:
            return {"task_id": "", "status": "error"}

    # GET /api/workers — auth required
    @app.get("/api/workers")
    async def get_workers():
        """Return list of registered workers."""
        try:
            if hasattr(orchestrator, "list_workers"):
                workers = await orchestrator.list_workers()
                return {"workers": workers}
            return {"workers": []}
        except Exception:
            return {"workers": []}

    # GET /api/trace — auth required
    @app.get("/api/trace")
    async def get_trace():
        """Return last 100 trace events from emitter."""
        try:
            events = _emitter.get_events()
            last_100 = events[-100:] if len(events) > 100 else events
            return {"events": last_100}
        except Exception:
            return {"events": []}

    # WebSocket /ws — auth required via ?token=<value> query param
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket endpoint for real-time task submission."""
        await websocket.accept()

        # Extract token from query param
        token = websocket.query_params.get("token")

        # Validate token
        if not token:
            await websocket.close(code=1008)
            return

        is_valid = await auth_manager.validate_token(token)
        if not is_valid:
            await websocket.close(code=1008)
            return

        try:
            event = TraceEvent(
                event_type=TraceEventType.WEB_WEBSOCKET_CONNECTED,
                component=TraceComponent.WEB,
                level=TraceLevel.INFO,
                message="WebSocket connected",
                data={},
                duration_ms=0,
            )
            await _emitter.emit(event)
        except Exception:
            pass  # Trace failure should not abort operation

        try:
            while True:
                # Receive message from client
                data = await websocket.receive_json()
                intent = data.get("intent", "")

                # Submit task to orchestrator
                task_id = await orchestrator.submit_task(intent, "medium")

                try:
                    event = TraceEvent(
                        event_type=TraceEventType.WEB_TASK_SUBMITTED,
                        component=TraceComponent.WEB,
                        level=TraceLevel.INFO,
                        message="Task submitted via WebSocket",
                        data={"task_id": task_id},
                        duration_ms=0,
                    )
                    await _emitter.emit(event)
                except Exception:
                    pass  # Trace failure should not abort operation

                # Send response back to client
                await websocket.send_json({"task_id": task_id, "status": "queued"})
        except WebSocketDisconnect:
            try:
                event = TraceEvent(
                    event_type=TraceEventType.WEB_WEBSOCKET_DISCONNECTED,
                    component=TraceComponent.WEB,
                    level=TraceLevel.INFO,
                    message="WebSocket disconnected",
                    data={},
                    duration_ms=0,
                )
                await _emitter.emit(event)
            except Exception:
                pass  # Trace failure should not abort operation
        except Exception:
            pass

    # Mount static files
    app.mount("/static", StaticFiles(directory="web/static"), name="static")

    return app
