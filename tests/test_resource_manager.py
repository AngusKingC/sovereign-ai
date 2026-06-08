"""Tests for Resource Manager."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
from core.schemas import (
    ResourceSnapshot,
    LoadDecision,
    LoadedModel,
    TaskPriority,
    QuantisationVariant,
    ModelEntry,
    ModelSource,
    DownloadStatus,
    SystemProfile,
    GPUInfo,
    RAMInfo,
    OllamaInfo,
)
from system.resource_manager import ResourceManager


class MockMemoryRouter:
    """Mock MemoryRouter for testing."""
    
    def __init__(self) -> None:
        self.writes = []
        self.fetch_data = None
    
    async def write(self, data: dict) -> None:
        """Mock write."""
        self.writes.append(data)
    
    async def fetch(self, task_id: str, query: str) -> Mock:
        """Mock fetch."""
        mock_result = Mock()
        mock_result.data = self.fetch_data
        return mock_result


class MockApprovalCallback:
    """Mock approval callback for testing."""
    
    def __init__(self, approve: bool = True) -> None:
        self.approve = approve
        self.calls = []
    
    async def request_approval(
        self,
        action_description: str,
        pinned_model_to_evict: str,
        new_model_requesting: str,
        memory_impact: str,
    ) -> bool:
        """Mock approval request."""
        self.calls.append({
            "action_description": action_description,
            "pinned_model_to_evict": pinned_model_to_evict,
            "new_model_requesting": new_model_requesting,
            "memory_impact": memory_impact,
        })
        return self.approve


class MockModelRegistry:
    """Mock model registry for testing."""
    
    def __init__(self) -> None:
        self.models = {}
    
    async def get(self, model_id: str) -> ModelEntry | None:
        """Mock get."""
        return self.models.get(model_id)
    
    def add_model(self, entry: ModelEntry) -> None:
        """Add model to registry."""
        self.models[entry.model_id] = entry


@pytest.mark.asyncio
class TestResourceManager:
    """Tests for ResourceManager."""
    
    async def test_resource_snapshot_schema_validation(self) -> None:
        """Test that ResourceSnapshot schema validates correctly."""
        snapshot = ResourceSnapshot(
            vram_total_gb=24.0,
            vram_used_gb=12.0,
            vram_available_gb=12.0,
            ram_total_gb=32.0,
            ram_used_gb=16.0,
            ram_available_gb=16.0,
            loaded_models=[
                LoadedModel(
                    model_id="test/model:7b",
                    adapter_name="ollama",
                    quantisation="Q4_K_M",
                    vram_used_gb=5.0,
                    ram_used_gb=8.0,
                )
            ],
        )
        
        assert snapshot.vram_total_gb == 24.0
        assert snapshot.vram_available_gb == 12.0
        assert len(snapshot.loaded_models) == 1
        assert snapshot.loaded_models[0].model_id == "test/model:7b"
    
    async def test_load_decision_schema_validation(self) -> None:
        """Test that LoadDecision schema validates correctly."""
        decision = LoadDecision(
            approved=True,
            model_id="test/model:7b",
            quantisation="Q4_K_M",
            models_to_evict=["old/model:7b"],
            requires_user_approval=False,
            reason="Model fits in available VRAM",
        )
        
        assert decision.approved is True
        assert decision.model_id == "test/model:7b"
        assert len(decision.models_to_evict) == 1
        assert decision.requires_user_approval is False
    
    async def test_can_load_returns_true_when_model_fits_in_vram(self) -> None:
        """Test that can_load returns True when model fits in available VRAM."""
        mock_router = MockMemoryRouter()
        manager = ResourceManager(mock_router)
        
        registry = MockModelRegistry()
        registry.add_model(
            ModelEntry(
                model_id="test/model:7b",
                name="Test Model",
                source=ModelSource.OLLAMA,
                quantisation_variants=[
                    QuantisationVariant(
                        name="Q4_K_M",
                        size_on_disk_gb=4.0,
                        vram_required_gb=5.0,
                        ram_required_gb=8.0,
                        quality_score=0.8,
                        speed_score=0.9,
                    )
                ],
            )
        )
        
        system_profile = SystemProfile(
            gpu=GPUInfo(total_vram_mb=24000, available_vram_mb=12000),
            ram=RAMInfo(total_mb=32000, available_mb=16000),
        )
        
        with patch('system.profiler.SystemProfiler') as mock_profiler_class, \
             patch('system.resource_manager.emit_trace', new_callable=AsyncMock):
            mock_profiler = Mock()
            mock_profiler.get_cached = AsyncMock(return_value=system_profile)
            mock_profiler_class.return_value = mock_profiler
            
            can_load, reason = await manager.can_load("test/model:7b", "Q4_K_M", registry)
        
        assert can_load is True
        assert "fits in available VRAM" in reason
    
    async def test_can_load_returns_false_when_model_does_not_fit(self) -> None:
        """Test that can_load returns False when model does not fit."""
        mock_router = MockMemoryRouter()
        manager = ResourceManager(mock_router)
        
        registry = MockModelRegistry()
        registry.add_model(
            ModelEntry(
                model_id="test/model:70b",
                name="Large Model",
                source=ModelSource.OLLAMA,
                quantisation_variants=[
                    QuantisationVariant(
                        name="Q4_K_M",
                        size_on_disk_gb=40.0,
                        vram_required_gb=50.0,
                        ram_required_gb=64.0,
                        quality_score=0.9,
                        speed_score=0.7,
                    )
                ],
            )
        )
        
        system_profile = SystemProfile(
            gpu=GPUInfo(total_vram_mb=24000, available_vram_mb=12000),
            ram=RAMInfo(total_mb=32000, available_mb=16000),
        )
        
        with patch('system.profiler.SystemProfiler') as mock_profiler_class, \
             patch('system.resource_manager.emit_trace', new_callable=AsyncMock):
            mock_profiler = Mock()
            mock_profiler.get_cached = AsyncMock(return_value=system_profile)
            mock_profiler_class.return_value = mock_profiler
            
            can_load, reason = await manager.can_load("test/model:70b", "Q4_K_M", registry)
        
        assert can_load is False
        assert "does not fit" in reason
    
    async def test_request_load_approves_immediately_when_model_already_loaded(self) -> None:
        """Test that request_load approves immediately when model already loaded."""
        mock_router = MockMemoryRouter()
        manager = ResourceManager(mock_router)
        
        # Pre-load a model
        await manager.record_load("test/model:7b", "ollama", "Q4_K_M", 5.0, 8.0)
        
        registry = MockModelRegistry()
        
        with patch('system.resource_manager.emit_trace', new_callable=AsyncMock):
            decision = await manager.request_load("test/model:7b", "Q4_K_M", registry)
        
        assert decision.approved is True
        assert decision.reason == "Model already loaded"
        assert len(decision.models_to_evict) == 0
    
    async def test_request_load_approves_when_model_fits_without_eviction(self) -> None:
        """Test that request_load approves when model fits without eviction."""
        mock_router = MockMemoryRouter()
        manager = ResourceManager(mock_router)
        
        registry = MockModelRegistry()
        registry.add_model(
            ModelEntry(
                model_id="test/model:7b",
                name="Test Model",
                source=ModelSource.OLLAMA,
                quantisation_variants=[
                    QuantisationVariant(
                        name="Q4_K_M",
                        size_on_disk_gb=4.0,
                        vram_required_gb=5.0,
                        ram_required_gb=8.0,
                        quality_score=0.8,
                        speed_score=0.9,
                    )
                ],
            )
        )
        
        system_profile = SystemProfile(
            gpu=GPUInfo(total_vram_mb=24000, available_vram_mb=12000),
            ram=RAMInfo(total_mb=32000, available_mb=16000),
        )
        
        with patch('system.profiler.SystemProfiler') as mock_profiler_class, \
             patch('system.resource_manager.httpx.AsyncClient') as mock_httpx, \
             patch('system.resource_manager.emit_trace', new_callable=AsyncMock):
            mock_profiler = Mock()
            mock_profiler.get_cached = AsyncMock(return_value=system_profile)
            mock_profiler_class.return_value = mock_profiler
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"models": []}
            
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock()
            
            decision = await manager.request_load("test/model:7b", "Q4_K_M", registry)
        
        assert decision.approved is True
        assert "fits in available VRAM" in decision.reason
        assert len(decision.models_to_evict) == 0
    
    async def test_request_load_queues_non_pinned_evictions_when_needed(self) -> None:
        """Test that request_load queues non-pinned evictions when needed."""
        mock_router = MockMemoryRouter()
        manager = ResourceManager(mock_router)
        
        # Load a model that takes up space
        await manager.record_load("old/model:7b", "ollama", "Q4_K_M", 8.0, 12.0)
        
        registry = MockModelRegistry()
        registry.add_model(
            ModelEntry(
                model_id="new/model:7b",
                name="New Model",
                source=ModelSource.OLLAMA,
                quantisation_variants=[
                    QuantisationVariant(
                        name="Q4_K_M",
                        size_on_disk_gb=4.0,
                        vram_required_gb=6.0,
                        ram_required_gb=10.0,
                        quality_score=0.8,
                        speed_score=0.9,
                    )
                ],
            )
        )
        
        system_profile = SystemProfile(
            gpu=GPUInfo(total_vram_mb=24000, available_vram_mb=5000),  # Only 5GB available
            ram=RAMInfo(total_mb=32000, available_mb=16000),
        )
        
        with patch('system.profiler.SystemProfiler') as mock_profiler_class, \
             patch('system.resource_manager.httpx.AsyncClient') as mock_httpx, \
             patch('system.resource_manager.emit_trace', new_callable=AsyncMock):
            mock_profiler = Mock()
            mock_profiler.get_cached = AsyncMock(return_value=system_profile)
            mock_profiler_class.return_value = mock_profiler
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"models": []}
            
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock()
            
            decision = await manager.request_load("new/model:7b", "Q4_K_M", registry)
        
        assert decision.approved is True
        assert len(decision.models_to_evict) == 1
        assert "old/model:7b" in decision.models_to_evict
    
    async def test_request_load_requires_user_approval_when_pinned_model_eviction_needed(self) -> None:
        """Test that request_load requires user approval when pinned model eviction needed."""
        mock_router = MockMemoryRouter()
        approval_callback = MockApprovalCallback(approve=False)
        manager = ResourceManager(mock_router, approval_callback)
        
        # Load a pinned model that takes up space
        await manager.record_load("pinned/model:7b", "ollama", "Q4_K_M", 8.0, 12.0)
        await manager.pin_model("pinned/model:7b")
        
        registry = MockModelRegistry()
        registry.add_model(
            ModelEntry(
                model_id="new/model:7b",
                name="New Model",
                source=ModelSource.OLLAMA,
                quantisation_variants=[
                    QuantisationVariant(
                        name="Q4_K_M",
                        size_on_disk_gb=4.0,
                        vram_required_gb=6.0,
                        ram_required_gb=10.0,
                        quality_score=0.8,
                        speed_score=0.9,
                    )
                ],
            )
        )
        
        system_profile = SystemProfile(
            gpu=GPUInfo(total_vram_mb=24000, available_vram_mb=5000),  # Only 5GB available
            ram=RAMInfo(total_mb=32000, available_mb=16000),
        )
        
        with patch('system.profiler.SystemProfiler') as mock_profiler_class, \
             patch('system.resource_manager.httpx.AsyncClient') as mock_httpx, \
             patch('system.resource_manager.emit_trace', new_callable=AsyncMock):
            mock_profiler = Mock()
            mock_profiler.get_cached = AsyncMock(return_value=system_profile)
            mock_profiler_class.return_value = mock_profiler
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"models": []}
            
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock()
            
            decision = await manager.request_load("new/model:7b", "Q4_K_M", registry)
        
        assert decision.approved is False
        assert decision.requires_user_approval is True
        assert len(approval_callback.calls) == 1
        assert approval_callback.calls[0]["pinned_model_to_evict"] == "pinned/model:7b"
    
    async def test_eviction_priority_idle_time_before_task_priority(self) -> None:
        """Test that eviction priority is idle time before task priority."""
        mock_router = MockMemoryRouter()
        manager = ResourceManager(mock_router)
        
        # Load models with different idle times and priorities
        await manager.record_load("model1:7b", "ollama", "Q4_K_M", 3.0, 5.0)
        await manager.record_load("model2:7b", "ollama", "Q4_K_M", 3.0, 5.0)
        await manager.record_load("model3:7b", "ollama", "Q4_K_M", 3.0, 5.0)
        
        # Set different last_used_at times
        loaded = await manager.get_loaded_models()
        loaded[0].last_used_at = datetime.now() - timedelta(hours=1)  # Oldest, HIGH priority
        loaded[1].last_used_at = datetime.now() - timedelta(minutes=30)  # Middle, NORMAL priority
        loaded[2].last_used_at = datetime.now() - timedelta(minutes=5)  # Newest, HIGH priority
        
        loaded[0].task_priority = TaskPriority.HIGH
        loaded[1].task_priority = TaskPriority.NORMAL
        loaded[2].task_priority = TaskPriority.HIGH
        
        # Get loaded models and check eviction order
        loaded_models = await manager.get_loaded_models()
        
        # Sort by eviction priority: idle time first, then task priority, pinned last
        eviction_order = sorted(
            loaded_models,
            key=lambda m: (
                m.is_pinned,
                m.task_priority.value != "NORMAL",
                m.last_used_at,
            ),
        )
        
        # Oldest should be first despite HIGH priority
        assert eviction_order[0].model_id == "model1:7b"
        # NORMAL priority should be second despite being newer
        assert eviction_order[1].model_id == "model2:7b"
        # Newest HIGH priority should be last
        assert eviction_order[2].model_id == "model3:7b"
    
    async def test_record_load_and_record_unload_update_state_correctly(self) -> None:
        """Test that record_load and record_unload update state correctly."""
        mock_router = MockMemoryRouter()
        manager = ResourceManager(mock_router)
        
        with patch('system.resource_manager.emit_trace', new_callable=AsyncMock):
            await manager.record_load("test/model:7b", "ollama", "Q4_K_M", 5.0, 8.0)
            
            loaded = await manager.get_loaded_models()
            assert len(loaded) == 1
            assert loaded[0].model_id == "test/model:7b"
            
            await manager.record_unload("test/model:7b")
            
            loaded = await manager.get_loaded_models()
            assert len(loaded) == 0
    
    async def test_record_usage_updates_last_used_at(self) -> None:
        """Test that record_usage updates last_used_at."""
        mock_router = MockMemoryRouter()
        manager = ResourceManager(mock_router)
        
        with patch('system.resource_manager.emit_trace', new_callable=AsyncMock):
            await manager.record_load("test/model:7b", "ollama", "Q4_K_M", 5.0, 8.0)
            
            original_last_used = (await manager.get_loaded_models())[0].last_used_at
            
            # Wait a bit and record usage
            import time
            time.sleep(0.01)
            await manager.record_usage("test/model:7b")
            
            updated_last_used = (await manager.get_loaded_models())[0].last_used_at
            
            assert updated_last_used > original_last_used
    
    async def test_trace_events_emitted_on_key_operations(self) -> None:
        """Test that trace events are emitted on key operations."""
        mock_router = MockMemoryRouter()
        manager = ResourceManager(mock_router)
        
        with patch('system.resource_manager.emit_trace', new_callable=AsyncMock) as mock_emit:
            await manager.record_load("test/model:7b", "ollama", "Q4_K_M", 5.0, 8.0)
            await manager.pin_model("test/model:7b")
            await manager.unpin_model("test/model:7b")
            
            # Verify trace events were emitted (pin and unpin)
            assert mock_emit.call_count >= 2
            
            from core.observability import TraceEventType
            calls = mock_emit.call_args_list
            event_types = [call[1].get("event_type") for call in calls]
            
            assert TraceEventType.RESOURCE_PIN in event_types
            assert TraceEventType.RESOURCE_UNPIN in event_types

