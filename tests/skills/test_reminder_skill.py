"""Tests for ReminderSkill."""

import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from unittest.mock import AsyncMock

from skills.reminder.reminder_skill import ReminderSkill
from core.observability import MemoryTraceEmitter
from core.approval_gate import ApprovalGate, ApprovalRequest, ApprovalActionType, ApprovalResponse
from core.memory_router import MemoryRouter
from core.exceptions import SkillExecutionError


class TestReminderSkill:
    """Test suite for ReminderSkill."""

    def setup_method(self):
        """Set up test fixtures."""
        self.emitter = MemoryTraceEmitter()
        self.memory_router = AsyncMock()
        self.approval_gate = AsyncMock(spec=ApprovalGate)
        self.skill = ReminderSkill(
            memory_router=self.memory_router,
            emitter=self.emitter,
            approval_gate=self.approval_gate,
        )

    def test_reminder_skill_initialises_with_correct_defaults(self):
        """ReminderSkill initialises with correct defaults."""
        skill = ReminderSkill(
            memory_router=self.memory_router,
            emitter=self.emitter,
        )
        assert skill._emitter == self.emitter
        assert skill._memory_router == self.memory_router

    @pytest.mark.asyncio
    async def test_create_stores_reminder_with_correct_schema_in_memory_router(self):
        """create stores reminder with correct schema in MemoryRouter."""
        self.approval_gate.request_approval.return_value = ApprovalResponse(
            request_id=str(uuid4()),
            task_id=str(uuid4()),
            approved=True,
            decision_reason="Approved",
            approved_by="test_user",
            approved_at=datetime.now(timezone.utc),
        )

        due_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        reminder_id = await self.skill.create("Test reminder", due_at, "console")
        
        # Verify scoped_write was called with correct schema
        self.memory_router.scoped_write.assert_called_once()
        call_args = self.memory_router.scoped_write.call_args
        assert call_args[0][0] == "reminders"
        assert call_args[0][1].startswith("reminders:")
        reminder = call_args[0][2]
        assert "id" in reminder
        assert reminder["text"] == "Test reminder"
        assert reminder["due_at"] == due_at
        assert reminder["delivered"] is False
        assert reminder["channel"] == "console"
        assert reminder_id == reminder["id"]

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

        due_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        reminder_id = await self.skill.create("Test reminder", due_at)
        
        assert reminder_id is not None
        assert len(reminder_id) > 0

    @pytest.mark.asyncio
    async def test_create_emits_trace_event_with_due_at_and_channel(self):
        """create emits trace event with due_at and channel."""
        self.approval_gate.request_approval.return_value = ApprovalResponse(
            request_id=str(uuid4()),
            task_id=str(uuid4()),
            approved=True,
            decision_reason="Approved",
            approved_by="test_user",
            approved_at=datetime.now(timezone.utc),
        )

        due_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        await self.skill.create("Test reminder", due_at, "telegram")
        
        events = self.emitter.get_events()
        assert len(events) >= 2
        # Check for operation_complete event with due_at and channel
        complete_events = [e for e in events if e.event_type == "operation_complete"]
        assert len(complete_events) > 0
        assert "due_at" in complete_events[0].data
        assert "channel" in complete_events[0].data

    @pytest.mark.asyncio
    async def test_create_proceeds_without_approval_when_no_gate_injected(self):
        """create proceeds without approval when no gate injected (low-risk operation)."""
        skill = ReminderSkill(
            memory_router=self.memory_router,
            emitter=self.emitter,
            approval_gate=None,
        )

        due_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        reminder_id = await self.skill.create("Test reminder", due_at)
        
        # Verify scoped_write was called
        self.memory_router.scoped_write.assert_called_once()
        assert reminder_id is not None

    @pytest.mark.asyncio
    async def test_list_pending_returns_only_undelivered_reminders(self):
        """list_pending returns only undelivered reminders."""
        self.memory_router.scoped_read.return_value = [
            {"id": "1", "text": "Reminder 1", "due_at": "2026-06-20T12:00:00", "delivered": False, "channel": "console"},
            {"id": "2", "text": "Reminder 2", "due_at": "2026-06-20T13:00:00", "delivered": True, "channel": "console"},
            {"id": "3", "text": "Reminder 3", "due_at": "2026-06-20T14:00:00", "delivered": False, "channel": "console"},
        ]

        pending = await self.skill.list_pending()
        
        assert len(pending) == 2
        assert all(r["delivered"] is False for r in pending)

    @pytest.mark.asyncio
    async def test_list_pending_returns_results_sorted_by_due_at(self):
        """list_pending returns results sorted by due_at."""
        self.memory_router.scoped_read.return_value = [
            {"id": "1", "text": "Reminder 1", "due_at": "2026-06-20T14:00:00", "delivered": False, "channel": "console"},
            {"id": "2", "text": "Reminder 2", "due_at": "2026-06-20T12:00:00", "delivered": False, "channel": "console"},
            {"id": "3", "text": "Reminder 3", "due_at": "2026-06-20T13:00:00", "delivered": False, "channel": "console"},
        ]

        pending = await self.skill.list_pending()
        
        assert len(pending) == 3
        assert pending[0]["due_at"] == "2026-06-20T12:00:00"
        assert pending[1]["due_at"] == "2026-06-20T13:00:00"
        assert pending[2]["due_at"] == "2026-06-20T14:00:00"

    @pytest.mark.asyncio
    async def test_list_pending_emits_trace_event_with_pending_count(self):
        """list_pending emits trace event with pending_count."""
        self.memory_router.scoped_read.return_value = [
            {"id": "1", "text": "Reminder 1", "due_at": "2026-06-20T12:00:00", "delivered": False, "channel": "console"},
            {"id": "2", "text": "Reminder 2", "due_at": "2026-06-20T13:00:00", "delivered": False, "channel": "console"},
        ]

        await self.skill.list_pending()
        
        events = self.emitter.get_events()
        assert len(events) >= 2
        # Check for operation_complete event with pending_count
        complete_events = [e for e in events if e.event_type == "operation_complete"]
        assert len(complete_events) > 0
        assert "pending_count" in complete_events[0].data
        assert complete_events[0].data["pending_count"] == 2

    @pytest.mark.asyncio
    async def test_mark_delivered_sets_delivered_true_on_correct_reminder(self):
        """mark_delivered sets delivered=True on correct reminder."""
        reminder = {"id": "1", "text": "Reminder 1", "due_at": "2026-06-20T12:00:00", "delivered": False, "channel": "console"}
        self.memory_router.scoped_read.return_value = reminder

        result = await self.skill.mark_delivered("1")
        
        assert result is True
        # Verify scoped_write was called with delivered=True
        self.memory_router.scoped_write.assert_called_once()
        call_args = self.memory_router.scoped_write.call_args
        assert call_args[0][2]["delivered"] is True

    @pytest.mark.asyncio
    async def test_mark_delivered_returns_false_for_unknown_id(self):
        """mark_delivered returns False for unknown ID."""
        self.memory_router.scoped_read.return_value = None

        result = await self.skill.mark_delivered("unknown")
        
        assert result is False

    @pytest.mark.asyncio
    async def test_get_due_returns_only_reminders_whose_due_at_is_in_the_past(self):
        """get_due returns only reminders whose due_at is in the past."""
        now = datetime.now(timezone.utc)
        past = now - timedelta(hours=1)
        future = now + timedelta(hours=1)
        
        self.memory_router.scoped_read.return_value = [
            {"id": "1", "text": "Past reminder", "due_at": past.isoformat(), "delivered": False, "channel": "console"},
            {"id": "2", "text": "Future reminder", "due_at": future.isoformat(), "delivered": False, "channel": "console"},
        ]

        due = await self.skill.get_due()
        
        assert len(due) == 1
        assert due[0]["id"] == "1"

    @pytest.mark.asyncio
    async def test_get_due_does_not_return_already_delivered_reminders(self):
        """get_due does not return already-delivered reminders."""
        now = datetime.now(timezone.utc)
        past = now - timedelta(hours=1)
        
        self.memory_router.scoped_read.return_value = [
            {"id": "1", "text": "Undelivered past reminder", "due_at": past.isoformat(), "delivered": False, "channel": "console"},
            {"id": "2", "text": "Delivered past reminder", "due_at": past.isoformat(), "delivered": True, "channel": "console"},
        ]

        due = await self.skill.get_due()
        
        assert len(due) == 1
        assert due[0]["id"] == "1"
        assert due[0]["delivered"] is False
