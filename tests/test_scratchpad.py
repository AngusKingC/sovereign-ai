"""Tests for Scratchpad Manager."""

import pytest
from datetime import datetime
from uuid import uuid4

from core.schemas import Scratchpad, ScratchpadEntry, ScratchpadEntryType
from core.scratchpad import ScratchpadManager
from core.memory_router import MemoryRouter


class MockMemoryRouter:
    """Mock MemoryRouter for testing."""
    
    def __init__(self) -> None:
        self.writes = []
    
    async def write(self, task_id: str, content: str, metadata: dict | None = None) -> None:
        """Mock write."""
        self.writes.append({
            "task_id": task_id,
            "content": content,
            "metadata": metadata or {},
        })
    
    async def fetch(self, task) -> list:
        """Mock fetch."""
        return []
    
    async def fetch_by_filter(self, filter: dict, collection: str | None, limit: int | None) -> list:
        """Mock fetch_by_filter."""
        return []
    
    async def write_to_collection(self, data: dict, collection: str, document_id: str | None) -> None:
        """Mock write_to_collection."""
        self.writes.append({
            "data": data,
            "collection": collection,
            "document_id": document_id,
        })
    
    async def get_global_context(self, caller_id: str = "orchestrator"):
        """Mock get_global_context."""
        return None
    
    async def set_global_context(self, context, caller_id: str = "orchestrator"):
        """Mock set_global_context."""
        pass


