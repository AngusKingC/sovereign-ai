"""FastAPI web server for Jarvis."""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
import uuid
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from core.auth import AuthManager
from core.input_sanitiser import InputSanitiser
from core.observability import (
    MemoryTraceEmitter,
    TraceComponent,
    TraceEmitter,
    TraceEvent,
    TraceEventType,
    TraceLevel,
)
from web.middleware.auth_middleware import AuthMiddleware, SecretsAudit

if TYPE_CHECKING:
    from core.observability import TraceEmitter
    from core.orchestrator import Orchestrator

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI app."""
    # Startup: run secrets audit
    try:
        _emitter = app.state._emitter
        audit = SecretsAudit(emitter=_emitter)
        await audit.audit()
    except Exception as e:
        logger.warning(
            f"Secrets audit failed: {e}"
        )  # Secrets audit failure should not crash the server
        pass
    yield
    # Shutdown: no cleanup needed currently


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
    app = FastAPI(lifespan=lifespan)
    _emitter = emitter or MemoryTraceEmitter()
    app.state._emitter = _emitter
    sanitiser = InputSanitiser(emitter=_emitter)

    # Wire AuthMiddleware into the app
    app.add_middleware(AuthMiddleware, auth_manager=auth_manager)

    # Add CORS middleware for frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # GET /health — no auth required
    @app.get("/health")
    async def health():
        """Health check endpoint."""
        return {"status": "ok", "version": "0.1.0"}

    # GET /api/status — auth required
    @app.get("/api/status")
    async def get_status():
        """Agent phase, session ID, uptime, model slug."""
        try:
            # Try to get real status from orchestrator if available
            if hasattr(orchestrator, "get_status"):
                return await orchestrator.get_status()
            # Fallback to basic status
            return {
                "session_id": "unknown",
                "phase": "idle",
                "uptime": 0,
                "model": "unknown",
            }
        except Exception as e:
            logger.warning(f"get_status failed: {e}")
            return {
                "session_id": "unknown",
                "phase": "idle",
                "uptime": 0,
                "model": "unknown",
            }

    # GET /api/tasks — auth required
    @app.get("/api/tasks")
    async def get_tasks():
        """Return list of recent tasks from orchestrator."""
        try:
            if hasattr(orchestrator, "list_tasks"):
                tasks = await orchestrator.list_tasks()
                return {"tasks": tasks}
            return {"tasks": []}
        except Exception as e:
            logger.warning(f"get_tasks failed: {e}")
            return {"tasks": []}

    # POST /api/tasks — auth required
    @app.post("/api/tasks")
    async def create_task(body: dict):
        """Create and submit a task to the orchestrator."""
        try:
            intent = body.get("intent", "")
            # Sanitise external input at HTTP boundary (Rule 14)
            intent = await sanitiser.sanitise(intent, source="http_post_tasks")
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
            except Exception as e:
                logger.warning(
                    f"Trace emission failed in create_task: {e}"
                )  # Trace failure should not abort operation
                pass

            return {"task_id": task_id, "status": "queued"}
        except Exception as e:
            logger.warning(f"create_task failed: {e}")
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
        except Exception as e:
            logger.warning(f"get_workers failed: {e}")
            return {"workers": []}

    # GET /api/subagents — auth required
    @app.get("/api/subagents")
    async def get_subagents():
        """Active subagent list."""
        try:
            if hasattr(orchestrator, "list_subagents"):
                subagents = await orchestrator.list_subagents()
                return {"subagents": subagents}
            return {"subagents": []}
        except Exception as e:
            logger.warning(f"get_subagents failed: {e}")
            return {"subagents": []}

    # DELETE /api/subagents/{subagent_id} — auth required
    @app.delete("/api/subagents/{subagent_id}")
    async def kill_subagent(subagent_id: str):
        """Kill a subagent."""
        try:
            if hasattr(orchestrator, "kill_subagent"):
                await orchestrator.kill_subagent(subagent_id)
                return {"status": "killed", "subagent": subagent_id}
            return {"status": "not_implemented", "subagent": subagent_id}
        except Exception as e:
            logger.warning(f"kill_subagent failed: {e}")
            return {"status": "error", "subagent": subagent_id}

    # SSE generator helper
    async def sse_generator(event_factory):
        """Generate SSE events with data: <JSON>\n\n framing."""
        try:
            async for event in event_factory():
                yield f"data: {json.dumps(event)}\n\n"
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("SSE stream failed: %s", e)

    # GET /api/agent/reasoning — auth required (SSE)
    @app.get("/api/agent/reasoning")
    async def reasoning_stream():
        """Streaming reasoning tokens."""

        async def factory():
            # Try to get real reasoning stream from orchestrator
            if hasattr(orchestrator, "get_reasoning_stream"):
                async for token in orchestrator.get_reasoning_stream():
                    yield token
            else:
                # Fallback: mock tokens
                tokens = ["Planning", " step", " 1", ":", " analyze", " input", "..."]
                while True:
                    for token in tokens:
                        yield {"token": token, "timestamp": int(time.time() * 1000)}

        return StreamingResponse(
            sse_generator(factory),
            media_type="text/event-stream",
        )

    # GET /api/tools/stream — auth required (SSE)
    @app.get("/api/tools/stream")
    async def tools_stream():
        """Tool call events."""

        async def factory():
            # Try to get real tool stream from orchestrator
            if hasattr(orchestrator, "get_tool_stream"):
                async for event in orchestrator.get_tool_stream():
                    yield event
            else:
                # Fallback: mock events
                while True:
                    yield {
                        "id": str(uuid.uuid4()),
                        "tool": random.choice(
                            ["web_search", "memory_write", "code_exec"]
                        ),
                        "status": "running",
                        "args": {"query": "mock query"},
                    }
                    await asyncio.sleep(2)

        return StreamingResponse(
            sse_generator(factory),
            media_type="text/event-stream",
        )

    # GET /api/memory/activations — auth required (SSE)
    @app.get("/api/memory/activations")
    async def activations_stream():
        """Memory slot activation deltas."""

        async def factory():
            # Try to get real activations from memory router
            if hasattr(orchestrator, "memory_router"):
                async for (
                    activation
                ) in orchestrator.memory_router.get_activation_stream():
                    yield activation
            else:
                # Fallback: mock activations
                while True:
                    yield {
                        "index": random.randint(0, 511),
                        "activation": random.random(),
                        "timestamp": int(time.time() * 1000),
                    }

        return StreamingResponse(
            sse_generator(factory),
            media_type="text/event-stream",
        )

    # GET /api/trace — auth required
    @app.get("/api/trace")
    async def get_trace():
        """Return last 100 trace events from emitter."""
        try:
            events = _emitter.get_events()
            last_100 = events[-100:] if len(events) > 100 else events
            return {"events": last_100}
        except Exception as e:
            logger.warning(f"get_trace failed: {e}")
            return {"events": []}

    # GET /api/costs/summary — auth required
    @app.get("/api/costs/summary")
    async def get_costs_summary():
        """Return cost summary."""
        try:
            if hasattr(orchestrator, "cost_tracker"):
                summary = orchestrator.cost_tracker.get_spend_summary()
                return {
                    "daily_spend": summary.get("daily_spend", 0.0),
                    "daily_cap": summary.get("daily_cap_usd", 10.0),
                    "monthly_spend": summary.get("monthly_spend", 0.0),
                    "monthly_cap": summary.get("monthly_cap_usd", 100.0),
                    "alert_threshold": 80,
                    "fallback_threshold": 90,
                    "model_breakdown": summary.get("model_spend", {}),
                }
            # Fallback
            return {
                "daily_spend": 0.0,
                "daily_cap": 10.0,
                "monthly_spend": 0.0,
                "monthly_cap": 100.0,
                "alert_threshold": 80,
                "fallback_threshold": 90,
                "model_breakdown": {},
            }
        except Exception as e:
            logger.warning(f"get_costs_summary failed: {e}")
            return {
                "daily_spend": 0.0,
                "daily_cap": 10.0,
                "monthly_spend": 0.0,
                "monthly_cap": 100.0,
                "alert_threshold": 80,
                "fallback_threshold": 90,
                "model_breakdown": {},
            }

    # GET /api/costs/daily — auth required
    @app.get("/api/costs/daily")
    async def get_costs_daily():
        """Return daily cost usage."""
        try:
            if hasattr(orchestrator, "cost_tracker"):
                usage = orchestrator.cost_tracker.daily_usage
                return usage
            # Fallback
            return {"date": "", "total_usd": 0.0, "entries": []}
        except Exception as e:
            logger.warning(f"get_costs_daily failed: {e}")
            return {"date": "", "total_usd": 0.0, "entries": []}

    # GET /api/circuit-breaker/status — auth required
    @app.get("/api/circuit-breaker/status")
    async def get_circuit_breaker_status():
        """Return circuit breaker status."""
        try:
            if hasattr(orchestrator, "worker_circuit_breaker"):
                status = orchestrator.worker_circuit_breaker.get_status()
                degraded_ratio = (
                    orchestrator.worker_circuit_breaker.get_degraded_worker_ratio()
                )
                return {"workers": status, "degraded_ratio": degraded_ratio}
            # Fallback
            return {"workers": [], "degraded_ratio": 0.0}
        except Exception as e:
            logger.warning(f"get_circuit_breaker_status failed: {e}")
            return {"workers": [], "degraded_ratio": 0.0}

    # POST /api/circuit-breaker/reset — auth required
    @app.post("/api/circuit-breaker/reset")
    async def reset_circuit(body: dict):
        """Reset circuit breaker for a worker."""
        try:
            worker_id = body.get("worker_id", "")
            if (
                orchestrator
                and hasattr(orchestrator, "worker_circuit_breaker")
                and orchestrator.worker_circuit_breaker
            ):
                await orchestrator.worker_circuit_breaker.reset_circuit(worker_id)
                return {"status": "ok", "worker_id": worker_id}
            # Fallback
            return {"status": "not_implemented", "worker_id": worker_id}
        except Exception as e:
            logger.warning(f"reset_circuit failed: {e}")
            return {"status": "not_implemented", "worker_id": body.get("worker_id", "")}

    # GET /api/approvals/pending — auth required
    @app.get("/api/approvals/pending")
    async def get_approvals_pending():
        """Return pending approval requests."""
        try:
            if hasattr(orchestrator, "approval_gate"):
                pending = await orchestrator.approval_gate.list_pending()
                return pending
            # Fallback
            return []
        except Exception as e:
            logger.warning(f"get_approvals_pending failed: {e}")
            return []

    # POST /api/approvals/{id}/respond — auth required
    @app.post("/api/approvals/{approval_id}/respond")
    async def respond_approval(approval_id: str, body: dict):
        """Respond to an approval request."""
        try:
            approved = body.get("approved", False)
            if (
                orchestrator
                and hasattr(orchestrator, "approval_gate")
                and orchestrator.approval_gate
            ):
                await orchestrator.approval_gate.respond(
                    approval_id, approved, responder="api"
                )
                return {"status": "ok", "id": approval_id}
            # Fallback
            return {"status": "not_found", "id": approval_id}
        except Exception as e:
            logger.warning(f"respond_approval failed: {e}")
            return {"status": "not_found", "id": approval_id}

    # GET /api/memory/slots — auth required
    @app.get("/api/memory/slots")
    async def get_memory_slots():
        """Return memory slots."""
        try:
            if hasattr(orchestrator, "memory_router"):
                slots = await orchestrator.memory_router.fetch_by_filter(filter={})
                return slots
            # Fallback
            return []
        except Exception as e:
            logger.warning(f"get_memory_slots failed: {e}")
            return []

    # GET /api/memory/slots/export — auth required
    @app.get("/api/memory/slots/export")
    async def export_memory():
        """Export memory slots as JSON."""
        try:
            if hasattr(orchestrator, "memory_router"):
                slots = await orchestrator.memory_router.fetch_by_filter(filter={})
                return slots
            # Fallback
            return []
        except Exception as e:
            logger.warning(f"export_memory failed: {e}")
            return []

    # POST /api/memory/slots/import — auth required
    @app.post("/api/memory/slots/import")
    async def import_memory(slots: list[dict]):
        """Import memory slots."""
        try:
            if hasattr(orchestrator, "memory_router"):
                imported = 0
                errors = []
                for slot in slots:
                    try:
                        key = slot.get("key", "")
                        value = slot.get("value")
                        scope = slot.get("scope", "default")
                        await orchestrator.memory_router.scoped_write(scope, key, value)
                        imported += 1
                    except Exception as e:
                        errors.append(str(e))
                return {"imported": imported, "errors": errors}
            # Fallback
            return {"imported": 0, "errors": ["not_implemented"]}
        except Exception as e:
            logger.warning(f"import_memory failed: {e}")
            return {"imported": 0, "errors": [str(e)]}

    # GET /api/skills — auth required
    @app.get("/api/skills")
    async def get_skills():
        """Return list of skills."""
        try:
            if hasattr(orchestrator, "skill_registry"):
                skills = orchestrator.skill_registry.list_skills()
                return skills
            # Fallback
            return []
        except Exception as e:
            logger.warning(f"get_skills failed: {e}")
            return []

    # GET /api/sessions/{session_id}/timeline — auth required
    @app.get("/api/sessions/{session_id}/timeline")
    async def get_session_timeline(session_id: str):
        """Return session timeline."""
        try:
            if hasattr(orchestrator, "get_session_timeline"):
                timeline = await orchestrator.get_session_timeline(session_id)
                return timeline
            # Fallback
            return []
        except Exception as e:
            logger.warning(f"get_session_timeline failed: {e}")
            return []

    # GET /api/system — auth required
    @app.get("/api/system")
    async def get_system_stats():
        """Return system stats."""
        try:
            from system.system_monitor import SystemMonitor

            monitor = SystemMonitor()
            stats = monitor.get_stats()
            return stats
        except Exception as e:
            logger.warning(f"get_system_stats failed: {e}")
            return {
                "cpu_percent": 0.0,
                "memory_percent": 0.0,
                "uptime_seconds": 0,
                "active_workers": 0,
            }

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
        except Exception as e:
            logger.warning(
                f"Trace emission failed in websocket connect: {e}"
            )  # Trace failure should not abort operation
            pass

        try:
            while True:
                # Receive message from client
                data = await websocket.receive_json()
                intent = data.get("intent", "")
                # Sanitise external input at WebSocket boundary (Rule 14)
                intent = await sanitiser.sanitise(intent, source="websocket_tasks")

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
                except Exception as e:
                    logger.warning(
                        f"Trace emission failed in websocket message: {e}"
                    )  # Trace failure should not abort operation
                    pass

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
            except Exception as e:
                logger.warning(
                    f"Trace emission failed in websocket disconnect: {e}"
                )  # Trace failure should not abort operation
                pass
        except Exception as e:
            logger.warning(f"WebSocket handler error: {e}")
            pass

    # WebSocket /api/pty — auth required via ?token=<value> query param
    @app.websocket("/api/pty")
    async def pty_websocket(websocket: WebSocket):
        """Bidirectional PTY stream for xterm.js (DEFERRED — stub only)."""
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
            while True:
                data = await websocket.receive_text()
                await websocket.send_text(f"[PTY stub] received: {data}")
        except WebSocketDisconnect:
            logger.info("PTY WebSocket disconnected")
        except Exception as e:
            logger.warning("PTY WebSocket error: %s", e)

    # Mount static files
    app.mount("/static", StaticFiles(directory="web/static"), name="static")

    return app
