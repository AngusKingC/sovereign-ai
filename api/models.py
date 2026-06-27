"""API router for model registry endpoints.
Wired to system.model_registry.ModelRegistry in Plan 91.
Rev2 H1 fix: static routes defined before parameterized routes.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/models", tags=["models"])


def get_model_registry(request: Request):
    """Dependency: return the orchestrator's model registry.
    Raises 503 if model registry is not configured.
    """
    orchestrator = request.app.state.orchestrator
    if (
        not orchestrator
        or not hasattr(orchestrator, "model_registry")
        or not orchestrator.model_registry
    ):
        raise HTTPException(status_code=503, detail="Model registry not configured")
    return orchestrator.model_registry


def get_model_acquisition(request: Request):
    """Dependency: return the orchestrator's model acquisition.
    Raises 503 if model acquisition is not configured.
    """
    orchestrator = request.app.state.orchestrator
    if (
        not orchestrator
        or not hasattr(orchestrator, "model_acquisition")
        or not orchestrator.model_acquisition
    ):
        raise HTTPException(status_code=503, detail="Model acquisition not configured")
    return orchestrator.model_acquisition


def get_approval_gate(request: Request):
    """Dependency: return the orchestrator's approval gate.
    Raises 503 if approval gate is not configured.
    """
    orchestrator = request.app.state.orchestrator
    if (
        not orchestrator
        or not hasattr(orchestrator, "approval_gate")
        or not orchestrator.approval_gate
    ):
        raise HTTPException(status_code=503, detail="Approval gate not configured")
    return orchestrator.approval_gate


def get_resource_manager(request: Request):
    """Dependency: return the orchestrator's resource manager.
    Raises 503 if resource manager is not configured.
    """
    orchestrator = request.app.state.orchestrator
    if (
        not orchestrator
        or not hasattr(orchestrator, "resource_manager")
        or not orchestrator.resource_manager
    ):
        raise HTTPException(status_code=503, detail="Resource manager not configured")
    return orchestrator.resource_manager


# Rev2 H13 fix — fields made optional with defaults to avoid ValidationError
# if ModelEntry doesn't populate them.
class ModelResponse(BaseModel):
    """API response model for a single model."""

    model_id: str
    name: str
    source: str = ""
    adapter_compatibility: list[str] = []
    task_tags: list[str] = []
    download_status: str = "unknown"
    downloaded_quantisation: str | None = None
    license: str = ""
    description: str = ""


def _entry_to_response(entry) -> ModelResponse:
    """Convert ModelEntry to API response. Uses getattr defaults for safety."""

    def _safe_attr(obj, attr, default=None):
        val = getattr(obj, attr, default)
        if hasattr(val, "value"):  # Enum
            return val.value
        return val if val is not None else default

    return ModelResponse(
        model_id=entry.model_id,
        name=entry.name,
        source=_safe_attr(entry, "source", ""),
        adapter_compatibility=getattr(entry, "adapter_compatibility", []),
        task_tags=getattr(entry, "task_tags", []),
        download_status=_safe_attr(entry, "download_status", "unknown"),
        downloaded_quantisation=getattr(entry, "downloaded_quantisation", None),
        license=getattr(entry, "license", ""),
        description=getattr(entry, "description", ""),
    )


# Rev2 H1 fix — /search MUST come before /{model_id}
@router.get("/search")
async def search_models(
    query: str = "", registry=Depends(get_model_registry)
) -> list[ModelResponse]:
    """Search models by name, tag, or adapter compatibility.
    Note: This searches the LOCAL registry only. HuggingFace/Ollama search
    is Plan 92 scope (Model Downloader).
    """
    all_models = await registry.list_all()
    if not query:
        return [_entry_to_response(e) for e in all_models]

    query_lower = query.lower()
    filtered = [
        e
        for e in all_models
        if query_lower in e.name.lower()
        or query_lower in e.model_id.lower()
        or any(query_lower in tag.lower() for tag in getattr(e, "task_tags", []))
        or any(
            query_lower in adapter.lower()
            for adapter in getattr(e, "adapter_compatibility", [])
        )
    ]
    return [_entry_to_response(e) for e in filtered]


# Rev2 H1 fix — /download and /download/{id}/status MUST come before /{model_id}
LARGE_DOWNLOAD_THRESHOLD_BYTES = 1_000_000_000  # 1 GB


@router.post("/download")
async def download_model(
    model_id: str,
    quantisation: str = "default",
    acquisition=Depends(get_model_acquisition),
    registry=Depends(get_model_registry),
    approval_gate=Depends(get_approval_gate),
    resource_manager=Depends(get_resource_manager),
) -> dict[str, Any]:
    """Download a model from HuggingFace or Ollama.

    Rev2 H3 fix: Uses approval gate for downloads >1GB (per gap analysis §9).
    Returns download_id for status polling.
    """
    from core.approval_gate import ApprovalActionType, ApprovalRequest
    from core.schemas import DownloadRequest, ModelSource

    # Check if already downloaded
    entry = await registry.get(model_id)
    if (
        entry
        and getattr(
            getattr(entry, "download_status", None),
            "value",
            str(getattr(entry, "download_status", "")),
        )
        == "downloaded"
    ):
        return {"status": "already_downloaded", "model_id": model_id}

    # Rev2 H3 fix — estimate size and require approval for large downloads
    estimated_size = await _estimate_download_size(entry, model_id)
    if estimated_size and estimated_size > LARGE_DOWNLOAD_THRESHOLD_BYTES:
        approval_request = ApprovalRequest(
            request_id=f"model-download-{model_id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            task_id=f"download-{model_id}",
            session_id="model-download",
            action_type=ApprovalActionType.MODEL_DOWNLOAD,
            action_description=f"Download model '{model_id}' ({estimated_size / 1e9:.1f} GB)",
            action_parameters={
                "model_id": model_id,
                "estimated_size_bytes": estimated_size,
            },
            risk_level="medium",
            reason_for_approval=f"Large model download: {estimated_size / 1e9:.1f} GB",
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=300),
        )
        response = await approval_gate.request_approval(approval_request)
        if not response.approved:
            return {
                "status": "approval_required",
                "request_id": approval_request.request_id,
            }

    # Initiate download (async — returns immediately with download_id)
    # Adaptation: construct DownloadRequest object per S0.5 verification
    download_request = DownloadRequest(
        model_id=model_id,
        source=(
            ModelSource.HUGGINGFACE if "huggingface" in model_id else ModelSource.OLLAMA
        ),
        quantisation=quantisation if quantisation != "default" else None,
        adapter_name="default",
        reason="User requested download via UI",
    )

    # Generate download_id and track in ModelAcquisition
    import uuid

    download_id = f"dl-{uuid.uuid4().hex[:8]}"

    # Initialize download status in ModelAcquisition
    acquisition._in_flight_downloads[download_id] = {
        "download_id": download_id,
        "model_id": model_id,
        "status": "initiated",
        "progress_pct": 0.0,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "error": None,
    }

    # Launch download as background task
    import asyncio

    async def _run_download():
        try:
            result = await acquisition.request_download(
                request=download_request,
                resource_manager=resource_manager,
                registry=registry,
            )
            status = acquisition._in_flight_downloads.get(download_id)
            if status:
                if result.success:
                    status["status"] = "complete"
                    status["progress_pct"] = 100.0
                else:
                    status["status"] = "failed"
                    status["error"] = result.error
        except Exception as e:
            status = acquisition._in_flight_downloads.get(download_id)
            if status:
                status["status"] = "failed"
                status["error"] = str(e)

    asyncio.create_task(_run_download())

    return {"download_id": download_id, "model_id": model_id, "status": "initiated"}


async def _estimate_download_size(entry, model_id: str) -> int | None:
    """Estimate download size from registry entry. Returns bytes or None if unknown."""
    if not entry:
        return None
    variants = getattr(entry, "quantisation_variants", [])
    if variants:
        # Take the first variant's size as estimate
        first = variants[0]
        return (
            getattr(first, "size_bytes", None)
            or getattr(first, "size_mb", None)
            and getattr(first, "size_mb", 0) * 1_000_000
        )
    return None


@router.get("/download/{download_id}/status")
async def get_download_status(
    download_id: str,
    acquisition=Depends(get_model_acquisition),
) -> dict[str, Any]:
    """Poll download progress by download_id."""
    status = await acquisition.get_download_status(download_id)
    if not status:
        raise HTTPException(
            status_code=404, detail=f"Download '{download_id}' not found"
        )
    return status


# Rev2 H1 fix — /{model_id} MUST come AFTER all static routes
@router.get("")
async def list_models(registry=Depends(get_model_registry)) -> list[ModelResponse]:
    """List all registered models."""
    entries = await registry.list_all()
    return [_entry_to_response(e) for e in entries]


@router.get("/{model_id}")
async def get_model(
    model_id: str, registry=Depends(get_model_registry)
) -> ModelResponse:
    """Get model details by ID."""
    entry = await registry.get(model_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")
    return _entry_to_response(entry)
