"""Tests for EmailSkill."""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from uuid import uuid4

from skills.email.email_skill import EmailSkill
from core.observability import MemoryTraceEmitter
from core.approval_gate import ApprovalGate, ApprovalRequest, ApprovalActionType, ApprovalResponse
from core.exceptions import SkillExecutionError


class TestEmailSkill:
    """Test suite for EmailSkill."""

    def setup_method(self):
        """Set up test fixtures."""
        self.emitter = MemoryTraceEmitter()
        self.approval_gate = AsyncMock(spec=ApprovalGate)
        self.skill = EmailSkill(
            emitter=self.emitter,
            approval_gate=self.approval_gate,
            imap_host="imap.example.com",
            smtp_host="smtp.example.com",
            username="test@example.com",
            password="testpass",
        )

    def test_email_skill_initialises_with_correct_defaults(self):
        """EmailSkill initialises with correct defaults."""
        skill = EmailSkill(
            emitter=self.emitter,
            approval_gate=self.approval_gate,
        )
        assert skill._emitter == self.emitter
        assert skill._approval_gate == self.approval_gate
        assert skill._imap_port == 993
        assert skill._smtp_port == 587

    def test_email_skill_loads_credentials_from_env_vars(self):
        """EmailSkill loads credentials from env vars when not passed."""
        os.environ["EMAIL_IMAP_HOST"] = "imap.env.com"
        os.environ["EMAIL_SMTP_HOST"] = "smtp.env.com"
        os.environ["EMAIL_USERNAME"] = "env@example.com"
        os.environ["EMAIL_PASSWORD"] = "envpass"
        
        skill = EmailSkill(emitter=self.emitter)
        assert skill._imap_host == "imap.env.com"
        assert skill._smtp_host == "smtp.env.com"
        assert skill._username == "env@example.com"
        assert skill._password == "envpass"
        
        # Clean up
        del os.environ["EMAIL_IMAP_HOST"]
        del os.environ["EMAIL_SMTP_HOST"]
        del os.environ["EMAIL_USERNAME"]
        del os.environ["EMAIL_PASSWORD"]

    @pytest.mark.asyncio
    async def test_read_inbox_returns_correctly_structured_list_from_mocked_imap(self):
        """read_inbox returns correctly structured list from mocked IMAP."""
        mock_mail = MagicMock()
        mock_mail.search.return_value = ("OK", [b"1"])
        
        def mock_fetch(email_id, criteria):
            if criteria == "(RFC822)":
                return ("OK", [(None, b"From: sender@example.com\r\nSubject: Test\r\nDate: Mon, 01 Jan 2026 12:00:00 +0000\r\n\r\nTest body")])
            elif criteria == "(FLAGS)":
                return ("OK", [b"\\Seen"])
            return ("OK", [])
        
        mock_mail.fetch = mock_fetch
        mock_mail.select.return_value = ("OK", [b"0"])
        mock_mail.close.return_value = ("OK", [])
        mock_mail.logout.return_value = ("OK", [])

        with patch("imaplib.IMAP4_SSL", return_value=mock_mail):
            result = await self.skill.read_inbox(limit=1, unread_only=False)
            
            assert len(result) == 1
            assert "uid" in result[0]
            assert "subject" in result[0]
            assert "sender" in result[0]
            assert "date" in result[0]
            assert "body_preview" in result[0]
            assert "unread" in result[0]

    @pytest.mark.asyncio
    async def test_read_inbox_respects_unread_only_flag(self):
        """read_inbox respects unread_only=True flag."""
        mock_mail = MagicMock()
        mock_mail.search.return_value = ("OK", [b"1"])
        
        def mock_fetch(email_id, criteria):
            if criteria == "(RFC822)":
                return ("OK", [(None, b"From: sender@example.com\r\nSubject: Test\r\nDate: Mon, 01 Jan 2026 12:00:00 +0000\r\n\r\nTest body")])
            elif criteria == "(FLAGS)":
                return ("OK", [b"\\Seen"])
            return ("OK", [])
        
        mock_mail.fetch = mock_fetch
        mock_mail.select.return_value = ("OK", [b"0"])
        mock_mail.close.return_value = ("OK", [])
        mock_mail.logout.return_value = ("OK", [])

        with patch("imaplib.IMAP4_SSL", return_value=mock_mail):
            await self.skill.read_inbox(unread_only=True)
            
            # Verify search was called with UNSEEN
            mock_mail.search.assert_called_once_with(None, "UNSEEN")

    @pytest.mark.asyncio
    async def test_read_inbox_respects_limit_parameter(self):
        """read_inbox respects limit parameter."""
        mock_mail = MagicMock()
        mock_mail.search.return_value = ("OK", [b"1 2 3 4 5"])
        
        def mock_fetch(email_id, criteria):
            if criteria == "(RFC822)":
                return ("OK", [(None, b"From: sender@example.com\r\nSubject: Test\r\nDate: Mon, 01 Jan 2026 12:00:00 +0000\r\n\r\nTest body")])
            elif criteria == "(FLAGS)":
                return ("OK", [b"\\Seen"])
            return ("OK", [])
        
        mock_mail.fetch = mock_fetch
        mock_mail.select.return_value = ("OK", [b"0"])
        mock_mail.close.return_value = ("OK", [])
        mock_mail.logout.return_value = ("OK", [])

        with patch("imaplib.IMAP4_SSL", return_value=mock_mail):
            result = await self.skill.read_inbox(limit=2, unread_only=False)
            
            # Should limit to 2 messages
            assert len(result) <= 2

    @pytest.mark.asyncio
    async def test_read_inbox_raises_skill_execution_error_on_imap_connection_failure(self):
        """read_inbox raises SkillExecutionError on IMAP connection failure."""
        with patch("imaplib.IMAP4_SSL", side_effect=Exception("Connection failed")):
            with pytest.raises(SkillExecutionError) as exc_info:
                await self.skill.read_inbox()
            
            assert "Failed to read inbox" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_read_inbox_raises_skill_execution_error_when_imap_host_missing(self):
        """read_inbox raises SkillExecutionError when IMAP host missing."""
        skill = EmailSkill(emitter=self.emitter, imap_host=None)
        
        with pytest.raises(SkillExecutionError) as exc_info:
            await skill.read_inbox()
        
        assert "EMAIL_IMAP_HOST" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_read_inbox_emits_trace_event_with_message_count(self):
        """read_inbox emits trace event with message count."""
        mock_mail = MagicMock()
        mock_mail.search.return_value = ("OK", [b"1 2"])
        
        def mock_fetch(email_id, criteria):
            if criteria == "(RFC822)":
                return ("OK", [(None, b"From: sender@example.com\r\nSubject: Test\r\nDate: Mon, 01 Jan 2026 12:00:00 +0000\r\n\r\nTest body")])
            elif criteria == "(FLAGS)":
                return ("OK", [b"\\Seen"])
            return ("OK", [])
        
        mock_mail.fetch = mock_fetch
        mock_mail.select.return_value = ("OK", [b"0"])
        mock_mail.close.return_value = ("OK", [])
        mock_mail.logout.return_value = ("OK", [])

        with patch("imaplib.IMAP4_SSL", return_value=mock_mail):
            await self.skill.read_inbox(unread_only=False)
            
            events = self.emitter.get_events()
            assert len(events) >= 2
            # Check for operation_complete event with message_count
            complete_events = [e for e in events if e.event_type == "operation_complete"]
            assert len(complete_events) > 0
            assert "message_count" in complete_events[0].data

    @pytest.mark.asyncio
    async def test_send_raises_skill_execution_error_when_no_approval_gate_injected(self):
        """send raises SkillExecutionError when no approval_gate is injected."""
        skill = EmailSkill(emitter=self.emitter, approval_gate=None)
        
        with pytest.raises(SkillExecutionError) as exc_info:
            await skill.send("recipient@example.com", "Test", "Body")
        
        assert "Approval gate not injected" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_send_requests_approval_before_sending(self):
        """send requests approval before sending."""
        self.approval_gate.request_approval.return_value = ApprovalResponse(
            request_id=str(uuid4()),
            task_id=str(uuid4()),
            approved=True,
            decision_reason="Approved",
            approved_by="test_user",
            approved_at=datetime.now(timezone.utc),
        )

        mock_smtp = MagicMock()
        mock_smtp.starttls.return_value = None
        mock_smtp.login.return_value = (235, b"OK")
        mock_smtp.send_message.return_value = {}
        mock_smtp.quit.return_value = (221, b"Bye")

        with patch("smtplib.SMTP", return_value=mock_smtp):
            await self.skill.send("recipient@example.com", "Test", "Body")
            
            # Verify approval was requested
            self.approval_gate.request_approval.assert_called_once()
            request = self.approval_gate.request_approval.call_args[0][0]
            assert isinstance(request, ApprovalRequest)
            assert request.action_type == ApprovalActionType.NETWORK_REQUEST

    @pytest.mark.asyncio
    async def test_send_raises_skill_execution_error_on_approval_denial(self):
        """send raises SkillExecutionError on approval denial."""
        self.approval_gate.request_approval.return_value = ApprovalResponse(
            request_id=str(uuid4()),
            task_id=str(uuid4()),
            approved=False,
            decision_reason="Denied",
            approved_by="test_user",
            approved_at=datetime.now(timezone.utc),
        )

        with pytest.raises(SkillExecutionError) as exc_info:
            await self.skill.send("recipient@example.com", "Test", "Body")
        
        assert "Approval denied" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_send_raises_skill_execution_error_on_smtp_failure(self):
        """send raises SkillExecutionError on SMTP failure."""
        self.approval_gate.request_approval.return_value = ApprovalResponse(
            request_id=str(uuid4()),
            task_id=str(uuid4()),
            approved=True,
            decision_reason="Approved",
            approved_by="test_user",
            approved_at=datetime.now(timezone.utc),
        )

        with patch("smtplib.SMTP", side_effect=Exception("SMTP failed")):
            with pytest.raises(SkillExecutionError) as exc_info:
                await self.skill.send("recipient@example.com", "Test", "Body")
            
            assert "Failed to send email" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_send_emits_trace_event_with_to_and_subject_length(self):
        """send emits trace event with to and subject_length — never body text."""
        self.approval_gate.request_approval.return_value = ApprovalResponse(
            request_id=str(uuid4()),
            task_id=str(uuid4()),
            approved=True,
            decision_reason="Approved",
            approved_by="test_user",
            approved_at=datetime.now(timezone.utc),
        )

        mock_smtp = MagicMock()
        mock_smtp.starttls.return_value = None
        mock_smtp.login.return_value = (235, b"OK")
        mock_smtp.send_message.return_value = {}
        mock_smtp.quit.return_value = (221, b"Bye")

        with patch("smtplib.SMTP", return_value=mock_smtp):
            await self.skill.send("recipient@example.com", "Test Subject", "Test Body")
            
            events = self.emitter.get_events()
            assert len(events) >= 2
            # Check for operation_complete event
            complete_events = [e for e in events if e.event_type == "operation_complete"]
            assert len(complete_events) > 0
            assert "to" in complete_events[0].data
            assert "subject_length" in complete_events[0].data
            # Verify body is not in the trace event data
            assert "body" not in complete_events[0].data
            assert "Test Body" not in str(complete_events[0].data)

    @pytest.mark.asyncio
    async def test_send_raises_skill_execution_error_when_smtp_host_missing(self):
        """send raises SkillExecutionError when SMTP host missing."""
        skill = EmailSkill(emitter=self.emitter, approval_gate=self.approval_gate, smtp_host=None)
        
        self.approval_gate.request_approval.return_value = ApprovalResponse(
            request_id=str(uuid4()),
            task_id=str(uuid4()),
            approved=True,
            decision_reason="Approved",
            approved_by="test_user",
            approved_at=datetime.now(timezone.utc),
        )

        with pytest.raises(SkillExecutionError) as exc_info:
            await skill.send("recipient@example.com", "Test", "Body")
        
        assert "EMAIL_SMTP_HOST" in str(exc_info.value)
