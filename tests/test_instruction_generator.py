"""Tests for InstructionGenerator."""

import pytest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, AsyncMock

from core.instruction_generator import InstructionGenerator
from core.worker_factory import DynamicWorkerProfile
from core.schemas import InstructionFile, InstructionChangelogEntry
from core.observability import MemoryTraceEmitter, TraceEventType, TraceComponent
from core.worker_base import LLMResponse


class TestInstructionGenerator:
    """Tests for InstructionGenerator class."""
    
    @pytest.fixture
    def mock_adapter(self):
        """Create a mock LLMAdapter."""
        adapter = Mock()
        adapter.generate = AsyncMock()
        return adapter
    
    @pytest.fixture
    def mock_rating_system(self):
        """Create a mock RatingSystem."""
        rating_system = Mock()
        rating_system.get_trend = AsyncMock()
        return rating_system
    
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
    def temp_vault(self):
        """Create a temporary Obsidian vault directory."""
        with TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def instruction_generator(self, mock_adapter, mock_rating_system, mock_memory_router, emitter):
        """Create an InstructionGenerator instance with mocked dependencies."""
        return InstructionGenerator(
            adapter=mock_adapter,
            rating_system=mock_rating_system,
            memory_router=mock_memory_router,
            obsidian_vault_path=None,
            emitter=emitter
        )
    
    @pytest.fixture
    def sample_profile(self):
        """Create a sample DynamicWorkerProfile for testing."""
        return DynamicWorkerProfile(
            worker_id="test-worker",
            worker_type="specialist",
            name="Test Worker",
            description="A test worker for unit tests",
            purpose="Testing instruction generation",
            capabilities=["test_capability_1", "test_capability_2"],
            preferred_models=["qwen2.5-coder:7b"],
            performance_score=0.8
        )
    
    @pytest.mark.asyncio
    async def test_generate_instruction_file_returns_instruction_file_with_correct_worker_id_and_version_1(
        self, instruction_generator, mock_adapter, sample_profile
    ):
        """Test that generate_instruction_file returns InstructionFile with correct worker_id and version 1."""
        mock_adapter.generate.return_value = LLMResponse(
            content="# Test Worker — Instruction File\n\n## Role\nTest role\n\n## Goal\nTest goal",
            raw={},
            model="qwen2.5-coder:7b",
            tokens_used=150,
            duration_ms=1000
        )
        
        instruction_file, _ = await instruction_generator.generate_instruction_file(
            profile=sample_profile,
            trigger="Initial generation"
        )
        
        assert isinstance(instruction_file, InstructionFile)
        assert instruction_file.worker_id == "test-worker"
        assert instruction_file.version == 1
        assert instruction_file.content is not None
        assert instruction_file.obsidian_path is not None
    
    @pytest.mark.asyncio
    async def test_generate_instruction_file_sets_instruction_file_ref_on_profile(
        self, instruction_generator, mock_adapter, sample_profile
    ):
        """Test that generate_instruction_file sets instruction_file_ref on profile."""
        mock_adapter.generate.return_value = LLMResponse(
            content="# Test Worker — Instruction File\n\n## Role\nTest role",
            raw={},
            model="qwen2.5-coder:7b",
            tokens_used=150,
            duration_ms=1000
        )
        
        instruction_file, updated_profile = await instruction_generator.generate_instruction_file(
            profile=sample_profile,
            trigger="Initial generation"
        )
        
        assert updated_profile.instruction_file_ref == instruction_file.obsidian_path
    
    @pytest.mark.asyncio
    async def test_generate_instruction_file_writes_instruction_file_to_obsidian_path(
        self, mock_adapter, mock_rating_system, mock_memory_router, emitter, sample_profile, temp_vault
    ):
        """Test that generate_instruction_file writes instruction file to Obsidian path."""
        instruction_generator = InstructionGenerator(
            adapter=mock_adapter,
            rating_system=mock_rating_system,
            memory_router=mock_memory_router,
            obsidian_vault_path=temp_vault,
            emitter=emitter
        )
        
        mock_adapter.generate.return_value = LLMResponse(
            content="# Test Worker — Instruction File\n\n## Role\nTest role",
            raw={},
            model="qwen2.5-coder:7b",
            tokens_used=150,
            duration_ms=1000
        )
        
        await instruction_generator.generate_instruction_file(
            profile=sample_profile,
            trigger="Initial generation"
        )
        
        # Check that file was created
        workers_dir = Path(temp_vault) / "workers"
        assert workers_dir.exists()
        files = list(workers_dir.glob("test-worker_INSTRUCTION.md"))
        assert len(files) == 1
        content = files[0].read_text(encoding='utf-8')
        assert "Test Worker" in content
    
    @pytest.mark.asyncio
    async def test_generate_instruction_file_creates_changelog_entry(
        self, instruction_generator, mock_adapter, sample_profile, mock_memory_router
    ):
        """Test that generate_instruction_file creates changelog entry."""
        mock_adapter.generate.return_value = LLMResponse(
            content="# Test Worker — Instruction File\n\n## Role\nTest role",
            raw={},
            model="qwen2.5-coder:7b",
            tokens_used=150,
            duration_ms=1000
        )
        
        await instruction_generator.generate_instruction_file(
            profile=sample_profile,
            trigger="Initial generation"
        )
        
        # Verify changelog entry was written
        assert mock_memory_router.write_to_collection.call_count >= 2
        changelog_call = [call for call in mock_memory_router.write_to_collection.call_args_list 
                         if call.kwargs.get("data", {}).get("type") == "instruction_changelog"]
        assert len(changelog_call) == 1
        assert changelog_call[0].kwargs["data"]["version"] == 1
        assert changelog_call[0].kwargs["data"]["trigger"] == "Initial generation"
    
    @pytest.mark.asyncio
    async def test_update_instruction_file_increments_version(
        self, instruction_generator, mock_adapter, mock_rating_system, sample_profile
    ):
        """Test that update_instruction_file increments version."""
        mock_rating_system.get_trend.return_value = None
        
        existing = InstructionFile(
            worker_id="test-worker",
            version=1,
            content="# Old content",
            obsidian_path="workers/test-worker_INSTRUCTION.md",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        mock_adapter.generate.return_value = LLMResponse(
            content="# Updated content",
            raw={},
            model="qwen2.5-coder:7b",
            tokens_used=150,
            duration_ms=1000
        )
        
        new_file = await instruction_generator.update_instruction_file(
            profile=sample_profile,
            existing=existing,
            trigger="Performance decline"
        )
        
        assert new_file.version == 2
        assert new_file.worker_id == "test-worker"
    
    @pytest.mark.asyncio
    async def test_update_instruction_file_preserves_old_version_in_changelog(
        self, instruction_generator, mock_adapter, mock_rating_system, sample_profile, mock_memory_router
    ):
        """Test that update_instruction_file preserves old version in changelog."""
        mock_rating_system.get_trend.return_value = None
        
        existing = InstructionFile(
            worker_id="test-worker",
            version=1,
            content="# Old content",
            obsidian_path="workers/test-worker_INSTRUCTION.md",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        mock_adapter.generate.return_value = LLMResponse(
            content="# Updated content",
            raw={},
            model="qwen2.5-coder:7b",
            tokens_used=150,
            duration_ms=1000
        )
        
        await instruction_generator.update_instruction_file(
            profile=sample_profile,
            existing=existing,
            trigger="Performance decline"
        )
        
        # Verify changelog entry was written with new version
        changelog_call = [call for call in mock_memory_router.write_to_collection.call_args_list 
                         if call.kwargs.get("data", {}).get("type") == "instruction_changelog"]
        assert len(changelog_call) >= 1
        assert changelog_call[-1].kwargs["data"]["version"] == 2
    
    @pytest.mark.asyncio
    async def test_update_instruction_file_includes_trigger_in_changelog_entry(
        self, instruction_generator, mock_adapter, mock_rating_system, sample_profile, mock_memory_router
    ):
        """Test that update_instruction_file includes trigger in changelog entry."""
        mock_rating_system.get_trend.return_value = None
        
        existing = InstructionFile(
            worker_id="test-worker",
            version=1,
            content="# Old content",
            obsidian_path="workers/test-worker_INSTRUCTION.md",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        mock_adapter.generate.return_value = LLMResponse(
            content="# Updated content",
            raw={},
            model="qwen2.5-coder:7b",
            tokens_used=150,
            duration_ms=1000
        )
        
        await instruction_generator.update_instruction_file(
            profile=sample_profile,
            existing=existing,
            trigger="Performance decline"
        )
        
        changelog_call = [call for call in mock_memory_router.write_to_collection.call_args_list 
                         if call.kwargs.get("data", {}).get("type") == "instruction_changelog"]
        assert changelog_call[-1].kwargs["data"]["trigger"] == "Performance decline"
    
    @pytest.mark.asyncio
    async def test_update_instruction_file_includes_rating_trend_in_changelog_entry_when_available(
        self, instruction_generator, mock_adapter, mock_rating_system, sample_profile, mock_memory_router
    ):
        """Test that update_instruction_file includes rating trend in changelog entry when available."""
        mock_rating_system.get_trend.return_value = -0.5
        
        existing = InstructionFile(
            worker_id="test-worker",
            version=1,
            content="# Old content",
            obsidian_path="workers/test-worker_INSTRUCTION.md",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        mock_adapter.generate.return_value = LLMResponse(
            content="# Updated content",
            raw={},
            model="qwen2.5-coder:7b",
            tokens_used=150,
            duration_ms=1000
        )
        
        await instruction_generator.update_instruction_file(
            profile=sample_profile,
            existing=existing,
            trigger="Performance decline"
        )
        
        changelog_call = [call for call in mock_memory_router.write_to_collection.call_args_list 
                         if call.kwargs.get("data", {}).get("type") == "instruction_changelog"]
        assert changelog_call[-1].kwargs["data"]["rating_trend"] == -0.5
    
    @pytest.mark.asyncio
    async def test_get_instruction_file_returns_existing_file(
        self, instruction_generator, mock_memory_router
    ):
        """Test that get_instruction_file returns existing file."""
        mock_memory_router.fetch_by_filter.return_value = [
            {
                "content": {
                    "worker_id": "test-worker",
                    "version": 1,
                    "content": "# Test content",
                    "obsidian_path": "workers/test-worker_INSTRUCTION.md",
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat()
                }
            }
        ]
        
        instruction_file = await instruction_generator.get_instruction_file("test-worker")
        
        assert instruction_file is not None
        assert instruction_file.worker_id == "test-worker"
        assert instruction_file.version == 1
    
    @pytest.mark.asyncio
    async def test_get_instruction_file_returns_none_when_not_found(
        self, instruction_generator, mock_memory_router
    ):
        """Test that get_instruction_file returns None when not found."""
        mock_memory_router.fetch_by_filter.return_value = []
        
        instruction_file = await instruction_generator.get_instruction_file("test-worker")
        
        assert instruction_file is None
    
    @pytest.mark.asyncio
    async def test_get_instruction_changelog_returns_entries_in_order(
        self, instruction_generator, mock_memory_router
    ):
        """Test that get_instruction_changelog returns entries in order."""
        mock_memory_router.fetch_by_filter.return_value = [
            {
                "content": {
                    "worker_id": "test-worker",
                    "version": 1,
                    "trigger": "Initial",
                    "diff_summary": "Initial file",
                    "rating_trend": None,
                    "created_at": datetime(2026, 6, 9, 10, 0, 0).isoformat()
                }
            },
            {
                "content": {
                    "worker_id": "test-worker",
                    "version": 2,
                    "trigger": "Update",
                    "diff_summary": "Updated content",
                    "rating_trend": 0.5,
                    "created_at": datetime(2026, 6, 9, 11, 0, 0).isoformat()
                }
            }
        ]
        
        changelog = await instruction_generator.get_instruction_changelog("test-worker")
        
        assert len(changelog) == 2
        assert changelog[0].version == 1
        assert changelog[1].version == 2
        # Should be sorted by created_at ascending
        assert changelog[0].created_at < changelog[1].created_at
    
    @pytest.mark.asyncio
    async def test_trace_event_emitted_for_instruction_generated(
        self, instruction_generator, mock_adapter, emitter, sample_profile
    ):
        """Test that trace event is emitted for instruction_generated."""
        mock_adapter.generate.return_value = LLMResponse(
            content="# Test Worker — Instruction File\n\n## Role\nTest role",
            raw={},
            model="qwen2.5-coder:7b",
            tokens_used=150,
            duration_ms=1000
        )
        
        await instruction_generator.generate_instruction_file(
            profile=sample_profile,
            trigger="Initial generation"
        )
        
        events = emitter.get_events()
        assert len(events) > 0
        assert any(
            event.event_type == TraceEventType.OPERATION_COMPLETE and
            event.component == TraceComponent.SYSTEM and
            "Generated instruction file" in event.message
            for event in events
        )
    
    @pytest.mark.asyncio
    async def test_trace_event_emitted_for_instruction_updated(
        self, instruction_generator, mock_adapter, mock_rating_system, emitter, sample_profile
    ):
        """Test that trace event is emitted for instruction_updated."""
        mock_rating_system.get_trend.return_value = None
        
        existing = InstructionFile(
            worker_id="test-worker",
            version=1,
            content="# Old content",
            obsidian_path="workers/test-worker_INSTRUCTION.md",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        mock_adapter.generate.return_value = LLMResponse(
            content="# Updated content",
            raw={},
            model="qwen2.5-coder:7b",
            tokens_used=150,
            duration_ms=1000
        )
        
        await instruction_generator.update_instruction_file(
            profile=sample_profile,
            existing=existing,
            trigger="Performance decline"
        )
        
        events = emitter.get_events()
        assert len(events) > 0
        assert any(
            event.event_type == TraceEventType.OPERATION_COMPLETE and
            event.component == TraceComponent.SYSTEM and
            "Updated instruction file" in event.message
            for event in events
        )
    
    @pytest.mark.asyncio
    async def test_mock_llm_response_is_used_as_instruction_content(
        self, instruction_generator, mock_adapter, sample_profile
    ):
        """Test that mock LLM response is used as instruction content."""
        expected_content = "# Custom Instruction Content\n\n## Role\nCustom role"
        mock_adapter.generate.return_value = LLMResponse(
            content=expected_content,
            raw={},
            model="qwen2.5-coder:7b",
            tokens_used=150,
            duration_ms=1000
        )
        
        instruction_file, _ = await instruction_generator.generate_instruction_file(
            profile=sample_profile,
            trigger="Initial generation"
        )
        
        assert instruction_file.content == expected_content
    
    @pytest.mark.asyncio
    async def test_orchestrator_synthetic_profile_generates_valid_instruction_file(
        self, instruction_generator, mock_adapter
    ):
        """Test that orchestrator synthetic profile generates valid instruction file."""
        orchestrator_profile = DynamicWorkerProfile(
            worker_id="orchestrator",
            worker_type="orchestrator",
            name="Orchestrator",
            description="Central coordination system",
            purpose="Coordinate workers and manage task routing",
            capabilities=["routing", "coordination", "planning"],
            preferred_models=["qwen2.5-coder:7b"],
            performance_score=0.9
        )
        
        mock_adapter.generate.return_value = LLMResponse(
            content="# Orchestrator — Instruction File\n\n## Role\nCentral coordinator",
            raw={},
            model="qwen2.5-coder:7b",
            tokens_used=150,
            duration_ms=1000
        )
        
        instruction_file, _ = await instruction_generator.generate_instruction_file(
            profile=orchestrator_profile,
            trigger="Initial orchestrator setup"
        )
        
        assert isinstance(instruction_file, InstructionFile)
        assert instruction_file.worker_id == "orchestrator"
        assert instruction_file.version == 1
        assert "Orchestrator" in instruction_file.content
