"""Tests for TraceOptimiser."""

import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock

from core.trace_optimiser import TraceOptimiser
from core.observability import MemoryTraceEmitter, TraceEventType, TraceComponent
from core.schemas import VersionUpdateProposal


class TestTraceOptimiser:
    """Tests for TraceOptimiser class."""

    pytestmark = pytest.mark.asyncio

    @pytest.fixture
    def mock_memory_router(self):
        """Create a mock MemoryRouter."""
        router = Mock()
        router.fetch = AsyncMock()
        router.fetch_by_filter = AsyncMock(return_value=[])
        router.write_to_collection = AsyncMock()
        router.get_global_context = AsyncMock(return_value=None)
        router.set_global_context = AsyncMock()
        return router

    @pytest.fixture
    def mock_instruction_version_manager(self):
        """Create a mock InstructionVersionManager."""
        manager = Mock()
        manager.check_and_trigger_update = AsyncMock()
        return manager

    @pytest.fixture
    def emitter(self):
        """Create a MemoryTraceEmitter for testing."""
        return MemoryTraceEmitter()

    @pytest.fixture
    def trace_optimiser(self, mock_memory_router, mock_instruction_version_manager, emitter):
        """Create a TraceOptimiser instance with mocked dependencies."""
        return TraceOptimiser(
            memory_router=mock_memory_router,
            instruction_version_manager=mock_instruction_version_manager,
            emitter=emitter,
            trace_threshold=0.65,
            min_traces=10
        )

    async def test_score_recent_traces_returns_1_when_fewer_than_min_traces(
        self, trace_optimiser, mock_memory_router
    ):
        """Test that score_recent_traces returns 1.0 when fewer than min_traces traces exist."""
        mock_memory_router.fetch_by_filter.return_value = [
            {"content": {"event_type": "tool_call", "level": "info"}}
            for _ in range(5)  # Only 5 traces, below min_traces=10
        ]

        score = await trace_optimiser.score_recent_traces("test-worker")

        assert score == 1.0

    async def test_score_recent_traces_correctly_computes_success_rate(
        self, trace_optimiser, mock_memory_router
    ):
        """Test that score_recent_traces correctly computes success rate from tool call events."""
        mock_memory_router.fetch_by_filter.return_value = [
            {"content": {"event_type": "tool_call", "level": "info"}}
            for _ in range(7)  # 7 successful
        ] + [
            {"content": {"event_type": "tool_call", "level": "warning"}}
            for _ in range(3)  # 3 failed
        ]

        score = await trace_optimiser.score_recent_traces("test-worker")

        # Success rate = 7/10 = 0.7, error penalty = 0/10 = 0.0
        # Composite = (0.7 * 0.7) + ((1.0 - 0.0) * 0.3) = 0.49 + 0.3 = 0.79
        assert abs(score - 0.79) < 0.01

    async def test_score_recent_traces_correctly_applies_error_penalty(
        self, trace_optimiser, mock_memory_router
    ):
        """Test that score_recent_traces correctly applies error penalty."""
        mock_memory_router.fetch_by_filter.return_value = [
            {"content": {"event_type": "tool_call", "level": "info"}}
            for _ in range(5)  # 5 successful
        ] + [
            {"content": {"event_type": "tool_call", "level": "error"}}
            for _ in range(5)  # 5 errors
        ]

        score = await trace_optimiser.score_recent_traces("test-worker")

        # Success rate = 5/10 = 0.5, error penalty = 5/10 = 0.5
        # Composite = (0.5 * 0.7) + ((1.0 - 0.5) * 0.3) = 0.35 + 0.15 = 0.5
        assert score == 0.5

    async def test_score_recent_traces_returns_composite_score_in_range(
        self, trace_optimiser, mock_memory_router
    ):
        """Test that score_recent_traces returns composite score in [0.0, 1.0] range (clamp test)."""
        # All errors - should clamp to 0.0
        mock_memory_router.fetch_by_filter.return_value = [
            {"content": {"event_type": "tool_call", "level": "error"}}
            for _ in range(20)
        ]

        score = await trace_optimiser.score_recent_traces("test-worker")
        assert 0.0 <= score <= 1.0

    async def test_score_recent_traces_emits_trace_score_computed_event(
        self, trace_optimiser, mock_memory_router, emitter
    ):
        """Test that score_recent_traces emits trace_score_computed event with correct fields."""
        mock_memory_router.fetch_by_filter.return_value = [
            {"content": {"event_type": "tool_call", "level": "info"}}
            for _ in range(10)
        ]

        await trace_optimiser.score_recent_traces("test-worker")

        events = emitter.get_events()
        assert len(events) > 0
        assert any(
            event.event_type == TraceEventType.TRACE_SCORE_COMPUTED and
            event.component == TraceComponent.TRACE_OPTIMISER and
            "Trace score for worker test-worker" in event.message
            for event in events
        )

    async def test_score_recent_traces_returns_1_on_memory_router_error(
        self, trace_optimiser, mock_memory_router
    ):
        """Test that score_recent_traces returns 1.0 (fail safe) when MemoryRouter raises."""
        mock_memory_router.fetch_by_filter.side_effect = Exception("MemoryRouter error")

        score = await trace_optimiser.score_recent_traces("test-worker")

        assert score == 1.0

    async def test_check_and_trigger_update_returns_none_when_score_above_threshold(
        self, trace_optimiser, mock_memory_router
    ):
        """Test that check_and_trigger_update returns None when score is at or above threshold."""
        mock_memory_router.fetch_by_filter.return_value = [
            {"content": {"event_type": "tool_call", "level": "info"}}
            for _ in range(10)
        ]

        result = await trace_optimiser.check_and_trigger_update("test-worker")

        assert result is None

    async def test_check_and_trigger_update_calls_instruction_version_manager_when_score_below_threshold(
        self, trace_optimiser, mock_memory_router, mock_instruction_version_manager
    ):
        """Test that check_and_trigger_update calls InstructionVersionManager.check_and_trigger_update when score is below threshold."""
        # All errors - score will be low
        mock_memory_router.fetch_by_filter.return_value = [
            {"content": {"event_type": "tool_call", "level": "error"}}
            for _ in range(10)
        ]

        # Mock the instruction version manager to return None (no proposal)
        mock_instruction_version_manager.check_and_trigger_update.return_value = None

        await trace_optimiser.check_and_trigger_update("test-worker")

        assert mock_instruction_version_manager.check_and_trigger_update.call_count >= 1

    async def test_check_and_trigger_update_emits_trace_update_triggered_event_when_threshold_crossed(
        self, trace_optimiser, mock_memory_router, mock_instruction_version_manager, emitter
    ):
        """Test that check_and_trigger_update emits trace_update_triggered event when threshold crossed."""
        # All errors - score will be low
        mock_memory_router.fetch_by_filter.return_value = [
            {"content": {"event_type": "tool_call", "level": "error"}}
            for _ in range(10)
        ]

        # Mock the instruction version manager to return None
        mock_instruction_version_manager.check_and_trigger_update.return_value = None

        await trace_optimiser.check_and_trigger_update("test-worker")

        events = emitter.get_events()
        assert len(events) > 0
        assert any(
            event.event_type == TraceEventType.TRACE_UPDATE_TRIGGERED and
            event.component == TraceComponent.TRACE_OPTIMISER and
            "Trace score below threshold" in event.message
            for event in events
        )

    async def test_check_and_trigger_update_returns_proposal_from_instruction_version_manager(
        self, trace_optimiser, mock_memory_router, mock_instruction_version_manager
    ):
        """Test that check_and_trigger_update returns the VersionUpdateProposal from InstructionVersionManager."""
        # All errors - score will be low
        mock_memory_router.fetch_by_filter.return_value = [
            {"content": {"event_type": "tool_call", "level": "error"}}
            for _ in range(10)
        ]

        # Mock the instruction version manager to return a proposal
        proposal = VersionUpdateProposal(
            proposal_id="test-proposal",
            worker_id="test-worker",
            current_version=1,
            proposed_content="# Updated content",
            trigger_reason="trace score below threshold",
            rating_trend=0.0,
            status="pending",
            created_at=datetime.now()
        )
        mock_instruction_version_manager.check_and_trigger_update.return_value = proposal

        result = await trace_optimiser.check_and_trigger_update("test-worker")

        assert result is proposal
        assert result.proposal_id == "test-proposal"

    async def test_check_and_trigger_update_collision_case_returns_existing_proposal(
        self, trace_optimiser, mock_memory_router, mock_instruction_version_manager
    ):
        """Test that check_and_trigger_update returns existing proposal (returned by InstructionVersionManager) without calling MemoryRouter a second time."""
        # All errors - score will be low
        mock_memory_router.fetch_by_filter.return_value = [
            {"content": {"event_type": "tool_call", "level": "error"}}
            for _ in range(10)
        ]

        # Mock the instruction version manager to return a proposal (collision case)
        proposal = VersionUpdateProposal(
            proposal_id="existing-proposal",
            worker_id="test-worker",
            current_version=1,
            proposed_content="# Existing content",
            trigger_reason="rating trend",
            rating_trend=-0.8,
            status="pending",
            created_at=datetime.now()
        )
        mock_instruction_version_manager.check_and_trigger_update.return_value = proposal

        result = await trace_optimiser.check_and_trigger_update("test-worker")

        assert result is proposal
        # MemoryRouter should be called once for score_recent_traces
        assert mock_memory_router.fetch_by_filter.call_count == 1

    async def test_score_recent_traces_handles_empty_trace_list_gracefully(
        self, trace_optimiser, mock_memory_router
    ):
        """Test that score_recent_traces handles empty trace list (no tool call events) gracefully — returns computed score, not an exception."""
        # Empty traces
        mock_memory_router.fetch_by_filter.return_value = []

        score = await trace_optimiser.score_recent_traces("test-worker")

        # Should return 1.0 (fewer than min_traces)
        assert score == 1.0
