"""Tests for RatingSystem."""

import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock

from core.rating_system import RatingSystem
from core.schemas import WorkerRating
from core.observability import MemoryTraceEmitter, TraceEventType, TraceComponent


class TestRatingSystem:
    """Tests for RatingSystem class."""
    
    @pytest.fixture
    def mock_memory_router(self):
        """Create a mock MemoryRouter."""
        router = Mock()
        router.write = AsyncMock()
        router.fetch = AsyncMock()
        router.fetch_by_filter = AsyncMock(return_value=[])
        router.write_to_collection = AsyncMock()
        router.get_global_context = AsyncMock(return_value=None)
        router.set_global_context = AsyncMock()
        return router
    
    @pytest.fixture
    def emitter(self):
        """Create a MemoryTraceEmitter for testing."""
        return MemoryTraceEmitter()
    
    @pytest.fixture
    def rating_system(self, mock_memory_router, emitter):
        """Create a RatingSystem instance with mocked dependencies."""
        return RatingSystem(
            memory_router=mock_memory_router,
            emitter=emitter
        )
    
    @pytest.mark.asyncio
    async def test_record_rating_stores_correctly_and_returns_worker_rating(self, rating_system, mock_memory_router):
        """Test that record_rating() stores correctly and returns WorkerRating."""
        rating = await rating_system.record_rating(
            worker_id="test-worker",
            task_id="task-123",
            score=8,
            model_used="qwen2.5-coder:7b",
            instruction_file_version=1,
            comment="Good performance"
        )
        
        assert isinstance(rating, WorkerRating)
        assert rating.worker_id == "test-worker"
        assert rating.task_id == "task-123"
        assert rating.score == 8
        assert rating.model_used == "qwen2.5-coder:7b"
        assert rating.instruction_file_version == 1
        assert rating.comment == "Good performance"
        assert rating.rating_id is not None
        assert rating.created_at is not None
        
        # Verify write was called
        assert mock_memory_router.write.call_count >= 1
        call_args = mock_memory_router.write.call_args
        assert call_args[0][0]["type"] == "worker_rating"
        assert call_args[0][0]["worker_id"] == "test-worker"
        assert call_args[0][0]["score"] == 8
    
    @pytest.mark.asyncio
    async def test_record_rating_rejects_score_outside_1_to_10(self, rating_system):
        """Test that record_rating() rejects score outside 1–10."""
        with pytest.raises(ValueError, match="Score must be between 1 and 10"):
            await rating_system.record_rating(
                worker_id="test-worker",
                task_id="task-123",
                score=11,
                model_used="qwen2.5-coder:7b",
                instruction_file_version=1
            )
        
        with pytest.raises(ValueError, match="Score must be between 1 and 10"):
            await rating_system.record_rating(
                worker_id="test-worker",
                task_id="task-123",
                score=0,
                model_used="qwen2.5-coder:7b",
                instruction_file_version=1
            )
    
    @pytest.mark.asyncio
    async def test_get_ratings_returns_correct_workers_ratings_in_order(self, rating_system, mock_memory_router):
        """Test that get_ratings() returns correct worker's ratings in order."""
        mock_memory_router.fetch.return_value = [
            {
                "content": {
                    "rating_id": "rating-1",
                    "worker_id": "test-worker",
                    "task_id": "task-1",
                    "score": 7,
                    "model_used": "qwen2.5-coder:7b",
                    "instruction_file_version": 1,
                    "comment": "First rating",
                    "created_at": datetime(2026, 6, 9, 10, 0, 0).isoformat()
                }
            },
            {
                "content": {
                    "rating_id": "rating-2",
                    "worker_id": "test-worker",
                    "task_id": "task-2",
                    "score": 9,
                    "model_used": "qwen2.5-coder:7b",
                    "instruction_file_version": 1,
                    "comment": "Second rating",
                    "created_at": datetime(2026, 6, 9, 11, 0, 0).isoformat()
                }
            }
        ]
        
        ratings = await rating_system.get_ratings("test-worker")
        
        assert len(ratings) == 2
        assert all(r.worker_id == "test-worker" for r in ratings)
        # Should be sorted by created_at descending (newest first)
        assert ratings[0].score == 9
        assert ratings[1].score == 7
    
    @pytest.mark.asyncio
    async def test_get_ratings_respects_limit(self, rating_system, mock_memory_router):
        """Test that get_ratings() respects limit parameter."""
        mock_memory_router.fetch.return_value = [
            {
                "content": {
                    "rating_id": f"rating-{i}",
                    "worker_id": "test-worker",
                    "task_id": f"task-{i}",
                    "score": i,
                    "model_used": "qwen2.5-coder:7b",
                    "instruction_file_version": 1,
                    "created_at": datetime(2026, 6, 9, i, 0, 0).isoformat()
                }
            }
            for i in range(10)
        ]
        
        await rating_system.get_ratings("test-worker", limit=5)
        
        # Verify that limit was passed to fetch
        call_args = mock_memory_router.fetch.call_args
        assert call_args[1]["limit"] == 5
    
    @pytest.mark.asyncio
    async def test_get_average_score_returns_correct_average_across_all_ratings(self, rating_system, mock_memory_router):
        """Test that get_average_score() returns correct average across all ratings."""
        mock_memory_router.fetch.return_value = [
            {
                "content": {
                    "rating_id": "rating-1",
                    "worker_id": "test-worker",
                    "task_id": "task-1",
                    "score": 7,
                    "model_used": "qwen2.5-coder:7b",
                    "instruction_file_version": 1,
                    "created_at": datetime(2026, 6, 9, 10, 0, 0).isoformat()
                }
            },
            {
                "content": {
                    "rating_id": "rating-2",
                    "worker_id": "test-worker",
                    "task_id": "task-2",
                    "score": 9,
                    "model_used": "qwen2.5-coder:7b",
                    "instruction_file_version": 1,
                    "created_at": datetime(2026, 6, 9, 11, 0, 0).isoformat()
                }
            }
        ]
        
        avg = await rating_system.get_average_score("test-worker")
        
        assert avg == 8.0  # (7 + 9) / 2
    
    @pytest.mark.asyncio
    async def test_get_average_score_respects_last_n_parameter(self, rating_system, mock_memory_router):
        """Test that get_average_score() respects last_n parameter."""
        mock_memory_router.fetch.return_value = [
            {
                "content": {
                    "rating_id": f"rating-{i}",
                    "worker_id": "test-worker",
                    "task_id": f"task-{i}",
                    "score": i + 1,
                    "model_used": "qwen2.5-coder:7b",
                    "instruction_file_version": 1,
                    "created_at": datetime(2026, 6, 9, i, 0, 0).isoformat()
                }
            }
            for i in range(10)
        ]
        
        # Average of last 3 ratings (newest 3: 10, 9, 8)
        avg = await rating_system.get_average_score("test-worker", last_n=3)
        
        assert avg == 9.0  # (10 + 9 + 8) / 3
    
    @pytest.mark.asyncio
    async def test_get_average_score_returns_none_when_no_ratings_exist(self, rating_system, mock_memory_router):
        """Test that get_average_score() returns None when no ratings exist."""
        mock_memory_router.fetch.return_value = []
        
        avg = await rating_system.get_average_score("test-worker")
        
        assert avg is None
    
    @pytest.mark.asyncio
    async def test_get_trend_returns_positive_float_when_scores_are_improving(self, rating_system, mock_memory_router):
        """Test that get_trend() returns positive float when scores are improving."""
        # Create ratings that improve over time (5, 6, 7, 8, 9, 10)
        mock_memory_router.fetch.return_value = [
            {
                "content": {
                    "rating_id": f"rating-{i}",
                    "worker_id": "test-worker",
                    "task_id": f"task-{i}",
                    "score": 5 + i,
                    "model_used": "qwen2.5-coder:7b",
                    "instruction_file_version": 1,
                    "created_at": datetime(2026, 6, 9, i, 0, 0).isoformat()
                }
            }
            for i in range(6)
        ]
        
        trend = await rating_system.get_trend("test-worker", window=6)
        
        assert trend is not None
        assert trend > 0  # Should be positive (improving)
    
    @pytest.mark.asyncio
    async def test_get_trend_returns_negative_float_when_scores_are_declining(self, rating_system, mock_memory_router):
        """Test that get_trend() returns negative float when scores are declining."""
        # Create ratings that decline over time (10, 9, 8, 7, 6, 5)
        mock_memory_router.fetch.return_value = [
            {
                "content": {
                    "rating_id": f"rating-{i}",
                    "worker_id": "test-worker",
                    "task_id": f"task-{i}",
                    "score": 10 - i,
                    "model_used": "qwen2.5-coder:7b",
                    "instruction_file_version": 1,
                    "created_at": datetime(2026, 6, 9, i, 0, 0).isoformat()
                }
            }
            for i in range(6)
        ]
        
        trend = await rating_system.get_trend("test-worker", window=6)
        
        assert trend is not None
        assert trend < 0  # Should be negative (declining)
    
    @pytest.mark.asyncio
    async def test_get_trend_returns_none_when_fewer_than_window_ratings_exist(self, rating_system, mock_memory_router):
        """Test that get_trend() returns None when fewer than window ratings exist."""
        mock_memory_router.fetch.return_value = [
            {
                "content": {
                    "rating_id": f"rating-{i}",
                    "worker_id": "test-worker",
                    "task_id": f"task-{i}",
                    "score": 7,
                    "model_used": "qwen2.5-coder:7b",
                    "instruction_file_version": 1,
                    "created_at": datetime(2026, 6, 9, i, 0, 0).isoformat()
                }
            }
            for i in range(5)  # Only 5 ratings, but window is 10
        ]
        
        trend = await rating_system.get_trend("test-worker", window=10)
        
        assert trend is None
    
    @pytest.mark.asyncio
    async def test_get_best_model_returns_model_with_highest_average_score(self, rating_system, mock_memory_router):
        """Test that get_best_model() returns model with highest average score."""
        mock_memory_router.fetch.return_value = [
            {
                "content": {
                    "rating_id": "rating-1",
                    "worker_id": "test-worker",
                    "task_id": "task-1",
                    "score": 9,
                    "model_used": "qwen2.5-coder:7b",
                    "instruction_file_version": 1,
                    "created_at": datetime(2026, 6, 9, 10, 0, 0).isoformat()
                }
            },
            {
                "content": {
                    "rating_id": "rating-2",
                    "worker_id": "test-worker",
                    "task_id": "task-2",
                    "score": 8,
                    "model_used": "qwen2.5-coder:7b",
                    "instruction_file_version": 1,
                    "created_at": datetime(2026, 6, 9, 11, 0, 0).isoformat()
                }
            },
            {
                "content": {
                    "rating_id": "rating-3",
                    "worker_id": "test-worker",
                    "task_id": "task-3",
                    "score": 6,
                    "model_used": "llama3:8b",
                    "instruction_file_version": 1,
                    "created_at": datetime(2026, 6, 9, 12, 0, 0).isoformat()
                }
            },
            {
                "content": {
                    "rating_id": "rating-4",
                    "worker_id": "test-worker",
                    "task_id": "task-4",
                    "score": 7,
                    "model_used": "llama3:8b",
                    "instruction_file_version": 1,
                    "created_at": datetime(2026, 6, 9, 13, 0, 0).isoformat()
                }
            }
        ]
        
        best_model = await rating_system.get_best_model("test-worker")
        
        # qwen2.5-coder:7b average: (9 + 8) / 2 = 8.5
        # llama3:8b average: (6 + 7) / 2 = 6.5
        assert best_model == "qwen2.5-coder:7b"
    
    @pytest.mark.asyncio
    async def test_get_best_model_returns_none_when_no_ratings_exist(self, rating_system, mock_memory_router):
        """Test that get_best_model() returns None when no ratings exist."""
        mock_memory_router.fetch.return_value = []
        
        best_model = await rating_system.get_best_model("test-worker")
        
        assert best_model is None
    
    @pytest.mark.asyncio
    async def test_record_comparison_stores_winner_loser_correctly(self, rating_system, mock_memory_router):
        """Test that record_comparison() stores winner/loser correctly."""
        await rating_system.record_comparison(
            task_id="task-123",
            winner_worker_id="worker-a",
            loser_worker_id="worker-b",
            model_used="qwen2.5-coder:7b"
        )
        
        # Verify write was called
        assert mock_memory_router.write.call_count >= 1
        call_args = mock_memory_router.write.call_args
        assert call_args[0][0]["type"] == "worker_comparison"
        assert call_args[0][0]["task_id"] == "task-123"
        assert call_args[0][0]["winner_worker_id"] == "worker-a"
        assert call_args[0][0]["loser_worker_id"] == "worker-b"
        assert call_args[0][0]["model_used"] == "qwen2.5-coder:7b"
    
    @pytest.mark.asyncio
    async def test_trace_event_emitted_for_rating_recorded(self, rating_system, mock_memory_router, emitter):
        """Test that trace event is emitted for rating_recorded."""
        mock_memory_router.write.return_value = None
        
        await rating_system.record_rating(
            worker_id="test-worker",
            task_id="task-123",
            score=8,
            model_used="qwen2.5-coder:7b",
            instruction_file_version=1
        )
        
        events = emitter.get_events()
        assert len(events) > 0
        assert any(
            event.event_type == TraceEventType.OPERATION_COMPLETE and
            event.component == TraceComponent.SYSTEM and
            "Recorded rating" in event.message
            for event in events
        )
    
    @pytest.mark.asyncio
    async def test_trace_event_emitted_for_comparison_recorded(self, rating_system, mock_memory_router, emitter):
        """Test that trace event is emitted for comparison_recorded."""
        mock_memory_router.write.return_value = None
        
        await rating_system.record_comparison(
            task_id="task-123",
            winner_worker_id="worker-a",
            loser_worker_id="worker-b",
            model_used="qwen2.5-coder:7b"
        )
        
        events = emitter.get_events()
        assert len(events) > 0
        assert any(
            event.event_type == TraceEventType.OPERATION_COMPLETE and
            event.component == TraceComponent.SYSTEM and
            "Recorded comparison" in event.message
            for event in events
        )
    
    @pytest.mark.asyncio
    async def test_trace_event_emitted_for_trend_calculated(self, rating_system, mock_memory_router, emitter):
        """Test that trace event is emitted for trend_calculated."""
        mock_memory_router.fetch.return_value = [
            {
                "content": {
                    "rating_id": f"rating-{i}",
                    "worker_id": "test-worker",
                    "task_id": f"task-{i}",
                    "score": 5 + i,
                    "model_used": "qwen2.5-coder:7b",
                    "instruction_file_version": 1,
                    "created_at": datetime(2026, 6, 9, i, 0, 0).isoformat()
                }
            }
            for i in range(6)
        ]
        
        await rating_system.get_trend("test-worker", window=6)
        
        events = emitter.get_events()
        assert len(events) > 0
        assert any(
            event.event_type == TraceEventType.OPERATION_COMPLETE and
            event.component == TraceComponent.SYSTEM and
            "Calculated trend" in event.message
            for event in events
        )
