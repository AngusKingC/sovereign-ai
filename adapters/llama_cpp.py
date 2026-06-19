"""
llama.cpp adapter for local LLM inference.

Single responsibility: Provide local-first LLM inference using llama.cpp
with maximum hardware control for VRAM/RAM balancing.
"""

import time
from typing import TYPE_CHECKING, Any
from pydantic import BaseModel

import llama_cpp

from core.schemas import Message
from core.worker_base import LLMAdapter, LLMResponse
from core.observability import (
    TraceEventType,
    TraceComponent,
    TraceLevel,
    TraceEmitter,
    NullTraceEmitter,
    TraceEvent,
)




class LlamaCppAdapter(LLMAdapter):
    """Local LLM adapter using llama.cpp for maximum hardware control."""

    def __init__(
        self,
        model_path: str,
        n_ctx: int = 2048,
        n_gpu_layers: int = -1,
        n_threads: int = 4,
        temperature: float = 0.1,
        emitter: TraceEmitter | None = None,
    ) -> None:
        """Initialize the llama.cpp adapter with hardware configuration."""
        self.emitter = emitter or NullTraceEmitter()
        self.model_path = model_path
        self.n_ctx = n_ctx
        self.n_gpu_layers = n_gpu_layers
        self.n_threads = n_threads
        self.temperature = temperature
        self._model: llama_cpp.Llama | None = None
        self._model_name = model_path.split("/")[-1]

    def _ensure_model(self) -> None:
        """Ensure the model is loaded."""
        if self._model is None:
            self._model = llama_cpp.Llama(
                model_path=self.model_path,
                n_ctx=self.n_ctx,
                n_gpu_layers=self.n_gpu_layers,
                n_threads=self.n_threads,
                verbose=False,
            )

    def _messages_to_prompt(self, messages: list[Message]) -> str:
        """Convert messages to llama.cpp prompt format."""
        prompt_parts = []
        for msg in messages:
            if msg.role.value == "system":
                prompt_parts.append(f"System: {msg.content}")
            elif msg.role.value == "user":
                prompt_parts.append(f"User: {msg.content}")
            elif msg.role.value == "assistant":
                prompt_parts.append(f"Assistant: {msg.content}")
        return "\n".join(prompt_parts) + "\nAssistant:"

    async def generate(
        self,
        messages: list[Message],
        temperature: float = 0.1,
        max_tokens: int = 2048,
        structured_output: type[BaseModel] | None = None,
    ) -> LLMResponse:
        """Generate a response from the local LLM."""
        start_time = time.perf_counter()
        prompt_length = sum(len(msg.content) for msg in messages)

        try:
            # Emit adapter call start event
            await self.emitter.emit(TraceEvent(
                event_type=TraceEventType.ADAPTER_CALL,
                component=TraceComponent.ADAPTER,
                message="Llama.cpp adapter generation started",
                level=TraceLevel.INFO,
                data={
                    "adapter_name": "llama_cpp",
                    "model_name": self._model_name,
                    "prompt_length": prompt_length,
                    "temperature": temperature or self.temperature,
                },
            ))

            self._ensure_model()

            if self._model is None:
                raise RuntimeError("Model failed to load")

            prompt = self._messages_to_prompt(messages)

            output = self._model(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature or self.temperature,
            )

            duration_ms = int((time.perf_counter() - start_time) * 1000)
            response_length = len(output["choices"][0]["text"])

            # Emit adapter response event
            await self.emitter.emit(TraceEvent(
                event_type=TraceEventType.ADAPTER_RESPONSE,
                component=TraceComponent.ADAPTER,
                message="Llama.cpp adapter generation completed",
                level=TraceLevel.INFO,
                data={
                    "adapter_name": "llama_cpp",
                    "model_name": self._model_name,
                    "prompt_length": prompt_length,
                    "response_length": response_length,
                    "tokens_used": output.get("usage", {}).get("total_tokens", 0),
                },
                duration_ms=duration_ms,
            ))

            return LLMResponse(
                content=output["choices"][0]["text"],
                raw={"model": self._model_name, "usage": output.get("usage", {})},
                model=self._model_name,
                tokens_used=output.get("usage", {}).get("total_tokens", 0),
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            # Emit error event (wrapped to avoid crashing main path)
            try:
                await self.emitter.emit(TraceEvent(
                    event_type=TraceEventType.ADAPTER_ERROR,
                    component=TraceComponent.ADAPTER,
                    message="Llama.cpp adapter generation failed",
                    level=TraceLevel.ERROR,
                    data={
                        "adapter_name": "llama_cpp",
                        "model_name": self._model_name,
                        "prompt_length": prompt_length,
                    },
                    duration_ms=duration_ms,
                    error_type=type(e).__name__,
                    error_message=str(e),
                ))
            except Exception as e:
                await self.emitter.emit(TraceEvent(
                    event_type=TraceEventType.ADAPTER_ERROR,
                    component=TraceComponent.ADAPTER,
                    message="Trace emission failed in Llama.cpp adapter error handler",
                    level=TraceLevel.WARNING,
                    data={"error": str(e)},
                    duration_ms=0,
                ))
                pass  # Trace failure should not crash main path
            raise RuntimeError(f"llama.cpp generation failed: {e}")

    async def health_check(self) -> bool:
        """Check if the LLM is healthy and accessible."""
        try:
            self._ensure_model()
            return self._model is not None
        except Exception as e:
            await self.emitter.emit(TraceEvent(
                event_type=TraceEventType.ADAPTER_ERROR,
                component=TraceComponent.ADAPTER,
                message="Llama.cpp health check failed",
                level=TraceLevel.WARNING,
                data={"error": str(e)},
                duration_ms=0,
            ))
            return False

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


