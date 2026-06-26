"""
Multi-Channel Approval Gate

Wraps ApprovalGate and fans out approval requests to multiple channels:
- Web UI (always — this is the primary channel)
- Telegram (optional — if TelegramGateway is configured)
- Email (optional — if EmailGateway is configured)

Responses from any channel are routed back to ApprovalGate.respond.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from core.approval_gate import ApprovalGate, ApprovalRequest, ApprovalResponse
from gateways.email.gateway import EmailGateway
from gateways.telegram.gateway import TelegramGateway

logger = logging.getLogger(__name__)


class MultiChannelApprovalGate:
    def __init__(
        self,
        approval_gate: ApprovalGate,
        telegram_gateway: Optional[TelegramGateway] = None,
        email_gateway: Optional[EmailGateway] = None,
        emitter: Optional[Any] = None,
    ) -> None:
        self._gate = approval_gate
        self._telegram = telegram_gateway
        self._email = email_gateway
        self._emitter = emitter

    async def request_approval(self, request: ApprovalRequest) -> ApprovalResponse:
        """Request approval via all configured channels.

        Web UI is always notified (via the pending list).
        Telegram and Email are notified if configured.
        """
        # Primary: ApprovalGate (adds to pending list, persists to Postgres)
        response = await self._gate.request_approval(request)

        # Fan out to secondary channels (best-effort, non-blocking)
        if self._telegram:
            try:
                await self._telegram.send_notification(
                    self._build_telegram_notification(request)
                )
            except Exception as e:
                logger.warning(f"Telegram approval notification failed: {e}")

        if self._email:
            try:
                await self._email.send_approval_request(
                    request.request_id,
                    request.action_description,
                    request.risk_level,
                    request.expires_at.isoformat(),
                )
            except Exception as e:
                logger.warning(f"Email approval notification failed: {e}")

        return response

    async def respond(
        self,
        request_id: str,
        approved: bool,
        responder: str,
        channel: str = "web",
        always_approve: bool = False,
    ) -> ApprovalResponse:
        """Respond to an approval request from any channel."""
        response = await self._gate.respond(
            request_id, approved, responder, always_approve=always_approve
        )

        # Notify all channels of the decision
        notification_text = f"Approval {request_id} {'APPROVED' if approved else 'DENIED'} by {responder} ({channel})"

        if self._telegram:
            try:
                from core.notification import Notification, NotificationType

                await self._telegram.send_notification(
                    Notification(
                        type=NotificationType.INFO,
                        title="Approval Decision",
                        source="multi_channel_approval_gate",
                        message=notification_text,
                    )
                )
            except Exception:
                pass  # Best-effort

        return response

    async def poll_telegram_responses(self) -> None:
        """Poll Telegram for approval responses and route them to ApprovalGate.

        Call this periodically (e.g., every 5 seconds) from a background task.
        Looks for messages like "APPROVE <request_id>" or "DENY <request_id>".
        """
        if not self._telegram:
            return

        try:
            updates = await self._telegram.poll_updates()
            commands = await self._telegram.extract_commands(updates)

            for cmd in commands:
                parts = cmd.upper().split()
                if len(parts) == 2 and parts[0] in ("APPROVE", "DENY"):
                    action = parts[0]
                    request_id = parts[1].lower()
                    approved = action == "APPROVE"

                    await self.respond(
                        request_id=request_id,
                        approved=approved,
                        responder="telegram",
                        channel="telegram",
                    )
        except Exception as e:
            logger.warning(f"Telegram polling failed: {e}")

    def _build_telegram_notification(self, request: ApprovalRequest):
        """Build a Notification for Telegram."""
        from core.notification import Notification, NotificationType

        urgency = (
            NotificationType.URGENT
            if request.risk_level in ("high", "critical")
            else NotificationType.REQUIRES_ACTION
        )

        return Notification(
            type=urgency,
            title=f"Approval Required: {request.risk_level}",
            source="multi_channel_approval_gate",
            message=(
                f"ID: {request.request_id}\n"
                f"Action: {request.action_description}\n"
                f"Risk: {request.risk_level}\n"
                f"Expires: {request.expires_at.isoformat()}\n\n"
                f"Reply: APPROVE {request.request_id} or DENY {request.request_id}"
            ),
        )
