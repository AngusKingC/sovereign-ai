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
    **kwargs: Any,
) -> LLMAdapter:
    """Create an LLM adapter instance based on adapter_name.

    Args:
        adapter_name: Name of the adapter to create (e.g., "ollama", "lm_studio")
        model_name: Name of the model to use
        base_url: Optional base URL for the adapter (defaults to adapter-specific default)
        **kwargs: Adapter-specific configuration (e.g., port, n_gpu_layers for prism_llama)

    Returns:
        An instance of the requested adapter satisfying LLMAdapter Protocol

    Raises:
        ValueError: If adapter_name is unknown
    """
    import os

    adapter_name_lower = adapter_name.lower()

    # NOTE: Cloud adapters (openai, cohere, groq, anthropic) raise ValueError
    # if their API key env var is not set. The TUI's /adapter command (caller)
    # should catch this ValueError and display a user-friendly message like
    # "OPENAI_API_KEY not set — get one at https://platform.openai.com/api-keys"
    # instead of crashing with a traceback. This TUI-level handler is deferred
    # to Plan 41 (broad-except audit will address the /adapter call site).
    # See handoff "What's broken" section for the /adapter ValueError bug.

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
    elif adapter_name_lower == "openai":
        from adapters.openai import OpenAIAdapter

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        return OpenAIAdapter(api_key=api_key, model_name=model_name)
    elif adapter_name_lower == "cohere":
        from adapters.cohere import CohereAdapter

        api_key = os.getenv("COHERE_API_KEY")
        if not api_key:
            raise ValueError("COHERE_API_KEY environment variable not set")
        return CohereAdapter(api_key=api_key, model_name=model_name)
    elif adapter_name_lower == "groq":
        from adapters.groq import GroqAdapter

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable not set")
        return GroqAdapter(api_key=api_key, model_name=model_name)
    elif adapter_name_lower == "anthropic":
        from adapters.anthropic import AnthropicAdapter

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        return AnthropicAdapter(api_key=api_key, model_name=model_name)
    elif adapter_name_lower == "mistral":
        from adapters.mistral import MistralAdapter

        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            raise ValueError("MISTRAL_API_KEY environment variable not set")
        return MistralAdapter(api_key=api_key, model_name=model_name)
    elif adapter_name_lower == "together":
        from adapters.together import TogetherAdapter

        api_key = os.getenv("TOGETHER_API_KEY")
        if not api_key:
            raise ValueError("TOGETHER_API_KEY environment variable not set")
        return TogetherAdapter(api_key=api_key, model_name=model_name)
    elif adapter_name_lower == "deepseek":
        from adapters.deepseek import DeepSeekAdapter

        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY environment variable not set")
        return DeepSeekAdapter(api_key=api_key, model_name=model_name)
    elif adapter_name_lower == "huggingface":
        from adapters.huggingface import HuggingFaceAdapter

        api_key = os.getenv("HUGGINGFACE_API_KEY") or os.getenv("HF_TOKEN")
        if not api_key:
            raise ValueError(
                "HUGGINGFACE_API_KEY (or HF_TOKEN) environment variable not set"
            )
        return HuggingFaceAdapter(api_key=api_key, model_name=model_name)
    elif adapter_name_lower == "prism_llama":
        from adapters.prism_llama import PrismLlamaAdapter

        return PrismLlamaAdapter(
            model_path=model_name,  # model_name = path to .gguf file
            binary_path=base_url or kwargs.get("binary_path", "llama-server"),
            port=kwargs.get("port", 8081),
            n_gpu_layers=kwargs.get("n_gpu_layers", -1),
            n_threads=kwargs.get("n_threads", 4),
            context_size=kwargs.get("context_size", 4096),
        )
    else:
        available = [
            "ollama",
            "lm_studio",
            "openai",
            "cohere",
            "groq",
            "anthropic",
            "mistral",
            "together",
            "deepseek",
            "huggingface",
            "prism_llama",
        ]
        raise ValueError(
            f"Unknown adapter: {adapter_name}. Available adapters: {', '.join(available)}"
        )


def create_worker(
    adapter_name: str,
    model_name: str,
    base_url: str | None = None,
    memory_router: Any = None,
    **kwargs: Any,
) -> OllamaWorker:
    """Create a worker instance wrapping an adapter.

    Args:
        adapter_name: Name of the adapter to create (e.g., "ollama", "lm_studio")
        model_name: Name of the model to use
        base_url: Optional base URL for the adapter (defaults to adapter-specific default)
        memory_router: Optional memory router for the worker
        **kwargs: Adapter-specific configuration (e.g., port, n_gpu_layers for prism_llama)

    Returns:
        An OllamaWorker instance wrapping the requested adapter

    Raises:
        ValueError: If adapter_name is unknown
    """
    adapter = create_adapter(adapter_name, model_name, base_url, **kwargs)
    return OllamaWorker(adapter=adapter, memory_router=memory_router)
