"""FastAPI web server for Jarvis."""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

# Rev2 H12 fix — module-level import, not inside endpoint
import psutil
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from api.adapters import router as adapters_router
from api.models import router as models_router
from api.workers import router as workers_router
from core.auth import AuthManager
from core.cost_tracker import CostPolicy
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

# Configure backend logging to file — Hermes-style
LOG_FILE = Path(__file__).resolve().parent.parent / "logs" / "backend.log"
LOG_FILE.parent.mkdir(exist_ok=True)

# Configure root logger to write to file
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(str(LOG_FILE), encoding="utf-8"),
        logging.StreamHandler(),  # Also log to console
    ],
)

logger = logging.getLogger("sovereign_ai")

# Store the polling task handle so we can cancel it on shutdown
_telegram_poll_task: asyncio.Task | None = None


# Rev3: Frontend error log models (defined at module level for Pydantic)
class ErrorLogItem(BaseModel):
    timestamp: str
    type: str
    message: str
    stack: Optional[str] = None
    filename: Optional[str] = None
    line: Optional[int] = None
    column: Optional[int] = None
    componentStack: Optional[str] = None
    componentName: Optional[str] = None


class ErrorLogRequest(BaseModel):
    # Rev3: max 200 items per batch
    errors: List[ErrorLogItem] = Field(default_factory=list, max_length=200)


