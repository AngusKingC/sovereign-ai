"""Tests for Multi-Worker Dispatcher."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.multi_worker import MultiWorkerDispatcher, MultiWorkerResult, WorkerResponse
from core.observability import MemoryTraceEmitter


@pytest.mark.asyncio
class TestMultiWorkerSchemas:
    """Tests for multi-worker Pydantic schemas."""

    async def test_worker_response_schema_validation(self) -> None:
        """Test WorkerResponse schema validation."""
        response = WorkerResponse(
            worker_id="worker_1",
            response="Test response",
            duration_ms=100.0,
            succeeded=True,
        )

        assert response.worker_id == "worker_1"
        assert response.response == "Test response"
        assert response.error is None
        assert response.duration_ms == 100.0
        assert response.succeeded is True

    async def test_worker_response_with_error(self) -> None:
        """Test WorkerResponse with error."""
        response = WorkerResponse(
            worker_id="worker_1",
            error="Worker failed",
            duration_ms=50.0,
            succeeded=False,
        )

        assert response.worker_id == "worker_1"
        assert response.response is None
        assert response.error == "Worker failed"
        assert response.succeeded is False

    async def test_multi_worker_result_schema_validation(self) -> None:
        """Test MultiWorkerResult schema validation."""
        responses = [
            WorkerResponse(
                worker_id="worker_1",
                response="Response 1",
                duration_ms=100.0,
                succeeded=True,
            ),
            WorkerResponse(
                worker_id="worker_2",
                response="Response 2",
                duration_ms=150.0,
                succeeded=True,
            ),
        ]

        result = MultiWorkerResult(
            task="Test task",
            mode="parallel",
            responses=responses,
        )

        assert result.task == "Test task"
        assert result.mode == "parallel"
        assert len(result.responses) == 2
        assert result.winner_worker_id is None
        assert isinstance(result.result_id, str)
        assert isinstance(result.created_at, datetime)


@pytest.mark.asyncio
class TestMultiWorkerDispatcher:
    """Tests for MultiWorkerDispatcher class."""

    async def test_dispatch_queries_orchestrator_when_worker_ids_none(self) -> None:
        """Test dispatch() queries orchestrator for top-N candidates when worker_ids is None."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.get_top_candidates = AsyncMock(
            return_value=["worker_1", "worker_2"]
        )
        mock_orchestrator.workers = {}
        mock_orchestrator.adapter = MagicMock()

        mock_resource_budget = MagicMock()
        mock_resource_budget.check_all_budgets = AsyncMock(return_value=True)

        mock_rating_system = MagicMock()
        mock_rating_system.record_rating = AsyncMock()

        emitter = MemoryTraceEmitter()

        dispatcher = MultiWorkerDispatcher(
            orchestrator=mock_orchestrator,
            resource_budget=mock_resource_budget,
            rating_system=mock_rating_system,
            emitter=emitter,
        )

        # Create mock workers
        mock_worker_1 = MagicMock()
        mock_worker_1.execute = AsyncMock(return_value="Response 1")
        mock_worker_1.adapter = MagicMock()

        mock_worker_2 = MagicMock()
        mock_worker_2.execute = AsyncMock(return_value="Response 2")
        mock_worker_2.adapter = MagicMock()

        mock_orchestrator.workers = {
            "worker_1": mock_worker_1,
            "worker_2": mock_worker_2,
        }

        await dispatcher.dispatch("Test task", worker_ids=None, mode="parallel")

        mock_orchestrator.get_top_candidates.assert_called_once_with("Test task", 3)

    async def test_dispatch_uses_provided_worker_ids(self) -> None:
        """Test dispatch() uses provided worker_ids when given."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.get_top_candidates = AsyncMock()
        mock_orchestrator.workers = {}
        mock_orchestrator.adapter = MagicMock()

        mock_resource_budget = MagicMock()
        mock_resource_budget.check_all_budgets = AsyncMock(return_value=True)

        mock_rating_system = MagicMock()
        mock_rating_system.record_rating = AsyncMock()

        emitter = MemoryTraceEmitter()

        dispatcher = MultiWorkerDispatcher(
            orchestrator=mock_orchestrator,
            resource_budget=mock_resource_budget,
            rating_system=mock_rating_system,
            emitter=emitter,
        )

        # Create mock workers
        mock_worker_1 = MagicMock()
        mock_worker_1.execute = AsyncMock(return_value="Response 1")
        mock_worker_1.adapter = MagicMock()

        mock_worker_2 = MagicMock()
        mock_worker_2.execute = AsyncMock(return_value="Response 2")
        mock_worker_2.adapter = MagicMock()

        mock_orchestrator.workers = {
            "worker_1": mock_worker_1,
            "worker_2": mock_worker_2,
        }

        await dispatcher.dispatch(
            "Test task", worker_ids=["worker_1", "worker_2"], mode="parallel"
        )

        # Should NOT call get_top_candidates when worker_ids is provided
        mock_orchestrator.get_top_candidates.assert_not_called()

    async def test_dispatch_drops_workers_that_fail_budget_check(self) -> None:
        """Test dispatch() drops workers that fail resource budget check."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.workers = {}
        mock_orchestrator.adapter = MagicMock()

        mock_resource_budget = MagicMock()
        # Worker 1 passes, worker 2 fails
        mock_resource_budget.check_all_budgets = AsyncMock(
            side_effect=lambda wid: wid == "worker_1"
        )

        mock_rating_system = MagicMock()
        mock_rating_system.record_rating = AsyncMock()

        emitter = MemoryTraceEmitter()

        dispatcher = MultiWorkerDispatcher(
            orchestrator=mock_orchestrator,
            resource_budget=mock_resource_budget,
            rating_system=mock_rating_system,
            emitter=emitter,
        )

        # Create mock workers
        mock_worker_1 = MagicMock()
        mock_worker_1.execute = AsyncMock(return_value="Response 1")
        mock_worker_1.adapter = MagicMock()

        mock_worker_2 = MagicMock()
        mock_worker_2.execute = AsyncMock(return_value="Response 2")
        mock_worker_2.adapter = MagicMock()

        mock_orchestrator.workers = {
            "worker_1": mock_worker_1,
            "worker_2": mock_worker_2,
        }

        result = await dispatcher.dispatch(
            "Test task", worker_ids=["worker_1", "worker_2"], mode="parallel"
        )

        # Only worker_1 should have been dispatched
        assert len(result.responses) == 1
        assert result.responses[0].worker_id == "worker_1"

    async def test_dispatch_raises_runtime_error_when_all_fail_budget(self) -> None:
        """Test dispatch() raises RuntimeError when all workers fail budget check."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.workers = {}
        mock_orchestrator.adapter = MagicMock()

        mock_resource_budget = MagicMock()
        mock_resource_budget.check_all_budgets = AsyncMock(return_value=False)

        mock_rating_system = MagicMock()
        mock_rating_system.record_rating = AsyncMock()

        emitter = MemoryTraceEmitter()

        dispatcher = MultiWorkerDispatcher(
            orchestrator=mock_orchestrator,
            resource_budget=mock_resource_budget,
            rating_system=mock_rating_system,
            emitter=emitter,
        )

        # Create mock workers
        mock_worker_1 = MagicMock()
        mock_worker_1.adapter = MagicMock()

        mock_worker_2 = MagicMock()
        mock_worker_2.adapter = MagicMock()

        mock_orchestrator.workers = {
            "worker_1": mock_worker_1,
            "worker_2": mock_worker_2,
        }

        with pytest.raises(RuntimeError, match="No workers within resource budget"):
            await dispatcher.dispatch(
                "Test task", worker_ids=["worker_1", "worker_2"], mode="parallel"
            )

    async def test_dispatch_raises_value_error_for_unknown_mode(self) -> None:
        """Test dispatch() raises ValueError for unknown mode string."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.workers = {}
        mock_orchestrator.adapter = MagicMock()

        mock_resource_budget = MagicMock()
        mock_resource_budget.check_all_budgets = AsyncMock(return_value=True)

        mock_rating_system = MagicMock()
        mock_rating_system.record_rating = AsyncMock()

        emitter = MemoryTraceEmitter()

        dispatcher = MultiWorkerDispatcher(
            orchestrator=mock_orchestrator,
            resource_budget=mock_resource_budget,
            rating_system=mock_rating_system,
            emitter=emitter,
        )

        with pytest.raises(ValueError, match="Invalid mode"):
            await dispatcher.dispatch("Test task", mode="invalid_mode")

    async def test_parallel_all_workers_receive_original_task(self) -> None:
        """Test parallel mode: all workers receive the original unmodified task."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.workers = {}
        mock_orchestrator.adapter = MagicMock()

        mock_resource_budget = MagicMock()
        mock_resource_budget.check_all_budgets = AsyncMock(return_value=True)

        mock_rating_system = MagicMock()
        mock_rating_system.record_rating = AsyncMock()

        emitter = MemoryTraceEmitter()

        dispatcher = MultiWorkerDispatcher(
            orchestrator=mock_orchestrator,
            resource_budget=mock_resource_budget,
            rating_system=mock_rating_system,
            emitter=emitter,
        )

        # Create mock workers
        mock_worker_1 = MagicMock()
        mock_worker_1.execute = AsyncMock(return_value="Response 1")
        mock_worker_1.adapter = MagicMock()

        mock_worker_2 = MagicMock()
        mock_worker_2.execute = AsyncMock(return_value="Response 2")
        mock_worker_2.adapter = MagicMock()

        mock_orchestrator.workers = {
            "worker_1": mock_worker_1,
            "worker_2": mock_worker_2,
        }

        task = "Original task"
        await dispatcher.dispatch(
            task, worker_ids=["worker_1", "worker_2"], mode="parallel"
        )

        # Both workers should receive the original task
        mock_worker_1.execute.assert_called_once_with(task)
        mock_worker_2.execute.assert_called_once_with(task)

    async def test_parallel_records_failed_worker_without_aborting_others(self) -> None:
        """Test parallel mode: records failed worker without aborting others."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.workers = {}
        mock_orchestrator.adapter = MagicMock()

        mock_resource_budget = MagicMock()
        mock_resource_budget.check_all_budgets = AsyncMock(return_value=True)

        mock_rating_system = MagicMock()
        mock_rating_system.record_rating = AsyncMock()

        emitter = MemoryTraceEmitter()

        dispatcher = MultiWorkerDispatcher(
            orchestrator=mock_orchestrator,
            resource_budget=mock_resource_budget,
            rating_system=mock_rating_system,
            emitter=emitter,
        )

        # Create mock workers - worker_1 fails, worker_2 succeeds
        mock_worker_1 = MagicMock()
        mock_worker_1.execute = AsyncMock(side_effect=Exception("Worker failed"))
        mock_worker_1.adapter = MagicMock()

        mock_worker_2 = MagicMock()
        mock_worker_2.execute = AsyncMock(return_value="Response 2")
        mock_worker_2.adapter = MagicMock()

        mock_orchestrator.workers = {
            "worker_1": mock_worker_1,
            "worker_2": mock_worker_2,
        }

        result = await dispatcher.dispatch(
            "Test task", worker_ids=["worker_1", "worker_2"], mode="parallel"
        )

        # Both workers should have responses
        assert len(result.responses) == 2
        assert result.responses[0].succeeded is False
        assert result.responses[1].succeeded is True

    async def test_parallel_returns_multi_worker_result_with_correct_fields(
        self,
    ) -> None:
        """Test parallel mode: returns MultiWorkerResult with correct fields."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.workers = {}
        mock_orchestrator.adapter = MagicMock()

        mock_resource_budget = MagicMock()
        mock_resource_budget.check_all_budgets = AsyncMock(return_value=True)

        mock_rating_system = MagicMock()
        mock_rating_system.record_rating = AsyncMock()

        emitter = MemoryTraceEmitter()

        dispatcher = MultiWorkerDispatcher(
            orchestrator=mock_orchestrator,
            resource_budget=mock_resource_budget,
            rating_system=mock_rating_system,
            emitter=emitter,
        )

        # Create mock workers
        mock_worker_1 = MagicMock()
        mock_worker_1.execute = AsyncMock(return_value="Response 1")
        mock_worker_1.adapter = MagicMock()

        mock_orchestrator.workers = {
            "worker_1": mock_worker_1,
        }

        result = await dispatcher.dispatch(
            "Test task", worker_ids=["worker_1"], mode="parallel"
        )

        assert isinstance(result, MultiWorkerResult)
        assert result.task == "Test task"
        assert result.mode == "parallel"
        assert len(result.responses) == 1
        assert result.winner_worker_id is None
        assert isinstance(result.result_id, str)
        assert isinstance(result.created_at, datetime)

    async def test_sequential_workers_run_one_at_a_time(self) -> None:
        """Test sequential mode: workers run one at a time (verify ordering)."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.workers = {}
        mock_orchestrator.adapter = MagicMock()

        mock_resource_budget = MagicMock()
        mock_resource_budget.check_all_budgets = AsyncMock(return_value=True)

        mock_rating_system = MagicMock()
        mock_rating_system.record_rating = AsyncMock()

        emitter = MemoryTraceEmitter()

        dispatcher = MultiWorkerDispatcher(
            orchestrator=mock_orchestrator,
            resource_budget=mock_resource_budget,
            rating_system=mock_rating_system,
            emitter=emitter,
        )

        # Create mock workers with tracking
        execution_order = []

        async def track_execution_1(task):
            execution_order.append("worker_1")
            return "Response 1"

        async def track_execution_2(task):
            execution_order.append("worker_2")
            return "Response 2"

        mock_worker_1 = MagicMock()
        mock_worker_1.execute = AsyncMock(side_effect=track_execution_1)
        mock_worker_1.adapter = MagicMock()

        mock_worker_2 = MagicMock()
        mock_worker_2.execute = AsyncMock(side_effect=track_execution_2)
        mock_worker_2.adapter = MagicMock()

        mock_orchestrator.workers = {
            "worker_1": mock_worker_1,
            "worker_2": mock_worker_2,
        }

        await dispatcher.dispatch(
            "Test task", worker_ids=["worker_1", "worker_2"], mode="sequential"
        )

        # Workers should run in order
        assert execution_order == ["worker_1", "worker_2"]

    async def test_sequential_each_worker_receives_original_task(self) -> None:
        """Test sequential mode: each worker receives the original unmodified task."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.workers = {}
        mock_orchestrator.adapter = MagicMock()

        mock_resource_budget = MagicMock()
        mock_resource_budget.check_all_budgets = AsyncMock(return_value=True)

        mock_rating_system = MagicMock()
        mock_rating_system.record_rating = AsyncMock()

        emitter = MemoryTraceEmitter()

        dispatcher = MultiWorkerDispatcher(
            orchestrator=mock_orchestrator,
            resource_budget=mock_resource_budget,
            rating_system=mock_rating_system,
            emitter=emitter,
        )

        # Create mock workers
        mock_worker_1 = MagicMock()
        mock_worker_1.execute = AsyncMock(return_value="Response 1")
        mock_worker_1.adapter = MagicMock()

        mock_worker_2 = MagicMock()
        mock_worker_2.execute = AsyncMock(return_value="Response 2")
        mock_worker_2.adapter = MagicMock()

        mock_orchestrator.workers = {
            "worker_1": mock_worker_1,
            "worker_2": mock_worker_2,
        }

        task = "Original task"
        await dispatcher.dispatch(
            task, worker_ids=["worker_1", "worker_2"], mode="sequential"
        )

        # Both workers should receive the original task
        mock_worker_1.execute.assert_called_once_with(task)
        mock_worker_2.execute.assert_called_once_with(task)

    async def test_sequential_ensure_model_called_before_each_worker(self) -> None:
        """Test sequential mode: ensure_model called before each worker when resource_manager is set."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.workers = {}
        mock_orchestrator.adapter = MagicMock()

        mock_resource_budget = MagicMock()
        mock_resource_budget.check_all_budgets = AsyncMock(return_value=True)

        mock_rating_system = MagicMock()
        mock_rating_system.record_rating = AsyncMock()

        emitter = MemoryTraceEmitter()

        dispatcher = MultiWorkerDispatcher(
            orchestrator=mock_orchestrator,
            resource_budget=mock_resource_budget,
            rating_system=mock_rating_system,
            emitter=emitter,
        )

        # Create mock workers
        mock_worker_1 = MagicMock()
        mock_worker_1.execute = AsyncMock(return_value="Response 1")
        mock_worker_1.adapter = MagicMock()

        mock_worker_2 = MagicMock()
        mock_worker_2.execute = AsyncMock(return_value="Response 2")
        mock_worker_2.adapter = MagicMock()

        mock_orchestrator.workers = {
            "worker_1": mock_worker_1,
            "worker_2": mock_worker_2,
        }

        await dispatcher.dispatch(
            "Test task", worker_ids=["worker_1", "worker_2"], mode="sequential"
        )

        # resource_manager removed - no VRAM management in current implementation

    async def test_sequential_release_model_called_after_each_worker(self) -> None:
        """Test sequential mode: release_model called after each worker when resource_manager is set."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.workers = {}
        mock_orchestrator.adapter = MagicMock()

        mock_resource_budget = MagicMock()
        mock_resource_budget.check_all_budgets = AsyncMock(return_value=True)

        mock_rating_system = MagicMock()
        mock_rating_system.record_rating = AsyncMock()

        emitter = MemoryTraceEmitter()

        dispatcher = MultiWorkerDispatcher(
            orchestrator=mock_orchestrator,
            resource_budget=mock_resource_budget,
            rating_system=mock_rating_system,
            emitter=emitter,
        )

        # Create mock workers
        mock_worker_1 = MagicMock()
        mock_worker_1.execute = AsyncMock(return_value="Response 1")
        mock_worker_1.adapter = MagicMock()

        mock_worker_2 = MagicMock()
        mock_worker_2.execute = AsyncMock(return_value="Response 2")
        mock_worker_2.adapter = MagicMock()

        mock_orchestrator.workers = {
            "worker_1": mock_worker_1,
            "worker_2": mock_worker_2,
        }

        await dispatcher.dispatch(
            "Test task", worker_ids=["worker_1", "worker_2"], mode="sequential"
        )

        # resource_manager removed - no VRAM management in current implementation

    async def test_sequential_failed_worker_continues_chain(self) -> None:
        """Test sequential mode: a failed worker is recorded but the chain continues to next worker."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.workers = {}
        mock_orchestrator.adapter = MagicMock()

        mock_resource_budget = MagicMock()
        mock_resource_budget.check_all_budgets = AsyncMock(return_value=True)

        mock_rating_system = MagicMock()
        mock_rating_system.record_rating = AsyncMock()

        emitter = MemoryTraceEmitter()

        dispatcher = MultiWorkerDispatcher(
            orchestrator=mock_orchestrator,
            resource_budget=mock_resource_budget,
            rating_system=mock_rating_system,
            emitter=emitter,
        )

        # Create mock workers - worker_1 fails, worker_2 succeeds
        mock_worker_1 = MagicMock()
        mock_worker_1.execute = AsyncMock(side_effect=Exception("Worker failed"))
        mock_worker_1.adapter = MagicMock()

        mock_worker_2 = MagicMock()
        mock_worker_2.execute = AsyncMock(return_value="Response 2")
        mock_worker_2.adapter = MagicMock()

        mock_orchestrator.workers = {
            "worker_1": mock_worker_1,
            "worker_2": mock_worker_2,
        }

        result = await dispatcher.dispatch(
            "Test task", worker_ids=["worker_1", "worker_2"], mode="sequential"
        )

        # Both workers should have responses
        assert len(result.responses) == 2
        assert result.responses[0].succeeded is False
        assert result.responses[1].succeeded is True

    async def test_get_result_returns_stored_result_by_id(self) -> None:
        """Test get_result() returns stored result by ID."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.workers = {}
        mock_orchestrator.adapter = MagicMock()

        mock_resource_budget = MagicMock()
        mock_resource_budget.check_all_budgets = AsyncMock(return_value=True)

        mock_rating_system = MagicMock()
        mock_rating_system.record_rating = AsyncMock()

        emitter = MemoryTraceEmitter()

        dispatcher = MultiWorkerDispatcher(
            orchestrator=mock_orchestrator,
            resource_budget=mock_resource_budget,
            rating_system=mock_rating_system,
            emitter=emitter,
        )

        # Create mock worker
        mock_worker_1 = MagicMock()
        mock_worker_1.execute = AsyncMock(return_value="Response 1")
        mock_worker_1.adapter = MagicMock()

        mock_orchestrator.workers = {
            "worker_1": mock_worker_1,
        }

        result = await dispatcher.dispatch(
            "Test task", worker_ids=["worker_1"], mode="parallel"
        )

        # Retrieve the result
        retrieved = await dispatcher.get_result(result.result_id)

        assert retrieved is not None
        assert retrieved.result_id == result.result_id
        assert retrieved.task == "Test task"

    async def test_get_result_returns_none_for_unknown_id(self) -> None:
        """Test get_result() returns None for unknown ID."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.workers = {}
        mock_orchestrator.adapter = MagicMock()

        mock_resource_budget = MagicMock()
        mock_resource_budget.check_all_budgets = AsyncMock(return_value=True)

        mock_rating_system = MagicMock()
        mock_rating_system.record_rating = AsyncMock()

        emitter = MemoryTraceEmitter()

        dispatcher = MultiWorkerDispatcher(
            orchestrator=mock_orchestrator,
            resource_budget=mock_resource_budget,
            rating_system=mock_rating_system,
            emitter=emitter,
        )

        # Try to retrieve a non-existent result
        result = await dispatcher.get_result("unknown_id")

        assert result is None

    async def test_select_winner_raises_key_error_for_unknown_result_id(self) -> None:
        """Test select_winner() raises KeyError for unknown result_id."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.workers = {}
        mock_orchestrator.adapter = MagicMock()

        mock_resource_budget = MagicMock()
        mock_resource_budget.check_all_budgets = AsyncMock(return_value=True)

        mock_rating_system = MagicMock()
        mock_rating_system.record_rating = AsyncMock()

        emitter = MemoryTraceEmitter()

        dispatcher = MultiWorkerDispatcher(
            orchestrator=mock_orchestrator,
            resource_budget=mock_resource_budget,
            rating_system=mock_rating_system,
            emitter=emitter,
        )

        with pytest.raises(KeyError, match="Result not found"):
            await dispatcher.select_winner("unknown_id", "worker_1")

    async def test_select_winner_calls_rating_system_for_winner_and_non_winners(
        self,
    ) -> None:
        """Test select_winner() calls rating_system.record_rating() for winner and non-winners."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.workers = {}
        mock_orchestrator.adapter = MagicMock()

        mock_resource_budget = MagicMock()
        mock_resource_budget.check_all_budgets = AsyncMock(return_value=True)

        mock_rating_system = MagicMock()
        mock_rating_system.record_rating = AsyncMock()

        emitter = MemoryTraceEmitter()

        dispatcher = MultiWorkerDispatcher(
            orchestrator=mock_orchestrator,
            resource_budget=mock_resource_budget,
            rating_system=mock_rating_system,
            emitter=emitter,
        )

        # Create mock workers
        mock_worker_1 = MagicMock()
        mock_worker_1.execute = AsyncMock(return_value="Response 1")
        mock_worker_1.adapter = MagicMock()

        mock_worker_2 = MagicMock()
        mock_worker_2.execute = AsyncMock(return_value="Response 2")
        mock_worker_2.adapter = MagicMock()

        mock_orchestrator.workers = {
            "worker_1": mock_worker_1,
            "worker_2": mock_worker_2,
        }

        result = await dispatcher.dispatch(
            "Test task", worker_ids=["worker_1", "worker_2"], mode="parallel"
        )

        # Select winner
        await dispatcher.select_winner(result.result_id, "worker_1")

        # Should call record_rating for winner (1.0) and non-winner (0.9)
        assert mock_rating_system.record_rating.call_count == 2
        mock_rating_system.record_rating.assert_any_call("worker_1", 1.0)
        mock_rating_system.record_rating.assert_any_call("worker_2", 0.9)

    async def test_select_winner_sets_winner_worker_id_on_stored_result(self) -> None:
        """Test select_winner() sets winner_worker_id on the stored result."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.workers = {}
        mock_orchestrator.adapter = MagicMock()

        mock_resource_budget = MagicMock()
        mock_resource_budget.check_all_budgets = AsyncMock(return_value=True)

        mock_rating_system = MagicMock()
        mock_rating_system.record_rating = AsyncMock()

        emitter = MemoryTraceEmitter()

        dispatcher = MultiWorkerDispatcher(
            orchestrator=mock_orchestrator,
            resource_budget=mock_resource_budget,
            rating_system=mock_rating_system,
            emitter=emitter,
        )

        # Create mock worker
        mock_worker_1 = MagicMock()
        mock_worker_1.execute = AsyncMock(return_value="Response 1")
        mock_worker_1.adapter = MagicMock()

        mock_orchestrator.workers = {
            "worker_1": mock_worker_1,
        }

        result = await dispatcher.dispatch(
            "Test task", worker_ids=["worker_1"], mode="parallel"
        )

        # Initially no winner
        assert result.winner_worker_id is None

        # Select winner
        await dispatcher.select_winner(result.result_id, "worker_1")

        # Winner should be set
        retrieved = await dispatcher.get_result(result.result_id)
        if retrieved:
            assert retrieved.winner_worker_id == "worker_1"

    async def test_orchestrator_release_model_called_before_any_worker(self) -> None:
        """Test orchestrator release_model called before any worker in both modes."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.workers = {}
        mock_orchestrator.adapter = MagicMock()

        mock_resource_budget = MagicMock()
        mock_resource_budget.check_all_budgets = AsyncMock(return_value=True)

        mock_rating_system = MagicMock()
        mock_rating_system.record_rating = AsyncMock()

        emitter = MemoryTraceEmitter()

        dispatcher = MultiWorkerDispatcher(
            orchestrator=mock_orchestrator,
            resource_budget=mock_resource_budget,
            rating_system=mock_rating_system,
            emitter=emitter,
        )

        # Create mock worker
        mock_worker_1 = MagicMock()
        mock_worker_1.execute = AsyncMock(return_value="Response 1")
        mock_worker_1.adapter = MagicMock()

        mock_orchestrator.workers = {
            "worker_1": mock_worker_1,
        }

        # resource_manager removed - no VRAM management in current implementation
        result = await dispatcher.dispatch(
            "Test task", worker_ids=["worker_1"], mode="parallel"
        )
        assert len(result.responses) == 1

    async def test_release_failure_does_not_abort_dispatch(self) -> None:
        """Test release failure does not abort dispatch."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.workers = {}
        mock_orchestrator.adapter = MagicMock()

        mock_resource_budget = MagicMock()
        mock_resource_budget.check_all_budgets = AsyncMock(return_value=True)

        mock_rating_system = MagicMock()
        mock_rating_system.record_rating = AsyncMock()

        emitter = MemoryTraceEmitter()

        dispatcher = MultiWorkerDispatcher(
            orchestrator=mock_orchestrator,
            resource_budget=mock_resource_budget,
            rating_system=mock_rating_system,
            emitter=emitter,
        )

        # Create mock worker
        mock_worker_1 = MagicMock()
        mock_worker_1.execute = AsyncMock(return_value="Response 1")
        mock_worker_1.adapter = MagicMock()

        mock_orchestrator.workers = {
            "worker_1": mock_worker_1,
        }

        # resource_manager removed - no VRAM management in current implementation
        result = await dispatcher.dispatch(
            "Test task", worker_ids=["worker_1"], mode="parallel"
        )

        # Dispatch should still succeed
        assert len(result.responses) == 1
        assert result.responses[0].succeeded is True
