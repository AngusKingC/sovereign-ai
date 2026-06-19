"""
Groq cloud LLM adapter.

Single responsibility: Handle interactions with Groq's API,
providing ultra-fast inference for time-sensitive tasks.
"""

import time
from typing import TYPE_CHECKING, Any

from groq import AsyncGroq

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


class GroqAdapter(LLMAdapter):
    """Groq adapter for ultra-fast cloud LLM inference."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "llama-3.3-70b-versatile",
        temperature: float = 0.1,
        emitter: TraceEmitter | None = None,
    ) -> None:
        """Initialize the Groq adapter with API configuration."""
        self.api_key = api_key
        self._model_name = model_name
        self.temperature = temperature
        self._client: AsyncGroq | None = None
        self._emitter = emitter or MemoryTraceEmitter()

    def _ensure_client(self) -> None:
        """Ensure Groq client is initialized."""
        if self._client is None:
            self._client = AsyncGroq(api_key=self.api_key)

    def _messages_to_groq_format(self, messages: list[Message]) -> list[dict[str, str]]:
        """Convert messages to Groq format."""
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
        Generate a response from Groq API.

        Uses Groq's ultra-fast inference API.
        """
        start_time = time.perf_counter()
        prompt_length = sum(len(msg.content) for msg in messages)

        try:
            # Emit adapter call start event
            try:
                event = TraceEvent(
                    event_type=TraceEventType.ADAPTER_CALL,
                    component=TraceComponent.ADAPTER,
                    message="Groq adapter generation started",
                    level=TraceLevel.INFO,
                    data={
                        "adapter_name": "groq",
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
                    message="Trace emission failed in Groq adapter call start",
                    level=TraceLevel.WARNING,
                    data={"error": str(e)},
                    duration_ms=0,
                ))
                pass

            self._ensure_client()

            if self._client is None:
                raise RuntimeError("Groq client failed to initialize")

            groq_messages = self._messages_to_groq_format(messages)

            response = await self._client.chat.completions.create(
                model=self._model_name,
                messages=groq_messages,
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
                    message="Groq adapter generation completed",
                    level=TraceLevel.INFO,
                    data={
                        "adapter_name": "groq",
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
                    message="Trace emission failed in Groq adapter response",
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
                    message="Groq adapter generation failed",
                    level=TraceLevel.ERROR,
                    data={
                        "adapter_name": "groq",
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
                    message="Trace emission failed in Groq adapter error handler",
                    level=TraceLevel.WARNING,
                    data={"error": str(e)},
                    duration_ms=0,
                ))
                pass  # Trace failure should not crash main path
            raise RuntimeError(f"Groq generation failed: {e}")

    async def health_check(self) -> bool:
        """Check if Groq API is accessible."""
        try:
            self._ensure_client()

            if self._client is None:
                return False

            response = await self._client.chat.completions.create(
                model=self._model_name,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1,
            )
            return True
        except Exception as e:
            await self._emitter.emit(TraceEvent(
                event_type=TraceEventType.ADAPTER_ERROR,
                component=TraceComponent.ADAPTER,
                message="Groq health check failed",
                level=TraceLevel.WARNING,
                data={"error": str(e)},
                duration_ms=0,
            ))
            return False

    async def close(self) -> None:
        """Close the Groq client."""
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
        """Cost per token for this model (Groq: ~$0.00059/1K tokens)."""
        return 0.00059  # Groq's competitive pricing

