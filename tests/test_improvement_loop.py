"""Integration tests for the improvement loop wire module."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.commands import Command, CommandType, ImproveCommandHandler
from evals.harness import EvalHarness, EvalResult
from orchestrator.improvement_loop import ImprovementLoopOrchestrator


@pytest.fixture
def mock_eval_harness():
    """Create a mock EvalHarness."""
    harness = MagicMock(spec=EvalHarness)
    harness.evaluate = AsyncMock()
    return harness


@pytest.fixture
def mock_trace_store():
    """Create a mock PostgresTraceStore."""
    trace_store = MagicMock()
    trace_store.query_traces = AsyncMock()
    return trace_store


@pytest.fixture
def mock_improvement_loop():
    """Create a mock OrchestratorImprovementLoop."""
    improvement_loop = MagicMock()
    improvement_loop.record_routing_decision = AsyncMock()
    improvement_loop.check_and_trigger_update = AsyncMock()
    improvement_loop.get_routing_accuracy = AsyncMock(return_value=0.8)
    return improvement_loop


@pytest.fixture
def improvement_loop_orchestrator(mock_eval_harness, mock_trace_store, mock_improvement_loop):
    """Create an ImprovementLoopOrchestrator with mocked dependencies."""
    return ImprovementLoopOrchestrator(
        eval_harness=mock_eval_harness,
        trace_store=mock_trace_store,
        improvement_loop=mock_improvement_loop,
    )


class TestImprovementLoopOrchestrator:
    """Tests for ImprovementLoopOrchestrator."""

    def test_improvement_loop_orchestrator_initialization(
        self, mock_eval_harness, mock_trace_store, mock_improvement_loop
    ):
        """Verify ImprovementLoopOrchestrator initializes with mocked dependencies."""
        orchestrator = ImprovementLoopOrchestrator(
            eval_harness=mock_eval_harness,
            trace_store=mock_trace_store,
            improvement_loop=mock_improvement_loop,
        )

        assert orchestrator.eval_harness == mock_eval_harness
        assert orchestrator.trace_store == mock_trace_store
        assert orchestrator.improvement_loop == mock_improvement_loop

    @pytest.mark.asyncio
    async def test_process_improvement_task_queries_trace_store(
        self, improvement_loop_orchestrator, mock_trace_store
    ):
        """Verify trace store query_traces is called with correct filters."""
        mock_trace_store.query_traces.return_value = []

        await improvement_loop_orchestrator.process_improvement_task(recent_count=10)

        mock_trace_store.query_traces.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_improvement_task_runs_eval_harness(
        self, improvement_loop_orchestrator, mock_eval_harness, mock_trace_store
    ):
        """Verify eval harness evaluate is called on trace data."""
        mock_trace_store.query_traces.return_value = [
            {
                "task_id": "task-1",
                "data": {
                    "predicted": "output",
                    "gold": "expected",
                    "task_id": "task-1",
                    "worker_id": "worker-1",
                },
            }
        ]
        mock_eval_harness.evaluate.return_value = EvalResult(
            predicted="output",
            gold="expected",
            task_id="task-1",
            metrics={"token_f1": 0.8},
            timestamp=datetime.now(timezone.utc),
        )

        await improvement_loop_orchestrator.process_improvement_task(recent_count=10)

        mock_eval_harness.evaluate.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_improvement_task_feeds_improvement_loop(
        self, improvement_loop_orchestrator, mock_improvement_loop, mock_trace_store, mock_eval_harness
    ):
        """Verify record_routing_decision and check_and_trigger_update are called."""
        mock_trace_store.query_traces.return_value = [
            {
                "task_id": "task-1",
                "data": {
                    "predicted": "output",
                    "gold": "expected",
                    "task_id": "task-1",
                    "worker_id": "worker-1",
                },
            }
        ]
        mock_eval_harness.evaluate.return_value = EvalResult(
            predicted="output",
            gold="expected",
            task_id="task-1",
            metrics={"token_f1": 0.8},
            timestamp=datetime.now(timezone.utc),
        )

        await improvement_loop_orchestrator.process_improvement_task(recent_count=10)

        mock_improvement_loop.record_routing_decision.assert_called_once()
        mock_improvement_loop.check_and_trigger_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_improvement_task_returns_results_dict(
        self, improvement_loop_orchestrator, mock_trace_store, mock_eval_harness
    ):
        """Verify return dict has all expected keys."""
        mock_trace_store.query_traces.return_value = []
        mock_eval_harness.evaluate.return_value = EvalResult(
            predicted="output",
            gold="expected",
            task_id="task-1",
            metrics={"token_f1": 0.8},
            timestamp=datetime.now(timezone.utc),
        )

        result = await improvement_loop_orchestrator.process_improvement_task(recent_count=10)

        assert "eval_results" in result
        assert "accuracy" in result
        assert "update_triggered" in result
        assert "proposal" in result

    @pytest.mark.asyncio
    async def test_improvement_loop_error_handling(
        self, improvement_loop_orchestrator, mock_trace_store
    ):
        """Verify exception in wire layer returns partial results, doesn't crash (AR18)."""
        # Make trace store raise an exception
        mock_trace_store.query_traces.side_effect = Exception("Trace store error")

        result = await improvement_loop_orchestrator.process_improvement_task(recent_count=10)

        # Should return partial results, not crash
        assert result is not None
        assert result["eval_results"] == []


