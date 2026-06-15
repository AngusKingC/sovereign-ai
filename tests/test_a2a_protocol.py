"""Tests for A2A Protocol."""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from uuid import uuid4, UUID

from core.a2a_protocol import A2ARequest, A2AResponse, A2ARouter
from core.schemas import TaskPriority, WorkerOutput
from core.observability import MemoryTraceEmitter
from core.exceptions import CircularDependencyError


@pytest.mark.asyncio
class TestA2ARequest:
    """Tests for A2ARequest model."""

    async def test_a2a_request_constructs_with_required_fields_and_correct_defaults(self) -> None:
        """Test that A2ARequest constructs with required fields and correct defaults."""
        request = A2ARequest(
            input="test input",
            requester_agent_id="worker_1",
        )
        
        assert request.input == "test input"
        assert request.requester_agent_id == "worker_1"
        assert isinstance(request.task_id, UUID)
        assert request.metadata == {}
        assert request.parent_task_id is None
        assert request.priority == TaskPriority.NORMAL

    async def test_a2a_request_priority_defaults_to_task_priority_normal(self) -> None:
        """Test that A2ARequest.priority defaults to TaskPriority.NORMAL."""
        request = A2ARequest(
            input="test input",
            requester_agent_id="worker_1",
        )
        
        assert request.priority == TaskPriority.NORMAL

    async def test_a2a_request_parent_task_id_defaults_to_none(self) -> None:
        """Test that A2ARequest.parent_task_id defaults to None."""
        request = A2ARequest(
            input="test input",
            requester_agent_id="worker_1",
        )
        
        assert request.parent_task_id is None


@pytest.mark.asyncio
class TestA2AResponse:
    """Tests for A2AResponse model."""

    async def test_a2a_response_constructs_with_status_completed_and_output(self) -> None:
        """Test that A2AResponse constructs with status='completed' and output."""
        response = A2AResponse(
            task_id=uuid4(),
            status="completed",
            output="test output",
        )
        
        assert response.status == "completed"
        assert response.output == "test output"

    async def test_a2a_response_artifacts_defaults_to_empty_list(self) -> None:
        """Test that A2AResponse.artifacts defaults to empty list."""
        response = A2AResponse(
            task_id=uuid4(),
            status="completed",
        )
        
        assert response.artifacts == []
        assert response.metadata == {}


