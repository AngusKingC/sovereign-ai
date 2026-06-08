"""
Adapter factory for CLI layer.

Single responsibility: Construct LLM adapter instances based on configuration.
This is the only place outside the adapters layer where adapter imports are allowed.
"""

from typing import Any

from core.worker_base import LLMAdapter
from workers.ollama_worker import OllamaWorker


def create_adapter(
    adapter_name: str,
    model_name: str,
    base_url: str | None = None,
) -> LLMAdapter:
    """Create an LLM adapter instance based on adapter_name.
    
    Args:
        adapter_name: Name of the adapter to create (e.g., "ollama", "lm_studio")
        model_name: Name of the model to use
        base_url: Optional base URL for the adapter (defaults to adapter-specific default)
    
    Returns:
        An instance of the requested adapter satisfying LLMAdapter Protocol
    
    Raises:
        ValueError: If adapter_name is unknown
    """
    adapter_name_lower = adapter_name.lower()
    
    if adapter_name_lower == "ollama":
        from adapters.ollama import OllamaAdapter
        return OllamaAdapter(
            base_url=base_url or "http://localhost:11434",
            model_name=model_name,
        )
    elif adapter_name_lower == "lm_studio":
        from adapters.lm_studio import LMStudioAdapter
        return LMStudioAdapter(
            base_url=base_url or "http://localhost:1234",
            model_name=model_name,
        )
    else:
        available = ["ollama", "lm_studio"]
        raise ValueError(
            f"Unknown adapter: {adapter_name}. Available adapters: {', '.join(available)}"
        )


def create_worker(
    adapter_name: str,
    model_name: str,
    base_url: str | None = None,
    memory_router: Any = None,
) -> OllamaWorker:
    """Create a worker instance wrapping an adapter.
    
    Args:
        adapter_name: Name of the adapter to create (e.g., "ollama", "lm_studio")
        model_name: Name of the model to use
        base_url: Optional base URL for the adapter (defaults to adapter-specific default)
        memory_router: Optional memory router for the worker
    
    Returns:
        An OllamaWorker instance wrapping the requested adapter
    
    Raises:
        ValueError: If adapter_name is unknown
    """
    adapter = create_adapter(adapter_name, model_name, base_url)
    return OllamaWorker(adapter=adapter, memory_router=memory_router)

