"""Sovereign AI UI Backend — FastAPI stubs with mocked data.

This module serves mocked data per the UI brief's §5 API contract.
Real orchestrator integration is deferred to a follow-on plan.

Applying AR6-equivalent: backend/ may import from core/ only (when real
integration lands; this plan uses in-memory mocks, no core/ imports).
Applying AR17: auth middleware wraps ALL routes except /health.
Applying AR18: all except Exception blocks have inline comment + logging.
"""

import asyncio
import json
import logging
import os
import random
import time
import uuid
from typing import Any

from fastapi import (
    FastAPI,
    HTTPException,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

app = FastAPI(title="Sovereign AI UI Backend", version="0.1.0")

DEV_TOKEN = os.environ.get("SOVEREIGN_DEV_TOKEN")
if DEV_TOKEN is None:
    raise RuntimeError(
        "SOVEREIGN_DEV_TOKEN environment variable must be set. "
        "For dev: export SOVEREIGN_DEV_TOKEN=dev-token"
    )
# Type narrowing: DEV_TOKEN is now guaranteed to be str
assert isinstance(DEV_TOKEN, str)


class AgentStatus(BaseModel):
    """Matches web/static/api.js AgentStatus interface."""

    sessionId: str
    phase: str
    modelSlug: str
    uptime: int


class MemorySlot(BaseModel):
    """Matches web/static/api.js MemorySlot interface."""

    index: int
    key: str
    value: str
    activation: float
    lastWritten: int


class ToolCallEvent(BaseModel):
    """Matches web/static/api.js ToolCallEvent interface."""

    id: str
    tool: str
    status: str
    args: dict[str, Any]
    output: str | None = None
    durationMs: int | None = None


class TimelineSegment(BaseModel):
    """Matches web/static/api.js TimelineSegment interface."""

    phase: str
    startMs: int
    durationMs: int
    confidence: float


class Subagent(BaseModel):
    """Matches web/static/api.js Subagent interface."""

    id: str
    task: str
    status: str
    tokenCost: int


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """AR17: auth middleware wraps ALL routes except /health and /api/auth/login."""
    if request.url.path == "/health" or request.url.path == "/api/auth/login":
        return await call_next(request)

    auth = request.headers.get("Authorization", "")
    if auth == f"Bearer {DEV_TOKEN}":
        return await call_next(request)

    if request.cookies.get("sovereign_token") == DEV_TOKEN:
        return await call_next(request)

    raise HTTPException(status_code=401, detail="Unauthorized")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


@app.post("/api/auth/login")
async def login(response: Response):
    """Set auth cookie for SSE requests."""
    cookie_domain = os.environ.get("SOVEREIGN_COOKIE_DOMAIN")
    cookie_secure = os.environ.get("SOVEREIGN_COOKIE_SECURE", "false").lower() == "true"
    response.set_cookie(
        key="sovereign_token",
        value=DEV_TOKEN,  # type: ignore[arg-type]  # DEV_TOKEN is str after assert
        httponly=True,
        samesite="lax",
        secure=cookie_secure,
        domain=cookie_domain,
        max_age=3600,
    )
    return {"status": "ok"}


SESSION_ID = f"SES-{uuid.uuid4().hex[:4]}"
START_TIME = time.time()
MOCK_PHASES = ["planning", "acting", "reflecting", "idle"]
_phase_index = 0
MOCK_MODEL = "GLM-4.5 Flash"


def _next_phase() -> str:
    """Cycle through mock phases for each /api/status request."""
    global _phase_index
    phase = MOCK_PHASES[_phase_index % len(MOCK_PHASES)]
    _phase_index += 1
    return phase


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check — no auth required (AR17 exception)."""
    return {"status": "ok"}


@app.get("/api/status")
async def get_status() -> dict[str, Any]:
    """Agent phase, session ID, uptime, model slug."""
    return {
        "sessionId": SESSION_ID,
        "phase": _next_phase(),
        "uptime": int(time.time() - START_TIME),
        "modelSlug": MOCK_MODEL,
    }


@app.get("/api/memory/slots")
async def get_memory_slots() -> list[dict[str, Any]]:
    """All slots (mocked — 512 slots, random activation)."""
    return [
        {
            "index": i,
            "key": f"slot_{i}",
            "value": f"mock value {i}",
            "activation": random.random(),
            "lastWritten": int(time.time()) - random.randint(0, 3600),
        }
        for i in range(512)
    ]


@app.post("/api/memory/import")
async def import_memory(slots: list[dict[str, Any]]) -> dict[str, int]:
    """Bulk import slots from JSON (mocked — returns count)."""
    return {"imported": len(slots)}


@app.delete("/api/memory/slots/{slot_id}")
async def clear_slot(slot_id: int) -> dict[str, str]:
    """Clear one slot (mocked)."""
    return {"status": "cleared", "slot": str(slot_id)}


@app.get("/api/sessions")
async def get_sessions() -> list[dict[str, Any]]:
    """Session list with metadata (mocked)."""
    return [
        {
            "id": SESSION_ID,
            "startedAt": int(START_TIME),
            "phase": MOCK_PHASES[0],
            "toolCalls": 0,
        }
    ]


@app.get("/api/sessions/{session_id}/timeline")
async def get_timeline(session_id: str) -> list[dict[str, Any]]:
    """Phase segments for timeline (mocked)."""
    return [
        {
            "phase": "planning",
            "startMs": 0,
            "durationMs": 1500,
            "confidence": 0.85,
        },
        {
            "phase": "acting",
            "startMs": 1500,
            "durationMs": 3200,
            "confidence": 0.92,
        },
    ]


@app.get("/api/subagents")
async def get_subagents() -> list[dict[str, Any]]:
    """Active subagent list (mocked — empty)."""
    return []


@app.delete("/api/subagents/{subagent_id}")
async def kill_subagent(subagent_id: str) -> dict[str, str]:
    """Kill a subagent (mocked)."""
    return {"status": "killed", "subagent": subagent_id}


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


@app.get("/api/agent/reasoning")
async def reasoning_stream() -> StreamingResponse:
    """Streaming reasoning tokens (mocked)."""

    async def factory():
        tokens = ["Planning", " step", " 1", ":", " analyze", " input", "..."]
        while True:
            for token in tokens:
                yield {"token": token, "timestamp": int(time.time() * 1000)}

    return StreamingResponse(
        sse_generator(factory),
        media_type="text/event-stream",
    )


@app.get("/api/tools/stream")
async def tools_stream() -> StreamingResponse:
    """Tool call events (mocked)."""

    async def factory():
        while True:
            yield {
                "id": str(uuid.uuid4()),
                "tool": random.choice(["web_search", "memory_write", "code_exec"]),
                "status": "running",
                "args": {"query": "mock query"},
            }
            await asyncio.sleep(2)

    return StreamingResponse(
        sse_generator(factory),
        media_type="text/event-stream",
    )


@app.get("/api/memory/activations")
async def activations_stream() -> StreamingResponse:
    """Memory slot activation deltas (mocked)."""

    async def factory():
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


@app.websocket("/api/pty")
async def pty_websocket(websocket: WebSocket):
    """Bidirectional PTY stream for xterm.js (DEFERRED — stub only)."""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"[PTY stub] received: {data}")
    except WebSocketDisconnect:
        logger.info("PTY WebSocket disconnected")
    except Exception as e:
        logger.warning("PTY WebSocket error: %s", e)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
