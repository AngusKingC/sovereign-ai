"""API router for worker CRUD endpoints.
Stubs created in Plan 90 scan. Full implementation in Plan 93-94.
"""

from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/workers", tags=["workers"])


@router.post("/create")
async def create_worker(description: str) -> dict[str, Any]:
    """Create a worker from natural language description. Stub — returns 501.
    TODO: Wire to core.worker_factory.WorkerFactory.create_worker() in Plan 93.
    """
    raise HTTPException(
        status_code=501, detail="Worker creation not yet implemented (stub)"
    )


@router.put("/{worker_id}")
async def update_worker(worker_id: str, config: dict) -> dict[str, Any]:
    """Update worker configuration. Stub — returns 501.
    TODO: Wire to core.worker_factory in Plan 94.
    """
    raise HTTPException(
        status_code=501, detail="Worker update not yet implemented (stub)"
    )


@router.delete("/{worker_id}")
async def delete_worker(worker_id: str) -> dict[str, Any]:
    """Delete/deregister a worker. Stub — returns 501.
    TODO: Wire to core.worker_factory.WorkerFactory.deregister_worker() in Plan 94.
    """
    raise HTTPException(
        status_code=501, detail="Worker deletion not yet implemented (stub)"
    )