@pytest.mark.asyncio
class TestScratchpadManager:
    """Tests for ScratchpadManager."""
    
    async def test_scratchpad_entry_schema_validation(self) -> None:
        """Test ScratchpadEntry schema validation."""
        task_id = uuid4()
        entry = ScratchpadEntry(
            task_id=task_id,
            worker_id="test_worker",
            entry_type=ScratchpadEntryType.REASONING,
            content="Test reasoning",
        )
        
        assert entry.task_id == task_id
        assert entry.worker_id == "test_worker"
        assert entry.entry_type == ScratchpadEntryType.REASONING
        assert entry.content == "Test reasoning"
        assert entry.entry_id is not None
        assert entry.timestamp is not None
        assert entry.metadata == {}
    
    async def test_scratchpad_schema_validation(self) -> None:
        """Test Scratchpad schema validation."""
        task_id = uuid4()
        scratchpad = Scratchpad(task_id=task_id)
        
        assert scratchpad.task_id == task_id
        assert scratchpad.scratchpad_id is not None
        assert scratchpad.entries == []
        assert scratchpad.created_at is not None
        assert scratchpad.completed_at is None
        assert scratchpad.summary is None
        assert scratchpad.is_compacted is False
    
    async def test_create_returns_new_scratchpad_stored_in_cache(self) -> None:
        """Test create() returns new Scratchpad stored in cache."""
        mock_router = MockMemoryRouter()
        manager = ScratchpadManager(mock_router)
        
        task_id = uuid4()
        scratchpad = await manager.create(task_id)
        
        assert scratchpad.task_id == task_id
        assert scratchpad.scratchpad_id is not None
        assert len(scratchpad.entries) == 0
        assert scratchpad.is_compacted is False
        
        # Verify it's stored in cache
        retrieved = await manager.get(task_id)
        assert retrieved is not None
        assert retrieved.scratchpad_id == scratchpad.scratchpad_id
    
    async def test_get_retrieves_correct_scratchpad_by_task_id(self) -> None:
        """Test get() retrieves correct scratchpad by task_id."""
        mock_router = MockMemoryRouter()
        manager = ScratchpadManager(mock_router)
        
        task_id1 = uuid4()
        task_id2 = uuid4()
        
        scratchpad1 = await manager.create(task_id1)
        scratchpad2 = await manager.create(task_id2)
        
        # Verify we can retrieve both
        retrieved1 = await manager.get(task_id1)
        retrieved2 = await manager.get(task_id2)
        
        assert retrieved1 is not None
        assert retrieved1.scratchpad_id == scratchpad1.scratchpad_id
        assert retrieved2 is not None
        assert retrieved2.scratchpad_id == scratchpad2.scratchpad_id
        
        # Verify they're different
        assert retrieved1.scratchpad_id != retrieved2.scratchpad_id
    
    async def test_add_entry_appends_entry_with_correct_type_and_content(self) -> None:
        """Test add_entry() appends entry with correct type and content."""
        mock_router = MockMemoryRouter()
        manager = ScratchpadManager(mock_router)
        
        task_id = uuid4()
        await manager.create(task_id)
        
        entry = await manager.add_entry(
            task_id=task_id,
            worker_id="test_worker",
            entry_type=ScratchpadEntryType.REASONING,
            content="Test reasoning",
            metadata={"key": "value"},
        )
        
        assert entry.task_id == task_id
        assert entry.worker_id == "test_worker"
        assert entry.entry_type == ScratchpadEntryType.REASONING
        assert entry.content == "Test reasoning"
        assert entry.metadata == {"key": "value"}
        
        # Verify it's in the scratchpad
        scratchpad = await manager.get(task_id)
        assert len(scratchpad.entries) == 1
        assert scratchpad.entries[0].entry_id == entry.entry_id
    
    async def test_compact_with_provided_summary_uses_that_summary(self) -> None:
        """Test compact() with provided summary uses that summary."""
        mock_router = MockMemoryRouter()
        manager = ScratchpadManager(mock_router)
        
        task_id = uuid4()
        await manager.create(task_id)
        
        custom_summary = "Custom summary provided by LLM"
        compacted = await manager.compact(task_id, llm_summary=custom_summary)
        
        assert compacted.summary == custom_summary
        assert compacted.is_compacted is True
        assert compacted.completed_at is not None
        
        # Verify summary was written to memory
        assert len(mock_router.writes) == 1
        assert custom_summary in mock_router.writes[0]["content"]
    
    async def test_compact_without_summary_generates_rule_based_summary(self) -> None:
        """Test compact() without summary generates rule-based summary."""
        mock_router = MockMemoryRouter()
        manager = ScratchpadManager(mock_router)
        
        task_id = uuid4()
        await manager.create(task_id)
        
        # Add some entries
        await manager.add_entry(
            task_id=task_id,
            worker_id="test_worker",
            entry_type=ScratchpadEntryType.REASONING,
            content="Test reasoning",
        )
        await manager.add_entry(
            task_id=task_id,
            worker_id="test_worker",
            entry_type=ScratchpadEntryType.INTERMEDIATE_RESULT,
            content="Result 1",
        )
        
        compacted = await manager.compact(task_id)
        
        assert compacted.summary is not None
        assert compacted.is_compacted is True
        assert compacted.completed_at is not None
        assert "reasoning" in compacted.summary.lower()
        assert "intermediate_result" in compacted.summary.lower()
    
    async def test_compact_writes_summary_to_long_term_memory(self) -> None:
        """Test compact() writes summary to long-term memory."""
        mock_router = MockMemoryRouter()
        manager = ScratchpadManager(mock_router)
        
        task_id = uuid4()
        await manager.create(task_id)
        
        custom_summary = "Test summary"
        await manager.compact(task_id, llm_summary=custom_summary)
        
        # Verify summary was written to memory
        assert len(mock_router.writes) == 1
        assert mock_router.writes[0]["task_id"] == str(task_id)
        assert custom_summary in mock_router.writes[0]["content"]
        assert mock_router.writes[0]["metadata"]["type"] == "scratchpad_summary"
    
    async def test_compact_marks_scratchpad_as_compacted(self) -> None:
        """Test compact() marks scratchpad as compacted."""
        mock_router = MockMemoryRouter()
        manager = ScratchpadManager(mock_router)
        
        task_id = uuid4()
        await manager.create(task_id)
        
        # Before compaction
        scratchpad = await manager.get(task_id)
        assert scratchpad.is_compacted is False
        assert scratchpad.completed_at is None
        
        # After compaction
        await manager.compact(task_id)
        scratchpad = await manager.get(task_id)
        assert scratchpad.is_compacted is True
        assert scratchpad.completed_at is not None
    
    async def test_get_entries_by_type_returns_only_matching_entries(self) -> None:
        """Test get_entries_by_type() returns only matching entries."""
        mock_router = MockMemoryRouter()
        manager = ScratchpadManager(mock_router)
        
        task_id = uuid4()
        await manager.create(task_id)
        
        # Add entries of different types
        await manager.add_entry(
            task_id=task_id,
            worker_id="test_worker",
            entry_type=ScratchpadEntryType.REASONING,
            content="Reasoning 1",
        )
        await manager.add_entry(
            task_id=task_id,
            worker_id="test_worker",
            entry_type=ScratchpadEntryType.REASONING,
            content="Reasoning 2",
        )
        await manager.add_entry(
            task_id=task_id,
            worker_id="test_worker",
            entry_type=ScratchpadEntryType.INTERMEDIATE_RESULT,
            content="Result 1",
        )
        
        reasoning_entries = await manager.get_entries_by_type(task_id, ScratchpadEntryType.REASONING)
        result_entries = await manager.get_entries_by_type(task_id, ScratchpadEntryType.INTERMEDIATE_RESULT)
        
        assert len(reasoning_entries) == 2
        assert all(e.entry_type == ScratchpadEntryType.REASONING for e in reasoning_entries)
        
        assert len(result_entries) == 1
        assert result_entries[0].entry_type == ScratchpadEntryType.INTERMEDIATE_RESULT
    
    async def test_delete_removes_scratchpad_from_cache(self) -> None:
        """Test delete() removes scratchpad from cache."""
        mock_router = MockMemoryRouter()
        manager = ScratchpadManager(mock_router)
        
        task_id = uuid4()
        await manager.create(task_id)
        
        # Verify it exists
        assert await manager.get(task_id) is not None
        
        # Delete it
        await manager.delete(task_id)
        
        # Verify it's gone
        assert await manager.get(task_id) is None
    
    async def test_trace_events_emitted_on_key_operations(self) -> None:
        """Test trace events emitted on key operations (verify methods don't crash)."""
        # The scratchpad manager wraps trace emissions in try-except to prevent crashes
        # This test verifies that the methods complete successfully without raising errors
        mock_router = MockMemoryRouter()
        manager = ScratchpadManager(mock_router)
        
        task_id = uuid4()
        
        # Create - should not crash even if trace emission fails
        await manager.create(task_id)
        
        # Add entry - should not crash even if trace emission fails
        await manager.add_entry(
            task_id=task_id,
            worker_id="test_worker",
            entry_type=ScratchpadEntryType.REASONING,
            content="Test",
        )
        
        # Compact - should not crash even if trace emission fails
        await manager.compact(task_id)
        
        # Delete - should not crash even if trace emission fails
        await manager.delete(task_id)

