"""
Google Gemini cloud LLM adapter.

Single responsibility: Handle interactions with Google's Gemini API,
providing free API tier access for cost-effective inference.
"""

import asyncio
import time
from typing import TYPE_CHECKING, Any

from google import genai
from google.genai import types

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


class GeminiAdapter(LLMAdapter):
    """Google Gemini adapter for cloud LLM inference with free API tier."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-3.5-flash",
        temperature: float = 0.1,
    ) -> None:
        """Initialize the Gemini adapter with API configuration."""
        self.api_key = api_key
        self._model_name = model_name
        self.temperature = temperature
        self._client: genai.Client | None = None

    def _ensure_client(self) -> None:
        """Ensure Gemini client is initialized."""
        if self._client is None:
            self._client = genai.Client(api_key=self.api_key)

    def _messages_to_gemini_format(self, messages: list[Message]) -> str:
        """Convert messages to Gemini format (single string)."""
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
        Generate a response from Gemini API.

        Uses Google's Generative AI API with free tier support.
        """
        start_time = time.perf_counter()
        prompt_length = sum(len(msg.content) for msg in messages)

        try:
            # Emit adapter call start event
            await emit_trace(
                event_type=TraceEventType.ADAPTER_CALL,
                component=TraceComponent.ADAPTER,
                message="Gemini adapter generation started",
                level=TraceLevel.INFO,
                data={
                    "adapter_name": "gemini",
                    "model_name": self._model_name,
                    "prompt_length": prompt_length,
                    "temperature": temperature or self.temperature,
                },
            )

            self._ensure_client()

            if self._client is None:
                raise RuntimeError("Gemini client failed to initialize")

            prompt = self._messages_to_gemini_format(messages)

            # Use new SDK async API
            response = await self._client.aio.models.generate_content(
                model=self._model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=temperature or self.temperature,
                    max_output_tokens=max_tokens,
                ),
            )

            duration_ms = int((time.perf_counter() - start_time) * 1000)
            response_length = len(response.text)

            # Emit adapter response event
            await emit_trace(
                event_type=TraceEventType.ADAPTER_RESPONSE,
                component=TraceComponent.ADAPTER,
                message="Gemini adapter generation completed",
                level=TraceLevel.INFO,
                data={
                    "adapter_name": "gemini",
                    "model_name": self._model_name,
                    "prompt_length": prompt_length,
                    "response_length": response_length,
                    "tokens_used": response.usage_metadata.total_token_count if response.usage_metadata else 0,
                },
                duration_ms=duration_ms,
            )

            return LLMResponse(
                content=response.text,
                raw={"model": self._model_name, "usage": {}},
                model=self._model_name,
                tokens_used=response.usage_metadata.total_token_count if response.usage_metadata else 0,
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            # Emit error event (wrapped to avoid crashing main path)
            try:
                await emit_trace(
                    event_type=TraceEventType.ADAPTER_ERROR,
                    component=TraceComponent.ADAPTER,
                    message="Gemini adapter generation failed",
                    level=TraceLevel.ERROR,
                    data={
                        "adapter_name": "gemini",
                        "model_name": self._model_name,
                        "prompt_length": prompt_length,
                    },
                    duration_ms=duration_ms,
                    error_type=type(e).__name__,
                    error_message=str(e),
                )
            except Exception:
                pass  # Trace failure should not crash main path
            raise RuntimeError(f"Gemini generation failed: {e}")

    async def health_check(self) -> bool:
        """Check if Gemini API is accessible."""
        try:
            self._ensure_client()

            if self._client is None:
                return False

            # Use new SDK async API
            await self._client.aio.models.generate_content(
                model=self._model_name,
                contents="test",
                config=types.GenerateContentConfig(max_output_tokens=1),
            )
            return True
        except Exception as e:
            print(f"Gemini health check failed: {e}")
            return False

    async def close(self) -> None:
        """Cleanup resources (no explicit close needed for Gemini)."""
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
        """Cost per token for this model (Free tier: $0)."""
        return 0.0  # Free API tier

