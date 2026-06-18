"""
Base worker interface.

Single responsibility: Define the abstract interface that all workers must implement,
ensuring consistency across Layer 2 components.
"""

import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from pydantic import BaseModel, ValidationError

from core.schemas import (
    Task,
    Message,
    WorkerOutput,
    WorkerProfile,
    ScratchpadEntryType,
)
from core.observability import (
    TraceComponent,
    TraceEventType,
    TraceLevel,
    TraceEvent,
)


if TYPE_CHECKING:
    from core.memory_router import MemoryRouter
    from core.scratchpad import ScratchpadManager


class LLMResponse(BaseModel):
    """Response from an LLM adapter."""
    content: str
    raw: dict[str, Any]
    model: str
    tokens_used: int
    duration_ms: int
    validated_output: BaseModel | None = None


@runtime_checkable
class LLMAdapter(Protocol):
    """Protocol for LLM adapters to avoid circular imports."""

    async def generate(
        self,
        messages: list[Message],
        temperature: float = 0.1,
        max_tokens: int = 2048,
        structured_output: type[BaseModel] | None = None,
    ) -> LLMResponse:
        """Generate a response from the LLM."""
        ...

    @property
    def model_name(self) -> str:
        """Name of the model this adapter uses."""
        ...

    @property
    def cost_per_token(self) -> float:
        """Cost per token for this model."""
        ...


class WorkerBase(ABC):
    """Abstract base class for all workers."""

    def __init__(
        self,
        profile: WorkerProfile,
        llm: LLMAdapter,
        memory_router: "MemoryRouter",
        scratchpad_manager: "ScratchpadManager | None" = None,
        emitter: "TraceEmitter | None" = None,
        fallback_chain: Any = None,
    ) -> None:
        """Initialize the worker with dependencies."""
        self.profile = profile
        self.llm = llm
        self.memory_router = memory_router
        self.scratchpad_manager = scratchpad_manager
        self.fallback_chain = fallback_chain
        self.current_task_id: str | None = None
        if emitter is None:
            from core.observability import MemoryTraceEmitter
            emitter = MemoryTraceEmitter()
        self.emitter = emitter

    @abstractmethod
    async def build_prompt(self, task: Task, memory: list) -> list[Message]:
        """Build the prompt for the LLM based on task and memory."""
        raise NotImplementedError

    @abstractmethod
    async def parse_output(self, raw: LLMResponse, task_id: str) -> WorkerOutput:
        """Parse the raw LLM response into a WorkerOutput."""
        raise NotImplementedError

    async def write_scratchpad(
        self,
        entry_type: ScratchpadEntryType,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Write an entry to the scratchpad if one exists for the current task.
        
        Args:
            entry_type: Type of scratchpad entry
            content: Entry content
            metadata: Optional additional metadata
        """
        if self.scratchpad_manager and self.current_task_id:
            try:
                from uuid import UUID
                await self.scratchpad_manager.add_entry(
                    task_id=UUID(self.current_task_id),
                    worker_id=self.profile.worker_id,
                    entry_type=entry_type,
                    content=content,
                    metadata=metadata,
                )
            except Exception:
                # Silently no-op if scratchpad writing fails
                pass

    async def run(self, task: Task) -> WorkerOutput:
        """
        Execute a task through the full worker pipeline with enforced tracing.

        This method cannot be bypassed - tracing is enforced at the base class level.
        """
        # Set current task ID for scratchpad operations
        self.current_task_id = str(task.task_id)
        # Step 1: MEMORY_QUERY
        start_time = time.perf_counter()
        memory = await self.memory_router.fetch(task)
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        await self.emitter.emit(TraceEvent(
            event_type=TraceEventType.DATA_READ,
            component=TraceComponent.WORKER,
            message="Memory query completed",
            level=TraceLevel.INFO,
            data={"task_id": str(task.task_id), "worker_id": self.profile.worker_id},
            duration_ms=duration_ms,
        ))

        # Step 2: PROMPT_BUILT
        start_time = time.perf_counter()
        prompt = await self.build_prompt(task, memory)
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        await self.emitter.emit(TraceEvent(
            event_type=TraceEventType.OPERATION_START,
            component=TraceComponent.WORKER,
            message="Prompt built",
            level=TraceLevel.INFO,
            data={"task_id": str(task.task_id), "message_count": len(prompt), "worker_id": self.profile.worker_id},
            duration_ms=duration_ms,
        ))

        # Step 3: LLM_CALLED
        start_time = time.perf_counter()
        
        # Use fallback chain if available, otherwise call adapter directly
        if self.fallback_chain is not None:
            llm_response = await self.fallback_chain.execute(
                prompt,
                temperature=0.1,
                max_tokens=2048,
            )
        else:
            llm_response = await self.llm.generate(
                messages=prompt,
                temperature=0.1,
                max_tokens=2048,
            )
        
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        await self.emitter.emit(TraceEvent(
            event_type=TraceEventType.ADAPTER_CALL,
            component=TraceComponent.WORKER,
            message="LLM call completed",
            level=TraceLevel.INFO,
            data={"task_id": str(task.task_id), "worker_id": self.profile.worker_id},
            duration_ms=duration_ms,
        ))

        # Step 4: LLM_RAW_RESPONSE
        await self.emitter.emit(TraceEvent(
            event_type=TraceEventType.ADAPTER_RESPONSE,
            component=TraceComponent.WORKER,
            message="LLM raw response received",
            level=TraceLevel.INFO,
            data={
                "task_id": str(task.task_id),
                "content": llm_response.content,
                "tokens_used": llm_response.tokens_used,
                "worker_id": self.profile.worker_id,
            },
            duration_ms=llm_response.duration_ms,
        ))

        # Step 5: Parse output with validation and retry logic
        max_retries = 1
        retry_count = 0

        while retry_count <= max_retries:
            try:
                output = await self.parse_output(llm_response, str(task.task_id))
                # Validation passed
                await self.emitter.emit(TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.WORKER,
                    message="Output validation passed",
                    level=TraceLevel.INFO,
                    data={"task_id": str(task.task_id), "worker_id": self.profile.worker_id},
                    duration_ms=0,
                ))
                break
            except ValidationError as e:
                task.validation_failures += 1
                retry_count += 1
                await self.emitter.emit(TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.WORKER,
                    message="Output validation failed",
                    level=TraceLevel.ERROR,
                    data={
                        "task_id": str(task.task_id),
                        "error": str(e),
                        "retry_count": retry_count,
                        "worker_id": self.profile.worker_id,
                    },
                    duration_ms=0,
                ))
                if retry_count > max_retries:
                    raise

        # Step 6: OUTPUT_FINAL
        await self.emitter.emit(TraceEvent(
            event_type=TraceEventType.OPERATION_COMPLETE,
            component=TraceComponent.WORKER,
            message="Worker output finalized",
            level=TraceLevel.INFO,
            data={
                "task_id": str(task.task_id),
                "worker_id": output.worker_id,
                "confidence": output.confidence,
            },
            duration_ms=0,
        ))

        return output









