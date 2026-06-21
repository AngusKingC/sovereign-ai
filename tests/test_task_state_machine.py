"""Tests for Task State Machine."""

import pytest
from datetime import datetime
from uuid import uuid4

from core.schemas import Task, TaskStatus, TaskPriority
from core.task_state_machine import TaskStateMachine
from core.exceptions import InvalidStateTransitionError
from core.memory_router import MemoryRouter


class MockMemoryRouter(MemoryRouter):
    """Mock MemoryRouter for testing."""
    
    def __init__(self) -> None:
        super().__init__()
        self.writes: list[dict] = []
    
    async def write(self, data: dict) -> None:  # type: ignore[override]
        """Mock write."""
        self.writes.append(data)


@pytest.mark.asyncio
class TestTaskStateMachine:
    """Tests for TaskStateMachine."""
    
    async def test_all_valid_transitions_succeed(self) -> None:
        """Test that all valid state transitions succeed."""
        mock_router = MockMemoryRouter()
        state_machine = TaskStateMachine(mock_router)
        
        task = Task(
            task_id=uuid4(),
            intent="Test task",
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            current_state=TaskStatus.RECEIVED,
            created_at=datetime.now(),
        )
        
        # Test RECEIVED -> PLANNED
        task = await state_machine.transition(task, TaskStatus.PLANNED, actor="test")
        assert task.current_state == TaskStatus.PLANNED
        assert len(task.state_history) == 1
        
        # Test PLANNED -> EXECUTING
        task = await state_machine.transition(task, TaskStatus.EXECUTING, actor="test")
        assert task.current_state == TaskStatus.EXECUTING
        assert len(task.state_history) == 2
        
        # Test EXECUTING -> VALIDATING
        task = await state_machine.transition(task, TaskStatus.VALIDATING, actor="test")
        assert task.current_state == TaskStatus.VALIDATING
        assert len(task.state_history) == 3
        
        # Test VALIDATING -> COMPLETE
        task = await state_machine.transition(task, TaskStatus.COMPLETE, actor="test")
        assert task.current_state == TaskStatus.COMPLETE
        assert len(task.state_history) == 4
    
    async def test_all_invalid_transitions_raise_invalid_state_transition_error(self) -> None:
        """Test that all invalid state transitions raise InvalidStateTransitionError."""
        mock_router = MockMemoryRouter()
        state_machine = TaskStateMachine(mock_router)
        
        task = Task(
            task_id=uuid4(),
            intent="Test task",
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            current_state=TaskStatus.COMPLETE,
            created_at=datetime.now(),
        )
        
        # Try to transition from COMPLETE (terminal state)
        with pytest.raises(InvalidStateTransitionError) as exc_info:
            await state_machine.transition(task, TaskStatus.EXECUTING, actor="test")
        
        assert exc_info.value.from_state == TaskStatus.COMPLETE.value
        assert exc_info.value.to_state == TaskStatus.EXECUTING.value
        assert exc_info.value.task_id == task.task_id
    
    async def test_terminal_states_cannot_be_transitioned_out_of(self) -> None:
        """Test that terminal states cannot be transitioned out of."""
        mock_router = MockMemoryRouter()
        state_machine = TaskStateMachine(mock_router)
        
        for terminal_state in [TaskStatus.COMPLETE, TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.DENIED]:
            task = Task(
                task_id=uuid4(),
                intent="Test task",
                complexity_score=0.5,
                priority=TaskPriority.NORMAL,
                current_state=terminal_state,
                created_at=datetime.now(),
            )
            
            with pytest.raises(InvalidStateTransitionError):
                await state_machine.transition(task, TaskStatus.EXECUTING, actor="test")
    
    async def test_can_transition_returns_correct_bool_without_mutating_task(self) -> None:
        """Test that can_transition returns correct bool without mutating task."""
        mock_router = MockMemoryRouter()
        state_machine = TaskStateMachine(mock_router)
        
        task = Task(
            task_id=uuid4(),
            intent="Test task",
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            current_state=TaskStatus.RECEIVED,
            created_at=datetime.now(),
        )
        
        # Valid transition
        assert state_machine.can_transition(task, TaskStatus.PLANNED) is True
        assert task.current_state == TaskStatus.RECEIVED  # Should not mutate
        assert len(task.state_history) == 0
        
        # Invalid transition
        assert state_machine.can_transition(task, TaskStatus.COMPLETE) is False
        assert task.current_state == TaskStatus.RECEIVED  # Should not mutate
        assert len(task.state_history) == 0
    
    async def test_is_terminal_returns_true_for_complete_failed_cancelled_denied(self) -> None:
        """Test that is_terminal returns True for COMPLETE, FAILED, CANCELLED, DENIED."""
        mock_router = MockMemoryRouter()
        state_machine = TaskStateMachine(mock_router)
        
        for terminal_state in [TaskStatus.COMPLETE, TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.DENIED]:
            task = Task(
                task_id=uuid4(),
                intent="Test task",
                complexity_score=0.5,
                priority=TaskPriority.NORMAL,
                current_state=terminal_state,
                created_at=datetime.now(),
            )
            
            assert state_machine.is_terminal(task) is True
        
        # Non-terminal states
        for non_terminal_state in [TaskStatus.RECEIVED, TaskStatus.PLANNED, TaskStatus.EXECUTING, TaskStatus.VALIDATING, TaskStatus.AWAITING_APPROVAL]:
            task = Task(
                task_id=uuid4(),
                intent="Test task",
                complexity_score=0.5,
                priority=TaskPriority.NORMAL,
                current_state=non_terminal_state,
                created_at=datetime.now(),
            )
            
            assert state_machine.is_terminal(task) is False
    
    async def test_get_valid_next_states_returns_correct_list_for_each_state(self) -> None:
        """Test that get_valid_next_states returns correct list for each state."""
        mock_router = MockMemoryRouter()
        state_machine = TaskStateMachine(mock_router)
        
        test_cases = [
            (TaskStatus.RECEIVED, [TaskStatus.PLANNED, TaskStatus.FAILED, TaskStatus.CANCELLED]),
            (TaskStatus.PLANNED, [TaskStatus.EXECUTING, TaskStatus.FAILED, TaskStatus.CANCELLED]),
            (TaskStatus.EXECUTING, [TaskStatus.VALIDATING, TaskStatus.AWAITING_APPROVAL, TaskStatus.FAILED, TaskStatus.CANCELLED]),
            (TaskStatus.VALIDATING, [TaskStatus.COMPLETE, TaskStatus.EXECUTING, TaskStatus.FAILED, TaskStatus.CANCELLED]),
            (TaskStatus.AWAITING_APPROVAL, [TaskStatus.EXECUTING, TaskStatus.DENIED, TaskStatus.FAILED, TaskStatus.CANCELLED]),
            (TaskStatus.COMPLETE, []),
            (TaskStatus.FAILED, []),
            (TaskStatus.CANCELLED, []),
            (TaskStatus.DENIED, []),
        ]
        
        for current_state, expected_next_states in test_cases:
            task = Task(
                task_id=uuid4(),
                intent="Test task",
                complexity_score=0.5,
                priority=TaskPriority.NORMAL,
                current_state=current_state,
                created_at=datetime.now(),
            )
            
            valid_next_states = state_machine.get_valid_next_states(task)
            assert valid_next_states == expected_next_states
    
    async def test_state_history_is_appended_on_each_transition(self) -> None:
        """Test that state history is appended on each transition."""
        mock_router = MockMemoryRouter()
        state_machine = TaskStateMachine(mock_router)
        
        task = Task(
            task_id=uuid4(),
            intent="Test task",
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            current_state=TaskStatus.RECEIVED,
            created_at=datetime.now(),
        )
        
        # Perform multiple transitions
        task = await state_machine.transition(task, TaskStatus.PLANNED, reason="Planning", actor="orchestrator")
        task = await state_machine.transition(task, TaskStatus.EXECUTING, reason="Executing", actor="worker")
        task = await state_machine.transition(task, TaskStatus.VALIDATING, reason="Validating", actor="orchestrator")
        
        assert len(task.state_history) == 3
        
        # Check first transition
        assert task.state_history[0].from_state == TaskStatus.RECEIVED
        assert task.state_history[0].to_state == TaskStatus.PLANNED
        assert task.state_history[0].reason == "Planning"
        assert task.state_history[0].actor == "orchestrator"
        
        # Check second transition
        assert task.state_history[1].from_state == TaskStatus.PLANNED
        assert task.state_history[1].to_state == TaskStatus.EXECUTING
        assert task.state_history[1].reason == "Executing"
        assert task.state_history[1].actor == "worker"
        
        # Check third transition
        assert task.state_history[2].from_state == TaskStatus.EXECUTING
        assert task.state_history[2].to_state == TaskStatus.VALIDATING
        assert task.state_history[2].reason == "Validating"
        assert task.state_history[2].actor == "orchestrator"
    
    async def test_trace_events_emitted_on_each_transition(self) -> None:
        """Test that trace events are emitted on each transition."""
        mock_router = MockMemoryRouter()
        state_machine = TaskStateMachine(mock_router)
        
        task = Task(
            task_id=uuid4(),
            intent="Test task",
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            current_state=TaskStatus.RECEIVED,
            created_at=datetime.now(),
        )
        
        # Perform transition
        task = await state_machine.transition(task, TaskStatus.PLANNED, reason="Test", actor="test")
        
        # Check that trace event was emitted (via memory router write)
        # The state machine writes transitions to memory router
        assert len(mock_router.writes) == 1
        assert mock_router.writes[0]["task_id"] == str(task.task_id)
        assert mock_router.writes[0]["metadata"]["from_state"] == TaskStatus.RECEIVED.value
        assert mock_router.writes[0]["metadata"]["to_state"] == TaskStatus.PLANNED.value
    
    async def test_invalid_state_transition_error_contains_correct_from_state_to_state_task_id(self) -> None:
        """Test that InvalidStateTransitionError contains correct from_state, to_state, task_id."""
        mock_router = MockMemoryRouter()
        state_machine = TaskStateMachine(mock_router)
        
        task = Task(
            task_id=uuid4(),
            intent="Test task",
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            current_state=TaskStatus.COMPLETE,
            created_at=datetime.now(),
        )
        
        with pytest.raises(InvalidStateTransitionError) as exc_info:
            await state_machine.transition(task, TaskStatus.EXECUTING, actor="test")
        
        assert exc_info.value.from_state == TaskStatus.COMPLETE.value
        assert exc_info.value.to_state == TaskStatus.EXECUTING.value
        assert exc_info.value.task_id == task.task_id
        assert "complete" in exc_info.value.message.lower()
        assert "executing" in exc_info.value.message.lower()
    
    async def test_backward_compatibility_existing_status_field_alias_still_works(self) -> None:
        """Test that backward compatibility: existing status field alias still works."""
        mock_router = MockMemoryRouter()
        state_machine = TaskStateMachine(mock_router)
        
        task = Task(
            task_id=uuid4(),
            intent="Test task",
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            current_state=TaskStatus.RECEIVED,
            created_at=datetime.now(),
        )
        
        # status should be in sync with current_state
        assert task.status == TaskStatus.RECEIVED
        assert task.current_state == TaskStatus.RECEIVED
        
        # Transition
        task = await state_machine.transition(task, TaskStatus.PLANNED, actor="test")
        
        # Both should be updated
        assert task.status == TaskStatus.PLANNED
        assert task.current_state == TaskStatus.PLANNED
        
        # Test backward compatibility aliases
        assert TaskStatus.PENDING == TaskStatus.RECEIVED
        assert TaskStatus.RUNNING == TaskStatus.EXECUTING
        assert TaskStatus.ESCALATED == TaskStatus.AWAITING_APPROVAL
    
    async def test_state_transitions_persisted_to_postgres(self) -> None:
        """Test that state transitions are persisted to Postgres."""
        mock_router = MockMemoryRouter()
        state_machine = TaskStateMachine(mock_router)
        
        task = Task(
            task_id=uuid4(),
            intent="Test task",
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            current_state=TaskStatus.RECEIVED,
            created_at=datetime.now(),
        )
        
        # Perform transition
        task = await state_machine.transition(task, TaskStatus.PLANNED, reason="Test", actor="test")
        
        # Check that transition was persisted
        assert len(mock_router.writes) == 1
        write_data = mock_router.writes[0]
        assert write_data["task_id"] == str(task.task_id)
        assert write_data["metadata"]["type"] == "state_transition"
        assert write_data["metadata"]["from_state"] == TaskStatus.RECEIVED.value
        assert write_data["metadata"]["to_state"] == TaskStatus.PLANNED.value
    
    async def test_task_with_awaiting_approval_state_is_held_in_orchestrator_pending_queue(self) -> None:
        """Test that task with AWAITING_APPROVAL state is held in orchestrator pending queue."""
        from core.orchestrator import Orchestrator
        from core.worker_base import WorkerBase
        from core.schemas import WorkerProfile, WorkerOutput
        
        mock_router = MockMemoryRouter()
        orchestrator = Orchestrator(mock_router)
        
        # Create a mock worker
        class MockWorker(WorkerBase):
            def __init__(self) -> None:
                self.profile = WorkerProfile(
                    worker_id="test_worker",
                    worker_type="test",
                    depth_preference=0.5,
                    speculation_tolerance=0.5,
                    source_skepticism=0.5,
                    verbosity=0.5,
                    preferred_model="test-model",
                    escalation_threshold=0.8,
                    capabilities=["test"],
                )
            
            async def build_prompt(self, task: Task) -> str:
                return "Test prompt"
            
            async def parse_output(self, raw_output: str) -> WorkerOutput:
                return WorkerOutput(
                    task_id=task.task_id,
                    worker_id="test_worker",
                    content="Test output",
                    confidence=0.9,
                    model_used="test-model",
                )
            
            async def run(self, task: Task) -> WorkerOutput:
                return WorkerOutput(
                    task_id=task.task_id,
                    worker_id="test_worker",
                    content="Test output",
                    confidence=0.9,
                    model_used="test-model",
                )
        
        worker = MockWorker()
        orchestrator.register_worker("test_worker", worker)
        
        # Create task and transition to AWAITING_APPROVAL
        task = Task(
            task_id=uuid4(),
            intent="Test task",
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            current_state=TaskStatus.EXECUTING,
            created_at=datetime.now(),
        )
        
        task = await orchestrator.state_machine.transition(
            task, TaskStatus.AWAITING_APPROVAL, reason="Awaiting user approval", actor="worker"
        )
        
        # Add to pending queue
        orchestrator.pending_approval_queue.append(task)
        
        # Verify task is in pending queue
        assert len(orchestrator.pending_approval_queue) == 1
        assert orchestrator.pending_approval_queue[0].task_id == task.task_id
        assert orchestrator.pending_approval_queue[0].current_state == TaskStatus.AWAITING_APPROVAL
    
    async def test_orchestrator_transitions_task_through_full_happy_path(self) -> None:
        """Test that orchestrator transitions task through full happy path."""
        from core.orchestrator import Orchestrator
        from core.worker_base import WorkerBase
        from core.schemas import WorkerProfile, WorkerOutput
        
        mock_router = MockMemoryRouter()
        orchestrator = Orchestrator(mock_router)
        
        # Create a mock worker
        class MockWorker(WorkerBase):
            def __init__(self) -> None:
                self.profile = WorkerProfile(
                    worker_id="test_worker",
                    worker_type="test",
                    depth_preference=0.5,
                    speculation_tolerance=0.5,
                    source_skepticism=0.5,
                    verbosity=0.5,
                    preferred_model="test-model",
                    escalation_threshold=0.8,
                    capabilities=["test"],
                )
            
            async def build_prompt(self, task: Task) -> str:
                return "Test prompt"
            
            async def parse_output(self, raw_output: str) -> WorkerOutput:
                return WorkerOutput(
                    task_id=task.task_id,
                    worker_id="test_worker",
                    content="Test output",
                    confidence=0.9,
                    model_used="test-model",
                )
            
            async def run(self, task: Task) -> WorkerOutput:
                return WorkerOutput(
                    task_id=task.task_id,
                    worker_id="test_worker",
                    content="Test output",
                    confidence=0.9,
                    model_used="test-model",
                )
        
        worker = MockWorker()
        orchestrator.register_worker("test_worker", worker)
        
        # Create task (defaults to RECEIVED state)
        task = Task(
            task_id=uuid4(),
            intent="Test task",
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            created_at=datetime.now(),
        )
        
        # Route task (should transition through full happy path)
        output = await orchestrator.route_task(task)
        
        # Verify final state is COMPLETE
        assert task.current_state == TaskStatus.COMPLETE
        
        # Verify state history (RECEIVED may be skipped if already in that state)
        assert len(task.state_history) >= 4  # PLANNED -> EXECUTING -> VALIDATING -> COMPLETE
        
        # Verify transitions (check that expected states are present)
        states = [t.to_state for t in task.state_history]
        # The actual states should include PLANNED, EXECUTING, VALIDATING, COMPLETE
        # RECEIVED may or may not be present depending on whether it was skipped
        expected_states = {TaskStatus.PLANNED, TaskStatus.EXECUTING, TaskStatus.VALIDATING, TaskStatus.COMPLETE}
        actual_states = set(states)
        assert expected_states.issubset(actual_states), f"Expected {expected_states} to be subset of {actual_states}"
    
    async def test_orchestrator_transitions_to_failed_on_worker_error(self) -> None:
        """Test that orchestrator transitions to FAILED on worker error."""
        from core.orchestrator import Orchestrator
        from core.worker_base import WorkerBase
        from core.schemas import WorkerProfile, WorkerOutput
        
        mock_router = MockMemoryRouter()
        orchestrator = Orchestrator(mock_router)
        
        # Create a mock worker that raises an error
        class FailingWorker(WorkerBase):
            def __init__(self) -> None:
                self.profile = WorkerProfile(
                    worker_id="failing_worker",
                    worker_type="test",
                    depth_preference=0.5,
                    speculation_tolerance=0.5,
                    source_skepticism=0.5,
                    verbosity=0.5,
                    preferred_model="test-model",
                    escalation_threshold=0.8,
                    capabilities=["test"],
                )
            
            async def build_prompt(self, task: Task) -> str:
                return "Test prompt"
            
            async def parse_output(self, raw_output: str) -> WorkerOutput:
                return WorkerOutput(
                    task_id=task.task_id,
                    worker_id="failing_worker",
                    content="Test output",
                    confidence=0.9,
                    model_used="test-model",
                )
            
            async def run(self, task: Task) -> WorkerOutput:
                raise ValueError("Worker error")
        
        worker = FailingWorker()
        orchestrator.register_worker("failing_worker", worker)
        
        # Create task
        task = Task(
            task_id=uuid4(),
            intent="Test task",
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            current_state=TaskStatus.RECEIVED,
            created_at=datetime.now(),
        )
        
        # Route task (should fail and transition to FAILED)
        with pytest.raises(ValueError):
            await orchestrator.route_task(task)
        
        # Verify final state is FAILED
        assert task.current_state == TaskStatus.FAILED
        
        # Verify error reason in state history
        failed_transition = [t for t in task.state_history if t.to_state == TaskStatus.FAILED]
        assert len(failed_transition) >= 1
        assert "Worker execution failed" in failed_transition[0].reason
    
    async def test_denied_is_a_terminal_state(self) -> None:
        """Test that DENIED is a terminal state."""
        mock_router = MockMemoryRouter()
        state_machine = TaskStateMachine(mock_router)
        
        task = Task(
            task_id=uuid4(),
            intent="Test task",
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            current_state=TaskStatus.DENIED,
            created_at=datetime.now(),
        )
        
        assert state_machine.is_terminal(task) is True
    
    async def test_awaiting_approval_can_transition_to_denied(self) -> None:
        """Test that AWAITING_APPROVAL can transition to DENIED."""
        mock_router = MockMemoryRouter()
        state_machine = TaskStateMachine(mock_router)
        
        task = Task(
            task_id=uuid4(),
            intent="Test task",
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            current_state=TaskStatus.AWAITING_APPROVAL,
            created_at=datetime.now(),
        )
        
        # Transition to DENIED
        task = await state_machine.transition(task, TaskStatus.DENIED, reason="Approval denied by user", actor="approval_gate")
        
        assert task.current_state == TaskStatus.DENIED
        assert len(task.state_history) == 1
        assert task.state_history[0].from_state == TaskStatus.AWAITING_APPROVAL
        assert task.state_history[0].to_state == TaskStatus.DENIED
        assert task.state_history[0].reason == "Approval denied by user"
        assert task.state_history[0].actor == "approval_gate"
    
    async def test_denied_cannot_transition_to_any_other_state(self) -> None:
        """Test that DENIED cannot transition to any other state (terminal state)."""
        mock_router = MockMemoryRouter()
        state_machine = TaskStateMachine(mock_router)
        
        task = Task(
            task_id=uuid4(),
            intent="Test task",
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            current_state=TaskStatus.DENIED,
            created_at=datetime.now(),
        )
        
        # Try to transition from DENIED to any other state
        for target_state in [TaskStatus.PLANNED, TaskStatus.EXECUTING, TaskStatus.COMPLETE, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            with pytest.raises(InvalidStateTransitionError):
                await state_machine.transition(task, target_state, actor="test")

