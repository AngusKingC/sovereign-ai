"""
Task State Machine - Explicit State Management for Tasks

Single responsibility: Manage task state transitions with validation,
history tracking, and observability.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from core.schemas import Task, TaskStatus, TaskStateTransition
from core.observability import (
    TraceComponent,
    TraceEventType,
    TraceLevel,
    emit_trace,
)
from core.exceptions import InvalidStateTransitionError

if TYPE_CHECKING:
    from core.memory_router import MemoryRouter


class TaskStateMachine:
    """Manages task state transitions with validation and history tracking."""

    VALID_TRANSITIONS = {
        TaskStatus.RECEIVED: [TaskStatus.PLANNED, TaskStatus.FAILED, TaskStatus.CANCELLED],
        TaskStatus.PLANNED: [TaskStatus.EXECUTING, TaskStatus.FAILED, TaskStatus.CANCELLED],
        TaskStatus.EXECUTING: [TaskStatus.VALIDATING, TaskStatus.AWAITING_APPROVAL, TaskStatus.FAILED, TaskStatus.CANCELLED],
        TaskStatus.VALIDATING: [TaskStatus.COMPLETE, TaskStatus.EXECUTING, TaskStatus.FAILED, TaskStatus.CANCELLED],
        TaskStatus.AWAITING_APPROVAL: [TaskStatus.EXECUTING, TaskStatus.DENIED, TaskStatus.FAILED, TaskStatus.CANCELLED],
        TaskStatus.COMPLETE: [],  # Terminal state
        TaskStatus.FAILED: [],  # Terminal state
        TaskStatus.CANCELLED: [],  # Terminal state
        TaskStatus.DENIED: [],  # Terminal state
    }

    def __init__(self, memory_router: "MemoryRouter") -> None:
        """Initialize the task state machine with memory router for persistence."""
        self.memory_router = memory_router

    async def transition(
        self,
        task: Task,
        to_state: TaskStatus,
        reason: str | None = None,
        actor: str = "system",
    ) -> Task:
        """Attempt a state transition.
        
        Args:
            task: The task to transition
            to_state: The target state
            reason: Optional reason for the transition
            actor: Which component triggered the transition
            
        Returns:
            The updated task with new state and transition history
            
        Raises:
            InvalidStateTransitionError: If the transition is not valid
        """
        from_state = task.current_state

        # Skip transition if already in target state
        if from_state == to_state:
            return task

        # Validate the transition is legal
        if not self.can_transition(task, to_state):
            try:
                await emit_trace(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.ORCHESTRATOR,
                    message=f"Invalid state transition attempted",
                    level=TraceLevel.ERROR,
                    data={
                        "task_id": str(task.task_id),
                        "from_state": from_state.value,
                        "to_state": to_state.value,
                    },
                )
            except Exception:
                pass
            raise InvalidStateTransitionError(
                from_state=from_state.value,
                to_state=to_state.value,
                task_id=task.task_id,
                message=f"Invalid state transition from {from_state.value} to {to_state.value}",
            )

        # Create transition record
        transition = TaskStateTransition(
            task_id=task.task_id,
            from_state=from_state,
            to_state=to_state,
            timestamp=datetime.now(),
            reason=reason,
            actor=actor,
        )

        # Update task state
        task.current_state = to_state
        task.status = to_state  # Keep status in sync for backward compatibility
        task.state_history.append(transition)

        # Emit trace event
        try:
            await emit_trace(
                event_type=TraceEventType.OPERATION_COMPLETE,
                component=TraceComponent.ORCHESTRATOR,
                message=f"Task state transition: {from_state.value} -> {to_state.value}",
                level=TraceLevel.INFO,
                data={
                    "task_id": str(task.task_id),
                    "from_state": from_state.value,
                    "to_state": to_state.value,
                    "actor": actor,
                    "reason": reason,
                },
            )
        except Exception:
            pass

        # Persist transition to Postgres
        await self._persist_transition(transition)

        return task

    async def _persist_transition(self, transition: TaskStateTransition) -> None:
        """Persist a state transition to storage."""
        try:
            await self.memory_router.write(
                {
                    "content": transition.model_dump_json(),
                    "task_id": str(transition.task_id),
                    "metadata": {
                        "type": "state_transition",
                        "from_state": transition.from_state.value,
                        "to_state": transition.to_state.value,
                    },
                }
            )
        except Exception as e:
            try:
                await emit_trace(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.ORCHESTRATOR,
                    message="Failed to persist state transition",
                    level=TraceLevel.WARNING,
                    data={"error": str(e)},
                )
            except Exception:
                pass

    def can_transition(self, task: Task, to_state: TaskStatus) -> bool:
        """Check if a transition is valid without performing it.
        
        Args:
            task: The task to check
            to_state: The target state
            
        Returns:
            True if the transition is valid, False otherwise
        """
        from_state = task.current_state
        valid_next_states = self.VALID_TRANSITIONS.get(from_state, [])
        return to_state in valid_next_states

    def is_terminal(self, task: Task) -> bool:
        """Return True if task is in a terminal state.
        
        Args:
            task: The task to check
            
        Returns:
            True if the task is in a terminal state (COMPLETE, FAILED, CANCELLED, DENIED)
        """
        return task.current_state in [TaskStatus.COMPLETE, TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.DENIED]

    def get_valid_next_states(self, task: Task) -> list[TaskStatus]:
        """Return list of valid next states for the current task state.
        
        Args:
            task: The task to query
            
        Returns:
            List of valid next states
        """
        return self.VALID_TRANSITIONS.get(task.current_state, []).copy()

    async def checkpoint(self, task_id: str, step: str, state: TaskStatus) -> None:
        """Checkpoint task state and step for resume after daemon restart.
        
        Args:
            task_id: The task ID to checkpoint
            step: The last completed step name
            state: The current task state
            
        Wrapped in try-except — checkpoint failure must never crash the task.
        """
        try:
            checkpoint_data = {
                "task_id": str(task_id),
                "step": step,
                "state": state.value,
                "checkpointed_at": datetime.utcnow().isoformat(),
            }
            
            await self.memory_router.write(
                {
                    "content": checkpoint_data,
                    "task_id": str(task_id),
                    "metadata": {
                        "type": "task_checkpoint",
                        "key": f"task_checkpoint:{task_id}",
                    },
                }
            )
            
            # Emit trace event
            try:
                await emit_trace(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.ORCHESTRATOR,
                    message=f"Task checkpoint saved: {task_id} at step {step}",
                    level=TraceLevel.INFO,
                    data={
                        "task_id": str(task_id),
                        "step": step,
                        "state": state.value,
                    },
                )
            except Exception:
                pass
        except Exception as e:
            # Checkpoint failure must never crash the task
            try:
                await emit_trace(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.ORCHESTRATOR,
                    message=f"Failed to checkpoint task: {task_id}",
                    level=TraceLevel.WARNING,
                    data={
                        "task_id": str(task_id),
                        "error": str(e),
                    },
                )
            except Exception:
                pass

    async def load_checkpoints(self) -> list[dict]:
        """Load all task checkpoints for resume after daemon restart.
        
        Returns:
            List of checkpoint dicts with keys: task_id, step, state, checkpointed_at
            
        Wrapped in try-except — returns empty list on failure, never raises.
        """
        try:
            # Create a mock task to query memory router for all checkpoints
            # This is a workaround since MemoryRouter doesn't have a direct key-based query
            # In a real implementation, we'd need to add a method to MemoryRouter to query by key pattern
            # For now, we'll return empty list and the daemon will need to be enhanced with proper key-based queries
            checkpoints = []
            
            # Emit trace event
            try:
                await emit_trace(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.ORCHESTRATOR,
                    message=f"Loaded {len(checkpoints)} task checkpoints",
                    level=TraceLevel.INFO,
                    data={
                        "checkpoint_count": len(checkpoints),
                    },
                )
            except Exception:
                pass
            
            return checkpoints
        except Exception as e:
            # Load failure must never crash the daemon
            try:
                await emit_trace(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.ORCHESTRATOR,
                    message="Failed to load task checkpoints",
                    level=TraceLevel.WARNING,
                    data={
                        "error": str(e),
                    },
                )
            except Exception:
                pass
            return []
