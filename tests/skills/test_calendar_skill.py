"""Tests for CalendarSkill."""

import os
import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock

from skills.calendar.calendar_skill import CalendarSkill
from core.observability import MemoryTraceEmitter
from core.approval_gate import ApprovalGate, ApprovalRequest, ApprovalActionType, ApprovalResponse
from core.exceptions import SkillExecutionError


class TestCalendarSkill:
    """Test suite for CalendarSkill."""

    def setup_method(self):
        """Set up test fixtures."""
        self.emitter = MemoryTraceEmitter()
        self.approval_gate = AsyncMock(spec=ApprovalGate)
        self.skill = CalendarSkill(
            emitter=self.emitter,
            approval_gate=self.approval_gate,
            calendar_path="test.ics",
        )

    def test_calendar_skill_initialises_with_correct_defaults(self):
        """CalendarSkill initialises with correct defaults."""
        skill = CalendarSkill(
            emitter=self.emitter,
            approval_gate=self.approval_gate,
        )
        assert skill._emitter == self.emitter
        assert skill._approval_gate == self.approval_gate

    def test_calendar_skill_loads_calendar_path_from_env_var(self):
        """CalendarSkill loads calendar_path from env var when not passed."""
        os.environ["CALENDAR_ICS_PATH"] = "test_env.ics"
        
        skill = CalendarSkill(emitter=self.emitter)
        assert skill._calendar_path == "test_env.ics"
        
        # Clean up
        del os.environ["CALENDAR_ICS_PATH"]

    @pytest.mark.asyncio
    async def test_get_upcoming_returns_correctly_parsed_events_from_test_ics_string(self):
        """get_upcoming returns correctly parsed events from a test ICS string."""
        # Create a test ICS file
        ics_content = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Calendar//EN
BEGIN:VEVENT
UID:test1@example.com
DTSTART:20260620T140000Z
DTEND:20260620T150000Z
SUMMARY:Test Event
LOCATION:Test Location
DESCRIPTION:Test Description
END:VEVENT
END:VCALENDAR"""
        
        with open("test.ics", "wb") as f:
            f.write(ics_content)
        
        try:
            result = await self.skill.get_upcoming(days=7)
            
            assert len(result) == 1
            assert result[0]["uid"] == "test1@example.com"
            assert result[0]["summary"] == "Test Event"
            assert "start" in result[0]
            assert "end" in result[0]
            assert result[0]["location"] == "Test Location"
            assert result[0]["description"] == "Test Description"
        finally:
            if os.path.exists("test.ics"):
                os.remove("test.ics")

    @pytest.mark.asyncio
    async def test_get_upcoming_filters_to_only_events_within_requested_day_window(self):
        """get_upcoming filters to only events within the requested day window."""
        now = datetime.utcnow()
        future_event = now + timedelta(days=5)
        past_event = now - timedelta(days=5)
        
        ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Calendar//EN
BEGIN:VEVENT
UID:future@example.com
DTSTART:{future_event.strftime("%Y%m%dT%H%M%SZ")}
DTEND:{future_event.strftime("%Y%m%dT%H%M%SZ")}
SUMMARY:Future Event
END:VEVENT
BEGIN:VEVENT
UID:past@example.com
DTSTART:{past_event.strftime("%Y%m%dT%H%M%SZ")}
DTEND:{past_event.strftime("%Y%m%dT%H%M%SZ")}
SUMMARY:Past Event
END:VEVENT
END:VCALENDAR""".encode()
        
        with open("test.ics", "wb") as f:
            f.write(ics_content)
        
        try:
            result = await self.skill.get_upcoming(days=7)
            
            # Should only include the future event
            assert len(result) == 1
            assert result[0]["uid"] == "future@example.com"
        finally:
            if os.path.exists("test.ics"):
                os.remove("test.ics")

    @pytest.mark.asyncio
    async def test_get_upcoming_returns_events_sorted_by_start_time(self):
        """get_upcoming returns events sorted by start time."""
        now = datetime.utcnow()
        event1 = now + timedelta(days=3)
        event2 = now + timedelta(days=1)
        
        ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Calendar//EN
