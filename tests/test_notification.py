"""
Tests for Notification System.
"""

import pytest
from unittest.mock import AsyncMock
from uuid import uuid4

from core.notification import NotificationSystem, Notification, NotificationType
from core.observability import (
    TraceEventType,
    MemoryTraceEmitter,
)
from core.approval_gate import ApprovalGate, ApprovalResponse


@pytest.mark.asyncio
class TestNotificationSystem:
    """Test suite for NotificationSystem."""

    @pytest.fixture
    def emitter(self):
        """Create a memory trace emitter for testing."""
        return MemoryTraceEmitter()

    @pytest.fixture
    def mock_approval_gate(self):
        """Create a mock approval gate."""
        gate = AsyncMock(spec=ApprovalGate)
        gate.request_approval = AsyncMock(return_value=ApprovalResponse(
            request_id=str(uuid4()),
            task_id=str(uuid4()),
            approved=True,
            approved_by="test_user",
        ))
        return gate

    @pytest.fixture
    def notification_system(self, emitter):
        """Create a NotificationSystem instance for testing."""
        return NotificationSystem(emitter=emitter)

    async def test_info_notification_queued_not_immediately_delivered(self, notification_system, emitter):
        """Test that INFO notification is queued, not immediately delivered."""
        notification = Notification(
            type=NotificationType.INFO,
            title="Test Info",
            message="Test message",
            source="test_component",
        )
        await notification_system.notify(notification)

        assert notification.delivered is False
        assert len(notification_system.pending()) == 1

    async def test_warning_notification_queued(self, notification_system, emitter):
        """Test that WARNING notification is queued."""
        notification = Notification(
            type=NotificationType.WARNING,
            title="Test Warning",
            message="Test warning message",
            source="test_component",
        )
        await notification_system.notify(notification)

        assert notification.delivered is False
        assert len(notification_system.pending()) == 1

    async def test_urgent_notification_delivered_immediately_not_queued(self, notification_system, emitter):
        """Test that URGENT notification is delivered immediately, not queued."""
        notification = Notification(
            type=NotificationType.URGENT,
            title="Test Urgent",
            message="Test urgent message",
            source="test_component",
        )
        await notification_system.notify(notification)

        assert notification.delivered is True
        assert len(notification_system.pending()) == 0

    async def test_requires_action_with_approval_gate_present_routes_through_gate(self, mock_approval_gate, emitter):
        """Test that REQUIRES_ACTION with approval gate present routes through gate."""
        notification_system = NotificationSystem(approval_gate=mock_approval_gate, emitter=emitter)
        notification = Notification(
            type=NotificationType.REQUIRES_ACTION,
            title="Test Action",
            message="Test action message",
            source="test_component",
        )
        await notification_system.notify(notification)

        mock_approval_gate.request_approval.assert_called_once()
        assert notification.delivered is True

    async def test_requires_action_with_no_approval_gate_treated_as_urgent(self, emitter):
        """Test that REQUIRES_ACTION with no approval gate is treated as URGENT."""
        notification_system = NotificationSystem(approval_gate=None, emitter=emitter)
        notification = Notification(
            type=NotificationType.REQUIRES_ACTION,
            title="Test Action",
            message="Test action message",
            source="test_component",
        )
        await notification_system.notify(notification)

        assert notification.delivered is True

    async def test_flush_queue_delivers_all_queued_items_clears_queue(self, notification_system, emitter):
        """Test that flush_queue() delivers all queued items, clears queue."""
        notification1 = Notification(
            type=NotificationType.INFO,
            title="Test 1",
            message="Message 1",
            source="test",
        )
        notification2 = Notification(
            type=NotificationType.WARNING,
            title="Test 2",
            message="Message 2",
            source="test",
        )
        await notification_system.notify(notification1)
        await notification_system.notify(notification2)

        delivered = await notification_system.flush_queue()

        assert len(delivered) == 2
        assert all(n.delivered for n in delivered)
        assert len(notification_system.pending()) == 0

    async def test_pending_returns_undelivered_items_without_flushing(self, notification_system, emitter):
        """Test that pending() returns undelivered items without flushing."""
        notification = Notification(
            type=NotificationType.INFO,
            title="Test",
            message="Message",
            source="test",
        )
        await notification_system.notify(notification)

        pending = notification_system.pending()

        assert len(pending) == 1
        assert pending[0].delivered is False
        assert len(notification_system.pending()) == 1  # Queue not flushed

    async def test_trace_event_emitted_on_each_notification_type(self, notification_system, emitter):
        """Test that trace event is emitted on each notification type."""
        for notification_type in [NotificationType.INFO, NotificationType.WARNING, NotificationType.URGENT]:
            notification = Notification(
                type=notification_type,
                title="Test",
                message="Message",
                source="test",
            )
            await notification_system.notify(notification)

        events = emitter.get_events()
        start_events = [e for e in events if e.event_type == TraceEventType.COMPONENT_START]
        assert len(start_events) == 3

    async def test_trace_event_emitted_on_delivery(self, notification_system, emitter):
        """Test that trace event is emitted on delivery."""
        notification = Notification(
            type=NotificationType.URGENT,
            title="Test",
            message="Message",
            source="test",
        )
        await notification_system.notify(notification)

        events = emitter.get_events()
        complete_events = [e for e in events if e.event_type == TraceEventType.OPERATION_COMPLETE]
        assert len(complete_events) >= 1
        assert "Notification delivered" in complete_events[0].message

    async def test_delivered_flag_set_to_true_after_delivery(self, notification_system, emitter):
        """Test that delivered flag is set to True after delivery."""
        notification = Notification(
            type=NotificationType.URGENT,
            title="Test",
            message="Message",
            source="test",
        )
        await notification_system.notify(notification)

        assert notification.delivered is True

    async def test_multiple_notifications_queue_correctly(self, notification_system, emitter):
        """Test that multiple notifications queue correctly."""
        for i in range(5):
            notification = Notification(
                type=NotificationType.INFO,
                title=f"Test {i}",
                message=f"Message {i}",
                source="test",
            )
            await notification_system.notify(notification)

        assert len(notification_system.pending()) == 5

    async def test_approved_action_notification_delivers_denied_action_does_not(self, mock_approval_gate, emitter):
        """Test that approved action notification delivers; denied action does not."""
        notification_system = NotificationSystem(approval_gate=mock_approval_gate, emitter=emitter)

        # Approved
        mock_approval_gate.request_approval = AsyncMock(return_value=ApprovalResponse(
            request_id=str(uuid4()),
            task_id=str(uuid4()),
            approved=True,
            approved_by="test_user",
        ))
        notification_approved = Notification(
            type=NotificationType.REQUIRES_ACTION,
            title="Approved Action",
            message="Approved message",
            source="test",
        )
        await notification_system.notify(notification_approved)
        assert notification_approved.delivered is True

        # Denied
        mock_approval_gate.request_approval = AsyncMock(return_value=ApprovalResponse(
            request_id=str(uuid4()),
            task_id=str(uuid4()),
            approved=False,
            decision_reason="Test denial",
            approved_by="test_user",
        ))
        notification_denied = Notification(
            type=NotificationType.REQUIRES_ACTION,
            title="Denied Action",
            message="Denied message",
            source="test",
        )
        await notification_system.notify(notification_denied)
        assert notification_denied.delivered is False

    async def test_invalid_notification_raises_value_error(self, notification_system, emitter):
        """Test that invalid notification raises ValueError."""
        with pytest.raises(ValueError, match="Notification must be a valid Notification instance"):
            await notification_system.notify(None)

    async def test_trace_event_fields_are_correct(self, notification_system, emitter):
        """Test that TraceEvent fields are correct (event_type, component, level, message, data, duration_ms)."""
        notification = Notification(
            type=NotificationType.INFO,
            title="Test",
            message="Message",
            source="test",
        )
        await notification_system.notify(notification)

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

    async def test_telegram_gateway_called_when_set_and_notification_is_requires_action(self, emitter):
        """Test that telegram gateway is called when set and notification is REQUIRES_ACTION."""
        from unittest.mock import AsyncMock

        mock_gateway = AsyncMock()
        mock_gateway.send_notification = AsyncMock(return_value=True)

        notification_system = NotificationSystem(
            approval_gate=None,
            telegram_gateway=mock_gateway,
            emitter=emitter,
        )

        notification = Notification(
            type=NotificationType.REQUIRES_ACTION,
            title="Test Action",
            message="Test message",
            source="test",
        )
        await notification_system.notify(notification)

        mock_gateway.send_notification.assert_called_once_with(notification)

    async def test_telegram_gateway_not_called_when_none(self, emitter):
        """Test that telegram gateway is not called when None."""
        from unittest.mock import AsyncMock

        mock_gateway = AsyncMock()
        mock_gateway.send_notification = AsyncMock(return_value=True)

        notification_system = NotificationSystem(
            approval_gate=None,
            telegram_gateway=None,
            emitter=emitter,
        )

        notification = Notification(
            type=NotificationType.REQUIRES_ACTION,
            title="Test Action",
            message="Test message",
            source="test",
        )
        await notification_system.notify(notification)

        # Gateway should not be called since it's None
        assert mock_gateway.send_notification.call_count == 0

    async def test_telegram_gateway_not_called_for_info_notifications(self, emitter):
        """Test that telegram gateway is not called for INFO notifications."""
        from unittest.mock import AsyncMock

        mock_gateway = AsyncMock()
        mock_gateway.send_notification = AsyncMock(return_value=True)

        notification_system = NotificationSystem(
            approval_gate=None,
            telegram_gateway=mock_gateway,
            emitter=emitter,
        )

        notification = Notification(
            type=NotificationType.INFO,
            title="Test Info",
            message="Test message",
            source="test",
        )
        await notification_system.notify(notification)

        # Gateway should not be called for INFO notifications
        assert mock_gateway.send_notification.call_count == 0
