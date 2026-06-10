"""
Tests for Model Evaluator.
"""

import pytest
from datetime import datetime
from uuid import uuid4
from unittest.mock import AsyncMock, patch

from system.model_evaluator import ModelEvaluator, ModelRecommendation, EvaluationResult
from core.schemas import ModelEntry, QuantisationVariant, ModelSource, DownloadStatus, SystemProfile, GPUInfo, RAMInfo, EvaluationRecord
from core.observability import MemoryTraceEmitter, TraceComponent, TraceEventType, TraceLevel


class MockModelRegistry:
    """Mock model registry for testing."""
    
    def __init__(self):
        self._models = {}
    
    async def get(self, model_id):
        return self._models.get(model_id)
    
    async def list_by_tag(self, tag):
        return [m for m in self._models.values() if tag in m.task_tags]
    
    async def update_download_status(self, model_id, status, quantisation=None):
        if model_id in self._models:
            self._models[model_id].download_status = status


class MockResourceManager:
    """Mock resource manager for testing."""
    
    def __init__(self, memory_router):
        self.memory_router = memory_router
        self._snapshot = None
    
    def set_snapshot(self, vram_available_gb=8.0, ram_available_gb=16.0):
        """Set the hardware snapshot for testing."""
        self._snapshot = {
            "vram_available_gb": vram_available_gb,
            "vram_total_gb": 24.0,
            "ram_available_gb": ram_available_gb,
            "ram_total_gb": 32.0,
        }
    
    async def snapshot(self, system_profile):
        """Return the configured snapshot."""
        from core.schemas import ResourceSnapshot
        return ResourceSnapshot(
            timestamp=datetime.utcnow(),
            vram_total_gb=self._snapshot["vram_total_gb"],
            vram_used_gb=self._snapshot["vram_total_gb"] - self._snapshot["vram_available_gb"],
            vram_available_gb=self._snapshot["vram_available_gb"],
            ram_total_gb=self._snapshot["ram_total_gb"],
            ram_used_gb=self._snapshot["ram_total_gb"] - self._snapshot["ram_available_gb"],
            ram_available_gb=self._snapshot["ram_available_gb"],
            loaded_models=[],
        )


class MockMemoryRouter:
    """Mock memory router for testing."""
    
    async def fetch(self, task_id, query):
        return None
    
    async def write(self, document):
        pass


class MockSystemProfiler:
    """Mock system profiler for testing."""
    
    def __init__(self, memory_router):
        self.memory_router = memory_router
        self._profile = None
    
    def set_profile(self, profile):
        self._profile = profile
    
    async def get_cached(self):
        return self._profile


class TestModelRecommendation:
    """Test cases for ModelRecommendation schema."""
    
    def test_model_recommendation_creation(self):
        """Test ModelRecommendation can be created with required fields."""
        recommendation = ModelRecommendation(
            model_id="test_model",
            model_name="Test Model",
            quantisation="Q4_K_M",
            score=0.85,
            reasoning="Good fit",
            fits_vram=True,
            fits_ram=True,
            task_suitability=0.9,
        )
        
        assert recommendation.model_id == "test_model"
        assert recommendation.score == 0.85
        assert recommendation.fits_vram is True


class TestEvaluationResult:
    """Test cases for EvaluationResult schema."""
    
    def test_evaluation_result_creation(self):
        """Test EvaluationResult can be created with required fields."""
        result = EvaluationResult(
            worker_id="test_worker",
            task_type="code",
            recommendations=[],
            evaluated_at=datetime.utcnow(),
            hardware_snapshot={"vram_available_gb": 8.0},
        )
        
        assert result.worker_id == "test_worker"
        assert result.task_type == "code"
        assert len(result.recommendations) == 0


