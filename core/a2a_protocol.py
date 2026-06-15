"""
A2A (Agent-to-Agent) Protocol for worker-to-worker communication.

Single responsibility: Route sub-tasks between workers with circular dependency detection.
"""

from uuid import UUID, uuid4
from typing import Any

from pydantic import BaseModel, Field

from core.schemas import Task, WorkerOutput, TaskPriority, TaskStatus
from core.observability import (
    TraceComponent,
    TraceEventType,
    TraceLevel,
    TraceEvent,
    TraceEmitter,
    MemoryTraceEmitter,
)
from core.exceptions import CircularDependencyError


class A2ARequest(BaseModel):
    """Request envelope for A2A sub-task submission."""
    task_id: UUID = Field(default_factory=uuid4)
    input: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    requester_agent_id: str
    parent_task_id: UUID | None = None
    priority: TaskPriority = TaskPriority.NORMAL


class A2AResponse(BaseModel):
    """Response envelope for A2A sub-task results."""
    task_id: UUID
    status: str  # "completed", "failed", "pending"
    output: str = ""
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class A2ARouter:
    """Router for A2A sub-task communication between workers."""

    def __init__(self, orchestrator, emitter: TraceEmitter | None = None) -> None:
        """Initialize the A2A router.
        
        Args:
            orchestrator: The orchestrator instance for routing tasks
            emitter: Trace emitter for observability
        """
        self._orchestrator = orchestrator
        self._emitter = emitter or MemoryTraceEmitter()
        self._active_tasks: dict[UUID, set[UUID]] = {}  # parent -> set of child task_ids

    async def submit(self, request: A2ARequest) -> A2AResponse:
        """
        Submit an A2A sub-task request for routing.
        
        Args:
            request: The A2A request to submit
            
        Returns:
            A2AResponse with the result
            
        Raises:
            CircularDependencyError: If circular dependency detected
        """
        # Check for circular dependency before routing
        if self._check_circular(request.parent_task_id, request.task_id):
            try:
                event = TraceEvent(
                    event_type=TraceEventType.A2A_CIRCULAR_DEPENDENCY_DETECTED,
                    component=TraceComponent.A2A,
                    level=TraceLevel.ERROR,
                    message="Circular dependency detected in A2A request",
                    data={
                        "task_id": str(request.task_id),
                        "parent_task_id": str(request.parent_task_id),
                        "requester_agent_id": request.requester_agent_id,
                    },
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception:
                pass
            raise CircularDependencyError(request.task_id, request.parent_task_id)

        # Register child task under parent
        if request.parent_task_id:
            if request.parent_task_id not in self._active_tasks:
                self._active_tasks[request.parent_task_id] = set()
            self._active_tasks[request.parent_task_id].add(request.task_id)

        # Emit submit started event
        try:
            event = TraceEvent(
                event_type=TraceEventType.A2A_SUBMIT_STARTED,
                component=TraceComponent.A2A,
                level=TraceLevel.INFO,
                message="A2A sub-task submission started",
                data={
                    "task_id": str(request.task_id),
                    "parent_task_id": str(request.parent_task_id),
                    "requester_agent_id": request.requester_agent_id,
                    "priority": request.priority.value,
                },
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            pass

        try:
            # Convert A2ARequest to Task
            from datetime import datetime
            task = Task(
                task_id=request.task_id,
                parent_task_id=request.parent_task_id,
                intent=request.input,
                complexity_score=0.5,  # Default complexity for sub-tasks
                priority=request.priority,
                created_at=datetime.utcnow(),
            )

            # Route via orchestrator
            output = await self._orchestrator.route_task(task)

            # Convert WorkerOutput to A2AResponse
            response = A2AResponse(
                task_id=request.task_id,
                status="completed",
                output=output.content,
                metadata=output.metadata,
            )

            # Emit submit completed event
            try:
                event = TraceEvent(
                    event_type=TraceEventType.A2A_SUBMIT_COMPLETED,
                    component=TraceComponent.A2A,
                    level=TraceLevel.INFO,
                    message="A2A sub-task submission completed",
                    data={
                        "task_id": str(request.task_id),
                        "parent_task_id": str(request.parent_task_id),
                        "status": response.status,
                    },
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception:
                pass

            return response

        except Exception as e:
            # Emit submit failed event
            try:
                event = TraceEvent(
                    event_type=TraceEventType.A2A_SUBMIT_FAILED,
                    component=TraceComponent.A2A,
                    level=TraceLevel.ERROR,
                    message="A2A sub-task submission failed",
                    data={
                        "task_id": str(request.task_id),
                        "parent_task_id": str(request.parent_task_id),
                        "error": str(e),
                    },
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception:
                pass

            # Return failed response
            return A2AResponse(
                task_id=request.task_id,
                status="failed",
                metadata={"error": str(e)},
            )

    async def get_children(self, parent_task_id: UUID) -> list[UUID]:
        """
        Get all child task IDs for a given parent task.
        
        Args:
            parent_task_id: The parent task ID
            
        Returns:
            List of child task IDs
        """
        return list(self._active_tasks.get(parent_task_id, set()))

    async def cancel_children(self, parent_task_id: UUID) -> int:
        """
        Cancel all active child tasks for a given parent.
        
        Args:
            parent_task_id: The parent task ID
            
        Returns:
            Count of tasks cancelled
        """
        if parent_task_id not in self._active_tasks:
            return 0

        count = len(self._active_tasks[parent_task_id])
        del self._active_tasks[parent_task_id]

        # Emit children cancelled event
        try:
            event = TraceEvent(
                event_type=TraceEventType.A2A_CHILDREN_CANCELLED,
                component=TraceComponent.A2A,
                level=TraceLevel.INFO,
                message="A2A child tasks cancelled",
                data={
                    "parent_task_id": str(parent_task_id),
                    "count": count,
                },
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            pass

        return count

    def _check_circular(self, parent_task_id: UUID | None, new_task_id: UUID) -> bool:
        """
        Check if adding new_task_id would create a circular dependency.
        
        Args:
            parent_task_id: The parent task ID (can be None for root tasks)
            new_task_id: The new task ID to check
            
        Returns:
            True if circular dependency detected, False otherwise
        """
        if parent_task_id is None:
            return False

        if parent_task_id == new_task_id:
            return True

        # Check if parent_task_id is already in the ancestry of new_task_id
        # This would create a cycle if we add new_task_id as a child of parent_task_id
        visited = set()
        stack = [new_task_id]

        while stack:
            current = stack.pop()

            if current == parent_task_id:
                return True

            if current in visited:
                continue

            visited.add(current)

            # Get children of current task
            children = self._active_tasks.get(current, set())
            stack.extend(children)

        return False
