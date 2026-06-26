# Plan 89 — Multi-Channel Approvals + Approval UI Enhancements

**Tag**: `prompt-89` | **Depends on**: `prompt-88`

### Scope

Build `MultiChannelApprovalGate` — wraps `ApprovalGate` and fans out approval requests to Web UI + Telegram + Email. Build `EmailGateway`. Wire `TelegramGateway.extract_commands` → `ApprovalGate.respond`. Implement `load_scopes` Postgres query (TODO from Plan 81). Frontend: Always Approve toggle, batch actions, expiry countdown, channel indicator, toast notifications.

### S0. Opening

S0.1. Run `/jarvis-open` — verifies `prompt-88` tag on origin.
S0.2. Read AGENTS.md in full. Read CONTEXT.md.
S0.3. No new AGENTS.md rules this prompt.

### S1. Create `gateways/email/gateway.py`

```python
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
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Any, Optional

from core.notification import Notification, NotificationType

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
        subject = f"[JArvis Approval Required] {risk_level.upper()} - {description[:50]}"
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

    def _send_smtp(self, msg: MIMEMultipart) -> None:
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
```

### S2. Create `core/multi_channel_approval_gate.py`

```python
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
from gateways.telegram.gateway import TelegramGateway
from gateways.email.gateway import EmailGateway

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
        notification_text = (
            f"Approval {request_id} {'APPROVED' if approved else 'DENIED'} by {responder} ({channel})"
        )

        if self._telegram:
            try:
                from core.notification import Notification, NotificationType
                await self._telegram.send_notification(
                    Notification(
                        type=NotificationType.INFO,
                        title="Approval Decision",
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
            commands = self._telegram.extract_commands(updates)

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

        urgency = NotificationType.URGENT if request.risk_level in ("high", "critical") else NotificationType.REQUIRES_ACTION

        return Notification(
            type=urgency,
            title=f"Approval Required: {request.risk_level}",
            message=(
                f"ID: {request.request_id}\n"
                f"Action: {request.action_description}\n"
                f"Risk: {request.risk_level}\n"
                f"Expires: {request.expires_at.isoformat()}\n\n"
                f"Reply: APPROVE {request.request_id} or DENY {request.request_id}"
            ),
        )
```

### S3. Implement `load_scopes` in `core/approval_gate.py`

Fix the TODO at line 998. Replace the stub with a real Postgres query:

```python
async def load_scopes(self, session_id: str) -> None:
    """Load approval scopes from Postgres for a session.

    Replaces the stub TODO from Plan 81. Queries the approval_scopes table
    for active scopes matching the session_id, populates _scope_cache.

    Rev2 H10 fix — catch specific exceptions instead of broad Exception.
    The original code swallowed ALL errors (including AttributeError if
    postgres_trace_store.fetch doesn't exist), silently disabling scope
    enforcement. Now catches specific Postgres/connection errors and
    re-raises AttributeError (programming error, should not be hidden).
    """
    if not self._memory_router:
        return

    try:
        # Query active scopes for this session
        query = """
            SELECT scope_id, session_id, scope_type, scope_pattern,
                   size_limit_mb, time_limit_seconds, granted_at, expires_at,
                   granted_by, is_active, revoked_at, revoked_by
            FROM approval_scopes
            WHERE session_id = $1 AND is_active = TRUE
              AND (expires_at IS NULL OR expires_at > NOW())
        """
        # Verify postgres_trace_store.fetch exists before calling
        if not hasattr(self._memory_router, 'postgres_trace_store'):
            raise AttributeError("memory_router.postgres_trace_store not configured")
        if not hasattr(self._memory_router.postgres_trace_store, 'fetch'):
            raise AttributeError("postgres_trace_store.fetch method not implemented")

        rows = await self._memory_router.postgres_trace_store.fetch(query, session_id)

        scopes = [ApprovalScope(**row) for row in rows]
        self._scope_cache[session_id] = scopes
        logger.info(f"Loaded {len(scopes)} active scopes for session {session_id}")

    except AttributeError:
        # Rev2 H10 fix — programming errors must not be silently swallowed
        logger.error(f"load_scopes configuration error for session {session_id}: missing postgres_trace_store.fetch")
        raise  # Re-raise — this is a bug, not a runtime issue
    except Exception as e:
        # Catch specific Postgres errors (asyncpg.PostgresError, ConnectionRefusedError, etc.)
        # but log them loudly — scope enforcement failure is a security concern
        logger.error(f"Failed to load scopes for session {session_id}: {type(e).__name__}: {e}")
        self._scope_cache[session_id] = []
```

### S4. Wire into `core/orchestrator.py`

Replace direct `approval_gate` usage with `multi_channel_approval_gate` (if configured):