@pytest.mark.asyncio
class TestA2ARouter:
    """Tests for A2ARouter class."""

    async def test_a2a_router_submit_converts_request_to_task_and_routes_via_orchestrator(self) -> None:
        """Test that A2ARouter.submit() converts request to Task and routes via orchestrator."""
        emitter = MemoryTraceEmitter()
        mock_orchestrator = Mock()
        mock_orchestrator.route_task = AsyncMock()
        
        mock_output = WorkerOutput(
            task_id=uuid4(),
            worker_id="worker_1",
            content="test output",
            confidence=0.9,
            model_used="test_model",
        )
        mock_orchestrator.route_task.return_value = mock_output
        
        router = A2ARouter(mock_orchestrator, emitter=emitter)
        
        request = A2ARequest(
            input="test input",
            requester_agent_id="worker_1",
        )
        
        response = await router.submit(request)
        
        mock_orchestrator.route_task.assert_called_once()
        call_args = mock_orchestrator.route_task.call_args[0][0]
        assert call_args.intent == "test input"
        assert call_args.task_id == request.task_id

    async def test_a2a_router_submit_returns_response_with_status_completed_on_success(self) -> None:
        """Test that A2ARouter.submit() returns A2AResponse with status='completed' on success."""
        emitter = MemoryTraceEmitter()
        mock_orchestrator = Mock()
        mock_orchestrator.route_task = AsyncMock()
        
        mock_output = WorkerOutput(
            task_id=uuid4(),
            worker_id="worker_1",
            content="test output",
            confidence=0.9,
            model_used="test_model",
        )
        mock_orchestrator.route_task.return_value = mock_output
        
        router = A2ARouter(mock_orchestrator, emitter=emitter)
        
        request = A2ARequest(
            input="test input",
            requester_agent_id="worker_1",
        )
        
        response = await router.submit(request)
        
        assert response.status == "completed"
        assert response.output == "test output"

    async def test_a2a_router_submit_returns_response_with_status_failed_on_orchestrator_error(self) -> None:
        """Test that A2ARouter.submit() returns A2AResponse with status='failed' on orchestrator error."""
        emitter = MemoryTraceEmitter()
        mock_orchestrator = Mock()
        mock_orchestrator.route_task = AsyncMock(side_effect=Exception("orchestrator error"))
        
        router = A2ARouter(mock_orchestrator, emitter=emitter)
        
        request = A2ARequest(
            input="test input",
            requester_agent_id="worker_1",
        )
        
        response = await router.submit(request)
        
        assert response.status == "failed"
        assert "error" in response.metadata

    async def test_a2a_router_submit_emits_trace_event_on_submit(self) -> None:
        """Test that A2ARouter.submit() emits trace event on submit."""
        emitter = MemoryTraceEmitter()
        mock_orchestrator = Mock()
        mock_orchestrator.route_task = AsyncMock()
        
        mock_output = WorkerOutput(
            task_id=uuid4(),
            worker_id="worker_1",
            content="test output",
            confidence=0.9,
            model_used="test_model",
        )
        mock_orchestrator.route_task.return_value = mock_output
        
        router = A2ARouter(mock_orchestrator, emitter=emitter)
        
        request = A2ARequest(
            input="test input",
            requester_agent_id="worker_1",
        )
        
        await router.submit(request)
        
        events = emitter.get_events()
        submit_events = [e for e in events if e.event_type == "a2a_submit_started"]
        assert len(submit_events) > 0

    async def test_a2a_router_submit_emits_trace_event_on_completion(self) -> None:
        """Test that A2ARouter.submit() emits trace event on completion."""
        emitter = MemoryTraceEmitter()
        mock_orchestrator = Mock()
        mock_orchestrator.route_task = AsyncMock()
        
        mock_output = WorkerOutput(
            task_id=uuid4(),
            worker_id="worker_1",
            content="test output",
            confidence=0.9,
            model_used="test_model",
        )
        mock_orchestrator.route_task.return_value = mock_output
        
        router = A2ARouter(mock_orchestrator, emitter=emitter)
        
        request = A2ARequest(
            input="test input",
            requester_agent_id="worker_1",
        )
        
        await router.submit(request)
        
        events = emitter.get_events()
        complete_events = [e for e in events if e.event_type == "a2a_submit_completed"]
        assert len(complete_events) > 0

    async def test_a2a_router_submit_registers_child_task_under_parent_in_active_tasks(self) -> None:
        """Test that A2ARouter.submit() registers child task under parent in _active_tasks."""
        emitter = MemoryTraceEmitter()
        mock_orchestrator = Mock()
        mock_orchestrator.route_task = AsyncMock()
        
        mock_output = WorkerOutput(
            task_id=uuid4(),
            worker_id="worker_1",
            content="test output",
            confidence=0.9,
            model_used="test_model",
        )
        mock_orchestrator.route_task.return_value = mock_output
        
        router = A2ARouter(mock_orchestrator, emitter=emitter)
        
        parent_task_id = uuid4()
        request = A2ARequest(
            input="test input",
            requester_agent_id="worker_1",
            parent_task_id=parent_task_id,
        )
        
        await router.submit(request)
        
        children = await router.get_children(parent_task_id)
        assert request.task_id in children

    async def test_a2a_router_submit_raises_circular_dependency_error_when_circular_dependency_detected(self) -> None:
        """Test that A2ARouter.submit() raises CircularDependencyError when circular dependency detected."""
        emitter = MemoryTraceEmitter()
        mock_orchestrator = Mock()
        
        router = A2ARouter(mock_orchestrator, emitter=emitter)
        
        parent_task_id = uuid4()
        child_task_id = uuid4()
        
        # Register parent -> child
        router._active_tasks[parent_task_id] = {child_task_id}
        
        # Try to submit a task that would create a circular dependency
        request = A2ARequest(
            input="test input",
            requester_agent_id="worker_1",
            parent_task_id=child_task_id,
            task_id=parent_task_id,
        )
        
        with pytest.raises(CircularDependencyError):
            await router.submit(request)

    async def test_check_circular_returns_false_when_no_circular_dependency(self) -> None:
        """Test that _check_circular() returns False when no circular dependency."""
        emitter = MemoryTraceEmitter()
        mock_orchestrator = Mock()
        
        router = A2ARouter(mock_orchestrator, emitter=emitter)
        
        parent_task_id = uuid4()
        new_task_id = uuid4()
        
        result = router._check_circular(parent_task_id, new_task_id)
        assert result is False

    async def test_check_circular_returns_true_when_task_is_its_own_ancestor(self) -> None:
        """Test that _check_circular() returns True when task is its own ancestor."""
        emitter = MemoryTraceEmitter()
        mock_orchestrator = Mock()
        
        router = A2ARouter(mock_orchestrator, emitter=emitter)
        
        task_id = uuid4()
        
        result = router._check_circular(task_id, task_id)
        assert result is True

    async def test_get_children_returns_correct_list_of_child_task_ids(self) -> None:
        """Test that get_children() returns correct list of child task IDs."""
        emitter = MemoryTraceEmitter()
        mock_orchestrator = Mock()
        
        router = A2ARouter(mock_orchestrator, emitter=emitter)
        
        parent_task_id = uuid4()
        child1 = uuid4()
        child2 = uuid4()
        
        router._active_tasks[parent_task_id] = {child1, child2}
        
        children = await router.get_children(parent_task_id)
        assert child1 in children
        assert child2 in children
        assert len(children) == 2

    async def test_cancel_children_returns_correct_count_and_emits_trace_event(self) -> None:
        """Test that cancel_children() returns correct count and emits trace event."""
        emitter = MemoryTraceEmitter()
        mock_orchestrator = Mock()
        
        router = A2ARouter(mock_orchestrator, emitter=emitter)
        
        parent_task_id = uuid4()
        child1 = uuid4()
        child2 = uuid4()
        
        router._active_tasks[parent_task_id] = {child1, child2}
        
        count = await router.cancel_children(parent_task_id)
        
        assert count == 2
        assert parent_task_id not in router._active_tasks
        
        events = emitter.get_events()
        cancel_events = [e for e in events if e.event_type == "a2a_children_cancelled"]
        assert len(cancel_events) > 0

    async def test_sub_task_inherits_priority_from_a2a_request_priority(self) -> None:
        """Test that sub-task inherits priority from A2ARequest.priority."""
        emitter = MemoryTraceEmitter()
        mock_orchestrator = Mock()
        mock_orchestrator.route_task = AsyncMock()
        
        mock_output = WorkerOutput(
            task_id=uuid4(),
            worker_id="worker_1",
            content="test output",
            confidence=0.9,
            model_used="test_model",
        )
        mock_orchestrator.route_task.return_value = mock_output
        
        router = A2ARouter(mock_orchestrator, emitter=emitter)
        
        request = A2ARequest(
            input="test input",
            requester_agent_id="worker_1",
            priority=TaskPriority.HIGH,
        )
        
        await router.submit(request)
        
        call_args = mock_orchestrator.route_task.call_args[0][0]
        assert call_args.priority == TaskPriority.HIGH

    async def test_a2a_router_with_no_emitter_defaults_to_memory_trace_emitter(self) -> None:
        """Test that A2ARouter with no emitter defaults to MemoryTraceEmitter."""
        mock_orchestrator = Mock()
        mock_orchestrator.route_task = AsyncMock()
        
        mock_output = WorkerOutput(
            task_id=uuid4(),
            worker_id="worker_1",
            content="test output",
            confidence=0.9,
            model_used="test_model",
        )
        mock_orchestrator.route_task.return_value = mock_output
        
        router = A2ARouter(mock_orchestrator)
        
        assert isinstance(router._emitter, MemoryTraceEmitter)


