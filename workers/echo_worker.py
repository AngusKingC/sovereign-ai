"""
Echo worker - minimal concrete worker for testing.

Single responsibility: Provide a simple worker implementation that echoes
input back for integration testing purposes.
"""

import time
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.memory_router import MemoryRouter

from core.schemas import Message, MessageRole, Task, WorkerOutput, WorkerProfile
from core.worker_base import LLMAdapter, LLMResponse, WorkerBase
from core.observability import (
    TraceEventType,
    TraceComponent,
    TraceLevel,
    TraceEvent,
    TraceEmitter,
    MemoryTraceEmitter,
)


class MockLLMAdapter(LLMAdapter):
    """Mock LLM adapter for testing."""

    def __init__(self) -> None:
        self._model_name = "mock-model"
        self._cost_per_token = 0.0

    async def generate(
        self,
        messages: list[Message],
        temperature: float = 0.1,
        max_tokens: int = 2048,
        structured_output: type | None = None,
    ) -> LLMResponse:
        """Generate a mock response."""
        # Echo the last user message
        user_content = ""
        for msg in reversed(messages):
            if msg.role == MessageRole.USER:
                user_content = msg.content
                break

        return LLMResponse(
            content=f"Echo: {user_content}",
            raw={"mock": True},
            model=self._model_name,
            tokens_used=10,
            duration_ms=5,
        )

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def cost_per_token(self) -> float:
        return self._cost_per_token


class EchoWorker(WorkerBase):
    """Simple worker that echoes input for testing."""

    def __init__(
        self,
        profile: WorkerProfile,
        llm: LLMAdapter,
        memory_router: "MemoryRouter",
        emitter: TraceEmitter | None = None,
    ) -> None:
        """Initialize the echo worker."""
        super().__init__(profile, llm, memory_router, emitter=emitter)

    async def build_prompt(self, task: Task, memory: list) -> list[Message]:
        """Build a simple prompt with task intent and memory."""
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
                Message(role=MessageRole.SYSTEM, content="You are an echo assistant.", timestamp=now),
                Message(role=MessageRole.USER, content=f"Task: {task.intent}", timestamp=now),
            ]

            # Add memory context if available
            if memory:
                memory_text = "\n".join([str(m) for m in memory[:3]])
                messages.append(
                    Message(role=MessageRole.USER, content=f"Memory context:\n{memory_text}", timestamp=now)
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
        """Parse the LLM response into WorkerOutput."""
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
                reasoning_steps=["Echoed user input"],
                confidence=1.0,
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