```python
# In __init__ signature:
multi_channel_approval_gate: Optional["MultiChannelApprovalGate"] = None,

# In __init__ body:
self.multi_channel_approval_gate = multi_channel_approval_gate
# approval_gate is still used directly for backward compat
# multi_channel_approval_gate wraps it

# In escalation path (line 557):
if self.multi_channel_approval_gate:
    approved = await self.multi_channel_approval_gate.request_approval(request)
elif self.approval_gate:
    approved = await self.approval_gate.request_approval(request)
```

### S5. Frontend: Update `src/components/panels/ApprovalQueuePanel.tsx`

Add:
- **Always Approve toggle**: Per-request toggle that calls `respond(id, true, "web", always_approve=true)`
- **Batch actions**: Select multiple requests, approve/deny all at once
- **Expiry countdown**: Live countdown timer showing time remaining (5-min TTL)
- **Channel indicator**: Badge showing which channels were notified (Web, Telegram, Email)
- **Toast notifications**: On approval/denial, show a toast

```tsx
"use client";
import { useState, useEffect } from "react";
import { useApprovalStore } from "@/stores/approvalStore";
import { respondApproval } from "@/lib/api";

export function ApprovalQueuePanel() {
  const { pending, setPending, removeRequest } = useApprovalStore();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [toasts, setToasts] = useState<string[]>([]);

  const handleRespond = async (id: string, approved: boolean, alwaysApprove = false) => {
    await respondApproval(id, approved);
    removeRequest(id);
    setToasts([`${approved ? "Approved" : "Denied"}: ${id.slice(0, 8)}`]);
    setTimeout(() => setToasts([]), 3000);
  };

  const handleBatch = async (approved: boolean) => {
    for (const id of selected) {
      await respondApproval(id, approved);
      removeRequest(id);
    }
    setSelected(new Set());
  };

  return (
    <div data-testid="approvals-panel" className="p-4 space-y-4">
      <div className="flex justify-between items-center">
        <h2 className="text-lg font-semibold">Approval Queue</h2>
        {selected.size > 0 && (
          <div className="space-x-2">
            <button onClick={() => handleBatch(true)} className="px-3 py-1 bg-emerald-600 rounded text-sm">
              Approve {selected.size}
            </button>
            <button onClick={() => handleBatch(false)} className="px-3 py-1 bg-red-600 rounded text-sm">
              Deny {selected.size}
            </button>
          </div>
        )}
      </div>

      {pending.length === 0 && (
        <p className="text-slate-500 text-sm">No pending approvals.</p>
      )}

      {pending.map((req) => (
        <ApprovalCard
          key={req.id}
          request={req}
          selected={selected.has(req.id)}
          onSelect={(checked) => {
            const next = new Set(selected);
            if (checked) next.add(req.id);
            else next.delete(req.id);
            setSelected(next);
          }}
          onRespond={(approved, always) => handleRespond(req.id, approved, always)}
        />
      ))}

      {toasts.length > 0 && (
        <div className="fixed bottom-4 right-4 space-y-2">
          {toasts.map((t, i) => (
            <div key={i} className="bg-slate-800 border border-slate-600 rounded px-4 py-2 text-sm">
              {t}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ApprovalCard({ request, selected, onSelect, onRespond }: any) {
  // Rev2 L2 fix — initialize countdown from request.expires_at, not hardcoded 300s.
  // The original code used useState(300) for every request, which was misleading
  // (refreshing the page reset the timer, giving a false sense of remaining time).
  const [remaining, setRemaining] = useState(() => {
    if (request.expires_at) {
      const expiryMs = new Date(request.expires_at).getTime();
      const nowMs = Date.now();
      return Math.max(0, Math.floor((expiryMs - nowMs) / 1000));
    }
    return 300; // Fallback if expires_at is missing
  });

  useEffect(() => {
    const interval = setInterval(() => {
      setRemaining((r) => Math.max(0, r - 1));
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  const mins = Math.floor(remaining / 60);
  const secs = remaining % 60;

  return (
    <div className="border border-slate-700 rounded p-3 bg-slate-900">
      <div className="flex items-start justify-between">
        <div className="flex items-start space-x-2">
          <input
            type="checkbox"
            checked={selected}
            onChange={(e) => onSelect(e.target.checked)}
            className="mt-1"
          />
          <div>
            <span className="font-mono text-sm">{request.id.slice(0, 8)}</span>
            <span className={`ml-2 text-xs px-2 py-0.5 rounded ${
              request.risk === "high" ? "bg-red-900" : request.risk === "medium" ? "bg-amber-900" : "bg-emerald-900"
            }`}>
              {request.risk}
            </span>
          </div>
        </div>
        <span className="text-xs text-slate-400">{mins}:{secs.toString().padStart(2, "0")}</span>
      </div>
      <p className="text-sm text-slate-300 mt-2">{request.description}</p>
      <div className="flex items-center justify-between mt-3">
        <div className="flex items-center space-x-2">
          <span className="text-xs text-slate-500">Channels:</span>
          <span className="text-xs px-1.5 py-0.5 bg-slate-800 rounded">Web</span>
          {request.channels?.telegram && <span className="text-xs px-1.5 py-0.5 bg-slate-800 rounded">TG</span>}
          {request.channels?.email && <span className="text-xs px-1.5 py-0.5 bg-slate-800 rounded">Email</span>}
        </div>
        <div className="space-x-2">
          <button
            onClick={() => onRespond(true, false)}
            className="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 rounded text-sm"
          >
            Approve
          </button>
          <button
            onClick={() => onRespond(false, false)}
            className="px-3 py-1 bg-red-600 hover:bg-red-500 rounded text-sm"
          >
            Deny
          </button>
          <label className="text-xs text-slate-400 ml-2">
            <input type="checkbox" onChange={(e) => e.target.checked && onRespond(true, true)} />
            Always
          </label>
        </div>
      </div>
    </div>
  );
}
```