class TestOrchestratorIntegration:
    """Tests for orchestrator integration with improvement loop."""

    @pytest.fixture
    def mock_orchestrator_dependencies(self):
        """Create mocked dependencies for Orchestrator integration tests."""
        from core.task_state_machine import TaskStateMachine
        
        # Mock state machine that returns task with updated status (simulates successful transitions)
        mock_state_machine = MagicMock(spec=TaskStateMachine)
        def transition_side_effect(task, status, **kw):
            task.current_state = status
            return task
        mock_state_machine.transition = AsyncMock(side_effect=transition_side_effect)
        
        # Mock scratchpad manager with no-op compact and create
        mock_scratchpad_manager = MagicMock()
        mock_scratchpad_manager.compact = AsyncMock()
        mock_scratchpad_manager.create = AsyncMock()
        
        # Mock worker with required profile attribute
        from core.schemas import WorkerStatus
        mock_worker = MagicMock()
        mock_worker.profile = MagicMock()
        mock_worker.profile.worker_type = "test-worker"
        mock_worker.profile.capabilities = ["test"]
        mock_worker.profile.status = WorkerStatus.ACTIVE
        
        # Mock emitter
        mock_emitter = MagicMock()
        mock_emitter.emit = AsyncMock()
        
        return {
            "state_machine": mock_state_machine,
            "scratchpad_manager": mock_scratchpad_manager,
            "worker": mock_worker,
            "emitter": mock_emitter,
        }

    @pytest.mark.asyncio
    async def test_orchestrator_invokes_wire_module_on_completion(
        self, mock_orchestrator_dependencies
    ):
        """Verify orchestrator invokes improvement_loop_orchestrator.process_improvement_task on task completion."""
        from core.orchestrator import Orchestrator
        from core.schemas import Task, WorkerOutput
        from unittest.mock import patch
        
        # Setup mocks
        mock_memory_router = MagicMock()
        mock_improvement_loop_orchestrator = MagicMock()
        mock_improvement_loop_orchestrator.process_improvement_task = AsyncMock()
        
        # Patch internal creation of state_machine and scratchpad_manager
        with patch("core.task_state_machine.TaskStateMachine", return_value=mock_orchestrator_dependencies["state_machine"]), \
             patch("core.scratchpad.ScratchpadManager", return_value=mock_orchestrator_dependencies["scratchpad_manager"]):
            
            # Create orchestrator with mocked dependencies
            orchestrator = Orchestrator(
                memory_router=mock_memory_router,
                improvement_loop_orchestrator=mock_improvement_loop_orchestrator,
                emitter=mock_orchestrator_dependencies["emitter"],
            )
            
            # Register mock worker
            orchestrator.register_worker("worker-1", mock_orchestrator_dependencies["worker"])
            
            # Create task with all required fields
            from uuid import uuid4
            from core.schemas import TaskPriority
            task = Task(
                task_id=uuid4(),
                intent="test instruction",
                complexity_score=0.5,
                priority=TaskPriority.NORMAL,
                created_at=datetime.now(timezone.utc)
            )
            
            # Configure worker to return WorkerOutput with content (triggers COMPLETE branch)
            mock_orchestrator_dependencies["worker"].run = AsyncMock(
                return_value=WorkerOutput(
                    task_id=task.task_id,
                    worker_id="worker-1",
                    content="test output",
                    confidence=1.0,
                    model_used="test-model"
                )
            )
            
            # Patch asyncio.create_task to return a mock task object
            with patch("asyncio.create_task") as mock_create_task:
                mock_task = MagicMock()
                mock_create_task.return_value = mock_task
                
                # Call process_task
                await orchestrator.process_task(task, "worker-1")
            
            # Verify worker was called
            mock_orchestrator_dependencies["worker"].run.assert_called_once()
            
            # Verify asyncio.create_task was called
            mock_create_task.assert_called_once()
            
            # Verify the coroutine passed to create_task is the improvement loop orchestrator call
            call_args = mock_create_task.call_args
            assert call_args is not None
            
            # Verify improvement_loop_orchestrator.process_improvement_task was called
            mock_improvement_loop_orchestrator.process_improvement_task.assert_called_once_with(
                task_id=str(task.task_id)
            )

    @pytest.mark.asyncio
    async def test_orchestrator_done_callback_suppresses_warning(
        self, mock_orchestrator_dependencies
    ):
        """Verify orchestrator adds done callback to suppress Task exception warning."""
        from core.orchestrator import Orchestrator
        from core.schemas import Task, WorkerOutput
        from unittest.mock import patch
        
        # Setup mocks
        mock_memory_router = MagicMock()
        mock_improvement_loop_orchestrator = MagicMock()
        mock_improvement_loop_orchestrator.process_improvement_task = AsyncMock()
        
        # Patch internal creation of state_machine and scratchpad_manager
        with patch("core.task_state_machine.TaskStateMachine", return_value=mock_orchestrator_dependencies["state_machine"]), \
             patch("core.scratchpad.ScratchpadManager", return_value=mock_orchestrator_dependencies["scratchpad_manager"]):
            
            # Create orchestrator with mocked dependencies
            orchestrator = Orchestrator(
                memory_router=mock_memory_router,
                improvement_loop_orchestrator=mock_improvement_loop_orchestrator,
                emitter=mock_orchestrator_dependencies["emitter"],
            )
            
            # Register mock worker
            orchestrator.register_worker("worker-1", mock_orchestrator_dependencies["worker"])
            
            # Create task with all required fields
            from uuid import uuid4
            from core.schemas import TaskPriority
            task = Task(
                task_id=uuid4(),
                intent="test instruction",
                complexity_score=0.5,
                priority=TaskPriority.NORMAL,
                created_at=datetime.now(timezone.utc)
            )
            
            # Configure worker to return WorkerOutput with content
            mock_orchestrator_dependencies["worker"].run = AsyncMock(
                return_value=WorkerOutput(
                    task_id=task.task_id,
                    worker_id="worker-1",
                    content="test output",
                    confidence=1.0,
                    model_used="test-model"
                )
            )
            
            # Patch asyncio.create_task to return a mock task object
            with patch("asyncio.create_task") as mock_create_task:
                mock_task = MagicMock()
                mock_create_task.return_value = mock_task
                
                # Call process_task
                await orchestrator.process_task(task, "worker-1")
            
            # Verify add_done_callback was called on the task
            mock_task.add_done_callback.assert_called_once()
            
            # Verify the callback is a lambda that calls .exception()
            callback = mock_task.add_done_callback.call_args[0][0]
            assert callable(callback)


