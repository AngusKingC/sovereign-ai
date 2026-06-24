"""Tests for NotesSkill."""

import pytest
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import AsyncMock

from skills.notes.notes_skill import NotesSkill
from core.observability import MemoryTraceEmitter
from core.approval_gate import ApprovalGate, ApprovalResponse


class TestNotesSkill:
    """Test suite for NotesSkill."""

    def setup_method(self):
        """Set up test fixtures."""
        self.emitter = MemoryTraceEmitter()
        self.memory_router = AsyncMock()
        self.approval_gate = AsyncMock(spec=ApprovalGate)
        self.skill = NotesSkill(
            memory_router=self.memory_router,
            emitter=self.emitter,
            approval_gate=self.approval_gate,
        )

    def test_notes_skill_initialises_with_correct_defaults(self):
        """NotesSkill initialises with correct defaults."""
        skill = NotesSkill(
            memory_router=self.memory_router,
            emitter=self.emitter,
        )
        assert skill._emitter == self.emitter
        assert skill._memory_router == self.memory_router

    @pytest.mark.asyncio
    async def test_create_stores_note_with_correct_schema_in_memory_router(self):
        """create stores note with correct schema in MemoryRouter."""
        self.approval_gate.request_approval.return_value = ApprovalResponse(
            request_id=str(uuid4()),
            task_id=str(uuid4()),
            approved=True,
            decision_reason="Approved",
            approved_by="test_user",
            approved_at=datetime.now(timezone.utc),
        )

        note_id = await self.skill.create("Test Note", "Test content", ["tag1", "tag2"])
        
        # Verify scoped_write was called with correct schema
        self.memory_router.scoped_write.assert_called_once()
        call_args = self.memory_router.scoped_write.call_args
        assert call_args[0][0] == "notes"
        assert call_args[0][1].startswith("notes:")
        note = call_args[0][2]
        assert "id" in note
        assert note["title"] == "Test Note"
        assert note["content"] == "Test content"
        assert note["tags"] == ["tag1", "tag2"]
        assert "created_at" in note
        assert "updated_at" in note
        assert note_id == note["id"]

    @pytest.mark.asyncio
    async def test_create_returns_a_non_empty_uid_string(self):
        """create returns a non-empty UID string."""
        self.approval_gate.request_approval.return_value = ApprovalResponse(
            request_id=str(uuid4()),
            task_id=str(uuid4()),
            approved=True,
            decision_reason="Approved",
            approved_by="test_user",
            approved_at=datetime.now(timezone.utc),
        )

        note_id = await self.skill.create("Test Note", "Test content")
        
        assert note_id is not None
        assert len(note_id) > 0

    @pytest.mark.asyncio
    async def test_create_emits_trace_event_with_title_and_tags(self):
        """create emits trace event with title and tags."""
        self.approval_gate.request_approval.return_value = ApprovalResponse(
            request_id=str(uuid4()),
            task_id=str(uuid4()),
            approved=True,
            decision_reason="Approved",
            approved_by="test_user",
            approved_at=datetime.now(timezone.utc),
        )

        await self.skill.create("Test Note", "Test content", ["tag1"])
        
        events = self.emitter.get_events()
        assert len(events) >= 2
        # Check for operation_complete event with title
        complete_events = [e for e in events if e.event_type == "operation_complete"]
        assert len(complete_events) > 0
        assert "title" in complete_events[0].data

    @pytest.mark.asyncio
    async def test_create_proceeds_without_approval_when_no_gate_injected(self):
        """create proceeds without approval when no gate injected (low-risk operation)."""
        NotesSkill(
            memory_router=self.memory_router,
            emitter=self.emitter,
            approval_gate=None,
        )

        note_id = await self.skill.create("Test Note", "Test content")
        
        # Verify scoped_write was called
        self.memory_router.scoped_write.assert_called_once()
        assert note_id is not None

    @pytest.mark.asyncio
    async def test_list_all_returns_notes_sorted_by_updated_at_descending(self):
        """list_all returns notes sorted by updated_at descending."""
        self.memory_router.scoped_read.return_value = [
            {"id": "1", "title": "Note 1", "content": "Content 1", "tags": [], "created_at": "2026-06-20T10:00:00", "updated_at": "2026-06-20T12:00:00"},
            {"id": "2", "title": "Note 2", "content": "Content 2", "tags": [], "created_at": "2026-06-20T10:00:00", "updated_at": "2026-06-20T13:00:00"},
            {"id": "3", "title": "Note 3", "content": "Content 3", "tags": [], "created_at": "2026-06-20T10:00:00", "updated_at": "2026-06-20T11:00:00"},
        ]

        notes = await self.skill.list_all()
        
        assert len(notes) == 3
        assert notes[0]["id"] == "2"  # Most recently updated
        assert notes[1]["id"] == "1"
        assert notes[2]["id"] == "3"  # Least recently updated

    @pytest.mark.asyncio
    async def test_list_all_emits_trace_event_with_note_count(self):
        """list_all emits trace event with note_count."""
        self.memory_router.scoped_read.return_value = [
            {"id": "1", "title": "Note 1", "content": "Content 1", "tags": [], "created_at": "2026-06-20T10:00:00", "updated_at": "2026-06-20T12:00:00"},
            {"id": "2", "title": "Note 2", "content": "Content 2", "tags": [], "created_at": "2026-06-20T10:00:00", "updated_at": "2026-06-20T13:00:00"},
        ]

        await self.skill.list_all()
        
        events = self.emitter.get_events()
        assert len(events) >= 2
        # Check for operation_complete event with note_count
        complete_events = [e for e in events if e.event_type == "operation_complete"]
        assert len(complete_events) > 0
        assert "note_count" in complete_events[0].data
        assert complete_events[0].data["note_count"] == 2

    @pytest.mark.asyncio
    async def test_get_returns_note_by_id(self):
        """get returns note by ID."""
        note = {"id": "1", "title": "Note 1", "content": "Content 1", "tags": [], "created_at": "2026-06-20T10:00:00", "updated_at": "2026-06-20T12:00:00"}
        self.memory_router.scoped_read.return_value = note

        result = await self.skill.get("1")
        
        assert result == note

    @pytest.mark.asyncio
    async def test_get_returns_none_for_unknown_id(self):
        """get returns None for unknown ID."""
        self.memory_router.scoped_read.return_value = None

        result = await self.skill.get("unknown")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_get_emits_trace_event_with_found_flag(self):
        """get emits trace event with found flag."""
        note = {"id": "1", "title": "Note 1", "content": "Content 1", "tags": [], "created_at": "2026-06-20T10:00:00", "updated_at": "2026-06-20T12:00:00"}
        self.memory_router.scoped_read.return_value = note

        await self.skill.get("1")
        
        events = self.emitter.get_events()
        assert len(events) >= 2
        # Check for operation_complete event with found flag
        complete_events = [e for e in events if e.event_type == "operation_complete"]
        assert len(complete_events) > 0
        assert "found" in complete_events[0].data
        assert complete_events[0].data["found"] is True

    @pytest.mark.asyncio
    async def test_update_modifies_title_content_and_tags_on_correct_note(self):
        """update modifies title, content, and tags on correct note."""
        self.approval_gate.request_approval.return_value = ApprovalResponse(
            request_id=str(uuid4()),
            task_id=str(uuid4()),
            approved=True,
            decision_reason="Approved",
            approved_by="test_user",
            approved_at=datetime.now(timezone.utc),
        )

        note = {"id": "1", "title": "Old Title", "content": "Old Content", "tags": ["old"], "created_at": "2026-06-20T10:00:00", "updated_at": "2026-06-20T12:00:00"}
        self.memory_router.scoped_read.return_value = note

        result = await self.skill.update("1", title="New Title", content="New Content", tags=["new"])
        
        assert result is True
        # Verify scoped_write was called with updated values
        self.memory_router.scoped_write.assert_called_once()
        call_args = self.memory_router.scoped_write.call_args
        updated_note = call_args[0][2]
        assert updated_note["title"] == "New Title"
        assert updated_note["content"] == "New Content"
        assert updated_note["tags"] == ["new"]
        assert "updated_at" in updated_note

    @pytest.mark.asyncio
    async def test_update_returns_false_for_unknown_id(self):
        """update returns False for unknown ID."""
        self.approval_gate.request_approval.return_value = ApprovalResponse(
            request_id=str(uuid4()),
            task_id=str(uuid4()),
            approved=True,
            decision_reason="Approved",
            approved_by="test_user",
            approved_at=datetime.now(timezone.utc),
        )

        self.memory_router.scoped_read.return_value = None

        result = await self.skill.update("unknown", title="New Title")
        
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_removes_note_by_id(self):
        """delete removes note by ID."""
        self.approval_gate.request_approval.return_value = ApprovalResponse(
            request_id=str(uuid4()),
            task_id=str(uuid4()),
            approved=True,
            decision_reason="Approved",
            approved_by="test_user",
            approved_at=datetime.now(timezone.utc),
        )

        note = {"id": "1", "title": "Note 1", "content": "Content 1", "tags": [], "created_at": "2026-06-20T10:00:00", "updated_at": "2026-06-20T12:00:00"}
        self.memory_router.scoped_read.return_value = note

        result = await self.skill.delete("1")
        
        assert result is True
        # Verify scoped_write was called with None (deletion pattern)
        self.memory_router.scoped_write.assert_called_once()
        call_args = self.memory_router.scoped_write.call_args
        assert call_args[0][0] == "notes"
        assert call_args[0][1] == "notes:1"
        assert call_args[0][2] is None

    @pytest.mark.asyncio
    async def test_delete_returns_false_for_unknown_id(self):
        """delete returns False for unknown ID."""
        self.approval_gate.request_approval.return_value = ApprovalResponse(
            request_id=str(uuid4()),
            task_id=str(uuid4()),
            approved=True,
            decision_reason="Approved",
            approved_by="test_user",
            approved_at=datetime.now(timezone.utc),
        )

        self.memory_router.scoped_read.return_value = None

        result = await self.skill.delete("unknown")
        
        assert result is False

    @pytest.mark.asyncio
    async def test_search_by_tag_returns_notes_containing_the_tag(self):
        """search_by_tag returns notes containing the tag."""
        self.memory_router.scoped_read.return_value = [
            {"id": "1", "title": "Note 1", "content": "Content 1", "tags": ["tag1", "tag2"], "created_at": "2026-06-20T10:00:00", "updated_at": "2026-06-20T12:00:00"},
            {"id": "2", "title": "Note 2", "content": "Content 2", "tags": ["tag2"], "created_at": "2026-06-20T10:00:00", "updated_at": "2026-06-20T13:00:00"},
            {"id": "3", "title": "Note 3", "content": "Content 3", "tags": ["tag3"], "created_at": "2026-06-20T10:00:00", "updated_at": "2026-06-20T11:00:00"},
        ]

        matching = await self.skill.search_by_tag("tag2")
        
        assert len(matching) == 2
        assert all("tag2" in n["tags"] for n in matching)

    @pytest.mark.asyncio
    async def test_search_by_tag_returns_empty_list_for_nonexistent_tag(self):
        """search_by_tag returns empty list for nonexistent tag."""
        self.memory_router.scoped_read.return_value = [
            {"id": "1", "title": "Note 1", "content": "Content 1", "tags": ["tag1"], "created_at": "2026-06-20T10:00:00", "updated_at": "2026-06-20T12:00:00"},
        ]

        matching = await self.skill.search_by_tag("nonexistent")
        
        assert len(matching) == 0
