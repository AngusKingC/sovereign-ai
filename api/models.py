"""API router for model registry endpoints.
Wired to system.model_registry.ModelRegistry in Plan 91.
Rev2 H1 fix: static routes defined before parameterized routes.
"""

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
