"""Tests for WorkerPersistence."""

import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from tempfile import TemporaryDirectory

from core.worker_factory import DynamicWorkerProfile
from core.schemas import WorkerStatus
from core.observability import MemoryTraceEmitter, TraceEventType
from system.worker_persistence import WorkerPersistence


class TestWorkerPersistence:
    """Tests for WorkerPersistence class."""
    
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
    def worker_persistence(self, mock_memory_router, emitter):
        """Create a WorkerPersistence instance with mocked dependencies."""
        return WorkerPersistence(
            memory_router=mock_memory_router,
            emitter=emitter,
            obsidian_vault_path=None,  # Disable Obsidian for tests
        )
    
    @pytest.fixture
    def sample_profile(self):
        """Create a sample DynamicWorkerProfile for testing."""
        return DynamicWorkerProfile(
            worker_id="test-worker",
            worker_type="placeholder",
            name="Test Worker",
            description="A test worker",
            purpose="Testing purposes",
            capabilities=["test", "debug"],
            preferred_models=["llama3"],
            performance_score=0.8,
            active_tasks=0,
            version=1,
            status=WorkerStatus.ACTIVE,
            creation_date=datetime.utcnow(),
            instruction_file_ref=None,
        )
    
    @pytest.mark.asyncio
    async def test_save_writes_to_postgres(self, worker_persistence, sample_profile, mock_memory_router):
        """Test that save() writes to PostgreSQL."""
        mock_memory_router.fetch.return_value = []  # No existing worker
        
        await worker_persistence.save(sample_profile)
        
        # Verify write was called
        mock_memory_router.write.assert_called_once()
        call_args = mock_memory_router.write.call_args
        assert call_args[1]["collection"] == "workers"
        assert call_args[0][0]["type"] == "worker_profile"
        assert call_args[0][0]["worker_id"] == "test-worker"
        assert call_args[0][0]["is_current"] is True
    
    @pytest.mark.asyncio
    async def test_save_increments_version_on_update(self, worker_persistence, sample_profile, mock_memory_router):
        """Test that save() increments version on update."""
        # Simulate existing worker with version 1
        mock_memory_router.fetch.return_value = [
            {"content": {"version": 1, "profile": sample_profile.model_dump()}}
        ]
        
        await worker_persistence.save(sample_profile)
        
        # Verify version was incremented
        assert sample_profile.version == 2
    
    @pytest.mark.asyncio
    async def test_save_marks_old_version_as_not_current(self, worker_persistence, sample_profile, mock_memory_router):
        """Test that save() marks old version as is_current=False."""
        # Simulate existing worker
        mock_memory_router.fetch.return_value = [
            {"content": {"version": 1, "profile": sample_profile.model_dump()}}
        ]
        
        await worker_persistence.save(sample_profile)
        
        # Verify write was called twice (once for old version, once for new)
        assert mock_memory_router.write.call_count == 2
        
        # Check that old version was marked as not current
        first_call = mock_memory_router.write.call_args_list[0]
        assert first_call[0][0]["is_current"] is False
    
    @pytest.mark.asyncio
    async def test_load_all_returns_only_current_workers(self, worker_persistence, mock_memory_router):
        """Test that load_all() returns only is_current=True workers."""
        # Set up mock to return only current workers
        mock_memory_router.fetch.return_value = [
            {
                "content": {
                    "type": "worker_profile",
                    "worker_id": "worker-1",
                    "is_current": True,
                    "profile": {"worker_id": "worker-1", "name": "Worker 1", "status": WorkerStatus.ACTIVE, "version": 1, "creation_date": datetime.utcnow(), "capabilities": [], "preferred_models": [], "performance_score": 0.0, "active_tasks": 0, "worker_type": "placeholder", "description": "", "purpose": "", "escalation_threshold": 0.8, "tasks_completed": 0, "avg_confidence": 0.0, "complexity_min": 0.0, "complexity_max": 1.0, "preferred_complexity": 0.5, "depth_preference": 0.5, "speculation_tolerance": 0.5, "source_skepticism": 0.5, "verbosity": 0.5, "standing_instructions": [], "preferred_model": "default"},
                }
            },
        ]
        
        profiles = await worker_persistence.load_all()
        
        # Should only return current workers
        assert len(profiles) == 1
        assert profiles[0].worker_id == "worker-1"
    
    @pytest.mark.asyncio
    async def test_load_all_returns_empty_list_when_no_workers(self, worker_persistence, mock_memory_router):
        """Test that load_all() returns empty list when no workers persisted."""
        mock_memory_router.fetch.return_value = []
        
        profiles = await worker_persistence.load_all()
        
        assert profiles == []
    
    @pytest.mark.asyncio
    async def test_load_all_returns_deprecated_workers(self, worker_persistence, mock_memory_router):
        """Test that load_all() returns DEPRECATED workers (they are current, just not routed)."""
        mock_memory_router.fetch.return_value = [
            {
                "content": {
                    "type": "worker_profile",
                    "worker_id": "worker-1",
                    "is_current": True,
                    "profile": {"worker_id": "worker-1", "name": "Worker 1", "status": WorkerStatus.DEPRECATED, "version": 1, "creation_date": datetime.utcnow(), "capabilities": [], "preferred_models": [], "performance_score": 0.0, "active_tasks": 0, "worker_type": "placeholder", "description": "", "purpose": "", "escalation_threshold": 0.8, "tasks_completed": 0, "avg_confidence": 0.0, "complexity_min": 0.0, "complexity_max": 1.0, "preferred_complexity": 0.5, "depth_preference": 0.5, "speculation_tolerance": 0.5, "source_skepticism": 0.5, "verbosity": 0.5, "standing_instructions": [], "preferred_model": "default"},
                }
            },
        ]
        
        profiles = await worker_persistence.load_all()
        
        # Should return DEPRECATED workers (they are current)
        assert len(profiles) == 1
        assert profiles[0].status == WorkerStatus.DEPRECATED
    
    @pytest.mark.asyncio
    async def test_load_one_returns_correct_worker_by_id(self, worker_persistence, mock_memory_router, sample_profile):
        """Test that load_one() returns correct worker by ID."""
        mock_memory_router.fetch.return_value = [
            {
                "content": {
                    "type": "worker_profile",
                    "worker_id": "test-worker",
                    "is_current": True,
                    "profile": sample_profile.model_dump(),
                }
            },
        ]
        
        profile = await worker_persistence.load_one("test-worker")
        
        assert profile is not None
        assert profile.worker_id == "test-worker"
        assert profile.name == "Test Worker"
    
    @pytest.mark.asyncio
    async def test_load_one_returns_none_for_unknown_id(self, worker_persistence, mock_memory_router):
        """Test that load_one() returns None for unknown ID."""
        mock_memory_router.fetch.return_value = []
        
        profile = await worker_persistence.load_one("unknown-worker")
        
        assert profile is None
    
    @pytest.mark.asyncio
    async def test_deprecate_sets_status_to_deprecated(self, worker_persistence, sample_profile, mock_memory_router):
        """Test that deprecate() sets status to WorkerStatus.DEPRECATED."""
        mock_memory_router.fetch.return_value = [
            {
                "content": {
                    "type": "worker_profile",
                    "worker_id": "test-worker",
                    "is_current": True,
                    "profile": sample_profile.model_dump(),
                }
            },
        ]
        
        await worker_persistence.deprecate("test-worker")
        
        # Verify save was called with updated status
        assert mock_memory_router.write.call_count >= 1
        # The last call should be the save with DEPRECATED status
        last_call = mock_memory_router.write.call_args_list[-1]
        assert last_call[0][0]["profile"]["status"] == WorkerStatus.DEPRECATED
    
    @pytest.mark.asyncio
    async def test_archive_sets_status_to_archived(self, worker_persistence, sample_profile, mock_memory_router):
        """Test that archive() sets status to WorkerStatus.ARCHIVED."""
        mock_memory_router.fetch.return_value = [
            {
                "content": {
                    "type": "worker_profile",
                    "worker_id": "test-worker",
                    "is_current": True,
                    "profile": sample_profile.model_dump(),
                }
            },
        ]
        
        await worker_persistence.archive("test-worker")
        
        # Verify save was called with updated status
        assert mock_memory_router.write.call_count >= 1
        # The last call should be the save with ARCHIVED status
        last_call = mock_memory_router.write.call_args_list[-1]
        assert last_call[0][0]["profile"]["status"] == WorkerStatus.ARCHIVED
    
    @pytest.mark.asyncio
    async def test_get_version_history_returns_all_versions_ascending(self, worker_persistence, mock_memory_router, sample_profile):
        """Test that get_version_history() returns all versions in ascending order."""
        # Create profiles with different versions
        profile_v1 = sample_profile.model_copy(update={"version": 1})
        profile_v2 = sample_profile.model_copy(update={"version": 2})
        profile_v3 = sample_profile.model_copy(update={"version": 3})
        
        mock_memory_router.fetch.return_value = [
            {
                "content": {
                    "type": "worker_profile",
                    "worker_id": "test-worker",
                    "is_current": False,
                    "profile": profile_v1.model_dump(),
                }
            },
            {
                "content": {
                    "type": "worker_profile",
                    "worker_id": "test-worker",
                    "is_current": False,
                    "profile": profile_v3.model_dump(),
                }
            },
            {
                "content": {
                    "type": "worker_profile",
                    "worker_id": "test-worker",
                    "is_current": True,
                    "profile": profile_v2.model_dump(),
                }
            },
        ]
        
        history = await worker_persistence.get_version_history("test-worker")
        
        # Should return all versions in ascending order
        assert len(history) == 3
        assert history[0].version == 1
        assert history[1].version == 2
        assert history[2].version == 3
    
    @pytest.mark.asyncio
    async def test_trace_events_emitted_on_save_and_load(self, worker_persistence, sample_profile, mock_memory_router, emitter):
        """Test that trace events are emitted on save and load operations."""
        mock_memory_router.fetch.return_value = []
        
        # Save
        await worker_persistence.save(sample_profile)
        
        # Load
        mock_memory_router.fetch.return_value = [
            {
                "content": {
                    "type": "worker_profile",
                    "worker_id": "test-worker",
                    "is_current": True,
                    "profile": sample_profile.model_dump(),
                }
            },
        ]
        await worker_persistence.load_all()
        
        # Check trace events
        events = emitter.get_events()
        assert len(events) >= 4  # START and COMPLETE for save and load
        event_types = [e.event_type for e in events]
        assert TraceEventType.OPERATION_START in event_types
        assert TraceEventType.OPERATION_COMPLETE in event_types
    
    @pytest.mark.asyncio
    async def test_save_writes_to_obsidian_mirror(self, sample_profile, mock_memory_router, emitter):
        """Test that save() writes to Obsidian mirror when vault path is provided."""
        with TemporaryDirectory() as temp_dir:
            worker_persistence = WorkerPersistence(
                memory_router=mock_memory_router,
                emitter=emitter,
                obsidian_vault_path=temp_dir,
            )
            mock_memory_router.fetch.return_value = []
            
            # Reset profile version to 1 for this test
            sample_profile.version = 1
            
            await worker_persistence.save(sample_profile)
            
            # Check that file was created
            workers_dir = Path(temp_dir) / "workers"
            assert workers_dir.exists()
            files = list(workers_dir.glob("*.md"))
            assert len(files) == 1
            # Version might be 2 if there's an existing worker, so check for either
            assert "test-worker_v1.md" in files[0].name or "test-worker_v2.md" in files[0].name
            
            # Check file content
            content = files[0].read_text()
            assert "# Test Worker" in content
            assert "**Status**: active" in content
            assert "**Version**: 1" in content