# Rev2 L2 fix — validation constraints on thresholds and caps
class CostPolicyUpdate(BaseModel):
    """Request to update cost policy. Rev2 L2 fix — validated constraints."""

    daily_cap_usd: float | None = Field(None, ge=0)
    monthly_cap_usd: float | None = Field(None, ge=0)
    alert_threshold_pct: float | None = Field(None, ge=0, le=1)
    fallback_threshold_pct: float | None = Field(None, ge=0, le=1)
    fallback_model: str | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI app."""
    global _telegram_poll_task

    # Startup: run secrets audit and start Telegram polling
    try:
        _emitter = app.state._emitter
        audit = SecretsAudit(emitter=_emitter)
        await audit.audit()
    except Exception as e:
        logger.warning(
            f"Secrets audit failed: {e}"
        )  # Secrets audit failure should not crash the server
        pass

    # Initialize model registry if configured
    try:
        orchestrator = app.state.orchestrator
        if orchestrator and orchestrator.model_registry:
            try:
                await orchestrator.model_registry.initialize(system_profile=None)
                logger.info("Model registry initialized")
            except Exception as e:
                logger.error(f"Failed to initialize model registry: {e}")
    except Exception as e:
        logger.warning(f"Model registry initialization check failed: {e}")

    # Start Telegram polling if multi_channel_approval_gate is configured
    try:
        orchestrator = app.state.orchestrator
        if (
            orchestrator.multi_channel_approval_gate
            and orchestrator.multi_channel_approval_gate._telegram
        ):

            async def poll_loop():
                try:
                    while True:
                        await orchestrator.multi_channel_approval_gate.poll_telegram_responses()
                        await asyncio.sleep(5)
                except asyncio.CancelledError:
                    logger.info("Telegram polling task cancelled")
                    raise
                except Exception as e:
                    logger.error(f"Telegram polling error: {e}")

            _telegram_poll_task = asyncio.create_task(poll_loop())
            logger.info("Telegram polling task started")
    except Exception as e:
        logger.warning(f"Failed to start Telegram polling: {e}")

    yield

    # Shutdown: cancel the Telegram polling task
    if _telegram_poll_task and not _telegram_poll_task.done():
        _telegram_poll_task.cancel()
        try:
            await _telegram_poll_task
        except asyncio.CancelledError:
            pass
        logger.info("Telegram polling task cancelled")


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
    app.state.orchestrator = orchestrator
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

    # GET /api/workers — auth required
    @app.get("/api/workers")
    async def get_workers():
        """Return list of registered workers."""
        try:
            if hasattr(orchestrator, "worker_registry"):
                workers = orchestrator.worker_registry.list_workers()
                return {"workers": workers, "degraded_ratio": 0.0}
            # Fallback: return empty list
            return {"workers": [], "degraded_ratio": 0.0}
        except Exception as e:
            logger.warning(f"get_workers failed: {e}")
            return {"workers": [], "degraded_ratio": 0.0}

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

    # PUT /api/costs/policy — auth required (Plan 94)
    @app.put("/api/costs/policy")
    async def update_cost_policy(update: CostPolicyUpdate):
        """Update cost policy (caps, thresholds, fallback model)."""
        if (
            not orchestrator
            or not hasattr(orchestrator, "cost_tracker")
            or not orchestrator.cost_tracker
        ):
            raise HTTPException(status_code=503, detail="Cost tracker not configured")

        # Rev2 H2 fix — use get_policy() instead of _policy
        current = orchestrator.cost_tracker.get_policy()

        # Rev2 L2 fix — validate alert <= fallback
        new_alert = (
            update.alert_threshold_pct
            if update.alert_threshold_pct is not None
            else current.alert_threshold_pct
        )
        new_fallback = (
            update.fallback_threshold_pct
            if update.fallback_threshold_pct is not None
            else current.fallback_threshold_pct
        )
        if new_alert > new_fallback:
            raise HTTPException(
                status_code=422,
                detail=f"alert_threshold ({new_alert}) cannot exceed fallback_threshold ({new_fallback})",
            )

        # Apply updates (only non-None fields)
        new_policy = CostPolicy(
            daily_cap_usd=(
                update.daily_cap_usd
                if update.daily_cap_usd is not None
                else current.daily_cap_usd
            ),
            monthly_cap_usd=(
                update.monthly_cap_usd
                if update.monthly_cap_usd is not None
                else current.monthly_cap_usd
            ),
            alert_threshold_pct=new_alert,
            fallback_threshold_pct=new_fallback,
            fallback_model=(
                update.fallback_model
                if update.fallback_model is not None
                else current.fallback_model
            ),
            enable_traces=current.enable_traces,
        )

        orchestrator.cost_tracker.update_policy(new_policy)

        return {
            "status": "updated",
            "policy": {
                "daily_cap_usd": new_policy.daily_cap_usd,
                "monthly_cap_usd": new_policy.monthly_cap_usd,
                "alert_threshold_pct": new_policy.alert_threshold_pct,
                "fallback_threshold_pct": new_policy.fallback_threshold_pct,
                "fallback_model": new_policy.fallback_model,
            },
        }

    # GET /api/costs/policy — auth required (Plan 94)
    @app.get("/api/costs/policy")
    async def get_cost_policy():
        """Get current cost policy."""
        if (
            not orchestrator
            or not hasattr(orchestrator, "cost_tracker")
            or not orchestrator.cost_tracker
        ):
            raise HTTPException(status_code=503, detail="Cost tracker not configured")

        # Rev2 H2 fix — use get_policy() instead of _policy
        p = orchestrator.cost_tracker.get_policy()
        return {
            "daily_cap_usd": p.daily_cap_usd,
            "monthly_cap_usd": p.monthly_cap_usd,
            "alert_threshold_pct": p.alert_threshold_pct,
            "fallback_threshold_pct": p.fallback_threshold_pct,
            "fallback_model": p.fallback_model,
        }

    # GET /api/resources/monitor — auth required (Plan 94)
    @app.get("/api/resources/monitor")
    async def get_resource_monitor():
        """Get real-time system resource usage (CPU, RAM, VRAM, Disk).

        Rev2 H8 fix: Defensive accessors for SystemProfile fields.
        Rev2 H11 fix: Guard against empty storage list.
        Rev2 H12 fix: psutil fallback uses interval=None (non-blocking).
        """
        if (
            not orchestrator
            or not hasattr(orchestrator, "system_profiler")
            or not orchestrator.system_profiler
        ):
            # Fallback: return basic psutil stats if profiler not configured
            # Rev2 H12 fix — interval=None is non-blocking (returns 0.0 on first call, then real %)
            return {
                "cpu_percent": psutil.cpu_percent(interval=None),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage("/").percent,
                "gpu_percent": None,
                "gpu_memory_used_mb": None,
                "gpu_memory_total_mb": None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        profile = await orchestrator.system_profiler.refresh()

        # Rev2 H8 fix — handle both object and dict return types
        def _get(obj, attr, default=None):
            """Get attribute from object or key from dict."""
            if isinstance(obj, dict):
                return obj.get(attr, default)
            return getattr(obj, attr, default)

        cpu = _get(profile, "cpu", None)
        ram = _get(profile, "ram", None)
        storage = _get(profile, "storage", [])
        gpu = _get(profile, "gpu", None)

        # Rev2 H11 fix — guard against empty storage list
        disk_percent = 0.0
        if storage and len(storage) > 0:
            disk_percent = _get(storage[0], "percent", 0.0)

        return {
            "cpu_percent": _get(cpu, "percent", 0.0) if cpu else 0.0,
            "memory_percent": _get(ram, "percent", 0.0) if ram else 0.0,
            "disk_percent": disk_percent,
            "gpu_percent": _get(gpu, "percent", None) if gpu else None,
            "gpu_memory_used_mb": _get(gpu, "memory_used_mb", None) if gpu else None,
            "gpu_memory_total_mb": _get(gpu, "memory_total_mb", None) if gpu else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

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

    # GET /api/debates/{debate_id}/verdict — auth required
    @app.get("/api/debates/{debate_id}/verdict")
    async def get_verdict(debate_id: str):
        """Return judge verdict for a debate."""
        try:
            if not orchestrator.pemads_judge:
                return {"error": "PEMADS judge not configured"}, 404
            # Return last verdict for this debate (cached or re-judged)
            # For now, re-judge on demand
            # In production, cache verdicts
            return {"debate_id": debate_id, "verdict": "endpoint placeholder"}
        except Exception as e:
            logger.warning(f"get_verdict failed: {e}")
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

    # Include new API routers (stubs for Plans 91-94)
    app.include_router(models_router)
    app.include_router(workers_router)
    app.include_router(adapters_router)

    # Rev3: absolute path
    ERROR_LOG_FILE = (
        Path(__file__).resolve().parent.parent / "logs" / "frontend-errors.log"
    )

    @app.post("/api/errors/log")
    async def log_frontend_errors(error_request: dict):
        """Receive frontend error logs and append to local file."""

        # Rev3: async file I/O — don't block event loop
        def _write():
            ERROR_LOG_FILE.parent.mkdir(exist_ok=True)
            with open(ERROR_LOG_FILE, "a", encoding="utf-8") as f:
                errors = error_request.get("errors", [])
                for error in errors:
                    f.write(json.dumps(error, default=str) + "\n")

        await asyncio.to_thread(_write)
        return {"status": "ok", "received": len(error_request.get("errors", []))}

    @app.get("/api/errors/log")
    async def get_frontend_errors():
        """Retrieve frontend error log for upload to GLM."""

        # Rev3: async file read
        def _read():
            if not ERROR_LOG_FILE.exists():
                return []
            lines = ERROR_LOG_FILE.read_text(encoding="utf-8").strip().split("\n")
            errors = []
            for line in lines:
                if line.strip():
                    try:
                        errors.append(json.loads(line))
                    except Exception:
                        pass
            return errors

        errors = await asyncio.to_thread(_read)
        return {"errors": errors, "count": len(errors)}

    @app.delete("/api/errors/log")
    async def clear_frontend_errors():
        """Clear frontend error log after upload."""

        def _clear():
            if ERROR_LOG_FILE.exists():
                ERROR_LOG_FILE.unlink()

        await asyncio.to_thread(_clear)
        return {"status": "cleared"}

    @app.get("/api/logs")
    async def get_logs(
        source: str = "all",
        tail: int = 100,
        level: str | None = None,
    ):
        """Read log files from disk. Hermes-style backend log serving.

        Sources:
        - 'agent' — Python backend logs (if logging configured)
        - 'web' — frontend errors (logs/frontend-errors.log)
        - 'system' — system/trace events
        - 'all' — combined from all sources

        Returns last N lines, optionally filtered by level.
        """
        lines = []

        # Frontend errors log
        frontend_log = (
            Path(__file__).resolve().parent.parent / "logs" / "frontend-errors.log"
        )
        if frontend_log.exists() and source in ("web", "all"):
            try:
                content = frontend_log.read_text(encoding="utf-8", errors="replace")
                for line in content.strip().split("\n"):
                    if line.strip():
                        try:
                            entry = json.loads(line)
                            lines.append(
                                {
                                    "source": "web",
                                    "timestamp": entry.get("timestamp", ""),
                                    "level": "ERROR",
                                    "message": entry.get("message", ""),
                                    "stack": entry.get("stack", ""),
                                    "component": entry.get("componentName", ""),
                                }
                            )
                        except Exception:
                            lines.append(
                                {
                                    "source": "web",
                                    "timestamp": "",
                                    "level": "ERROR",
                                    "message": line,
                                    "stack": "",
                                    "component": "",
                                }
                            )
            except Exception as e:
                lines.append(
                    {
                        "source": "web",
                        "timestamp": "",
                        "level": "ERROR",
                        "message": f"Failed to read frontend log: {e}",
                        "stack": "",
                        "component": "",
                    }
                )

        # Backend Python logs — read from stderr capture or log file
        backend_log_paths = [
            Path(__file__).resolve().parent.parent / "logs" / "backend.log",
            Path(__file__).resolve().parent.parent / "logs" / "agent.log",
        ]

        if source in ("agent", "all"):
            for log_path in backend_log_paths:
                if log_path.exists():
                    try:
                        content = log_path.read_text(encoding="utf-8", errors="replace")
                        for line in content.strip().split("\n")[-tail:]:
                            if line.strip():
                                # Parse level from line (Python logging format: "2026-06-27 12:00:00,000 - module - LEVEL - message")
                                log_level = "INFO"
                                if "ERROR" in line or "CRITICAL" in line:
                                    log_level = "ERROR"
                                elif "WARNING" in line or "WARN" in line:
                                    log_level = "WARNING"
                                elif "DEBUG" in line:
                                    log_level = "DEBUG"

                                if level and log_level != level:
                                    continue

                                lines.append(
                                    {
                                        "source": "agent",
                                        "timestamp": (
                                            line[:23] if len(line) > 23 else ""
                                        ),
                                        "level": log_level,
                                        "message": line,
                                        "stack": "",
                                        "component": "",
                                    }
                                )
                    except Exception as e:
                        lines.append(
                            {
                                "source": "agent",
                                "timestamp": "",
                                "level": "ERROR",
                                "message": f"Failed to read backend log: {e}",
                                "stack": "",
                                "component": "",
                            }
                        )
                    break

            # Also capture recent stderr output if no log file exists
            if not any(p.exists() for p in backend_log_paths):
                lines.append(
                    {
                        "source": "agent",
                        "timestamp": "",
                        "level": "INFO",
                        "message": "No backend log file found. Configure Python logging to write to logs/backend.log",
                        "stack": "",
                        "component": "",
                    }
                )

        # Trace events from the emitter (if configured)
        if source in ("system", "all"):
            try:
                events = _emitter.get_events(limit=tail)
                for event in events:
                    event_level = getattr(event, "level", "INFO")
                    if hasattr(event_level, "value"):
                        event_level = event_level.value

                    if level and event_level != level:
                        continue

                    lines.append(
                        {
                            "source": "system",
                            "timestamp": str(getattr(event, "timestamp", "")),
                            "level": str(event_level),
                            "message": str(getattr(event, "message", str(event))),
                            "stack": "",
                            "component": str(getattr(event, "component", "")),
                        }
                    )
            except Exception as e:
                lines.append(
                    {
                        "source": "system",
                        "timestamp": "",
                        "level": "ERROR",
                        "message": f"Failed to read trace events: {e}",
                        "stack": "",
                        "component": "",
                    }
                )

        # Sort by timestamp (newest last, so tail works correctly)
        try:
            lines.sort(key=lambda x: x.get("timestamp", ""))
        except Exception:
            pass  # Keep insertion order if sorting fails

        # Apply tail limit
        result = lines[-tail:] if len(lines) > tail else lines

        return {"lines": result, "count": len(result), "source": source}

    @app.get("/api/logs/sources")
    async def get_log_sources():
        """List available log sources for the UI dropdown."""
        sources = []

        # Check frontend errors log
        frontend_log = (
            Path(__file__).resolve().parent.parent / "logs" / "frontend-errors.log"
        )
        if frontend_log.exists():
            size = frontend_log.stat().st_size
            line_count = sum(
                1 for _ in open(frontend_log, encoding="utf-8", errors="replace")
            )
            sources.append(
                {
                    "id": "web",
                    "label": "Frontend Errors",
                    "file": str(frontend_log),
                    "size_bytes": size,
                    "lines": line_count,
                }
            )
        else:
            sources.append(
                {
                    "id": "web",
                    "label": "Frontend Errors",
                    "file": "",
                    "size_bytes": 0,
                    "lines": 0,
                }
            )

        # Check backend logs
        backend_log_paths = [
            ("backend.log", "Backend Log"),
            ("agent.log", "Agent Log"),
        ]
        for filename, label in backend_log_paths:
            log_path = Path(__file__).resolve().parent.parent / "logs" / filename
            if log_path.exists():
                size = log_path.stat().st_size
                line_count = sum(
                    1 for _ in open(log_path, encoding="utf-8", errors="replace")
                )
                sources.append(
                    {
                        "id": "agent",
                        "label": label,
                        "file": str(log_path),
                        "size_bytes": size,
                        "lines": line_count,
                    }
                )

        # Trace events
        sources.append(
            {
                "id": "system",
                "label": "System Traces",
                "file": "",
                "size_bytes": 0,
                "lines": 0,
            }
        )

        return {"sources": sources}

    @app.delete("/api/logs")
    async def clear_logs(source: str = "web"):
        """Clear a log file."""
        if source == "web":
            log_path = (
                Path(__file__).resolve().parent.parent / "logs" / "frontend-errors.log"
            )
            if log_path.exists():
                log_path.unlink()
            return {"status": "cleared", "source": source}
        return {"status": "not_supported", "source": source}

    # Mount static files
    app.mount("/static", StaticFiles(directory="web/static"), name="static")

    # Serve vanilla JS frontend (replaces Next.js)
    _static_dir = Path(__file__).resolve().parent / "static"
    if _static_dir.exists():
        app.mount(
            "/", StaticFiles(directory=str(_static_dir), html=True), name="frontend"
        )

    return app


async def _windows_pty_websocket(websocket, winpty_module, emitter):
    """Windows PTY implementation using pywinpty. Separate function for clarity."""
    await websocket.accept()
    loop = asyncio.get_event_loop()

    # Create winpty PTY process
    pty_proc = winpty_module.PTY(cols=80, rows=24)
    pty_proc.spawn("cmd.exe")  # or bash.exe

    async def read_pty_output():
        try:
            while True:
                # winpty read is blocking — run in executor
                data = await loop.run_in_executor(None, lambda: pty_proc.read())
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
        # pywinpty cleanup - try multiple possible methods
        try:
            if hasattr(pty_proc, "terminate"):
                pty_proc.terminate()
            elif hasattr(pty_proc, "close"):
                pty_proc.close()
            elif hasattr(pty_proc, "kill"):
                pty_proc.kill()
        except Exception as e:
            logger.warning(f"Failed to cleanup PTY: {e}")