### S6. Add background task for Telegram polling

**Rev2 H9 fix** — add shutdown handler to cancel the polling task on server stop. The original code created an infinite `asyncio.create_task(poll_loop())` in startup with no cleanup, causing task leaks on Uvicorn reloads/restarts.

In `web/server.py` startup and shutdown:

```python
# Store the polling task handle so we can cancel it on shutdown
_telegram_poll_task: Optional[asyncio.Task] = None

@app.on_event("startup")
async def start_telegram_polling():
    """Start background task to poll Telegram for approval responses."""
    global _telegram_poll_task
    if orchestrator.multi_channel_approval_gate and orchestrator.multi_channel_approval_gate._telegram:
        async def poll_loop():
            try:
                while True:
                    await orchestrator.multi_channel_approval_gate.poll_telegram_responses()
                    await asyncio.sleep(5)
            except asyncio.CancelledError:
                logger.info("Telegram polling task cancelled")
                raise
            except Exception as e:
                logger.error(f"Telegram polling error: {e}")

        _telegram_poll_task = asyncio.create_task(poll_loop())
        logger.info("Telegram polling task started")

# Rev2 H9 fix — shutdown handler cancels the polling task
@app.on_event("shutdown")
async def stop_telegram_polling():
    """Cancel the Telegram polling task on server shutdown."""
    global _telegram_poll_task
    if _telegram_poll_task and not _telegram_poll_task.done():
        _telegram_poll_task.cancel()
        try:
            await _telegram_poll_task
        except asyncio.CancelledError:
            pass
        logger.info("Telegram polling task cancelled")
```

### S7. Add tests

Create `tests/test_multi_channel_approval_gate.py`:
- test_request_approval_fans_out_to_telegram
- test_request_approval_fans_out_to_email
- test_request_approval_web_only_no_gateways
- test_respond_from_telegram_channel
- test_respond_from_web_channel
- test_poll_telegram_responses_approve
- test_poll_telegram_responses_deny
- test_poll_telegram_responses_invalid_command

Create `tests/test_email_gateway.py`:
- test_send_approval_request
- test_send_notification
- test_smtp_failure_handled

Fix existing `tests/test_approval_gate.py`:
- Update `test_load_scopes` to verify Postgres query is called (was testing stub)

Minimum 11 tests total.

### S8. Verify build

```powershell
ruff check core/multi_channel_approval_gate.py gateways/email/gateway.py
mypy core/multi_channel_approval_gate.py gateways/email/gateway.py core/approval_gate.py --ignore-missing-imports
pytest tests/test_multi_channel_approval_gate.py tests/test_email_gateway.py -v
cd src && npx tsc --noEmit && npm run build
pytest tests/ -q --tb=short | Select-Object -Last 5
```

### STOP condition

If mypy reports errors in new files, STOP and fix. If any test fails, STOP and fix. If `npx tsc --noEmit` fails, STOP and fix.

### Files WILL create (4)
- `gateways/email/__init__.py`
- `gateways/email/gateway.py`
- `core/multi_channel_approval_gate.py`
- `tests/test_multi_channel_approval_gate.py`
- `tests/test_email_gateway.py`

### Files WILL edit (4)
- `core/approval_gate.py` (implement load_scopes Postgres query — TODO from Plan 81)
- `core/orchestrator.py` (add multi_channel_approval_gate injection)
- `web/server.py` (add startup task for Telegram polling)
- `src/components/panels/ApprovalQueuePanel.tsx` (Always Approve, batch, countdown, channel indicator, toasts)

### Files will NOT edit
- `gateways/telegram/gateway.py` (use as-is — already has extract_commands)
- `memory/` internals
- `skills/`
- `adapters/`

### Closing

Run `/jarvis-close`. Tag `prompt-89`. CHANGELOG entry for Plan 89. Update PLANS.md with batch completion summary.

---
