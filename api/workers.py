"""API router for worker CRUD endpoints.
Wired to core.worker_factory.WorkerFactory in Plan 93.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/workers", tags=["workers"])


def get_worker_factory(request: Request):
    """Dependency to get worker factory from app state."""
    orchestrator = request.app.state.orchestrator
    if (
        not orchestrator
        or not hasattr(orchestrator, "worker_factory")
        or not orchestrator.worker_factory
    ):
        raise HTTPException(status_code=503, detail="Worker factory not configured")
    return orchestrator.worker_factory


class CreateWorkerRequest(BaseModel):
    """Request to create a worker from natural language description."""

    description: str
    task_intent: str = ""  # Optional: the task the worker will handle


class WorkerProfileResponse(BaseModel):
    """API response model for a worker profile."""

    worker_id: str
    worker_type: str
    name: str
    description: str
    purpose: str
    capabilities: list[str]
    complexity_min: float
    complexity_max: float
    preferred_complexity: float
    depth_preference: float
    speculation_tolerance: float
    source_skepticism: float
    verbosity: float
    standing_instructions: list[str]
    preferred_model: str
    preferred_models: list[str]
    escalation_threshold: float
    tasks_completed: int
    avg_confidence: float
    performance_score: float
    active_tasks: int
    status: str


class UpdateWorkerRequest(BaseModel):
    """Request to update worker configuration."""

    complexity_min: float | None = None
    complexity_max: float | None = None
    preferred_complexity: float | None = None
    depth_preference: float | None = None
    speculation_tolerance: float | None = None
    source_skepticism: float | None = None
    verbosity: float | None = None
    standing_instructions: list[str] | None = None
    preferred_model: str | None = None
    preferred_models: list[str] | None = None
    escalation_threshold: float | None = None


def _profile_to_response(profile) -> WorkerProfileResponse:
    """Convert WorkerProfile to API response with defaults for extended fields."""
    status_val = getattr(profile, "status", None)
    if status_val is not None and hasattr(status_val, "value"):
        status_str = status_val.value
    else:
        status_str = str(status_val) if status_val else "active"

    return WorkerProfileResponse(
        worker_id=profile.worker_id,
        worker_type=profile.worker_type,
        name=getattr(profile, "name", profile.worker_id),
        description=getattr(profile, "description", ""),
        purpose=getattr(profile, "purpose", ""),
        capabilities=profile.capabilities,
        complexity_min=getattr(profile, "complexity_min", 0.0),
        complexity_max=getattr(profile, "complexity_max", 1.0),
        preferred_complexity=profile.preferred_complexity,
        depth_preference=profile.depth_preference,
        speculation_tolerance=profile.speculation_tolerance,
        source_skepticism=profile.source_skepticism,
        verbosity=profile.verbosity,
        standing_instructions=profile.standing_instructions,
        preferred_model=profile.preferred_model,
        preferred_models=getattr(profile, "preferred_models", []),
        escalation_threshold=profile.escalation_threshold,
        tasks_completed=profile.tasks_completed,
        avg_confidence=profile.avg_confidence,
        performance_score=getattr(profile, "performance_score", 0.0),
        active_tasks=getattr(profile, "active_tasks", 0),
        status=status_str,
    )


@router.post("/create")
async def create_worker(
    request: CreateWorkerRequest,
    factory=Depends(get_worker_factory),
) -> WorkerProfileResponse:
    """Create a worker from natural language description."""
    from datetime import datetime, timezone
    from uuid import uuid4

    from core.schemas import Task, TaskPriority, TaskStatus

    task = Task(
        task_id=uuid4(),
        intent=request.task_intent or request.description,
        complexity_score=0.5,
        priority=TaskPriority.NORMAL,
        status=TaskStatus.RECEIVED,
        created_at=datetime.now(timezone.utc),
    )
    try:
        worker = await factory.create_worker(request.description, task)
        # Return the profile (worker may have a .profile attribute or be the profile itself)
        profile = getattr(worker, "profile", worker)
        return _profile_to_response(profile)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Worker creation failed: {e}")


@router.get("")
async def list_workers(
    factory=Depends(get_worker_factory),
) -> list[WorkerProfileResponse]:
    """List all registered workers."""
    profiles = await factory.list_workers()
    return [_profile_to_response(p) for p in profiles]


@router.get("/{worker_id}")
async def get_worker(
    worker_id: str, factory=Depends(get_worker_factory)
) -> WorkerProfileResponse:
    """Get worker details by ID."""
    profiles = await factory.list_workers()
    for p in profiles:
        if p.worker_id == worker_id:
            return _profile_to_response(p)
    raise HTTPException(status_code=404, detail=f"Worker '{worker_id}' not found")


@router.put("/{worker_id}")
async def update_worker(
    worker_id: str,
    request: UpdateWorkerRequest,
    factory=Depends(get_worker_factory),
) -> WorkerProfileResponse:
    """Update worker configuration."""
    profiles = await factory.list_workers()
    profile = next((p for p in profiles if p.worker_id == worker_id), None)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Worker '{worker_id}' not found")

    # Use model_dump() for Pydantic v2 (was .dict() which raises AttributeError in v2)
    try:
        update_data = request.model_dump(exclude_none=True)
    except AttributeError:
        # Fallback for Pydantic v1
        update_data = request.dict(exclude_none=True)

    for field, value in update_data.items():
        setattr(profile, field, value)

    # Persist the updated profile
    if hasattr(factory, "persistence") and factory.persistence:
        from core.schemas import WorkerStatus
        from core.worker_factory import DynamicWorkerProfile

        # Convert to DynamicWorkerProfile for persistence if needed
        if not isinstance(profile, DynamicWorkerProfile):
            dynamic_profile = DynamicWorkerProfile(
                worker_id=profile.worker_id,
                worker_type=profile.worker_type,
                name=getattr(profile, "name", profile.worker_id),
                description=getattr(profile, "description", ""),
                purpose=getattr(profile, "purpose", ""),
                capabilities=profile.capabilities,
                complexity_min=getattr(profile, "complexity_min", 0.0),
                complexity_max=getattr(profile, "complexity_max", 1.0),
                preferred_complexity=profile.preferred_complexity,
                depth_preference=profile.depth_preference,
                speculation_tolerance=profile.speculation_tolerance,
                source_skepticism=profile.source_skepticism,
                verbosity=profile.verbosity,
                standing_instructions=profile.standing_instructions,
                preferred_model=profile.preferred_model,
                preferred_models=getattr(profile, "preferred_models", []),
                escalation_threshold=profile.escalation_threshold,
                tasks_completed=profile.tasks_completed,
                avg_confidence=profile.avg_confidence,
                performance_score=getattr(profile, "performance_score", 0.0),
                active_tasks=getattr(profile, "active_tasks", 0),
                status=getattr(profile, "status", WorkerStatus.ACTIVE),
            )
            await factory.persistence.save(dynamic_profile)
        else:
            await factory.persistence.save(profile)

    return _profile_to_response(profile)


@router.delete("/{worker_id}")
async def delete_worker(
    worker_id: str, factory=Depends(get_worker_factory)
) -> dict[str, Any]:
    """Delete/deregister a worker."""
    try:
        await factory.deregister_worker(worker_id)
        return {"status": "deleted", "worker_id": worker_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Worker deletion failed: {e}")
