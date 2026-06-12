"""
Ollama worker - production worker wrapping OllamaAdapter.

Single responsibility: Provide a production-ready worker implementation
that wraps OllamaAdapter for general-purpose LLM interactions.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from core.schemas import Message, MessageRole, Task, WorkerOutput, WorkerProfile
from core.worker_base import LLMAdapter, LLMResponse, WorkerBase
from core.observability import (
    TraceComponent,
    TraceEventType,
    TraceLevel,
    TraceEvent,
    TraceEmitter,
    MemoryTraceEmitter,
)

if TYPE_CHECKING:
    from core.memory_router import MemoryRouter


class OllamaWorker(WorkerBase):
    """Production worker that wraps OllamaAdapter for general-purpose tasks."""

    def __init__(
        self,
        adapter: LLMAdapter,
        memory_router: "MemoryRouter | None" = None,
        profile: WorkerProfile | None = None,
    ) -> None:
        """Initialize the Ollama worker.
        
        Args:
            adapter: LLM adapter to use for generation
            memory_router: Memory router for context retrieval
            profile: Worker profile (uses default if not provided)
        """
        if profile is None:
            profile = WorkerProfile(
                worker_id="ollama_worker",
                worker_type="ollama",
                depth_preference=0.5,
                speculation_tolerance=0.5,
                source_skepticism=0.5,
                verbosity=0.5,
                preferred_model=adapter.model_name,
                escalation_threshold=0.8,
                capabilities=["general", "chat", "reasoning", "code", "analysis"],
                preferred_complexity=0.5,
            )
        
        # Create a mock memory router if none provided
        if memory_router is None:
            from core.memory_router import MemoryRouter, MemoryBackend
            from uuid import uuid4
            from typing import Any
            
            class NullMemoryBackend(MemoryBackend):
                async def fetch(self, task: Task) -> list[dict[str, Any]]:
                    return []
                async def write(self, data: dict[str, Any]) -> None:
                    pass
            
            memory_router = MemoryRouter(backends={"null": NullMemoryBackend()})
        
        super().__init__(profile, adapter, memory_router)

    async def build_prompt(self, task: Task, memory: list) -> list[Message]:
        """Build the prompt for the LLM based on task and memory.
        
        Constructs:
        1. System message establishing the agent's role
        2. Memory context messages (if any)
        3. User message from task.intent
        """
        import time
        start_time = time.perf_counter()

        try:
            # Emit prompt build start event
            try:
                event = TraceEvent(
                    event_type=TraceEventType.WORKER_PROMPT_BUILD,
                    component=TraceComponent.WORKER,
                    message="Worker prompt building started",
                    level=TraceLevel.INFO,
                    data={
                        "worker_name": self.profile.worker_id,
                        "task_id": str(task.task_id),
                        "memory_records_used": len(memory),
                    },
                    duration_ms=0,
                )
                await self.emitter.emit(event)
            except Exception:
                pass

            now = datetime.now()
            messages = [
                Message(
                    role=MessageRole.SYSTEM,
                    content="You are a helpful AI assistant that provides accurate, thoughtful responses.",
                    timestamp=now,
                )
            ]

            # Add memory context if available
            if memory:
                memory_text = "\n".join([str(m.get("content", str(m))) for m in memory[:5]])
                messages.append(
                    Message(
                        role=MessageRole.SYSTEM,
                        content=f"Context from memory:\n{memory_text}",
                        timestamp=now,
                    )
                )

            # Add user message from task intent
            messages.append(
                Message(
                    role=MessageRole.USER,
                    content=task.intent,
                    timestamp=now,
                )
            )

            duration_ms = int((time.perf_counter() - start_time) * 1000)

            # Emit prompt build complete event
            try:
                event = TraceEvent(
                    event_type=TraceEventType.WORKER_PROMPT_BUILD,
                    component=TraceComponent.WORKER,
                    message="Worker prompt building completed",
                    level=TraceLevel.INFO,
                    data={
                        "worker_name": self.profile.worker_id,
                        "task_id": str(task.task_id),
                        "memory_records_used": len(memory),
                    },
                    duration_ms=duration_ms,
                )
                await self.emitter.emit(event)
            except Exception:
                pass

            return messages
        except Exception as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            # Emit error event (wrapped to avoid crashing main path)
            try:
                event = TraceEvent(
                    event_type=TraceEventType.WORKER_PROMPT_BUILD,
                    component=TraceComponent.WORKER,
                    message="Worker prompt building failed",
                    level=TraceLevel.ERROR,
                    data={
                        "worker_name": self.profile.worker_id,
                        "task_id": str(task.task_id),
                    },
                    duration_ms=duration_ms,
                    error_type=type(e).__name__,
                    error_message=str(e),
                )
                await self.emitter.emit(event)
            except Exception:
                pass  # Trace failure should not crash main path
            raise

    async def parse_output(self, raw: LLMResponse, task_id: str) -> WorkerOutput:
        """Parse the raw LLM response into a WorkerOutput.
        
        Returns WorkerOutput with:
        - result set to the response text
        - confidence=0.9
        - empty reasoning_steps
        """
        import time
        start_time = time.perf_counter()

        try:
            # Emit output parse start event
            try:
                event = TraceEvent(
                    event_type=TraceEventType.WORKER_OUTPUT_PARSE,
                    component=TraceComponent.WORKER,
                    message="Worker output parsing started",
                    level=TraceLevel.INFO,
                    data={
                        "worker_name": self.profile.worker_id,
                        "task_id": str(task_id),
                    },
                    duration_ms=0,
                )
                await self.emitter.emit(event)
            except Exception:
                pass

            output = WorkerOutput(
                worker_id=self.profile.worker_id,
                task_id=task_id,
                content=raw.content,
                reasoning_steps=[],
                confidence=0.9,
                sources=[],
                claims=[raw.content],
                escalation_recommended=False,
                model_used=raw.model,
                tokens_used=raw.tokens_used,
            )

            duration_ms = int((time.perf_counter() - start_time) * 1000)

            # Emit output parse complete event
            try:
                event = TraceEvent(
                    event_type=TraceEventType.WORKER_OUTPUT_PARSE,
                    component=TraceComponent.WORKER,
                    message="Worker output parsing completed",
                    level=TraceLevel.INFO,
                    data={
                        "worker_name": self.profile.worker_id,
                        "task_id": str(task_id),
                        "confidence_score": output.confidence,
                    },
                    duration_ms=duration_ms,
                )
                await self.emitter.emit(event)
            except Exception:
                pass

            return output
        except Exception as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            # Emit error event (wrapped to avoid crashing main path)
            try:
                event = TraceEvent(
                    event_type=TraceEventType.WORKER_OUTPUT_PARSE,
                    component=TraceComponent.WORKER,
                    message="Worker output parsing failed",
                    level=TraceLevel.ERROR,
                    data={
                        "worker_name": self.profile.worker_id,
                        "task_id": str(task_id),
                    },
                    duration_ms=duration_ms,
                    error_type=type(e).__name__,
                    error_message=str(e),
                )
                await self.emitter.emit(event)
            except Exception:
                pass  # Trace failure should not crash main path
            raise

