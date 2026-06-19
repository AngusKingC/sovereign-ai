"""Clipboard skill for clipboard operations."""

import asyncio
from typing import Any

from core.approval_gate import ApprovalGate
from core.observability import (
    TraceEventType,
    TraceComponent,
    TraceLevel,
    TraceEvent,
    TraceEmitter,
    MemoryTraceEmitter,
)


class ClipboardSkill:
    """Clipboard skill for clipboard operations."""

    def __init__(
        self,
        emitter: TraceEmitter | None = None,
        approval_gate: ApprovalGate | None = None,
    ) -> None:
        """Initialize the clipboard skill.

        Args:
            emitter: Trace emitter for observability
            approval_gate: Approval gate for write operations
        """
        self._emitter = emitter or MemoryTraceEmitter()
        self._approval_gate = approval_gate

    async def read(self) -> str:
        """Read current clipboard content.

        Returns:
            Clipboard content as string
        """
        start_time = asyncio.get_event_loop().time()

        try:
            event = TraceEvent(
                event_type=TraceEventType.CLIPBOARD_OPERATION,
                component=TraceComponent.CLIPBOARD_SKILL,
                level=TraceLevel.INFO,
                message="Clipboard read",
                data={"operation": "read"},
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        loop = asyncio.get_event_loop()
        try:
            import pyperclip
            content = await loop.run_in_executor(None, pyperclip.paste)
        except Exception:
            content = ""

        duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

        try:
            event = TraceEvent(
                event_type=TraceEventType.CLIPBOARD_OPERATION,
                component=TraceComponent.CLIPBOARD_SKILL,
                level=TraceLevel.INFO,
                message="Clipboard read completed",
                data={"operation": "read"},
                duration_ms=duration_ms,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        return content

    async def write(self, content: str) -> dict[str, Any]:
        """Write content to clipboard.

        Args:
            content: Content to write to clipboard

        Returns:
            Dict with success status
        """
        if self._approval_gate:
            approved = await self._approval_gate.request_approval(
                action="clipboard write",
                context={"content_length": len(content)},
            )
            if not approved:
                return {
                    "success": False,
                }

        start_time = asyncio.get_event_loop().time()

        try:
            event = TraceEvent(
                event_type=TraceEventType.CLIPBOARD_OPERATION,
                component=TraceComponent.CLIPBOARD_SKILL,
                level=TraceLevel.INFO,
                message="Clipboard write",
                data={"operation": "write"},
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        loop = asyncio.get_event_loop()
        try:
            import pyperclip
            await loop.run_in_executor(None, pyperclip.copy, content)
            success = True
        except Exception:
            success = False

        duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

        try:
            event = TraceEvent(
                event_type=TraceEventType.CLIPBOARD_OPERATION,
                component=TraceComponent.CLIPBOARD_SKILL,
                level=TraceLevel.INFO,
                message="Clipboard write completed",
                data={"operation": "write", "success": success},
                duration_ms=duration_ms,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        return {
            "success": success,
        }

    async def clear(self) -> dict[str, Any]:
        """Clear clipboard.

        Returns:
            Dict with success status
        """
        if self._approval_gate:
            approved = await self._approval_gate.request_approval(
                action="clipboard clear",
                context={},
            )
            if not approved:
                return {
                    "success": False,
                }

        start_time = asyncio.get_event_loop().time()

        try:
            event = TraceEvent(
                event_type=TraceEventType.CLIPBOARD_OPERATION,
                component=TraceComponent.CLIPBOARD_SKILL,
                level=TraceLevel.INFO,
                message="Clipboard clear",
                data={"operation": "clear"},
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        loop = asyncio.get_event_loop()
        try:
            import pyperclip
            await loop.run_in_executor(None, pyperclip.copy, "")
            success = True
        except Exception:
            success = False

        duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

        try:
            event = TraceEvent(
                event_type=TraceEventType.CLIPBOARD_OPERATION,
                component=TraceComponent.CLIPBOARD_SKILL,
                level=TraceLevel.INFO,
                message="Clipboard clear completed",
                data={"operation": "clear", "success": success},
                duration_ms=duration_ms,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        return {
            "success": success,
        }
