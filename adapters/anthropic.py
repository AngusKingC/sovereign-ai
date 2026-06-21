"""
Anthropic cloud LLM adapter.

Single responsibility: Handle interactions with Anthropic's API,
providing alternative cloud escalation capability.
"""

import time
from typing import TYPE_CHECKING

from anthropic import AsyncAnthropic

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


class AnthropicAdapter(LLMAdapter):
    """Anthropic adapter for cloud LLM inference."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "claude-sonnet-4-6",
        temperature: float = 0.1,
        emitter: TraceEmitter | None = None,
    ) -> None:
        """Initialize the Anthropic adapter with API configuration."""
        self.api_key = api_key
        self._model_name = model_name
        self.temperature = temperature
        self._client: AsyncAnthropic | None = None
        self._emitter = emitter or MemoryTraceEmitter()

    def _ensure_client(self) -> None:
        """Ensure Anthropic client is initialized."""
        if self._client is None:
            self._client = AsyncAnthropic(api_key=self.api_key)

    def _messages_to_anthropic_format(self, messages: list[Message]) -> list[dict[str, str]]:
        """Convert messages to Anthropic format."""
        anthropic_messages = []
        for msg in messages:
            if msg.role.value == "system":
                anthropic_messages.append({"role": "user", "content": f"System: {msg.content}"})
            else:
                anthropic_messages.append({"role": msg.role.value, "content": msg.content})
        return anthropic_messages

    async def generate(
        self,
        messages: list[Message],
        temperature: float = 0.1,
        max_tokens: int = 2048,
        structured_output: type[BaseModel] | None = None,
    ) -> LLMResponse:
        """
        Generate a response from Anthropic API.

        Uses Anthropic's messages API.
        """
        start_time = time.perf_counter()
        prompt_length = sum(len(msg.content) for msg in messages)

        try:
            # Emit adapter call start event
            try:
                event = TraceEvent(
                    event_type=TraceEventType.ADAPTER_CALL,
                    component=TraceComponent.ADAPTER,
                    message="Anthropic adapter generation started",
                    level=TraceLevel.INFO,
                    data={
                        "adapter_name": "anthropic",
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
                    message="Trace emission failed in Anthropic adapter call start",
                    level=TraceLevel.WARNING,
                    data={"error": str(e)},
                    duration_ms=0,
                ))
                pass

            self._ensure_client()

            if self._client is None:
                raise RuntimeError("Anthropic client failed to initialize")

            anthropic_messages = self._messages_to_anthropic_format(messages)

            response = await self._client.messages.create(
                model=self._model_name,
                messages=anthropic_messages,
                temperature=temperature or self.temperature,
                max_tokens=max_tokens,
            )

            duration_ms = int((time.perf_counter() - start_time) * 1000)
            response_length = len(response.content[0].text)

            # Emit adapter response event
            try:
                event = TraceEvent(
                    event_type=TraceEventType.ADAPTER_RESPONSE,
                    component=TraceComponent.ADAPTER,
                    message="Anthropic adapter generation completed",
                    level=TraceLevel.INFO,
                    data={
                        "adapter_name": "anthropic",
                        "model_name": self._model_name,
                        "prompt_length": prompt_length,
                        "response_length": response_length,
                        "tokens_used": response.usage.input_tokens + response.usage.output_tokens if response.usage else 0,
                    },
                    duration_ms=duration_ms,
                )
                await self._emitter.emit(event)
            except Exception as e:
                await self._emitter.emit(TraceEvent(
                    event_type=TraceEventType.ADAPTER_ERROR,
                    component=TraceComponent.ADAPTER,
                    message="Trace emission failed in Anthropic adapter response",
                    level=TraceLevel.WARNING,
                    data={"error": str(e)},
                    duration_ms=0,
                ))
                pass

            return LLMResponse(
                content=response.content[0].text,
                raw={"model": self._model_name, "usage": response.usage.model_dump() if response.usage else {}},
                model=self._model_name,
                tokens_used=response.usage.input_tokens + response.usage.output_tokens if response.usage else 0,
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            # Emit error event (wrapped to avoid crashing main path)
            try:
                event = TraceEvent(
                    event_type=TraceEventType.ADAPTER_ERROR,
                    component=TraceComponent.ADAPTER,
                    message="Anthropic adapter generation failed",
                    level=TraceLevel.ERROR,
                    data={
                        "adapter_name": "anthropic",
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
                    message="Trace emission failed in Anthropic adapter error handler",
                    level=TraceLevel.WARNING,
                    data={"error": str(inner_e)},
                    duration_ms=0,
                ))
                pass  # Trace failure should not crash main path
            raise RuntimeError(f"Anthropic generation failed: {e}")

    async def health_check(self) -> bool:
        """Check if Anthropic API is accessible."""
        try:
            self._ensure_client()

            if self._client is None:
                return False

            await self._client.messages.create(
                model=self._model_name,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1,
            )
            return True
        except Exception as e:
            print(f"Anthropic health check failed: {e}")
            return False

    async def close(self) -> None:
        """Close the Anthropic client."""
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
        """Cost per token for this model (Claude 3 Haiku: ~$0.00025/1K tokens)."""
        costs = {
            "claude-3-5-sonnet": 0.003,
            "claude-3-opus-20240229": 0.015,
            "claude-3-sonnet-20240229": 0.003,
            "claude-3-haiku-20240307": 0.00025,
        }
        return costs.get(self._model_name, 0.003)

