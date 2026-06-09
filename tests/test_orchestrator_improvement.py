"""Tests for OrchestratorImprovementLoop."""

import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock

from core.orchestrator_improvement import OrchestratorImprovementLoop
from core.orchestrator import Orchestrator
from core.instruction_versioning import InstructionVersionManager
from core.schemas import OrchestratorMetrics, VersionUpdateProposal
from core.observability import MemoryTraceEmitter, TraceEventType, TraceComponent
from core.worker_factory import DynamicWorkerProfile


class TestOrchestratorImprovementLoop:
    """Tests for OrchestratorImprovementLoop class."""
    
    @pytest.fixture
    def mock_orchestrator(self):
        """Create a mock Orchestrator."""
        orchestrator = Mock()
        return orchestrator
    
    @pytest.fixture
    def mock_instruction_version_manager(self):
        """Create a mock InstructionVersionManager."""
        manager = Mock()
        manager.check_and_trigger_update = AsyncMock()
        return manager
    
    @pytest.fixture
    def mock_memory_router(self):
        """Create a mock MemoryRouter."""
        router = Mock()
        router.write = AsyncMock()
        router.fetch = AsyncMock()
        return router
    
    @pytest.fixture
    def emitter(self):
        """Create a MemoryTraceEmitter for testing."""
        return MemoryTraceEmitter()
    
    @pytest.fixture
    def improvement_loop(self, mock_orchestrator, mock_instruction_version_manager, mock_memory_router, emitter):
        """Create an OrchestratorImprovementLoop instance with mocked dependencies."""
        return OrchestratorImprovementLoop(
            orchestrator=mock_orchestrator,
            instruction_version_manager=mock_instruction_version_manager,
            memory_router=mock_memory_router,
            emitter=emitter,
            accuracy_threshold=0.6,
            trend_threshold=-0.5,
            min_samples=5,
            min_ratings=3
        )
    
    @pytest.fixture
    def sample_metrics(self):
        """Create sample OrchestratorMetrics for testing."""
        return OrchestratorMetrics(
            task_id="task-1",
            routed_to_worker_id="worker-1",
            routing_score=0.8,
            task_completed=True,
            user_rating=7.0
        )
    
    @pytest.mark.asyncio
    async def test_record_routing_decision_persists_metrics_to_memory_router(
        self, improvement_loop, mock_memory_router, sample_metrics
    ):
        """Test that record_routing_decision persists metrics to memory router."""
        await improvement_loop.record_routing_decision(sample_metrics)
        
        assert mock_memory_router.write.call_count >= 1
        call_args = mock_memory_router.write.call_args
        assert call_args[0][0]["type"] == "orchestrator_metrics"
        assert call_args[0][0]["task_id"] == "task-1"
        assert call_args[0][0]["routed_to_worker_id"] == "worker-1"
    
    @pytest.mark.asyncio
    async def test_record_routing_decision_emits_correct_trace_event_with_correct_fields(
        self, improvement_loop, emitter, sample_metrics
    ):
        """Test that record_routing_decision emits correct trace event with correct fields."""
        await improvement_loop.record_routing_decision(sample_metrics)
        
        events = emitter.get_events()
        assert len(events) > 0
        assert any(
            event.event_type == TraceEventType.OPERATION_COMPLETE and
            event.component == TraceComponent.ORCHESTRATOR and
            "Orchestrator routing metric recorded" in event.message and
            event.data.get("task_id") == "task-1" and
            event.data.get("routed_to") == "worker-1" and
            event.data.get("score") == 0.8
            for event in events
        )
    
    @pytest.mark.asyncio
    async def test_get_routing_accuracy_returns_correct_proportion_from_n_records(
        self, improvement_loop, mock_memory_router
    ):
        """Test that get_routing_accuracy returns correct proportion from N records."""
        mock_memory_router.fetch.return_value = [
            {"content": {"task_completed": True}},
            {"content": {"task_completed": True}},
            {"content": {"task_completed": False}},
            {"content": {"task_completed": True}},
            {"content": {"task_completed": False}},
        ]
        
        accuracy = await improvement_loop.get_routing_accuracy(n=5)
        
        assert accuracy == 0.6  # 3 out of 5 completed
    
    @pytest.mark.asyncio
    async def test_get_routing_accuracy_returns_0_0_when_fewer_than_min_samples_records(
        self, improvement_loop, mock_memory_router
    ):
        """Test that get_routing_accuracy returns 0.0 when fewer than min_samples records."""
        mock_memory_router.fetch.return_value = [
            {"content": {"task_completed": True}},
            {"content": {"task_completed": True}},
            {"content": {"task_completed": False}},
        ]  # Only 3 records, below min_samples=5
        
        accuracy = await improvement_loop.get_routing_accuracy(n=10)
        
        assert accuracy == 0.0
    
    @pytest.mark.asyncio
    async def test_get_routing_accuracy_handles_all_failed_routing_correctly_returns_0_0(
        self, improvement_loop, mock_memory_router
    ):
        """Test that get_routing_accuracy handles all-failed routing correctly (returns 0.0)."""
        mock_memory_router.fetch.return_value = [
            {"content": {"task_completed": False}},
            {"content": {"task_completed": False}},
            {"content": {"task_completed": False}},
            {"content": {"task_completed": False}},
            {"content": {"task_completed": False}},
        ]
        
        accuracy = await improvement_loop.get_routing_accuracy(n=5)
        
        assert accuracy == 0.0
    
    @pytest.mark.asyncio
    async def test_get_routing_accuracy_handles_all_successful_routing_correctly_returns_1_0(
        self, improvement_loop, mock_memory_router
    ):
        """Test that get_routing_accuracy handles all-successful routing correctly (returns 1.0)."""
        mock_memory_router.fetch.return_value = [
            {"content": {"task_completed": True}},
            {"content": {"task_completed": True}},
            {"content": {"task_completed": True}},
            {"content": {"task_completed": True}},
            {"content": {"task_completed": True}},
        ]
        
        accuracy = await improvement_loop.get_routing_accuracy(n=5)
        
        assert accuracy == 1.0
    
    @pytest.mark.asyncio
    async def test_get_rating_trend_returns_positive_slope_when_ratings_are_improving(
        self, improvement_loop, mock_memory_router
    ):
        """Test that get_rating_trend returns positive slope when ratings are improving."""
        mock_memory_router.fetch.return_value = [
            {"content": {"user_rating": 5.0}},
            {"content": {"user_rating": 6.0}},
            {"content": {"user_rating": 7.0}},
            {"content": {"user_rating": 8.0}},
            {"content": {"user_rating": 9.0}},
        ]
        
        trend = await improvement_loop.get_rating_trend(n=5)
        
        assert trend > 0  # Positive slope for improving ratings
    
    @pytest.mark.asyncio
    async def test_get_rating_trend_returns_negative_slope_when_ratings_are_declining(
        self, improvement_loop, mock_memory_router
    ):
        """Test that get_rating_trend returns negative slope when ratings are declining."""
        mock_memory_router.fetch.return_value = [
            {"content": {"user_rating": 9.0}},
            {"content": {"user_rating": 8.0}},
            {"content": {"user_rating": 7.0}},
            {"content": {"user_rating": 6.0}},
            {"content": {"user_rating": 5.0}},
        ]
        
        trend = await improvement_loop.get_rating_trend(n=5)
        
        assert trend < 0  # Negative slope for declining ratings
    
    @pytest.mark.asyncio
    async def test_get_rating_trend_returns_0_0_when_fewer_than_min_ratings_rated_records(
        self, improvement_loop, mock_memory_router
    ):
        """Test that get_rating_trend returns 0.0 when fewer than min_ratings rated records."""
        mock_memory_router.fetch.return_value = [
            {"content": {"user_rating": 7.0}},
            {"content": {"user_rating": 8.0}},
        ]  # Only 2 rated records, below min_ratings=3
        
        trend = await improvement_loop.get_rating_trend(n=10)
        
        assert trend == 0.0
    
    @pytest.mark.asyncio
    async def test_get_rating_trend_skips_records_where_user_rating_is_none(
        self, improvement_loop, mock_memory_router
    ):
        """Test that get_rating_trend skips records where user_rating is None."""
        mock_memory_router.fetch.return_value = [
            {"content": {"user_rating": None}},
            {"content": {"user_rating": 7.0}},
            {"content": {"user_rating": None}},
            {"content": {"user_rating": 8.0}},
            {"content": {"user_rating": 9.0}},
        ]
        
        trend = await improvement_loop.get_rating_trend(n=5)
        
        # Should only use the 3 rated records (7.0, 8.0, 9.0)
        assert trend > 0  # Positive slope for improving ratings
    
    @pytest.mark.asyncio
    async def test_check_and_trigger_update_triggers_when_accuracy_below_threshold(
        self, improvement_loop, mock_memory_router, mock_instruction_version_manager
    ):
        """Test that check_and_trigger_update triggers when accuracy < threshold."""
        mock_memory_router.fetch.return_value = [
            {"content": {"task_completed": True}},
            {"content": {"task_completed": False}},
            {"content": {"task_completed": False}},
            {"content": {"task_completed": False}},
            {"content": {"task_completed": False}},
        ]  # 1/5 = 0.2 accuracy, below 0.6 threshold
        
        mock_instruction_version_manager.check_and_trigger_update.return_value = VersionUpdateProposal(
            proposal_id="proposal-1",
            worker_id="orchestrator",
            current_version=1,
            proposed_content="# Updated instruction",
            trigger_reason="routing accuracy 0.20 below threshold 0.6",
            rating_trend=0.0,
            status="pending",
            created_at=datetime.now()
        )
        
        proposal = await improvement_loop.check_and_trigger_update()
        
        assert proposal is not None
        assert proposal.worker_id == "orchestrator"
        assert mock_instruction_version_manager.check_and_trigger_update.call_count >= 1
    
    @pytest.mark.asyncio
    async def test_check_and_trigger_update_triggers_when_rating_trend_below_threshold(
        self, improvement_loop, mock_memory_router, mock_instruction_version_manager
    ):
        """Test that check_and_trigger_update triggers when rating trend < threshold."""
        # Good accuracy
        mock_memory_router.fetch.side_effect = [
            [{"content": {"task_completed": True}} for _ in range(10)],  # For accuracy check
            [{"content": {"user_rating": 9.0}}, {"content": {"user_rating": 8.0}}, {"content": {"user_rating": 7.0}}]  # For trend check
        ]
        
        mock_instruction_version_manager.check_and_trigger_update.return_value = VersionUpdateProposal(
            proposal_id="proposal-1",
            worker_id="orchestrator",
            current_version=1,
            proposed_content="# Updated instruction",
            trigger_reason="rating trend -1.00 below threshold -0.5",
            rating_trend=-1.0,
            status="pending",
            created_at=datetime.now()
        )
        
        proposal = await improvement_loop.check_and_trigger_update()
        
        assert proposal is not None
        assert proposal.worker_id == "orchestrator"
    
    @pytest.mark.asyncio
    async def test_check_and_trigger_update_does_not_trigger_when_both_metrics_are_healthy(
        self, improvement_loop, mock_memory_router
    ):
        """Test that check_and_trigger_update does NOT trigger when both metrics are healthy."""
        # Good accuracy
        mock_memory_router.fetch.side_effect = [
            [{"content": {"task_completed": True}} for _ in range(10)],  # For accuracy check
            [{"content": {"user_rating": 7.0}}, {"content": {"user_rating": 8.0}}, {"content": {"user_rating": 9.0}}]  # For trend check
        ]
        
        proposal = await improvement_loop.check_and_trigger_update()
        
        assert proposal is None
    
    @pytest.mark.asyncio
    async def test_check_and_trigger_update_emits_correct_trace_event_when_triggered(
        self, improvement_loop, mock_memory_router, mock_instruction_version_manager, emitter
    ):
        """Test that check_and_trigger_update emits correct trace event when triggered."""
        mock_memory_router.fetch.return_value = [
            {"content": {"task_completed": True}},
            {"content": {"task_completed": False}},
            {"content": {"task_completed": False}},
            {"content": {"task_completed": False}},
            {"content": {"task_completed": False}},
        ]
        
        mock_instruction_version_manager.check_and_trigger_update.return_value = VersionUpdateProposal(
            proposal_id="proposal-1",
            worker_id="orchestrator",
            current_version=1,
            proposed_content="# Updated instruction",
            trigger_reason="routing accuracy 0.20 below threshold 0.6",
            rating_trend=0.0,
            status="pending",
            created_at=datetime.now()
        )
        
        await improvement_loop.check_and_trigger_update()
        
        events = emitter.get_events()
        assert len(events) > 0
        assert any(
            event.event_type == TraceEventType.OPERATION_COMPLETE and
            event.component == TraceComponent.ORCHESTRATOR and
            "Orchestrator instruction update triggered" in event.message
            for event in events
        )
    
    @pytest.mark.asyncio
    async def test_check_and_trigger_update_returns_none_when_no_update_needed(
        self, improvement_loop, mock_memory_router
    ):
        """Test that check_and_trigger_update returns None when no update needed."""
        # Good accuracy and good trend
        mock_memory_router.fetch.side_effect = [
            [{"content": {"task_completed": True}} for _ in range(10)],
            [{"content": {"user_rating": 7.0}}, {"content": {"user_rating": 8.0}}, {"content": {"user_rating": 9.0}}]
        ]
        
        proposal = await improvement_loop.check_and_trigger_update()
        
        assert proposal is None
