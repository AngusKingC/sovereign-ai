"""
Together AI cloud LLM adapter.

Single responsibility: Handle interactions with Together AI's API,
providing cost-effective access to open-source models.
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
    emit_trace,
)

if TYPE_CHECKING:
    from pydantic import BaseModel
else:
    from pydantic import BaseModel


class TogetherAdapter(LLMAdapter):
    """Together AI adapter for cost-effective open-source model inference."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "mistralai/Mixtral-8x7B-Instruct-v0.1",
        temperature: float = 0.1,
    ) -> None:
        """Initialize the Together AI adapter with API configuration."""
        self.api_key = api_key
        self._model_name = model_name
        self.temperature = temperature
        self._client: AsyncOpenAI | None = None

    def _ensure_client(self) -> None:
        """Ensure Together AI client is initialized (uses OpenAI-compatible API)."""
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self.api_key,
                base_url="https://api.together.xyz/v1",
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
        Generate a response from Together AI API.

        Uses Together AI's OpenAI-compatible API for cost-effective inference.
        """
        start_time = time.perf_counter()
        prompt_length = sum(len(msg.content) for msg in messages)

        try:
            # Emit adapter call start event
            await emit_trace(
                event_type=TraceEventType.ADAPTER_CALL,
                component=TraceComponent.ADAPTER,
                message="Together adapter generation started",
                level=TraceLevel.INFO,
                data={
                    "adapter_name": "together",
                    "model_name": self._model_name,
                    "prompt_length": prompt_length,
                    "temperature": temperature or self.temperature,
                },
            )

            self._ensure_client()

            if self._client is None:
                raise RuntimeError("Together AI client failed to initialize")

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
            await emit_trace(
                event_type=TraceEventType.ADAPTER_RESPONSE,
                component=TraceComponent.ADAPTER,
                message="Together adapter generation completed",
                level=TraceLevel.INFO,
                data={
                    "adapter_name": "together",
                    "model_name": self._model_name,
                    "prompt_length": prompt_length,
                    "response_length": response_length,
                    "tokens_used": response.usage.total_tokens if response.usage else 0,
                },
                duration_ms=duration_ms,
            )

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
                await emit_trace(
                    event_type=TraceEventType.ADAPTER_ERROR,
                    component=TraceComponent.ADAPTER,
                    message="Together adapter generation failed",
                    level=TraceLevel.ERROR,
                    data={
                        "adapter_name": "together",
                        "model_name": self._model_name,
                        "prompt_length": prompt_length,
                    },
                    duration_ms=duration_ms,
                    error_type=type(e).__name__,
                    error_message=str(e),
                )
            except Exception:
                pass  # Trace failure should not crash main path
            raise RuntimeError(f"Together AI generation failed: {e}")

    async def health_check(self) -> bool:
        """Check if Together AI API is accessible."""
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
        except Exception:
            return False

    async def close(self) -> None:
        """Close the Together AI client."""
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
        """Cost per token for this model (Together AI: ~$0.0006/1K tokens)."""
        return 0.0006  # Together AI's competitive pricing

