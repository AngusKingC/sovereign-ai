"""API router for model registry endpoints.
Stubs created in Plan 90 scan. Full implementation in Plan 91-92.
"""

from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("")
async def list_models() -> list[dict[str, Any]]:
    """List all registered models. Stub — returns empty list.
    TODO: Wire to system.model_registry.ModelRegistry.list_all() in Plan 91.
    """
    return []


@router.get("/search")
async def search_models(query: str = "") -> list[dict[str, Any]]:
    """Search HuggingFace/Ollama catalogues. Stub — returns empty list.
    TODO: Wire to system.model_acquisition in Plan 91.
    """
    return []


@router.get("/{model_id}")
async def get_model(model_id: str) -> dict[str, Any]:
    """Get model details by ID. Stub — returns 404.
    TODO: Wire to system.model_registry.ModelRegistry.get() in Plan 91.
    """
    raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found (stub)")