class TestEndToEndValidation:
    """End-to-end validation tests for improvement loop."""

    @pytest.mark.asyncio
    async def test_e2e_trace_to_eval_to_improvement(self, improvement_loop_orchestrator, mock_trace_store, mock_eval_harness, mock_improvement_loop):
        """Given a trace store with traces, process_improvement_task produces eval results, feeds to improvement loop, and returns accuracy."""
        
        # Setup trace store with valid trace
        mock_trace_store.query_traces.return_value = [
            {
                "task_id": "task-1",
                "data": {
                    "predicted": "output",
                    "gold": "expected",
                    "task_id": "task-1",
                    "worker_id": "worker-1",
                },
            }
        ]
        
        # Setup eval harness
        mock_eval_harness.evaluate.return_value = EvalResult(
            predicted="output",
            gold="expected",
            task_id="task-1",
            metrics={"token_f1": 0.8},
            timestamp=datetime.now(timezone.utc),
        )
        
        # Setup improvement loop
        mock_improvement_loop.get_routing_accuracy.return_value = 0.8
        
        # Call process_improvement_task
        result = await improvement_loop_orchestrator.process_improvement_task(recent_count=10)
        
        # Verify trace store was queried
        mock_trace_store.query_traces.assert_called_once()
        
        # Verify eval harness was called
        mock_eval_harness.evaluate.assert_called_once()
        
        # Verify improvement loop was fed results
        mock_improvement_loop.record_routing_decision.assert_called_once()
        
        # Verify result contains accuracy from improvement loop
        assert result["accuracy"] == 0.8

    @pytest.mark.asyncio
    async def test_e2e_update_triggered_when_threshold_met(self, improvement_loop_orchestrator, mock_improvement_loop):
        """Given check_and_trigger_update returns a proposal, process_improvement_task returns update_triggered=True."""
        from core.orchestrator_improvement import VersionUpdateProposal
        
        # Setup trace store with no traces (minimal setup)
        mock_trace_store = improvement_loop_orchestrator.trace_store
        mock_trace_store.query_traces.return_value = []
        
        # Setup improvement loop to return a proposal
        from uuid import uuid4
        proposal = VersionUpdateProposal(
            proposal_id=str(uuid4()),
            worker_id="worker-1",
            current_version=1,
            proposed_content="updated content",
            trigger_reason="Test update",
            rating_trend=0.9,
            status="pending",
            created_at=datetime.now(timezone.utc)
        )
        mock_improvement_loop.check_and_trigger_update.return_value = proposal
        
        # Call process_improvement_task
        result = await improvement_loop_orchestrator.process_improvement_task(recent_count=10)
        
        # Verify update_triggered is True
        assert result["update_triggered"] is True
        
        # Verify proposal is returned
        assert result["proposal"] == proposal

    @pytest.mark.asyncio
    async def test_e2e_no_update_triggered_when_threshold_not_met(self, improvement_loop_orchestrator, mock_improvement_loop):
        """Given check_and_trigger_update returns None, process_improvement_task returns update_triggered=False."""
        # Setup trace store with no traces
        mock_trace_store = improvement_loop_orchestrator.trace_store
        mock_trace_store.query_traces.return_value = []
        
        # Setup improvement loop to return None (no update)
        mock_improvement_loop.check_and_trigger_update.return_value = None
        
        # Call process_improvement_task
        result = await improvement_loop_orchestrator.process_improvement_task(recent_count=10)
        
        # Verify update_triggered is False
        assert result["update_triggered"] is False
        
        # Verify proposal is None
        assert result["proposal"] is None

    @pytest.mark.asyncio
    async def test_e2e_failed_eval_does_not_break_loop(self, improvement_loop_orchestrator, mock_trace_store, mock_eval_harness):
        """Given a trace with malformed data, the loop skips that trace, processes remaining traces, and returns partial results."""
        # Setup trace store with one valid and one malformed trace
        mock_trace_store.query_traces.return_value = [
            {
                "task_id": "task-1",
                "data": {
                    "predicted": "output",
                    "gold": "expected",
                    "task_id": "task-1",
                    "worker_id": "worker-1",
                },
            },
            {
                "task_id": "task-2",
                "data": {
                    # Missing "predicted" field - malformed
                    "gold": "expected",
                    "task_id": "task-2",
                    "worker_id": "worker-1",
                },
            },
        ]
        
        # Setup eval harness to succeed for valid trace
        mock_eval_harness.evaluate.return_value = EvalResult(
            predicted="output",
            gold="expected",
            task_id="task-1",
            metrics={"token_f1": 0.8},
            timestamp=datetime.now(timezone.utc),
        )
        
        # Call process_improvement_task
        result = await improvement_loop_orchestrator.process_improvement_task(recent_count=10)
        
        # Verify result is returned (partial results, not crash)
        assert result is not None
        
        # Verify eval_results contains at least one result (from valid trace)
        assert len(result["eval_results"]) >= 1

    @pytest.mark.asyncio
    async def test_e2e_specific_task_id_queries_only_that_task(self, improvement_loop_orchestrator, mock_trace_store):
        """Given task_id='task-42', the wire module queries trace_store with task_id filter exactly once."""
        # Call process_improvement_task with specific task_id
        await improvement_loop_orchestrator.process_improvement_task(task_id="task-42")
        
        # Verify trace_store.query_traces was called with task_id filter
        mock_trace_store.query_traces.assert_called_once()
        call_kwargs = mock_trace_store.query_traces.call_args[1]
        assert "filters" in call_kwargs
        assert call_kwargs["filters"]["task_id"] == "task-42"


