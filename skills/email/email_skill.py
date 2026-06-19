"""
Email Skill - IMAP read and SMTP send operations.

Single responsibility: Read email via IMAP and send email via SMTP with approval gating.
"""

import imaplib
import smtplib
import os
from email import message_from_bytes
from email.header import decode_header
from typing import Any

from core.observability import (
    TraceComponent,
    TraceEventType,
    TraceLevel,
    TraceEvent,
    TraceEmitter,
    MemoryTraceEmitter,
)
from core.approval_gate import ApprovalGate, ApprovalRequest, ApprovalActionType
from core.exceptions import SkillExecutionError


class EmailSkill:
    """Skill for reading and sending email."""

    def __init__(
        self,
        emitter: TraceEmitter | None = None,
        approval_gate: ApprovalGate | None = None,
        imap_host: str | None = None,
        smtp_host: str | None = None,
        username: str | None = None,
        password: str | None = None,
        imap_port: int = 993,
        smtp_port: int = 587,
    ) -> None:
        """Initialize the email skill.

        Args:
            emitter: Trace emitter for observability
            approval_gate: Optional approval gate for sending emails
            imap_host: IMAP server host (loaded from EMAIL_IMAP_HOST env var if None)
            smtp_host: SMTP server host (loaded from EMAIL_SMTP_HOST env var if None)
            username: Email username (loaded from EMAIL_USERNAME env var if None)
            password: Email password (loaded from EMAIL_PASSWORD env var if None)
            imap_port: IMAP port (default 993)
            smtp_port: SMTP port (default 587)
        """
        self._emitter = emitter or MemoryTraceEmitter()
        self._approval_gate = approval_gate
        self._imap_host = imap_host or os.getenv("EMAIL_IMAP_HOST")
        self._smtp_host = smtp_host or os.getenv("EMAIL_SMTP_HOST")
        self._username = username or os.getenv("EMAIL_USERNAME")
        self._password = password or os.getenv("EMAIL_PASSWORD")
        self._imap_port = imap_port
        self._smtp_port = smtp_port

    def _decode_header(self, header: str) -> str:
        """Decode email header."""
        decoded_parts = decode_header(header)
        decoded_str = ""
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                decoded_str += part.decode(encoding or "utf-8", errors="replace")
            else:
                decoded_str += part
        return decoded_str

    async def read_inbox(self, limit: int = 10, unread_only: bool = True) -> list[dict]:
        """
        Read inbox messages via IMAP.

        Args:
            limit: Maximum number of messages to fetch (default 10)
            unread_only: Only fetch unread messages (default True)

        Returns:
            List of dicts with keys: uid, subject, sender, date, body_preview, unread

        Raises:
            SkillExecutionError: On connection failure or auth failure
        """
        start_time = 0
        try:
            import asyncio
            start_time = asyncio.get_event_loop().time()
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        try:
            await self._emitter.emit(TraceEvent(
                event_type=TraceEventType.COMPONENT_START,
                component=TraceComponent.WORKER,
                level=TraceLevel.INFO,
                message="Email inbox read started",
                data={"limit": limit, "unread_only": unread_only},
                duration_ms=0,
            ))
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        # Check credentials
        if not self._imap_host:
            raise SkillExecutionError("EMAIL_IMAP_HOST environment variable not set")
        if not self._username:
            raise SkillExecutionError("EMAIL_USERNAME environment variable not set")
        if not self._password:
            raise SkillExecutionError("EMAIL_PASSWORD environment variable not set")

        try:
            # Connect to IMAP server
            import asyncio
            loop = asyncio.get_event_loop()
            
            mail = await loop.run_in_executor(
                None,
                lambda: imaplib.IMAP4_SSL(self._imap_host, self._imap_port)
            )
            
            # Login
            await loop.run_in_executor(
                None,
                lambda: mail.login(self._username, self._password)
            )
            
            # Select inbox
            await loop.run_in_executor(
                None,
                lambda: mail.select("INBOX")
            )
            
            # Search for messages
            if unread_only:
                status, messages = await loop.run_in_executor(
                    None,
                    lambda: mail.search(None, "UNSEEN")
                )
            else:
                status, messages = await loop.run_in_executor(
                    None,
                    lambda: mail.search(None, "ALL")
                )
            
            email_ids = messages[0].split()
            
            # Limit to most recent messages
            email_ids = email_ids[-limit:] if len(email_ids) > limit else email_ids
            
            messages_data = []
            for email_id in reversed(email_ids):
                # Fetch message
                status, msg_data = await loop.run_in_executor(
                    None,
                    lambda: mail.fetch(email_id, "(RFC822)")
                )
                
                # Parse message
                raw_email = msg_data[0][1]
                email_message = message_from_bytes(raw_email)
                
                # Extract fields
                subject = self._decode_header(email_message.get("Subject", ""))
                sender = self._decode_header(email_message.get("From", ""))
                date = email_message.get("Date", "")
                
                # Get body preview
                body = ""
                if email_message.is_multipart():
                    for part in email_message.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                            break
                else:
                    body = email_message.get_payload(decode=True).decode("utf-8", errors="replace")
                
                body_preview = body[:200] if body else ""
                
                # Check if unread
                unread = "\\Seen" not in mail.fetch(email_id, "(FLAGS)")[1][0].decode()
                
                messages_data.append({
                    "uid": email_id.decode(),
                    "subject": subject,
                    "sender": sender,
                    "date": date,
                    "body_preview": body_preview,
                    "unread": unread,
                })
            
            # Close connection
            await loop.run_in_executor(None, lambda: mail.close())
            await loop.run_in_executor(None, lambda: mail.logout())
            
            duration_ms = 0
            try:
                duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            except Exception:
                # Trace emission failure - non-critical, continue
                pass
            
            try:
                await self._emitter.emit(TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.INFO,
                    message="Email inbox read completed",
                    data={"message_count": len(messages_data), "unread_only": unread_only},
                    duration_ms=duration_ms,
                ))
            except Exception:
                # Trace emission failure - non-critical, continue
                pass
            
            return messages_data
            
        except Exception as e:
            duration_ms = 0
            try:
                duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            except Exception:
                # Trace emission failure - non-critical, continue
                pass
            
            try:
                await self._emitter.emit(TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.ERROR,
                    message="Email inbox read failed",
                    data={"error": str(e)},
                    duration_ms=duration_ms,
                ))
            except Exception:
                # Trace emission failure - non-critical, continue
                pass
            
            raise SkillExecutionError(f"Failed to read inbox: {str(e)}")

    async def send(self, to: str, subject: str, body: str) -> bool:
        """
        Send email via SMTP.

        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body

        Returns:
            True on success

        Raises:
            SkillExecutionError: On send failure or approval denial
        """
        start_time = 0
        try:
            import asyncio
            start_time = asyncio.get_event_loop().time()
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        try:
            await self._emitter.emit(TraceEvent(
                event_type=TraceEventType.COMPONENT_START,
                component=TraceComponent.WORKER,
                level=TraceLevel.INFO,
                message="Email send started",
                data={"to": to, "subject_length": len(subject)},
                duration_ms=0,
            ))
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        # Check approval gate
        if self._approval_gate is None:
            raise SkillExecutionError("Approval gate not injected — sending without approval is not permitted")
        
        # Request approval
        try:
            from datetime import datetime, timedelta
            from uuid import uuid4
            
            request = ApprovalRequest(
                request_id=str(uuid4()),
                task_id=str(uuid4()),
                session_id="default",
                action_type=ApprovalActionType.NETWORK_REQUEST,
                action_description=f"Send email to {to}",
                action_parameters={"to": to, "subject": subject},
                risk_level="medium",
                reason_for_approval="Email can send external communications",
                expires_at=datetime.utcnow() + timedelta(seconds=300),
            )
            response = await self._approval_gate.request_approval(request)
            if not response.approved:
                duration_ms = 0
                try:
                    duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
                except Exception:
                    # Trace emission failure - non-critical, continue
                    pass
                
                try:
                    await self._emitter.emit(TraceEvent(
                        event_type=TraceEventType.OPERATION_COMPLETE,
                        component=TraceComponent.WORKER,
                        level=TraceLevel.WARNING,
                        message="Email send denied by approval gate",
                        data={"to": to, "reason": response.decision_reason},
                        duration_ms=duration_ms,
                    ))
                except Exception:
                    # Trace emission failure - non-critical, continue
                    pass
                
                raise SkillExecutionError(f"Approval denied: {response.decision_reason}")
        except SkillExecutionError:
            raise
        except Exception as e:
            duration_ms = 0
            try:
                duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            except Exception:
                # Trace emission failure - non-critical, continue
                pass
            
            try:
                await self._emitter.emit(TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.ERROR,
                    message="Email send approval request failed",
                    data={"error": str(e)},
                    duration_ms=duration_ms,
                ))
            except Exception:
                # Trace emission failure - non-critical, continue
                pass
            
            raise SkillExecutionError(f"Approval request failed: {str(e)}")

        # Check credentials
        if not self._smtp_host:
            raise SkillExecutionError("EMAIL_SMTP_HOST environment variable not set")
        if not self._username:
            raise SkillExecutionError("EMAIL_USERNAME environment variable not set")
        if not self._password:
            raise SkillExecutionError("EMAIL_PASSWORD environment variable not set")

        try:
            import asyncio
            loop = asyncio.get_event_loop()
            
            # Connect to SMTP server
            server = await loop.run_in_executor(
                None,
                lambda: smtplib.SMTP(self._smtp_host, self._smtp_port)
            )
            
            # Start TLS
            await loop.run_in_executor(None, lambda: server.starttls())
            
            # Login
            await loop.run_in_executor(
                None,
                lambda: server.login(self._username, self._password)
            )
            
            # Send email
            from email.message import EmailMessage
            msg = EmailMessage()
            msg.set_content(body)
            msg["Subject"] = subject
            msg["From"] = self._username
            msg["To"] = to
            
            await loop.run_in_executor(
                None,
                lambda: server.send_message(msg)
            )
            
            # Close connection
            await loop.run_in_executor(None, lambda: server.quit())
            
            duration_ms = 0
            try:
                duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            except Exception:
                # Trace emission failure - non-critical, continue
                pass
            
            try:
                await self._emitter.emit(TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.INFO,
                    message="Email send completed",
                    data={"to": to, "subject_length": len(subject)},
                    duration_ms=duration_ms,
                ))
            except Exception:
                # Trace emission failure - non-critical, continue
                pass
            
            return True
            
        except Exception as e:
            duration_ms = 0
            try:
                duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            except Exception:
                # Trace emission failure - non-critical, continue
                pass
            
            try:
                await self._emitter.emit(TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.ERROR,
                    message="Email send failed",
                    data={"error": str(e)},
                    duration_ms=duration_ms,
                ))
            except Exception:
                # Trace emission failure - non-critical, continue
                pass
            
            raise SkillExecutionError(f"Failed to send email: {str(e)}")