BEGIN:VEVENT
UID:event1@example.com
DTSTART:{event1.strftime("%Y%m%dT%H%M%SZ")}
DTEND:{event1.strftime("%Y%m%dT%H%M%SZ")}
SUMMARY:Event 1
END:VEVENT
BEGIN:VEVENT
UID:event2@example.com
DTSTART:{event2.strftime("%Y%m%dT%H%M%SZ")}
DTEND:{event2.strftime("%Y%m%dT%H%M%SZ")}
SUMMARY:Event 2
END:VEVENT
END:VCALENDAR""".encode()
        
        with open("test.ics", "wb") as f:
            f.write(ics_content)
        
        try:
            result = await self.skill.get_upcoming(days=7)
            
            # Should be sorted by start time
            assert len(result) == 2
            assert result[0]["uid"] == "event2@example.com"
            assert result[1]["uid"] == "event1@example.com"
        finally:
            if os.path.exists("test.ics"):
                os.remove("test.ics")

    @pytest.mark.asyncio
    async def test_get_upcoming_raises_skill_execution_error_when_ics_file_not_found(self):
        """get_upcoming raises SkillExecutionError when ICS file not found."""
        skill = CalendarSkill(emitter=self.emitter, calendar_path="nonexistent.ics")
        
        with pytest.raises(SkillExecutionError) as exc_info:
            await skill.get_upcoming()
        
        assert "Calendar file not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_upcoming_raises_skill_execution_error_when_calendar_path_not_set(self):
        """get_upcoming raises SkillExecutionError when calendar path not set."""
        skill = CalendarSkill(emitter=self.emitter, calendar_path=None)
        
        with pytest.raises(SkillExecutionError) as exc_info:
            await skill.get_upcoming()
        
        assert "CALENDAR_ICS_PATH" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_upcoming_emits_trace_event_with_event_count(self):
        """get_upcoming emits trace event with event count."""
        now = datetime.utcnow()
        future_event = now + timedelta(days=1)
        
        ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Calendar//EN
BEGIN:VEVENT
UID:test@example.com
DTSTART:{future_event.strftime("%Y%m%dT%H%M%SZ")}
DTEND:{future_event.strftime("%Y%m%dT%H%M%SZ")}
SUMMARY:Test Event
END:VEVENT
END:VCALENDAR""".encode()
        
        with open("test.ics", "wb") as f:
            f.write(ics_content)
        
        try:
            await self.skill.get_upcoming(days=7)
            
            events = self.emitter.get_events()
            assert len(events) >= 2
            # Check for operation_complete event with event_count
            complete_events = [e for e in events if e.event_type == "operation_complete"]
            assert len(complete_events) > 0
            assert "event_count" in complete_events[0].data
        finally:
            if os.path.exists("test.ics"):
                os.remove("test.ics")

    @pytest.mark.asyncio
    async def test_create_event_requests_approval_before_writing(self):
        """create_event requests approval before writing."""
        self.approval_gate.request_approval.return_value = ApprovalResponse(
            request_id=str(uuid4()),
            task_id=str(uuid4()),
            approved=True,
            decision_reason="Approved",
            approved_by="test_user",
            approved_at=datetime.utcnow(),
        )

        now = datetime.utcnow()
        start = now + timedelta(days=1)
        end = now + timedelta(days=1, hours=1)
        
        # Create empty ICS file
        ics_content = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Calendar//EN
