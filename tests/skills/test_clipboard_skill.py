"""Clipboard skill tests."""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from skills.clipboard.skill import ClipboardSkill
from core.approval_gate import ApprovalGate
from core.observability import MemoryTraceEmitter, TraceEventType, TraceComponent


pytestmark = pytest.mark.asyncio


class TestClipboardSkill:
    """Test ClipboardSkill functionality."""

    @pytest.fixture
    def clipboard_skill(self):
        """Create a clipboard skill for testing."""
        return ClipboardSkill(
            emitter=MemoryTraceEmitter(),
            approval_gate=None,
        )

    async def test_read_returns_clipboard_string_content(self, clipboard_skill):
        """Test read() returns clipboard string content."""
        with patch("pyperclip.paste", return_value="test content"):
            result = await clipboard_skill.read()

        assert result == "test content"

    async def test_write_requires_approval_calls_pyperclip_copy_with_correct_content(self):
        """Test write() requires approval, calls pyperclip.copy with correct content."""
        mock_approval_gate = Mock(spec=ApprovalGate)
        mock_approval_gate.request_approval = AsyncMock(return_value=True)

        clipboard_skill = ClipboardSkill(
            emitter=MemoryTraceEmitter(),
            approval_gate=mock_approval_gate,
        )

        with patch("pyperclip.copy") as mock_copy:
            result = await clipboard_skill.write("test content")

        assert result["success"] is True
        mock_copy.assert_called_once_with("test content")
        mock_approval_gate.request_approval.assert_called_once()

    async def test_write_denied_by_approval_gate_pyperclip_copy_not_called(self):
        """Test write() denied by approval gate — pyperclip.copy not called."""
        mock_approval_gate = Mock(spec=ApprovalGate)
        mock_approval_gate.request_approval = AsyncMock(return_value=False)

        clipboard_skill = ClipboardSkill(
            emitter=MemoryTraceEmitter(),
            approval_gate=mock_approval_gate,
        )

        with patch("pyperclip.copy") as mock_copy:
            result = await clipboard_skill.write("test content")

        assert result["success"] is False
        mock_copy.assert_not_called()

    async def test_clear_requires_approval_clears_clipboard(self):
        """Test clear() requires approval, clears clipboard."""
        mock_approval_gate = Mock(spec=ApprovalGate)
        mock_approval_gate.request_approval = AsyncMock(return_value=True)

        clipboard_skill = ClipboardSkill(
            emitter=MemoryTraceEmitter(),
            approval_gate=mock_approval_gate,
        )

        with patch("pyperclip.copy") as mock_copy:
            result = await clipboard_skill.clear()

        assert result["success"] is True
        mock_copy.assert_called_once_with("")
        mock_approval_gate.request_approval.assert_called_once()

    async def test_trace_event_emitted_on_read_and_write(self, clipboard_skill):
        """Test trace event emitted on read and write."""
        with patch("pyperclip.paste", return_value="test"):
            await clipboard_skill.read()

        with patch("pyperclip.copy"):
            await clipboard_skill.write("test")

        events = clipboard_skill._emitter.get_events()
        assert len(events) > 0
        assert any(event.event_type == TraceEventType.CLIPBOARD_OPERATION for event in events)
        assert any(event.component == TraceComponent.CLIPBOARD_SKILL for event in events)

    async def test_read_handles_pyperclip_error_gracefully(self, clipboard_skill):
        """Test read() handles pyperclip error gracefully — returns empty string, does not raise."""
        with patch("pyperclip.paste", side_effect=Exception("Clipboard error")):
            result = await clipboard_skill.read()

        assert result == ""
