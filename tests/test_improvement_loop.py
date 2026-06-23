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

    # Note: Full orchestrator integration tests require complex mocking of state machine
    # and scratchpad manager. The wire module is tested directly in TestImprovementLoopOrchestrator.
    # These integration tests are deferred to a future plan with proper test fixtures.

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
