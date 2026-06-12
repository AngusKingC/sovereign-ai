"""
Notification System - routes interrupts and notifications with urgency-based delivery.

Single responsibility: Queue and deliver notifications based on urgency, integrate with ApprovalGate for action requests.
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from core.observability import (
    TraceComponent,
    TraceEventType,
    TraceLevel,
    TraceEvent,
    TraceEmitter,
    MemoryTraceEmitter,
)

if TYPE_CHECKING:
    from core.approval_gate import ApprovalGate


class NotificationType(str, Enum):
    """Urgency levels for notifications."""
    INFO = "info"
    WARNING = "warning"
    URGENT = "urgent"
    REQUIRES_ACTION = "requires_action"


class Notification(BaseModel):
    """A notification to be delivered to the user."""

    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique notification identifier")
    type: NotificationType = Field(..., description="Notification urgency type")
    title: str = Field(..., description="Notification title")
    message: str = Field(..., description="Notification message content")
    source: str = Field(..., description="Component that raised the notification")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="When notification was created")
    data: dict = Field(default_factory=dict, description="Arbitrary payload for downstream consumers")
    delivered: bool = Field(default=False, description="Whether notification has been delivered")


class NotificationSystem:
    """Manages notification queuing and delivery with urgency-based routing."""

    def __init__(
        self,
        approval_gate: "ApprovalGate | None" = None,
        telegram_gateway: "TelegramGateway | None" = None,
        emitter: TraceEmitter | None = None,
    ) -> None:
        """Initialize the notification system.

        Args:
            approval_gate: Optional approval gate for action-request notifications
            telegram_gateway: Optional Telegram gateway for outbound notifications
            emitter: Trace emitter for observability
        """
        self._emitter = emitter or MemoryTraceEmitter()
        self._approval_gate = approval_gate
        self._telegram_gateway = telegram_gateway
        self._queue: list[Notification] = []

    async def notify(self, notification: Notification) -> None:
        """
        Route a notification based on its type.

        Args:
            notification: The notification to route

        Raises:
            ValueError: If notification is invalid
        """
        if not notification or not isinstance(notification, Notification):
            raise ValueError("Notification must be a valid Notification instance")

        try:
            await self._emitter.emit(TraceEvent(
                event_type=TraceEventType.COMPONENT_START,
                component=TraceComponent.WORKER,
                level=TraceLevel.INFO,
                message="Notification received",
                data={
                    "notification_id": notification.id,
                    "type": notification.type.value,
                    "title": notification.title,
                    "source": notification.source,
                },
                duration_ms=0,
            ))
        except Exception:
            pass

        if notification.type in (NotificationType.INFO, NotificationType.WARNING):
            # Queue for later delivery
            self._queue.append(notification)
            try:
                await self._emitter.emit(TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.INFO,
                    message="Notification queued",
                    data={
                        "notification_id": notification.id,
                        "type": notification.type.value,
                        "queue_size": len(self._queue),
                    },
                    duration_ms=0,
                ))
            except Exception:
                pass

        elif notification.type == NotificationType.URGENT:
            # Deliver immediately
            await self._deliver(notification)

        elif notification.type == NotificationType.REQUIRES_ACTION:
            # Route through approval gate if present
            if self._approval_gate is not None:
                try:
                    from datetime import timedelta

                    from core.approval_gate import ApprovalRequest, ApprovalActionType

                    request = ApprovalRequest(
                        request_id=notification.id,
                        task_id=notification.id,  # Use notification ID as task ID
                        session_id="default",
                        action_type=ApprovalActionType.SYSTEM_CONFIG,
                        action_description=notification.title,
                        action_parameters=notification.data,
                        risk_level="medium",
                        reason_for_approval="Notification requires user action",
                        expires_at=datetime.utcnow() + timedelta(seconds=300),
                    )
                    response = await self._approval_gate.request_approval(request)

                    if response.approved:
                        await self._deliver(notification)
                    else:
                        # Denied - don't deliver
                        try:
                            await self._emitter.emit(TraceEvent(
                                event_type=TraceEventType.OPERATION_COMPLETE,
                                component=TraceComponent.WORKER,
                                level=TraceLevel.WARNING,
                                message="Action notification denied by approval gate",
                                data={
                                    "notification_id": notification.id,
                                    "reason": response.decision_reason,
                                },
                                duration_ms=0,
                            ))
                        except Exception:
                            pass
                except Exception as e:
                    # Approval gate failed - treat as urgent
                    try:
                        await self._emitter.emit(TraceEvent(
                            event_type=TraceEventType.OPERATION_ERROR,
                            component=TraceComponent.WORKER,
                            level=TraceLevel.ERROR,
                            message="Approval gate request failed, treating as urgent",
                            data={
                                "notification_id": notification.id,
                                "error": str(e),
                            },
                            duration_ms=0,
                        ))
                    except Exception:
                        pass
                    await self._deliver(notification)
            else:
                # No approval gate - treat as urgent
                try:
                    await self._emitter.emit(TraceEvent(
                        event_type=TraceEventType.OPERATION_COMPLETE,
                        component=TraceComponent.WORKER,
                        level=TraceLevel.INFO,
                        message="Action notification treated as urgent (no approval gate)",
                        data={
                            "notification_id": notification.id,
                        },
                        duration_ms=0,
                    ))
                except Exception:
                    pass
                await self._deliver(notification)

        # Send to Telegram gateway if set and notification is REQUIRES_ACTION or URGENT
        if self._telegram_gateway is not None and notification.type in (NotificationType.REQUIRES_ACTION, NotificationType.URGENT):
            try:
                await self._telegram_gateway.send_notification(notification)
            except Exception:
                pass

    async def _deliver(self, notification: Notification) -> None:
        """
        Deliver a notification.

        Args:
            notification: The notification to deliver
        """
        notification.delivered = True

        try:
            await self._emitter.emit(TraceEvent(
                event_type=TraceEventType.OPERATION_COMPLETE,
                component=TraceComponent.WORKER,
                level=TraceLevel.INFO,
                message="Notification delivered",
                data={
                    "notification_id": notification.id,
                    "type": notification.type.value,
                    "title": notification.title,
                },
                duration_ms=0,
            ))
        except Exception:
            pass

    async def flush_queue(self) -> list[Notification]:
        """
        Deliver all queued notifications and clear the queue.

        Returns:
            List of delivered notifications
        """
        delivered = []
        for notification in self._queue:
            await self._deliver(notification)
            delivered.append(notification)

        self._queue.clear()

        try:
            await self._emitter.emit(TraceEvent(
                event_type=TraceEventType.OPERATION_COMPLETE,
                component=TraceComponent.WORKER,
                level=TraceLevel.INFO,
                message="Notification queue flushed",
                data={
                    "delivered_count": len(delivered),
                },
                duration_ms=0,
            ))
        except Exception:
            pass

        return delivered

    def pending(self) -> list[Notification]:
        """
        Return undelivered queue items without flushing.

        Returns:
            List of pending notifications
        """
        return self._queue.copy()
