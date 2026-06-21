"""
HuggingFace Inference cloud LLM adapter.

Single responsibility: Handle interactions with HuggingFace Inference API,
providing access to thousands of open-source models.
"""

import time
from typing import TYPE_CHECKING

import httpx

from core.schemas import Message
from core.worker_base import LLMAdapter, LLMResponse
from core.observability import (
    TraceEventType,
    TraceComponent,
    TraceLevel,
    TraceEvent,
    TraceEmitter,
    MemoryTraceEmitter,
)

if TYPE_CHECKING:
    pass
else:
    pass


class HuggingFaceAdapter(LLMAdapter):
    """HuggingFace Inference adapter for accessing thousands of open-source models."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = "meta-llama/Meta-Llama-3-70B-Instruct",
        temperature: float = 0.1,
        emitter: TraceEmitter | None = None,
    ) -> None:
        """Initialize the HuggingFace adapter with API configuration."""
        self.api_key = api_key
        self._model_name = model_name
        self.temperature = temperature
        self._client: httpx.AsyncClient | None = None
        self.base_url = "https://api-inference.huggingface.co/models"
        self._emitter = emitter or MemoryTraceEmitter()

    def _ensure_client(self) -> None:
        """Ensure HTTP client is initialized."""
        if self._client is None:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._client = httpx.AsyncClient(headers=headers, timeout=60.0)

    def _messages_to_hf_format(self, messages: list[Message]) -> str:
        """Convert messages to HuggingFace format (single string)."""
        prompt_parts = []
        for msg in messages:
            if msg.role.value == "system":
                prompt_parts.append(f"System: {msg.content}")
            elif msg.role.value == "user":
                prompt_parts.append(f"User: {msg.content}")
            elif msg.role.value == "assistant":
                prompt_parts.append(f"Assistant: {msg.content}")
        return "\n".join(prompt_parts)

    async def generate(
        self,
        messages: list[Message],
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        """
        Generate a response from HuggingFace Inference API.

        Uses HuggingFace's serverless inference for thousands of models.
        """
        start_time = time.perf_counter()
        prompt_length = sum(len(msg.content) for msg in messages)

        try:
            # Emit adapter call start event
            try:
                event = TraceEvent(
                    event_type=TraceEventType.ADAPTER_CALL,
                    component=TraceComponent.ADAPTER,
                    message="HuggingFace adapter generation started",
                    level=TraceLevel.INFO,
                    data={
                        "adapter_name": "huggingface",
                        "model_name": self._model_name,
                        "prompt_length": prompt_length,
                        "temperature": temperature or self.temperature,
                    },
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception as e:
                await self._emitter.emit(TraceEvent(
                    event_type=TraceEventType.ADAPTER_ERROR,
                    component=TraceComponent.ADAPTER,
                    message="Trace emission failed in HuggingFace adapter call start",
                    level=TraceLevel.WARNING,
                    data={"error": str(e)},
                    duration_ms=0,
                ))
                pass

            self._ensure_client()

            if self._client is None:
                raise RuntimeError("HuggingFace client failed to initialize")

            prompt = self._messages_to_hf_format(messages)

            response = await self._client.post(
                f"{self.base_url}/{self._model_name}",
                json={
                    "inputs": prompt,
                    "parameters": {
                        "temperature": temperature or self.temperature,
                        "max_new_tokens": max_tokens,
                    },
                },
            )

            response.raise_for_status()
            data = response.json()

            duration_ms = int((time.perf_counter() - start_time) * 1000)

            # Handle different response formats from HF
            content = ""
            if isinstance(data, list) and len(data) > 0:
                content = data[0].get("generated_text", "")
            elif isinstance(data, dict):
                content = data.get("generated_text", "")

            response_length = len(content)

            # Emit adapter response event
            try:
                event = TraceEvent(
                    event_type=TraceEventType.ADAPTER_RESPONSE,
                    component=TraceComponent.ADAPTER,
                    message="HuggingFace adapter generation completed",
                    level=TraceLevel.INFO,
                    data={
                        "adapter_name": "huggingface",
                        "model_name": self._model_name,
                        "prompt_length": prompt_length,
                        "response_length": response_length,
                        "tokens_used": 0,
                    },
                    duration_ms=duration_ms,
                )
                await self._emitter.emit(event)
            except Exception as e:
                await self._emitter.emit(TraceEvent(
                    event_type=TraceEventType.ADAPTER_ERROR,
                    component=TraceComponent.ADAPTER,
                    message="Trace emission failed in HuggingFace adapter response",
                    level=TraceLevel.WARNING,
                    data={"error": str(e)},
                    duration_ms=0,
                ))
                pass

            return LLMResponse(
                content=content,
                raw={"model": self._model_name, "usage": {}},
                model=self._model_name,
                tokens_used=0,  # HF doesn't always return token counts
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            # Emit error event (wrapped to avoid crashing main path)
            try:
                event = TraceEvent(
                    event_type=TraceEventType.ADAPTER_ERROR,
                    component=TraceComponent.ADAPTER,
                    message="HuggingFace adapter generation failed",
                    level=TraceLevel.ERROR,
                    data={
                        "adapter_name": "huggingface",
                        "model_name": self._model_name,
                        "prompt_length": prompt_length,
                    },
                    duration_ms=duration_ms,
                    error_type=type(e).__name__,
                    error_message=str(e),
                )
                await self._emitter.emit(event)
            except Exception as inner_e:
                await self._emitter.emit(TraceEvent(
                    event_type=TraceEventType.ADAPTER_ERROR,
                    component=TraceComponent.ADAPTER,
                    message="Trace emission failed in HuggingFace adapter error handler",
                    level=TraceLevel.WARNING,
                    data={"error": str(inner_e)},
                    duration_ms=0,
                ))
                pass  # Trace failure should not crash main path
            raise RuntimeError(f"HuggingFace generation failed: {e}")

    async def health_check(self) -> bool:
        """Check if HuggingFace API is accessible."""
        try:
            self._ensure_client()

            if self._client is None:
                return False

            response = await self._client.post(
                f"{self.base_url}/{self._model_name}",
                json={"inputs": "test", "parameters": {"max_new_tokens": 1}},
            )
            return response.status_code == 200
        except Exception as e:
            await self._emitter.emit(TraceEvent(
                event_type=TraceEventType.ADAPTER_ERROR,
                component=TraceComponent.ADAPTER,
                message="HuggingFace health check failed",
                level=TraceLevel.WARNING,
                data={"error": str(e)},
                duration_ms=0,
            ))
            return False

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def model_name(self) -> str:
        """Name of the model this adapter uses."""
        return self._model_name

    @property
    def is_local(self) -> bool:
        """Whether this adapter uses a local model."""
        return False

    @property
    def cost_per_token(self) -> float:
        """Cost per token for this model (HF: varies by model, often free tier available)."""
        return 0.0  # HF often has free tier or very low cost