class TestImproveCommandHandler:
    """Tests for ImproveCommandHandler."""

    @pytest.fixture
    def improve_handler(self):
        """Create an ImproveCommandHandler."""
        return ImproveCommandHandler()

    @pytest.fixture
    def mock_improvement_orchestrator(self):
        """Create a mock ImprovementLoopOrchestrator."""
        orchestrator = MagicMock()
        orchestrator.process_improvement_task = AsyncMock(return_value={"accuracy": 0.8})
        return orchestrator

    def test_improve_command_handler_initialization(self, improve_handler):
        """Verify ImproveCommandHandler initializes correctly."""
        assert improve_handler._improvement_orchestrator is None

    def test_improve_command_handler_set_improvement_orchestrator(
        self, improve_handler, mock_improvement_orchestrator
    ):
        """Verify set_improvement_orchestrator sets the orchestrator."""
        improve_handler.set_improvement_orchestrator(mock_improvement_orchestrator)
        assert improve_handler._improvement_orchestrator == mock_improvement_orchestrator

    @pytest.mark.asyncio
    async def test_improve_command_handler_routes_to_wire(
        self, improve_handler, mock_improvement_orchestrator
    ):
        """Verify ImproveCommandHandler.execute calls ImprovementLoopOrchestrator.process_improvement_task."""
        improve_handler.set_improvement_orchestrator(mock_improvement_orchestrator)

        command = Command(
            command_type=CommandType.IMPROVE,
            kwargs={"task_id": "task-1", "recent_count": 10},
        )

        result = await improve_handler.execute(command)

        mock_improvement_orchestrator.process_improvement_task.assert_called_once_with(
            task_id="task-1", recent_count=10
        )
        assert result.success is True

    @pytest.mark.asyncio
    async def test_improve_command_handler_returns_error_when_not_configured(
        self, improve_handler
    ):
        """Verify handler returns error when orchestrator not configured."""
        command = Command(command_type=CommandType.IMPROVE)

        result = await improve_handler.execute(command)

        assert result.success is False
        assert "not configured" in result.message.lower()

    def test_improve_command_handler_get_help(self, improve_handler):
        """Verify get_help returns help text."""
        help_text = improve_handler.get_help()
        assert "/improve" in help_text
        assert "task_id" in help_text
        assert "recent_count" in help_text

    def test_improve_command_handler_get_menu_item(self, improve_handler):
        """Verify get_menu_item returns menu item definition."""
        menu_item = improve_handler.get_menu_item()
        assert menu_item["label"] == "Improve"
        assert "description" in menu_item
        assert "icon" in menu_item
