"""
Ollama local LLM adapter.

Single responsibility: Handle all interactions with local Ollama instances,
providing the primary local-first inference capability.
"""

import re
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


class OllamaAdapter(LLMAdapter):
    """Ollama adapter for local LLM inference."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model_name: str = "llama2",
        temperature: float = 0.1,
        emitter: TraceEmitter | None = None,
    ) -> None:
        """Initialize the Ollama adapter with server configuration."""
        self.base_url = base_url
        self._model_name = model_name
        self.temperature = temperature
        self._client: httpx.AsyncClient | None = None
        self._emitter = emitter or MemoryTraceEmitter()

    def _ensure_client(self) -> None:
        """Ensure HTTP client is initialized."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0)

    def _messages_to_ollama_format(self, messages: list[Message]) -> list[dict[str, str]]:
        """Convert messages to Ollama format."""
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
        Generate a response from Ollama local server.

        Uses Ollama's API format for communication.
        """
        start_time = time.perf_counter()
        prompt_length = sum(len(msg.content) for msg in messages)

        try:
            # Emit adapter call start event
            try:
                event = TraceEvent(
                    event_type=TraceEventType.ADAPTER_CALL,
                    component=TraceComponent.ADAPTER,
                    message="Ollama adapter generation started",
                    level=TraceLevel.INFO,
                    data={
                        "adapter_name": "ollama",
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

            ollama_messages = self._messages_to_ollama_format(messages)

            response = await self._client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self._model_name,
                    "messages": ollama_messages,
                    "stream": False,
                    "options": {
                        "temperature": temperature or self.temperature,
                        "num_predict": max_tokens,
                    },
                },
            )

            response.raise_for_status()
            data = response.json()

            duration_ms = int((time.perf_counter() - start_time) * 1000)
            response_length = len(data["message"]["content"])

            # Extract <thought> content if present
            raw_content = data["message"]["content"]
            thinking_match = re.search(r'<thought>(.*?)</thought>', raw_content, re.DOTALL)
            if thinking_match:
                thinking_content = thinking_match.group(1)
                # Emit model thinking captured event
                try:
                    event = TraceEvent(
                        event_type=TraceEventType.MODEL_THINKING_CAPTURED,
                        component=TraceComponent.ADAPTER,
                        message="Model thinking extracted",
                        level=TraceLevel.DEBUG,
                        data={
                            "adapter_name": "ollama",
                            "model_name": self._model_name,
                            "thinking": thinking_content,
                            "thinking_length": len(thinking_content),
                        },
                        duration_ms=0,
                    )
                    await self._emitter.emit(event)
                except Exception:
                    pass
                # Strip <thought> tags from response
                cleaned_content = re.sub(r'<thought>.*?</thought>', '', raw_content, flags=re.DOTALL).strip()
                data["message"]["content"] = cleaned_content

            # Emit adapter response event
            try:
                event = TraceEvent(
                    event_type=TraceEventType.ADAPTER_RESPONSE,
                    component=TraceComponent.ADAPTER,
                    message="Ollama adapter generation completed",
                    level=TraceLevel.INFO,
                    data={
                        "adapter_name": "ollama",
                        "model_name": self._model_name,
                        "prompt_length": prompt_length,
                        "response_length": response_length,
                        "tokens_used": data.get("eval_count", 0) + data.get("prompt_eval_count", 0),
                    },
                    duration_ms=duration_ms,
                )
                await self._emitter.emit(event)
            except Exception:
                pass

            return LLMResponse(
                content=data["message"]["content"],
                raw={"model": self._model_name, "usage": data.get("usage", {})},
                model=self._model_name,
                tokens_used=data.get("eval_count", 0) + data.get("prompt_eval_count", 0),
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            # Emit error event (wrapped to avoid crashing main path)
            try:
                event = TraceEvent(
                    event_type=TraceEventType.ADAPTER_ERROR,
                    component=TraceComponent.ADAPTER,
                    message="Ollama adapter generation failed",
                    level=TraceLevel.ERROR,
                    data={
                        "adapter_name": "ollama",
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
            raise RuntimeError(f"Ollama generation failed: {e}")

    async def health_check(self) -> bool:
        """Check if Ollama server is healthy and accessible."""
        try:
            self._ensure_client()

            if self._client is None:
                return False

            response = await self._client.get(f"{self.base_url}/api/tags")
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

