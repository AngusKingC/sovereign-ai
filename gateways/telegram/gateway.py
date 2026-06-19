"""
Telegram Gateway - pushes notifications to Telegram and receives commands.

Single responsibility: Send notifications to Telegram via bot API, poll for incoming commands.
"""

import asyncio
from typing import Any

import httpx

from core.observability import (
    TraceComponent,
    TraceEventType,
    TraceLevel,
    TraceEvent,
    TraceEmitter,
    MemoryTraceEmitter,
)
from core.notification import Notification, NotificationType


class TelegramGateway:
    """Gateway for Telegram bot communication."""

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        emitter: TraceEmitter | None = None,
    ) -> None:
        """Initialize the Telegram gateway.

        Args:
            bot_token: Telegram bot token
            chat_id: Telegram chat ID to send messages to
            emitter: Trace emitter for observability
        """
        self._emitter = emitter or MemoryTraceEmitter()
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._base_url = f"https://api.telegram.org/bot{bot_token}"

    async def send_message(self, text: str, notification: Notification | None = None) -> bool:
        """
        Send a message to Telegram.

        Args:
            text: Message text to send
            notification: Optional notification for context

        Returns:
            True on success, False on HTTP error or network failure
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self._base_url}/sendMessage",
                    json={
                        "chat_id": self._chat_id,
                        "text": text,
                    },
                    timeout=30.0,
                )
                response.raise_for_status()

                try:
                    await self._emitter.emit(TraceEvent(
                        event_type=TraceEventType.OPERATION_COMPLETE,
                        component=TraceComponent.WORKER,
                        level=TraceLevel.INFO,
                        message="Telegram message sent successfully",
                        data={
                            "message_length": len(text),
                        },
                        duration_ms=0,
                    ))
                except Exception as e:
                    await self._emitter.emit(TraceEvent(
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.WORKER,
                        level=TraceLevel.WARNING,
                        message="Trace emission failed in send_message success",
                        data={"error": str(e)},
                        duration_ms=0,
                    ))
                    pass

                return True

        except Exception as e:
            try:
                await self._emitter.emit(TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.ERROR,
                    message="Telegram message send failed",
                    data={
                        "error": str(e),
                    },
                    duration_ms=0,
                ))
            except Exception as e:
                await self._emitter.emit(TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.WARNING,
                    message="Trace emission failed in send_message error",
                    data={"error": str(e)},
                    duration_ms=0,
                ))
                pass
            return False

    async def send_notification(self, notification: Notification) -> bool:
        """
        Send a notification to Telegram with emoji prefix based on type.

        Args:
            notification: Notification to send

        Returns:
            True on success, False on failure
        """
        emoji_map = {
            NotificationType.INFO: "ℹ️",
            NotificationType.WARNING: "⚠️",
            NotificationType.URGENT: "🚨",
            NotificationType.REQUIRES_ACTION: "🔔",
        }

        emoji = emoji_map.get(notification.type, "ℹ️")
        message = f"{emoji} {notification.title}\n\n{notification.message}"

        return await self.send_message(message, notification)

    async def poll_updates(self, offset: int = 0) -> list[dict]:
        """
        Poll for updates from Telegram.

        Args:
            offset: Offset for polling (for long-polling)

        Returns:
            List of update dicts, empty list on failure
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._base_url}/getUpdates",
                    params={
                        "offset": offset,
                        "timeout": 5,
                    },
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()

                try:
                    await self._emitter.emit(TraceEvent(
                        event_type=TraceEventType.OPERATION_COMPLETE,
                        component=TraceComponent.WORKER,
                        level=TraceLevel.INFO,
                        message="Telegram updates polled successfully",
                        data={
                            "update_count": len(data.get("result", [])),
                        },
                        duration_ms=0,
                    ))
                except Exception as e:
                    await self._emitter.emit(TraceEvent(
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.WORKER,
                        level=TraceLevel.WARNING,
                        message="Trace emission failed in poll_updates success",
                        data={"error": str(e)},
                        duration_ms=0,
                    ))
                    pass

                return data.get("result", [])

        except Exception as e:
            try:
                await self._emitter.emit(TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.ERROR,
                    message="Telegram poll failed",
                    data={
                        "error": str(e),
                    },
                    duration_ms=0,
                ))
            except Exception as e:
                await self._emitter.emit(TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.WARNING,
                    message="Trace emission failed in poll_updates error",
                    data={"error": str(e)},
                    duration_ms=0,
                ))
                pass
            return []

    def extract_commands(self, updates: list[dict]) -> list[str]:
        """
        Extract commands from update dicts.

        Args:
            updates: List of update dicts from Telegram

        Returns:
            List of command strings (starting with /), empty list if none
        """
        commands = []
        for update in updates:
            try:
                message = update.get("message", {})
                text = message.get("text", "")
                if text.startswith("/"):
                    commands.append(text)
            except Exception as e:
                print(f"Failed to extract command from update: {e}")
                continue
        return commands
