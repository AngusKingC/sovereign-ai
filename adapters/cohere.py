"""
Cohere cloud LLM adapter.

Single responsibility: Handle interactions with Cohere's API,
providing enterprise-focused language models.
"""

import time
from typing import TYPE_CHECKING, Any

import cohere

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


class CohereAdapter(LLMAdapter):
    """Cohere adapter for enterprise-focused cloud LLM inference."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "command-r-plus",
        temperature: float = 0.1,
        emitter: TraceEmitter | None = None,
    ) -> None:
        """Initialize the Cohere adapter with API configuration."""
        self.api_key = api_key
        self._model_name = model_name
        self.temperature = temperature
        self._client: cohere.AsyncClient | None = None
        self._emitter = emitter or MemoryTraceEmitter()

    def _ensure_client(self) -> None:
        """Ensure Cohere client is initialized."""
        if self._client is None:
            self._client = cohere.AsyncClient(api_key=self.api_key)

    def _messages_to_cohere_format(self, messages: list[Message]) -> str:
        """Convert messages to Cohere format (single string)."""
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
        structured_output: type[BaseModel] | None = None,
    ) -> LLMResponse:
        """
        Generate a response from Cohere API.

        Uses Cohere's chat API for enterprise-focused inference.
        """
        start_time = time.perf_counter()
        prompt_length = sum(len(msg.content) for msg in messages)

        try:
            # Emit adapter call start event
            try:
                event = TraceEvent(
                    event_type=TraceEventType.ADAPTER_CALL,
                    component=TraceComponent.ADAPTER,
                    message="Cohere adapter generation started",
                    level=TraceLevel.INFO,
                    data={
                        "adapter_name": "cohere",
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
                raise RuntimeError("Cohere client failed to initialize")

            prompt = self._messages_to_cohere_format(messages)

            response = await self._client.chat(
                message=prompt,
                model=self._model_name,
                temperature=temperature or self.temperature,
                max_tokens=max_tokens,
            )

            duration_ms = int((time.perf_counter() - start_time) * 1000)
            response_length = len(response.text)

            # Emit adapter response event
            try:
                event = TraceEvent(
                    event_type=TraceEventType.ADAPTER_RESPONSE,
                    component=TraceComponent.ADAPTER,
                    message="Cohere adapter generation completed",
                    level=TraceLevel.INFO,
                    data={
                        "adapter_name": "cohere",
                        "model_name": self._model_name,
                        "prompt_length": prompt_length,
                        "response_length": response_length,
                        "tokens_used": response.meta.billed_units.input_tokens + response.meta.billed_units.output_tokens if response.meta else 0,
                    },
                    duration_ms=duration_ms,
                )
                await self._emitter.emit(event)
            except Exception:
                pass

            return LLMResponse(
                content=response.text,
                raw={"model": self._model_name, "usage": response.meta.model_dump() if response.meta else {}},
                model=self._model_name,
                tokens_used=response.meta.billed_units.input_tokens + response.meta.billed_units.output_tokens if response.meta else 0,
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            # Emit error event (wrapped to avoid crashing main path)
            try:
                event = TraceEvent(
                    event_type=TraceEventType.ADAPTER_ERROR,
                    component=TraceComponent.ADAPTER,
                    message="Cohere adapter generation failed",
                    level=TraceLevel.ERROR,
                    data={
                        "adapter_name": "cohere",
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
            raise RuntimeError(f"Cohere generation failed: {e}")

    async def health_check(self) -> bool:
        """Check if Cohere API is accessible."""
        try:
            self._ensure_client()

            if self._client is None:
                return False

            response = await self._client.chat(message="test", model=self._model_name, max_tokens=1)
            return True
        except Exception:
            return False

    async def close(self) -> None:
        """Close the Cohere client."""
        if self._client:
            await self._client.close()
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
        """Cost per token for this model (Command R+: ~$0.003/1K tokens)."""
        costs = {
            "command-r-plus": 0.003,
            "command-r": 0.0005,
            "command": 0.0015,
        }
        return costs.get(self._model_name, 0.003)

