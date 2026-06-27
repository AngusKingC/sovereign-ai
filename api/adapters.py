"""API router for adapter fallback chain management.
Rev2 H5 fix: Uses Pydantic model for request body.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/adapters", tags=["adapters"])


# Rev2 H5 fix — Pydantic model for request body
class FallbackChainRequest(BaseModel):
    """Request to set the fallback chain."""

    chain: list[str]


def get_orchestrator(request: Request):
    """Dependency: return the orchestrator."""
    return request.app.state.orchestrator


@router.get("/fallback")
async def get_fallback_chain(orchestrator=Depends(get_orchestrator)) -> dict[str, Any]:
    """Get the current adapter fallback chain."""
    if not hasattr(orchestrator, "fallback_chain") or not orchestrator.fallback_chain:
        return {"chain": []}
    return {
        "chain": [
            a.model_name if hasattr(a, "model_name") else str(a)
            for a in orchestrator.fallback_chain
        ]
    }


@router.put("/fallback")
async def set_fallback_chain(
    request: FallbackChainRequest,  # Rev2 H5 fix — Pydantic model, not bare list
    orchestrator=Depends(get_orchestrator),
) -> dict[str, Any]:
    """Set the adapter fallback chain by adapter name.

    Accepts a JSON body: {"chain": ["ollama", "openai", "anthropic"]}
    Resolves names to adapter instances via cli/adapter_factory.py.
    """
    from cli.adapter_factory import (  # Rev2 H7 fix — verify import per S0.5
        create_adapter,
    )

    resolved = []
    for name in request.chain:
        try:
            # Plan 92 S2 adaptation: use "default" as model_name placeholder
            adapter = create_adapter(name, model_name="default")
            resolved.append(adapter)
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Failed to create adapter '{name}': {e}"
            )

    orchestrator.fallback_chain = resolved
    return {"chain": request.chain, "resolved_count": len(resolved)}


@router.get("/available")
async def list_available_adapters() -> dict[str, Any]:
    """List all adapter types that can be created."""
    # Rev2 H7 fix — verify ADAPTER_TYPES exists per S0.5
    try:
        from cli.adapter_factory import ADAPTER_TYPES

        return {"adapters": list(ADAPTER_TYPES)}
    except ImportError:
        # Fallback: hardcoded list of known adapters
        return {
            "adapters": [
                "ollama",
                "openai",
                "anthropic",
                "gemini",
                "groq",
                "mistral",
                "cohere",
                "together",
                "deepseek",
                "lm_studio",
                "llama_cpp",
                "prism_llama",
                "huggingface",
                "mcp",
            ]
        }
