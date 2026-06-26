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

    # GET /api/vram/status — auth required
    @app.get("/api/vram/status")
    async def vram_status():
        """Return VRAM status for PEMADS debates."""
        try:
            if hasattr(orchestrator, "vram_manager") and orchestrator.vram_manager:
                return await orchestrator.vram_manager.get_vram_status()
            # Fallback
            return {"loaded_models": [], "debate_loaded": [], "loaded_count": 0}
        except Exception as e:
            logger.warning(f"vram_status failed: {e}")
            return {"loaded_models": [], "debate_loaded": [], "loaded_count": 0}

    # GET /api/debates/{debate_id} — auth required
    @app.get("/api/debates/{debate_id}")
    async def get_debate(debate_id: str):
        """Return debate history from DebatePool."""
        try:
            if (
                hasattr(orchestrator, "expert_panel_manager")
                and orchestrator.expert_panel_manager
            ):
                if hasattr(orchestrator, "debate_pool") and orchestrator.debate_pool:
                    history = orchestrator.debate_pool.get_debate_history(debate_id)
                    return {"debate_id": debate_id, "history": history}
                return {"error": "DebatePool not configured"}, 404
            return {"error": "PEMADS not configured"}, 404
        except Exception as e:
            logger.warning(f"get_debate failed: {e}")
            return {"error": str(e)}, 500

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

    # WebSocket /ws/pty — auth required via ?token=<value> query param
    @app.websocket("/ws/pty")
    async def pty_websocket(websocket: WebSocket):
        """WebSocket PTY endpoint for terminal access.

        Auth: token query param (same as existing /ws endpoint).
        Spawns a pseudo-terminal, streams output, receives input.

        Rev2 H1 fix: All blocking syscalls (select, os.read, os.write) run in
        executor to avoid freezing the asyncio event loop.
        Rev2 H2 fix: Platform-specific imports inside guards. Windows uses
        pywinpty if available, otherwise returns 501.
        """
        import sys

        token = websocket.query_params.get("token")
        if not token or not await auth_manager.validate_token(token):
            await websocket.close(code=4001, reason="Unauthorized")
            return

        # Rev2 H2 fix — platform-specific imports inside guard
        if sys.platform == "win32":
            try:
                import winpty  # type: ignore
            except ImportError:
                logger.warning(
                    "pywinpty not installed — PTY endpoint unavailable on Windows"
                )
                await websocket.close(
                    code=4002,
                    reason="PTY unavailable on Windows (pywinpty not installed)",
                )
                return
            # Windows implementation using winpty (similar pattern, different API)
            await _windows_pty_websocket(websocket, winpty, _emitter)
            return

        # Unix implementation
        try:
            import os
            import pty
            import select
            import signal
        except ImportError:
            await websocket.close(code=4003, reason="PTY unavailable on this platform")
            return

        await websocket.accept()

        loop = asyncio.get_event_loop()
        master, slave = pty.openpty()
        pid = os.fork()

        if pid == 0:
            # Child process — becomes the shell
            os.setsid()
            os.dup2(slave, 0)
            os.dup2(slave, 1)
            os.dup2(slave, 2)
            os.close(master)
            os.close(slave)
            os.execvp("bash", ["bash"])
        else:
            # Parent process — relay I/O via executor (Rev2 H1 fix)
            os.close(slave)

            async def read_pty_output():
                """Read from PTY master, send to WebSocket. Runs blocking read in executor."""
                try:
                    while True:
                        # Rev2 H1 fix — run blocking select in executor
                        readable, _, _ = await loop.run_in_executor(
                            None, lambda: select.select([master], [], [], 0.1)
                        )
                        if master in readable:
                            # Rev2 H1 fix — run blocking os.read in executor
                            data = await loop.run_in_executor(
                                None, lambda: os.read(master, 4096)
                            )
                            if not data:
                                break  # PTY closed
                            await websocket.send_text(
                                data.decode("utf-8", errors="replace")
                            )
                except Exception as e:
                    logger.warning(f"PTY read error: {e}")

            async def read_websocket_input():
                """Read from WebSocket, write to PTY master."""
                try:
                    while True:
                        message = await websocket.receive_text()
                        # Rev2 H1 fix — run blocking os.write in executor
                        await loop.run_in_executor(
                            None, lambda: os.write(master, message.encode())
                        )
                except Exception as e:
                    logger.warning(f"WebSocket read error: {e}")

            try:
                # Run reader and writer concurrently, cancel both when either finishes
                reader_task = asyncio.create_task(read_pty_output())
                writer_task = asyncio.create_task(read_websocket_input())

                done, pending = await asyncio.wait(
                    [reader_task, writer_task], return_when=asyncio.FIRST_COMPLETED
                )
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            finally:
                os.close(master)
                try:
                    os.kill(pid, signal.SIGTERM)
                    await asyncio.sleep(0.1)  # Give process time to exit
                    os.kill(pid, signal.SIGKILL)  # Force kill if still alive
                except ProcessLookupError:
                    pass  # Already dead
                os.waitpid(pid, 0)

    # Mount static files
    app.mount("/static", StaticFiles(directory="web/static"), name="static")

    return app


async def _windows_pty_websocket(websocket, winpty_module, emitter):
    """Windows PTY implementation using pywinpty. Separate function for clarity."""
    await websocket.accept()
    loop = asyncio.get_event_loop()

    # Create winpty PTY process
    pty_proc = winpty_module.PTY()
    pty_proc.spawn("cmd.exe")  # or powershell.exe

    async def read_pty_output():
        try:
            while True:
                # winpty read is blocking — run in executor
                data = await loop.run_in_executor(None, lambda: pty_proc.read(4096))
                if data:
                    await websocket.send_text(data)
        except Exception as e:
            logger.warning(f"Windows PTY read error: {e}")

    async def read_websocket_input():
        try:
            while True:
                message = await websocket.receive_text()
                # winpty write is blocking — run in executor
                await loop.run_in_executor(None, lambda: pty_proc.write(message))
        except Exception as e:
            logger.warning(f"Windows WebSocket read error: {e}")

    try:
        reader_task = asyncio.create_task(read_pty_output())
        writer_task = asyncio.create_task(read_websocket_input())

        done, pending = await asyncio.wait(
            [reader_task, writer_task], return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    finally:
        pty_proc.close()
