"""
LM Studio adapter for local LLM inference.

Single responsibility: Provide local LLM inference using LM Studio's
local server API, enabling hardware control through LM Studio's GUI.
"""

import time
from typing import TYPE_CHECKING, Any

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
    from pydantic import BaseModel
else:
    from pydantic import BaseModel


class LMStudioAdapter(LLMAdapter):
    """LM Studio adapter using local server API for hardware control."""

    def __init__(
        self,
        base_url: str = "http://localhost:1234/v1",
        model_name: str = "local-model",
        temperature: float = 0.1,
        emitter: TraceEmitter | None = None,
    ) -> None:
        """Initialize the LM Studio adapter with server configuration."""
        self.base_url = base_url
        self._model_name = model_name
        self.temperature = temperature
        self._client: httpx.AsyncClient | None = None
        self._emitter = emitter or MemoryTraceEmitter()

    def _ensure_client(self) -> None:
        """Ensure HTTP client is initialized."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0)

    def _messages_to_openai_format(self, messages: list[Message]) -> list[dict[str, str]]:
        """Convert messages to OpenAI-compatible format."""
        return [
            {"role": msg.role.value, "content": msg.content}
            for msg in messages
        ]

    async def generate(
        self,
        messages: list[Message],
        temperature: float = 0.1,
        max_tokens: int = 2048,
        structured_output: type[BaseModel] | None = None,
    ) -> LLMResponse:
        """
        Generate a response from LM Studio local server.

        Uses OpenAI-compatible API format for communication.
        """
        start_time = time.perf_counter()
        prompt_length = sum(len(msg.content) for msg in messages)

        try:
            # Emit adapter call start event
            try:
                event = TraceEvent(
                    event_type=TraceEventType.ADAPTER_CALL,
                    component=TraceComponent.ADAPTER,
                    message="LM Studio adapter generation started",
                    level=TraceLevel.INFO,
                    data={
                        "adapter_name": "lm_studio",
                        "model_name": self._model_name,
                        "prompt_length": prompt_length,
                        "temperature": temperature or self.temperature,
                    },
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception:
                pass

            self._ensure_client()

            if self._client is None:
                raise RuntimeError("HTTP client failed to initialize")

            openai_messages = self._messages_to_openai_format(messages)

            response = await self._client.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": self.model_name,
                    "messages": openai_messages,
                    "temperature": temperature or self.temperature,
                    "max_tokens": max_tokens,
                },
            )

            response.raise_for_status()
            data = response.json()

            duration_ms = int((time.perf_counter() - start_time) * 1000)
            response_length = len(data["choices"][0]["message"]["content"])

            # Emit adapter response event
            try:
                event = TraceEvent(
                    event_type=TraceEventType.ADAPTER_RESPONSE,
                    component=TraceComponent.ADAPTER,
                    message="LM Studio adapter generation completed",
                    level=TraceLevel.INFO,
                    data={
                        "adapter_name": "lm_studio",
                        "model_name": self._model_name,
                        "prompt_length": prompt_length,
                        "response_length": response_length,
                        "tokens_used": data.get("usage", {}).get("total_tokens", 0),
                    },
                    duration_ms=duration_ms,
                )
                await self._emitter.emit(event)
            except Exception:
                pass

            return LLMResponse(
                content=data["choices"][0]["message"]["content"],
                raw={"model": self.model_name, "usage": data.get("usage", {})},
                model=self.model_name,
                tokens_used=data.get("usage", {}).get("total_tokens", 0),
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            # Emit error event (wrapped to avoid crashing main path)
            try:
                event = TraceEvent(
                    event_type=TraceEventType.ADAPTER_ERROR,
                    component=TraceComponent.ADAPTER,
                    message="LM Studio adapter generation failed",
                    level=TraceLevel.ERROR,
                    data={
                        "adapter_name": "lm_studio",
                        "model_name": self._model_name,
                        "prompt_length": prompt_length,
                    },
                    duration_ms=duration_ms,
                    error_type=type(e).__name__,
                    error_message=str(e),
                )
                await self._emitter.emit(event)
            except Exception:
                pass  # Trace failure should not crash main path
            raise RuntimeError(f"LM Studio generation failed: {e}")

    async def health_check(self) -> bool:
        """Check if LM Studio server is healthy and accessible."""
        try:
            self._ensure_client()

            if self._client is None:
                return False

            response = await self._client.get(f"{self.base_url}/models")
            return response.status_code == 200
        except Exception:
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
        return True

    @property
    def cost_per_token(self) -> float:
        """Cost per token for this model (0 for local models)."""
        return 0.0