@pytest.mark.asyncio
class TestModelEvaluator:
    """Test cases for ModelEvaluator."""
    
    @pytest.fixture
    def memory_router(self):
        return MockMemoryRouter()
    
    @pytest.fixture
    def model_registry(self):
        return MockModelRegistry()
    
    @pytest.fixture
    def resource_manager(self, memory_router):
        return MockResourceManager(memory_router)
    
    @pytest.fixture
    def emitter(self):
        return MemoryTraceEmitter()
    
    @pytest.fixture
    def evaluator(self, model_registry, resource_manager, emitter):
        return ModelEvaluator(model_registry, resource_manager, emitter)
    
    @pytest.fixture
    def system_profile(self):
        return SystemProfile(
            gpu=GPUInfo(
                available_vram_mb=8192,
                total_vram_mb=24576,
            ),
            ram=RAMInfo(
                available_mb=16384,
                total_mb=32768,
            ),
        )
    
    @pytest.fixture
    def mock_profiler(self, system_profile):
        """Mock SystemProfiler to return a cached profile."""
        profiler = AsyncMock()
        profiler.get_cached = AsyncMock(return_value=system_profile)
        return profiler
    
    def setup_models(self, model_registry):
        """Setup test models in registry."""
        model_registry._models = {
            "test_model_1": ModelEntry(
                model_id="test_model_1",
                name="Test Model 1",
                source=ModelSource.OLLAMA,
                adapter_compatibility=["ollama"],
                task_tags=["code"],
                quantisation_variants=[
                    QuantisationVariant(
                        name="Q4_K_M",
                        size_on_disk_gb=4.5,
                        vram_required_gb=5.0,
                        ram_required_gb=8.0,
                        quality_score=0.85,
                        speed_score=0.90,
                    ),
                ],
                download_status=DownloadStatus.NOT_DOWNLOADED,
                license="Apache 2.0",
                description="Test model",
            ),
            "test_model_2": ModelEntry(
                model_id="test_model_2",
                name="Test Model 2",
                source=ModelSource.OLLAMA,
                adapter_compatibility=["ollama"],
                task_tags=["code", "reasoning"],
                quantisation_variants=[
                    QuantisationVariant(
                        name="Q4_K_M",
                        size_on_disk_gb=9.0,
                        vram_required_gb=10.0,
                        ram_required_gb=16.0,
                        quality_score=0.90,
                        speed_score=0.85,
                    ),
                ],
                download_status=DownloadStatus.NOT_DOWNLOADED,
                license="Apache 2.0",
                description="Test model",
            ),
        }
    
    async def test_evaluate_returns_empty_recommendations_when_no_models_match_task_tags(self, evaluator, resource_manager, mock_profiler):
        """Test evaluate returns empty recommendations when no models match task tags."""
        resource_manager.set_snapshot()
        
        with patch('system.profiler.SystemProfiler', return_value=mock_profiler):
            result = await evaluator.evaluate("test_worker", ["nonexistent_tag"])
        
        assert len(result.recommendations) == 0
        assert result.worker_id == "test_worker"
    
    async def test_evaluate_filters_out_models_that_do_not_fit_hardware_constraints(self, evaluator, model_registry, resource_manager, mock_profiler):
        """Test evaluate filters out models that do not fit hardware constraints."""
        self.setup_models(model_registry)
        resource_manager.set_snapshot(vram_available_gb=4.0, ram_available_gb=8.0)
        
        with patch('system.profiler.SystemProfiler', return_value=mock_profiler):
            result = await evaluator.evaluate("test_worker", ["code"])
        
        # Both models require more than 4GB VRAM, but test_model_1 fits in 8GB RAM
        assert len(result.recommendations) == 1
        assert result.recommendations[0].model_id == "test_model_1"
        assert result.recommendations[0].fits_ram is True
    
    async def test_evaluate_ranks_by_final_score_with_hardware_fit_weighted_highest(self, evaluator, model_registry, resource_manager, mock_profiler):
        """Test evaluate ranks by final score with hardware fit weighted highest."""
        self.setup_models(model_registry)
        resource_manager.set_snapshot(vram_available_gb=12.0, ram_available_gb=24.0)
        
        with patch('system.profiler.SystemProfiler', return_value=mock_profiler):
            result = await evaluator.evaluate("test_worker", ["code"])
        
        assert len(result.recommendations) == 2
        # test_model_2 has higher quality score (0.90 vs 0.85)
        assert result.recommendations[0].score >= result.recommendations[1].score
    
    async def test_evaluate_with_quality_preference_1_weights_quality_over_speed(self, evaluator, model_registry, resource_manager, mock_profiler):
        """Test evaluate with quality_preference=1.0 weights quality over speed."""
        self.setup_models(model_registry)
        resource_manager.set_snapshot(vram_available_gb=12.0, ram_available_gb=24.0)
        
        with patch('system.profiler.SystemProfiler', return_value=mock_profiler):
            result = await evaluator.evaluate("test_worker", ["code"], quality_preference=1.0)
        
        assert len(result.recommendations) == 2
        # test_model_2 has higher quality score
        assert result.recommendations[0].model_id == "test_model_2"
    
    async def test_evaluate_with_quality_preference_0_weights_speed_over_quality(self, evaluator, model_registry, resource_manager, mock_profiler):
        """Test evaluate with quality_preference=0.0 weights speed over quality."""
        self.setup_models(model_registry)
        resource_manager.set_snapshot(vram_available_gb=12.0, ram_available_gb=24.0)
        
        with patch('system.profiler.SystemProfiler', return_value=mock_profiler):
            result = await evaluator.evaluate("test_worker", ["code"], quality_preference=0.0)
        
        assert len(result.recommendations) == 2
        # test_model_1 has higher speed score
        assert result.recommendations[0].model_id == "test_model_1"
    
    async def test_evaluate_emits_trace_events(self, evaluator, model_registry, resource_manager, emitter, mock_profiler):
        """Test evaluate emits trace events."""
        self.setup_models(model_registry)
        resource_manager.set_snapshot()
        
        with patch('system.profiler.SystemProfiler', return_value=mock_profiler):
            await evaluator.evaluate("test_worker", ["code"])
        
        events = emitter.get_events()
        assert len(events) > 0
        assert any(event.event_type == TraceEventType.OPERATION_START for event in events)
        assert any(event.event_type == TraceEventType.OPERATION_COMPLETE for event in events)
    
    async def test_get_best_returns_top_recommendation_from_evaluate(self, evaluator, model_registry, resource_manager, mock_profiler):
        """Test get_best returns top recommendation from evaluate."""
        self.setup_models(model_registry)
        resource_manager.set_snapshot()
        
        with patch('system.profiler.SystemProfiler', return_value=mock_profiler):
            best = await evaluator.get_best("test_worker", ["code"])
        
        assert best is not None
        assert best.model_id in ["test_model_1", "test_model_2"]
    
    async def test_get_best_returns_none_when_no_models_fit_hardware(self, evaluator, resource_manager, mock_profiler):
        """Test get_best returns None when no models fit hardware."""
        resource_manager.set_snapshot(vram_available_gb=1.0, ram_available_gb=2.0)
        
        with patch('system.profiler.SystemProfiler', return_value=mock_profiler):
            best = await evaluator.get_best("test_worker", ["code"])
        
        assert best is None
    
    async def test_record_selection_emits_trace_event(self, evaluator, emitter):
        """Test record_selection emits trace event."""
        await evaluator.record_selection("test_worker", "test_model", "Q4_K_M")
        
        events = emitter.get_events()
        assert len(events) > 0
        assert any(event.event_type == TraceEventType.OPERATION_COMPLETE for event in events)
    
    async def test_evaluate_hardware_snapshot_captures_current_vram_and_ram_state(self, evaluator, model_registry, resource_manager, mock_profiler):
        """Test evaluate hardware snapshot captures current VRAM and RAM state."""
        self.setup_models(model_registry)
        resource_manager.set_snapshot(vram_available_gb=10.0, ram_available_gb=20.0)
        
        with patch('system.profiler.SystemProfiler', return_value=mock_profiler):
            result = await evaluator.evaluate("test_worker", ["code"])
        
        assert "vram_available_gb" in result.hardware_snapshot
        assert "ram_available_gb" in result.hardware_snapshot
        assert result.hardware_snapshot["vram_available_gb"] == 10.0
        assert result.hardware_snapshot["ram_available_gb"] == 20.0
    
    async def test_scoring_formula_produces_correct_relative_rankings(self, evaluator, model_registry, resource_manager, mock_profiler):
        """Test scoring formula produces correct relative rankings."""
        self.setup_models(model_registry)
        resource_manager.set_snapshot(vram_available_gb=12.0, ram_available_gb=24.0)
        
        with patch('system.profiler.SystemProfiler', return_value=mock_profiler):
            result = await evaluator.evaluate("test_worker", ["code"], quality_preference=0.5)
        
        # Both models fit VRAM, so hardware_score = 1.0 for both
        # Both have "code" tag, so suitability_score = 1.0 for both
        # test_model_2 has higher quality (0.90 vs 0.85) but lower speed (0.85 vs 0.90)
        # With quality_preference=0.5, the scores should be close
        assert len(result.recommendations) == 2
    
    def test_historical_performance_weight_returns_blended_score_when_more_than_10_records(self, evaluator):
        """Test historical_performance_weight returns blended score when >10 records exist."""
        # Create 11 evaluation records with final_score = 0.8
        evaluation_records = [
            EvaluationRecord(
                record_id=f"record-{i}",
                task_id=f"task-{i}",
                worker_id="worker-1",
                evaluator_score=None,
                manual_rating=8.0,
                final_score=0.8,
                timestamp=datetime.utcnow()
            )
            for i in range(11)
        ]
        
        # base_score = 0.6, avg_final_score = 0.8
        # blended = (0.8 * 0.7) + (0.6 * 0.3) = 0.56 + 0.18 = 0.74
        weighted_score = evaluator.historical_performance_weight(
            worker_id="worker-1",
            base_score=0.6,
            evaluation_records=evaluation_records
        )
        
        assert abs(weighted_score - 0.74) < 0.001
    
    def test_historical_performance_weight_returns_base_score_unchanged_when_10_or_fewer_records(self, evaluator):
        """Test historical_performance_weight returns base score unchanged when ≤10 records."""
        # Create 10 evaluation records
        evaluation_records = [
            EvaluationRecord(
                record_id=f"record-{i}",
                task_id=f"task-{i}",
                worker_id="worker-1",
                evaluator_score=None,
                manual_rating=8.0,
                final_score=0.8,
                timestamp=datetime.utcnow()
            )
            for i in range(10)
        ]
        
        # base_score should be returned unchanged
        weighted_score = evaluator.historical_performance_weight(
            worker_id="worker-1",
            base_score=0.6,
            evaluation_records=evaluation_records
        )
        
        assert weighted_score == 0.6