END:VCALENDAR"""
        with open("test.ics", "wb") as f:
            f.write(ics_content)
        
        try:
            await self.skill.create_event(
                summary="Test Event",
                start=start.isoformat(),
                end=end.isoformat(),
            )
            
            # Verify approval was requested
            self.approval_gate.request_approval.assert_called_once()
            request = self.approval_gate.request_approval.call_args[0][0]
            assert isinstance(request, ApprovalRequest)
            assert request.action_type == ApprovalActionType.FILE_WRITE
        finally:
            if os.path.exists("test.ics"):
                os.remove("test.ics")

    @pytest.mark.asyncio
    async def test_create_event_appends_a_valid_vevent_to_the_ics_file(self):
        """create_event appends a valid VEVENT to the ICS file."""
        self.approval_gate.request_approval.return_value = ApprovalResponse(
            request_id=str(uuid4()),
            task_id=str(uuid4()),
            approved=True,
            decision_reason="Approved",
            approved_by="test_user",
            approved_at=datetime.utcnow(),
        )

        now = datetime.utcnow()
        start = now + timedelta(days=1)
        end = now + timedelta(days=1, hours=1)
        
        # Create empty ICS file
        ics_content = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Calendar//EN
END:VCALENDAR"""
        with open("test.ics", "wb") as f:
            f.write(ics_content)
        
        try:
            uid = await self.skill.create_event(
                summary="Test Event",
                start=start.isoformat(),
                end=end.isoformat(),
                location="Test Location",
                description="Test Description",
            )
            
            # Verify event was added
            from icalendar import Calendar
            with open("test.ics", "rb") as f:
                calendar = Calendar.from_ical(f.read())
            
            events = [c for c in calendar.walk() if c.name == "VEVENT"]
            assert len(events) == 1
            assert str(events[0].get("summary")) == "Test Event"
            assert str(events[0].get("location")) == "Test Location"
            assert str(events[0].get("description")) == "Test Description"
            assert uid == str(events[0].get("uid"))
        finally:
            if os.path.exists("test.ics"):
                os.remove("test.ics")

    @pytest.mark.asyncio
    async def test_create_event_raises_skill_execution_error_when_no_approval_gate_injected(self):
        """create_event raises SkillExecutionError when no approval gate is injected."""
        skill = CalendarSkill(emitter=self.emitter, approval_gate=None, calendar_path="test.ics")
        
        with pytest.raises(SkillExecutionError) as exc_info:
            await skill.create_event("Test", "2026-06-20T14:00:00", "2026-06-20T15:00:00")
        
        assert "Approval gate not injected" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_cancel_event_sets_status_cancelled_on_correct_event_by_uid(self):
        """cancel_event sets STATUS:CANCELLED on the correct event by UID."""
        self.approval_gate.request_approval.return_value = ApprovalResponse(
            request_id=str(uuid4()),
            task_id=str(uuid4()),
            approved=True,
            decision_reason="Approved",
            approved_by="test_user",
            approved_at=datetime.utcnow(),
        )

        now = datetime.utcnow()
        future_event = now + timedelta(days=1)
        
        ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Calendar//EN
BEGIN:VEVENT
UID:test1@example.com
DTSTART:{future_event.strftime("%Y%m%dT%H%M%SZ")}
DTEND:{future_event.strftime("%Y%m%dT%H%M%SZ")}
SUMMARY:Event 1
END:VEVENT
BEGIN:VEVENT
UID:test2@example.com
DTSTART:{future_event.strftime("%Y%m%dT%H%M%SZ")}
DTEND:{future_event.strftime("%Y%m%dT%H%M%SZ")}
SUMMARY:Event 2
END:VEVENT
END:VCALENDAR""".encode()
        
        with open("test.ics", "wb") as f:
            f.write(ics_content)
        
        try:
            result = await self.skill.cancel_event("test1@example.com")
            
            assert result is True
            
            # Verify event was cancelled
            from icalendar import Calendar
            with open("test.ics", "rb") as f:
                calendar = Calendar.from_ical(f.read())
            
            events = [c for c in calendar.walk() if c.name == "VEVENT"]
            event1 = [e for e in events if str(e.get("uid")) == "test1@example.com"][0]
            assert str(event1.get("status")) == "CANCELLED"
        finally:
            if os.path.exists("test.ics"):
                os.remove("test.ics")

    @pytest.mark.asyncio
    async def test_cancel_event_returns_false_for_unknown_uid(self):
        """cancel_event returns False for unknown UID."""
        self.approval_gate.request_approval.return_value = ApprovalResponse(
            request_id=str(uuid4()),
            task_id=str(uuid4()),
            approved=True,
            decision_reason="Approved",
            approved_by="test_user",
            approved_at=datetime.utcnow(),
        )

        now = datetime.utcnow()
        future_event = now + timedelta(days=1)
        
        ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Calendar//EN
BEGIN:VEVENT
UID:test1@example.com
DTSTART:{future_event.strftime("%Y%m%dT%H%M%SZ")}
DTEND:{future_event.strftime("%Y%m%dT%H%M%SZ")}
SUMMARY:Event 1
END:VEVENT
END:VCALENDAR""".encode()
        
        with open("test.ics", "wb") as f:
            f.write(ics_content)
        
        try:
            result = await self.skill.cancel_event("unknown@example.com")
            
            assert result is False
        finally:
            if os.path.exists("test.ics"):
                os.remove("test.ics")

    @pytest.mark.asyncio
    async def test_cancel_event_raises_skill_execution_error_when_no_approval_gate_injected(self):
        """cancel_event raises SkillExecutionError when no approval gate is injected."""
        skill = CalendarSkill(emitter=self.emitter, approval_gate=None, calendar_path="test.ics")
        
        with pytest.raises(SkillExecutionError) as exc_info:
            await skill.cancel_event("test@example.com")
        
        assert "Approval gate not injected" in str(exc_info.value)
