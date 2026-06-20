"""
Mistral AI cloud LLM adapter.

Single responsibility: Handle interactions with Mistral AI's API,
providing access to open-source models from Mistral.
"""

import time
from typing import TYPE_CHECKING, Any

from openai import AsyncOpenAI

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


class MistralAdapter(LLMAdapter):
    """Mistral AI adapter for open-source model inference."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "mistral-large-latest",
        temperature: float = 0.1,
        emitter: TraceEmitter | None = None,
    ) -> None:
        """Initialize the Mistral AI adapter with API configuration."""
        self.api_key = api_key
        self._model_name = model_name
        self.temperature = temperature
        self._client: AsyncOpenAI | None = None
        self._emitter = emitter or MemoryTraceEmitter()

    def _ensure_client(self) -> None:
        """Ensure Mistral AI client is initialized (uses OpenAI-compatible API)."""
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self.api_key,
                base_url="https://api.mistral.ai/v1",
            )

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
        Generate a response from Mistral AI API.

        Uses Mistral AI's OpenAI-compatible API for open-source model inference.
        """
        start_time = time.perf_counter()
        prompt_length = sum(len(msg.content) for msg in messages)

        try:
            # Emit adapter call start event
            try:
                event = TraceEvent(
                    event_type=TraceEventType.ADAPTER_CALL,
                    component=TraceComponent.ADAPTER,
                    message="Mistral adapter generation started",
                    level=TraceLevel.INFO,
                    data={
                        "adapter_name": "mistral",
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
                    message="Trace emission failed in Mistral adapter call start",
                    level=TraceLevel.WARNING,
                    data={"error": str(e)},
                    duration_ms=0,
                ))
                pass

            self._ensure_client()

            if self._client is None:
                raise RuntimeError("Mistral AI client failed to initialize")

            openai_messages = self._messages_to_openai_format(messages)

            response = await self._client.chat.completions.create(
                model=self._model_name,
                messages=openai_messages,
                temperature=temperature or self.temperature,
                max_tokens=max_tokens,
            )

            duration_ms = int((time.perf_counter() - start_time) * 1000)
            response_length = len(response.choices[0].message.content)

            # Emit adapter response event
            try:
                event = TraceEvent(
                    event_type=TraceEventType.ADAPTER_RESPONSE,
                    component=TraceComponent.ADAPTER,
                    message="Mistral adapter generation completed",
                    level=TraceLevel.INFO,
                    data={
                        "adapter_name": "mistral",
                        "model_name": self._model_name,
                        "prompt_length": prompt_length,
                        "response_length": response_length,
                        "tokens_used": response.usage.total_tokens if response.usage else 0,
                    },
                    duration_ms=duration_ms,
                )
                await self._emitter.emit(event)
            except Exception as e:
                await self._emitter.emit(TraceEvent(
                    event_type=TraceEventType.ADAPTER_ERROR,
                    component=TraceComponent.ADAPTER,
                    message="Trace emission failed in Mistral adapter response",
                    level=TraceLevel.WARNING,
                    data={"error": str(e)},
                    duration_ms=0,
                ))
                pass

            return LLMResponse(
                content=response.choices[0].message.content,
                raw={"model": self._model_name, "usage": response.usage.model_dump() if response.usage else {}},
                model=self._model_name,
                tokens_used=response.usage.total_tokens if response.usage else 0,
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            # Emit error event (wrapped to avoid crashing main path)
            try:
                event = TraceEvent(
                    event_type=TraceEventType.ADAPTER_ERROR,
                    component=TraceComponent.ADAPTER,
                    message="Mistral adapter generation failed",
                    level=TraceLevel.ERROR,
                    data={
                        "adapter_name": "mistral",
                        "model_name": self._model_name,
                        "prompt_length": prompt_length,
                    },
                    duration_ms=duration_ms,
                    error_type=type(e).__name__,
                    error_message=str(e),
                )
                await self._emitter.emit(event)
            except Exception as e:
                await self._emitter.emit(TraceEvent(
                    event_type=TraceEventType.ADAPTER_ERROR,
                    component=TraceComponent.ADAPTER,
                    message="Trace emission failed in Mistral adapter error handler",
                    level=TraceLevel.WARNING,
                    data={"error": str(e)},
                    duration_ms=0,
                ))
                pass  # Trace failure should not crash main path
            raise RuntimeError(f"Mistral AI generation failed: {e}")

    async def health_check(self) -> bool:
        """Check if Mistral AI API is accessible."""
        try:
            self._ensure_client()

            if self._client is None:
                return False

            await self._client.chat.completions.create(
                model=self._model_name,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1,
            )
            return True
        except Exception as e:
            await self._emitter.emit(TraceEvent(
                event_type=TraceEventType.ADAPTER_ERROR,
                component=TraceComponent.ADAPTER,
                message="Mistral health check failed",
                level=TraceLevel.WARNING,
                data={"error": str(e)},
                duration_ms=0,
            ))
            return False

    async def close(self) -> None:
        """Close the Mistral AI client."""
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
        """Cost per token for this model (Mistral Large: ~$0.004/1K tokens)."""
        costs = {
            "mistral-large-latest": 0.004,
            "mistral-medium-latest": 0.002,
            "mistral-small-latest": 0.0002,
        }
        return costs.get(self._model_name, 0.004)

