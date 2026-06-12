"""Tests for Model Registry."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from core.schemas import (
    ModelEntry,
    ModelSource,
    DownloadStatus,
    QuantisationVariant,
    SystemProfile,
    GPUInfo,
    OllamaInfo,
    OllamaModelInfo,
)
from system.model_registry import ModelRegistry
from core.observability import MemoryTraceEmitter


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


@pytest.mark.asyncio
class TestModelRegistry:
    """Tests for ModelRegistry."""
    
    async def test_model_entry_schema_validation(self) -> None:
        """Test that ModelEntry schema validates correctly."""
        entry = ModelEntry(
            model_id="ollama/qwen2.5-coder:7b",
            name="Qwen2.5 Coder 7B",
            source=ModelSource.OLLAMA,
            adapter_compatibility=["ollama", "lm_studio"],
            task_tags=["code", "reasoning"],
            quantisation_variants=[
                QuantisationVariant(
                    name="Q4_K_M",
                    size_on_disk_gb=4.5,
                    vram_required_gb=5.0,
                    ram_required_gb=8.0,
                    quality_score=0.85,
                    speed_score=0.90,
                )
            ],
            download_status=DownloadStatus.NOT_DOWNLOADED,
            license="Apache 2.0",
            description="Code-focused model",
        )
        
        assert entry.model_id == "ollama/qwen2.5-coder:7b"
        assert entry.source == ModelSource.OLLAMA
        assert len(entry.quantisation_variants) == 1
        assert entry.quantisation_variants[0].quality_score == 0.85
    
    async def test_registry_register_and_retrieve(self) -> None:
        """Test registry register and retrieve operations."""
        mock_router = MockMemoryRouter()
        registry = ModelRegistry(mock_router, emitter=MemoryTraceEmitter())
        
        entry = ModelEntry(
            model_id="test/model:7b",
            name="Test Model",
            source=ModelSource.OLLAMA,
            adapter_compatibility=["ollama"],
            task_tags=["test"],
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
        
        await registry.register(entry)
        retrieved = await registry.get("test/model:7b")
        
        assert retrieved is not None
        assert retrieved.model_id == "test/model:7b"
        assert retrieved.name == "Test Model"
    
    async def test_list_by_tag(self) -> None:
        """Test filtering models by tag."""
        mock_router = MockMemoryRouter()
        registry = ModelRegistry(mock_router, emitter=MemoryTraceEmitter())
        
        entry1 = ModelEntry(
            model_id="test/code:7b",
            name="Code Model",
            source=ModelSource.OLLAMA,
            task_tags=["code"],
            quantisation_variants=[],
        )
        entry2 = ModelEntry(
            model_id="test/chat:7b",
            name="Chat Model",
            source=ModelSource.OLLAMA,
            task_tags=["chat"],
            quantisation_variants=[],
        )
        
        await registry.register(entry1)
        await registry.register(entry2)
        
        code_models = await registry.list_by_tag("code")
        chat_models = await registry.list_by_tag("chat")
        
        assert len(code_models) == 1
        assert code_models[0].model_id == "test/code:7b"
        assert len(chat_models) == 1
        assert chat_models[0].model_id == "test/chat:7b"
    
    async def test_list_by_adapter(self) -> None:
        """Test filtering models by adapter compatibility."""
        mock_router = MockMemoryRouter()
        registry = ModelRegistry(mock_router, emitter=MemoryTraceEmitter())
        
        entry1 = ModelEntry(
            model_id="test/ollama:7b",
            name="Ollama Model",
            source=ModelSource.OLLAMA,
            adapter_compatibility=["ollama"],
            quantisation_variants=[],
        )
        entry2 = ModelEntry(
            model_id="test/anthropic:7b",
            name="Anthropic Model",
            source=ModelSource.API,
            adapter_compatibility=["anthropic"],
            quantisation_variants=[],
        )
        
        await registry.register(entry1)
        await registry.register(entry2)
        
        ollama_models = await registry.list_by_adapter("ollama")
        anthropic_models = await registry.list_by_adapter("anthropic")
        
        assert len(ollama_models) == 1
        assert ollama_models[0].model_id == "test/ollama:7b"
        assert len(anthropic_models) == 1
        assert anthropic_models[0].model_id == "test/anthropic:7b"
    
    async def test_list_downloaded(self) -> None:
        """Test filtering models by download status."""
        mock_router = MockMemoryRouter()
        registry = ModelRegistry(mock_router, emitter=MemoryTraceEmitter())
        
        entry1 = ModelEntry(
            model_id="test/downloaded:7b",
            name="Downloaded Model",
            source=ModelSource.OLLAMA,
            download_status=DownloadStatus.DOWNLOADED,
            quantisation_variants=[],
        )
        entry2 = ModelEntry(
            model_id="test/not_downloaded:7b",
            name="Not Downloaded Model",
            source=ModelSource.OLLAMA,
            download_status=DownloadStatus.NOT_DOWNLOADED,
            quantisation_variants=[],
        )
        
        await registry.register(entry1)
        await registry.register(entry2)
        
        downloaded = await registry.list_downloaded()
        
        assert len(downloaded) == 1
        assert downloaded[0].model_id == "test/downloaded:7b"
    
    async def test_recommend_returns_only_models_that_fit_vram(self) -> None:
        """Test that recommend returns only models that fit available VRAM."""
        mock_router = MockMemoryRouter()
        registry = ModelRegistry(mock_router, emitter=MemoryTraceEmitter())
        
        # Model that fits
        entry1 = ModelEntry(
            model_id="test/small:7b",
            name="Small Model",
            source=ModelSource.OLLAMA,
            task_tags=["code"],
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
        
        # Model that doesn't fit
        entry2 = ModelEntry(
            model_id="test/large:70b",
            name="Large Model",
            source=ModelSource.OLLAMA,
            task_tags=["code"],
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
        
        system_profile = SystemProfile(
            gpu=GPUInfo(available_vram_mb=6000),  # 6GB available
        )
        
        await registry.register(entry1)
        await registry.register(entry2)
        
        recommendations = await registry.recommend(["code"], system_profile)
        
        assert len(recommendations) == 1
        assert recommendations[0].model_id == "test/small:7b"
    
    async def test_recommend_ranks_by_hardware_fit_before_quality(self) -> None:
        """Test that recommend ranks by hardware fit before quality score."""
        mock_router = MockMemoryRouter()
        registry = ModelRegistry(mock_router, emitter=MemoryTraceEmitter())
        
        # Lower quality but fits better
        entry1 = ModelEntry(
            model_id="test/efficient:7b",
            name="Efficient Model",
            source=ModelSource.OLLAMA,
            task_tags=["code"],
            quantisation_variants=[
                QuantisationVariant(
                    name="Q4_K_M",
                    size_on_disk_gb=2.0,
                    vram_required_gb=3.0,
                    ram_required_gb=4.0,
                    quality_score=0.7,
                    speed_score=0.95,
                )
            ],
        )
        
        # Higher quality but fits worse
        entry2 = ModelEntry(
            model_id="test/quality:7b",
            name="Quality Model",
            source=ModelSource.OLLAMA,
            task_tags=["code"],
            quantisation_variants=[
                QuantisationVariant(
                    name="Q8_0",
                    size_on_disk_gb=8.0,
                    vram_required_gb=9.0,
                    ram_required_gb=12.0,
                    quality_score=0.95,
                    speed_score=0.7,
                )
            ],
        )
        
        system_profile = SystemProfile(
            gpu=GPUInfo(available_vram_mb=10000),  # 10GB available
        )
        
        await registry.register(entry1)
        await registry.register(entry2)
        
        recommendations = await registry.recommend(["code"], system_profile)
        
        assert len(recommendations) == 2
        # Efficient model should rank first due to better hardware fit
        assert recommendations[0].model_id == "test/efficient:7b"
        assert recommendations[1].model_id == "test/quality:7b"
    
    async def test_download_status_update(self) -> None:
        """Test updating download status."""
        mock_router = MockMemoryRouter()
        registry = ModelRegistry(mock_router, emitter=MemoryTraceEmitter())
        
        entry = ModelEntry(
            model_id="test/model:7b",
            name="Test Model",
            source=ModelSource.OLLAMA,
            download_status=DownloadStatus.NOT_DOWNLOADED,
            quantisation_variants=[],
        )
        
        await registry.register(entry)
        await registry.update_download_status("test/model:7b", DownloadStatus.DOWNLOADED, "Q4_K_M")
        
        updated = await registry.get("test/model:7b")
        
        assert updated is not None
        assert updated.download_status == DownloadStatus.DOWNLOADED
        assert updated.downloaded_quantisation == "Q4_K_M"
    
    async def test_registry_persists_to_and_loads_from_storage(self) -> None:
        """Test that registry persists to and loads from storage."""
        mock_router = MockMemoryRouter()
        registry = ModelRegistry(mock_router, emitter=MemoryTraceEmitter())
        
        entry = ModelEntry(
            model_id="test/model:7b",
            name="Test Model",
            source=ModelSource.OLLAMA,
            quantisation_variants=[],
        )
        
        await registry.register(entry)
        
        # Verify it was written to storage
        assert len(mock_router.writes) == 1
        assert mock_router.writes[0]["metadata"]["model_id"] == "test/model:7b"
    
    async def test_seed_data_is_populated_on_startup(self) -> None:
        """Test that seed data is populated on startup."""
        mock_router = MockMemoryRouter()
        registry = ModelRegistry(mock_router, emitter=MemoryTraceEmitter())
        
        await registry.initialize()
        
        all_models = await registry.list_all()
        
        # Should have seed models
        assert len(all_models) > 0
        # Check for known seed models
        model_ids = [m.model_id for m in all_models]
        assert "ollama/qwen2.5-coder:7b" in model_ids
        assert "ollama/llama3.2:3b" in model_ids
        assert "anthropic/claude-sonnet-4-20250514" in model_ids
    
    async def test_cross_reference_with_profile_sets_correct_download_status(self) -> None:
        """Test that cross-reference with SystemProfile sets correct download status."""
        mock_router = MockMemoryRouter()
        registry = ModelRegistry(mock_router, emitter=MemoryTraceEmitter())
        
        system_profile = SystemProfile(
            ollama=OllamaInfo(
                running=True,
                models_downloaded=[
                    OllamaModelInfo(name="qwen2.5-coder:7b", size_on_disk_mb=4500),
                    OllamaModelInfo(name="llama3.2:3b", size_on_disk_mb=2000),
                ],
            ),
        )
        
        await registry.initialize(system_profile)
        
        qwen_model = await registry.get("ollama/qwen2.5-coder:7b")
        llama_model = await registry.get("ollama/llama3.2:3b")
        mistral_model = await registry.get("ollama/mistral:7b")
        
        assert qwen_model is not None
        assert qwen_model.download_status == DownloadStatus.DOWNLOADED
        
        assert llama_model is not None
        assert llama_model.download_status == DownloadStatus.DOWNLOADED
        
        assert mistral_model is not None
        assert mistral_model.download_status == DownloadStatus.NOT_DOWNLOADED
    
    async def test_trace_events_emitted_on_key_operations(self) -> None:
        """Test that trace events are emitted on key operations."""
        mock_router = MockMemoryRouter()
        registry = ModelRegistry(mock_router, emitter=MemoryTraceEmitter())
        
        entry = ModelEntry(
            model_id="test/model:7b",
            name="Test Model",
            source=ModelSource.OLLAMA,
            quantisation_variants=[],
        )
        
        await registry.initialize()
        await registry.register(entry)
        
        # Verify trace events were emitted
        events = registry._emitter.get_events()
        assert len(events) >= 3
        
        from core.observability import TraceEventType
        event_types = [event.event_type for event in events]
        
        assert TraceEventType.MODEL_REGISTRY_LOAD in event_types
        assert TraceEventType.MODEL_REGISTRY_REGISTER in event_types

