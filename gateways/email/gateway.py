"""
Email Gateway — sends approval requests via email and receives responses via reply.

Uses SMTP for sending. Responses are received via a reply-to address that
is polled via IMAP (or webhook in production).

This is a notification-only gateway (like TelegramGateway). Actual approval
responses come back through the Web UI or Telegram.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Optional

from core.notification import Notification

logger = logging.getLogger(__name__)


class EmailGateway:
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_password: str,
        from_addr: str,
        to_addrs: list[str],
        emitter: Optional[Any] = None,
    ) -> None:
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._smtp_user = smtp_user
        self._smtp_password = smtp_password
        self._from_addr = from_addr
        self._to_addrs = to_addrs
        self._emitter = emitter

    async def send_approval_request(
        self,
        request_id: str,
        description: str,
        risk_level: str,
        expires_at: str,
    ) -> bool:
        """Send an approval request email."""
        subject = (
            f"[JArvis Approval Required] {risk_level.upper()} - {description[:50]}"
        )
        body = f"""
Approval Request: {request_id}
Description: {description}
Risk Level: {risk_level}
Expires: {expires_at}

To approve, reply to this email with "APPROVE {request_id}".
To deny, reply with "DENY {request_id}".

Or approve via the JArvis Web UI.
"""
        msg = MIMEMultipart()
        msg["From"] = self._from_addr
        msg["To"] = ", ".join(self._to_addrs)
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._send_smtp, msg)
            return True
        except Exception as e:
            logger.warning(f"Failed to send approval email: {e}")
            return False

    def _send_smtp(self, msg: MIMEMultipart | MIMEText) -> None:
        """Synchronous SMTP send (run in executor)."""
        with smtplib.SMTP(self._smtp_host, self._smtp_port) as server:
            server.starttls()
            server.login(self._smtp_user, self._smtp_password)
            server.sendmail(self._from_addr, self._to_addrs, msg.as_string())

    async def send_notification(self, notification: Notification) -> bool:
        """Send a general notification email."""
        subject = f"[JArvis] {notification.type.value}: {notification.title}"
        body = notification.message
        msg = MIMEText(body)
        msg["From"] = self._from_addr
        msg["To"] = ", ".join(self._to_addrs)
        msg["Subject"] = subject

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._send_smtp, msg)
            return True
        except Exception as e:
            logger.warning(f"Failed to send notification email: {e}")
            return False