@pytest.mark.asyncio
class TestOrchestratorA2AIntegration:
    """Tests for Orchestrator A2A integration."""

    async def test_orchestrator_submit_subtask_delegates_to_a2a_router_submit(self) -> None:
        """Test that Orchestrator submit_subtask() delegates to A2ARouter.submit()."""
        from core.orchestrator import Orchestrator
        from core.memory_router import MemoryRouter
        
        mock_memory_router = Mock(spec=MemoryRouter)
        mock_a2a_router = Mock()
        mock_a2a_router.submit = AsyncMock()
        
        mock_response = A2AResponse(
            task_id=uuid4(),
            status="completed",
            output="test output",
        )
        mock_a2a_router.submit.return_value = mock_response
        
        orchestrator = Orchestrator(
            memory_router=mock_memory_router,
            a2a_router=mock_a2a_router,
        )
        
        request = A2ARequest(
            input="test input",
            requester_agent_id="worker_1",
        )
        
        response = await orchestrator.submit_subtask(request)
        
        mock_a2a_router.submit.assert_called_once_with(request)
        assert response.status == "completed"

    async def test_orchestrator_submit_subtask_raises_runtime_error_when_a2a_router_is_none(self) -> None:
        """Test that Orchestrator submit_subtask() raises RuntimeError when a2a_router is None."""
        from core.orchestrator import Orchestrator
        from core.memory_router import MemoryRouter
        
        mock_memory_router = Mock(spec=MemoryRouter)
        
        orchestrator = Orchestrator(
            memory_router=mock_memory_router,
            a2a_router=None,
        )
        
        request = A2ARequest(
            input="test input",
            requester_agent_id="worker_1",
        )
        
        with pytest.raises(RuntimeError, match="A2A router not configured"):
            await orchestrator.submit_subtask(request)
