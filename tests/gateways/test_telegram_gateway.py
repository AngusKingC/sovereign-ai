"""
Tests for Telegram Gateway.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from gateways.telegram.gateway import TelegramGateway
from core.notification import Notification, NotificationType
from core.observability import (
    TraceEvent,
    TraceEventType,
    TraceLevel,
    TraceComponent,
    MemoryTraceEmitter,
)


@pytest.mark.asyncio
class TestTelegramGateway:
    """Test suite for TelegramGateway."""

    @pytest.fixture
    def emitter(self):
        """Create a memory trace emitter for testing."""
        return MemoryTraceEmitter()

    @pytest.fixture
    def gateway(self, emitter):
        """Create a TelegramGateway instance for testing."""
        return TelegramGateway(
            bot_token="test_token",
            chat_id="test_chat_id",
            emitter=emitter,
        )

    async def test_send_message_success_returns_true_emits_trace_event(self, gateway, emitter):
        """Test that send_message success (200 response) returns True, emits trace event."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"ok": True})

        with patch("gateways.telegram.gateway.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await gateway.send_message("test message")

        assert result is True

        events = emitter.get_events()
        complete_events = [e for e in events if e.event_type == TraceEventType.OPERATION_COMPLETE]
        assert len(complete_events) >= 1
        assert "Telegram message sent successfully" in complete_events[0].message

        # Ensure bot_token and chat_id never appear in trace event data
        for event in events:
            assert "bot_token" not in event.data
            assert "test_token" not in str(event.data)
            assert "chat_id" not in event.data
            assert "test_chat_id" not in str(event.data)

    async def test_send_message_http_failure_returns_false_emits_trace_event_does_not_raise(self, gateway, emitter):
        """Test that send_message HTTP failure (non-200) returns False, emits trace event, does not raise."""
        import httpx

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock(side_effect=httpx.HTTPStatusError("Error", request=MagicMock(), response=MagicMock()))

        with patch("gateways.telegram.gateway.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await gateway.send_message("test message")

        assert result is False

        events = emitter.get_events()
        error_events = [e for e in events if e.event_type == TraceEventType.OPERATION_ERROR]
        assert len(error_events) >= 1
        assert "Telegram message send failed" in error_events[0].message

    async def test_send_message_network_exception_returns_false_emits_trace_event_does_not_raise(self, gateway, emitter):
        """Test that send_message network exception returns False, emits trace event, does not raise."""
        with patch("gateways.telegram.gateway.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value.post = AsyncMock(side_effect=Exception("Network error"))
            mock_client_class.return_value = mock_client

            result = await gateway.send_message("test message")

        assert result is False

        events = emitter.get_events()
        error_events = [e for e in events if e.event_type == TraceEventType.OPERATION_ERROR]
        assert len(error_events) >= 1

    async def test_send_notification_with_info_type_correct_emoji_prefix(self, gateway, emitter):
        """Test that send_notification with INFO type has correct emoji prefix in message text."""
        notification = Notification(
            type=NotificationType.INFO,
            title="Test Info",
            message="Test message",
            source="test",
        )

        with patch("gateways.telegram.gateway.httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            await gateway.send_notification(notification)

        call_args = mock_client.__aenter__.return_value.post.call_args
        assert call_args is not None
        message_text = call_args[1]["json"]["text"]
        assert "ℹ️" in message_text
        assert "Test Info" in message_text

    async def test_send_notification_with_warning_type_correct_emoji_prefix(self, gateway, emitter):
        """Test that send_notification with WARNING type has correct emoji prefix."""
        notification = Notification(
            type=NotificationType.WARNING,
            title="Test Warning",
            message="Test message",
            source="test",
        )

        with patch("gateways.telegram.gateway.httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            await gateway.send_notification(notification)

        call_args = mock_client.__aenter__.return_value.post.call_args
        message_text = call_args[1]["json"]["text"]
        assert "⚠️" in message_text

    async def test_send_notification_with_requires_action_type_correct_emoji_prefix(self, gateway, emitter):
        """Test that send_notification with REQUIRES_ACTION type has correct emoji prefix."""
        notification = Notification(
            type=NotificationType.REQUIRES_ACTION,
            title="Test Action",
            message="Test message",
            source="test",
        )

        with patch("gateways.telegram.gateway.httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            await gateway.send_notification(notification)

        call_args = mock_client.__aenter__.return_value.post.call_args
        message_text = call_args[1]["json"]["text"]
        assert "🔔" in message_text

    async def test_send_notification_with_urgent_type_correct_emoji_prefix(self, gateway, emitter):
        """Test that send_notification with URGENT type has correct emoji prefix."""
        notification = Notification(
            type=NotificationType.URGENT,
            title="Test Urgent",
            message="Test message",
            source="test",
        )

        with patch("gateways.telegram.gateway.httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            await gateway.send_notification(notification)

        call_args = mock_client.__aenter__.return_value.post.call_args
        message_text = call_args[1]["json"]["text"]
        assert "🚨" in message_text

    async def test_send_notification_success_returns_true(self, gateway, emitter):
        """Test that send_notification success returns True."""
        notification = Notification(
            type=NotificationType.INFO,
            title="Test",
            message="Test message",
            source="test",
        )

        with patch("gateways.telegram.gateway.httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await gateway.send_notification(notification)

        assert result is True

    async def test_send_notification_failure_returns_false(self, gateway, emitter):
        """Test that send_notification failure returns False."""
        notification = Notification(
            type=NotificationType.INFO,
            title="Test",
            message="Test message",
            source="test",
        )

        with patch("gateways.telegram.gateway.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value.post = AsyncMock(side_effect=Exception("Error"))
            mock_client_class.return_value = mock_client

            result = await gateway.send_notification(notification)

        assert result is False

    async def test_poll_updates_success_returns_list_of_update_dicts(self, gateway, emitter):
        """Test that poll_updates success returns list of update dicts."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"result": [{"update_id": 1, "message": {"text": "test"}}]})

        with patch("gateways.telegram.gateway.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await gateway.poll_updates()

        assert len(result) == 1
        assert result[0]["update_id"] == 1

    async def test_poll_updates_http_failure_returns_empty_list_does_not_raise(self, gateway, emitter):
        """Test that poll_updates HTTP failure returns empty list, does not raise."""
        import httpx

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock(side_effect=httpx.HTTPStatusError("Error", request=MagicMock(), response=MagicMock()))

        with patch("gateways.telegram.gateway.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await gateway.poll_updates()

        assert result == []

    async def test_poll_updates_network_exception_returns_empty_list_does_not_raise(self, gateway, emitter):
        """Test that poll_updates network exception returns empty list, does not raise."""
        with patch("gateways.telegram.gateway.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value.get = AsyncMock(side_effect=Exception("Network error"))
            mock_client_class.return_value = mock_client

            result = await gateway.poll_updates()

        assert result == []

    async def test_extract_commands_with_mixed_messages_returns_only_slash_prefixed_entries(self, gateway):
        """Test that extract_commands with mixed messages returns only /-prefixed entries."""
        updates = [
            {"update_id": 1, "message": {"text": "/start"}},
            {"update_id": 2, "message": {"text": "regular message"}},
            {"update_id": 3, "message": {"text": "/help"}},
            {"update_id": 4, "message": {"text": "another regular"}},
        ]

        result = await gateway.extract_commands(updates)

        assert len(result) == 2
        assert "/start" in result
        assert "/help" in result
        assert "regular message" not in result

    async def test_extract_commands_with_no_commands_returns_empty_list(self, gateway):
        """Test that extract_commands with no commands returns empty list."""
        updates = [
            {"update_id": 1, "message": {"text": "regular message"}},
            {"update_id": 2, "message": {"text": "another regular"}},
        ]

        result = await gateway.extract_commands(updates)

        assert result == []

    async def test_trace_event_fields_are_correct(self, gateway, emitter):
        """Test that TraceEvent fields are correct (event_type, component, level, message, data, duration_ms)."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"ok": True})

        with patch("gateways.telegram.gateway.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            await gateway.send_message("test")

        events = emitter.get_events()
        for event in events:
            assert hasattr(event, "event_type")
            assert hasattr(event, "component")
            assert hasattr(event, "level")
            assert hasattr(event, "message")
            assert hasattr(event, "data")
            assert hasattr(event, "duration_ms")
            # Should NOT have these fields from the incorrect schema
            assert not hasattr(event, "layer")
            assert not hasattr(event, "payload")
            assert not hasattr(event, "success")
