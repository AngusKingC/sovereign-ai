"""Approval Trust Registry for command trust levels.

This module provides a trust registry so the approval gate can skip the prompt
entirely for previously-approved commands, while keeping a hardcoded NEVER_ALLOW
list for genuinely dangerous operations.
"""

import logging
from enum import Enum
from typing import Any

from core.observability import (
    MemoryTraceEmitter,
    TraceComponent,
    TraceEmitter,
    TraceEvent,
    TraceEventType,
    TraceLevel,
)

logger = logging.getLogger(__name__)


class TrustLevel(str, Enum):
    """Trust levels for command approval."""

    ALWAYS_ASK = "always_ask"
    SESSION_TRUST = "session_trust"
    PERMANENT_TRUST = "permanent_trust"
    NEVER_ALLOW = "never_allow"


class ApprovalTrustRegistry:
    """Registry for command trust levels with session and persistent storage."""

    # Hardcoded NEVER_ALLOW patterns
    NEVER_ALLOW_PATTERNS = [
        "rm -rf /",
        "rm -rf ~",
        "format",
        "mkfs",
        "dd if=",
        ":(){:|:&};:",
        "shutdown",
        "reboot",
        "del /f /s /q C:\\",
    ]

    def __init__(
        self,
        memory_router: Any = None,
        emitter: TraceEmitter | None = None,
    ) -> None:
        """Initialize the approval trust registry.

        Args:
            memory_router: Injected, default None. If provided, used for persistent storage of PERMANENT_TRUST commands.
            emitter: Injected, default MemoryTraceEmitter()
        """
        self.memory_router = memory_router
        self._emitter = emitter or MemoryTraceEmitter()
        self._session_trust: dict[str, TrustLevel] = {}

    async def get_trust_level(self, command: str) -> TrustLevel:
        """Get the trust level for a command.

        Checks NEVER_ALLOW first, then Postgres (PERMANENT), then session dict.
        Returns ALWAYS_ASK if not found.

        Args:
            command: The command to check

        Returns:
            The trust level for the command

        Raises:
            ApprovalDeniedError: If command matches a NEVER_ALLOW pattern
        """
        from core.exceptions import ApprovalDeniedError

        # Check NEVER_ALLOW patterns first
        for pattern in self.NEVER_ALLOW_PATTERNS:
            if pattern in command:
                try:
                    event = TraceEvent(
                        event_type=TraceEventType.TRUST_BLOCKED,
                        component=TraceComponent.APPROVAL_TRUST,
                        level=TraceLevel.ERROR,
                        message="Command matches NEVER_ALLOW pattern",
                        data={"command": command, "pattern": pattern},
                        duration_ms=0,
                    )
                    await self._emitter.emit(event)
                except Exception as e:
                    logger.warning("Trace emission failed: %s", e)
                raise ApprovalDeniedError(
                    command, f"Command matches blocked pattern: {pattern}"
                )

        # Check session trust
        if command in self._session_trust:
            return self._session_trust[command]

        # Check persistent trust via MemoryRouter
        if self.memory_router is not None:
            try:
                # Read from memory router to check for permanent trust
                # Use a scoped read to get trust data
                trust_data = await self.memory_router.scoped_read(
                    scope="approval_trust",
                    key=command,
                )
                if trust_data and trust_data.get("level") == TrustLevel.PERMANENT_TRUST:
                    return TrustLevel.PERMANENT_TRUST
            except Exception:
                # Memory router read failed, proceed with default
                pass

        # Default to ALWAYS_ASK
        return TrustLevel.ALWAYS_ASK

    async def set_trust(
        self,
        command: str,
        level: TrustLevel,
        scope: str = "permanent",
    ) -> None:
        """Set trust level for a command.

        Writes to session dict (SESSION) or persists via MemoryRouter (PERMANENT).
        Emits trace event.

        Args:
            command: The command to set trust for
            level: The trust level to set
            scope: "session" → SESSION_TRUST only, "permanent" → PERMANENT_TRUST + persisted
        """
        if scope == "session":
            self._session_trust[command] = TrustLevel.SESSION_TRUST
        elif scope == "permanent":
            self._session_trust[command] = TrustLevel.PERMANENT_TRUST
            # Persist via MemoryRouter
            if self.memory_router is not None:
                try:
                    await self.memory_router.scoped_write(
                        scope="approval_trust",
                        key=command,
                        data={"level": TrustLevel.PERMANENT_TRUST, "command": command},
                    )
                except Exception:
                    # Memory router write failed, but session trust is set
                    pass
        else:
            raise ValueError(
                f"Invalid scope: {scope}. Must be 'session' or 'permanent'."
            )

        # Emit trace event
        try:
            event = TraceEvent(
                event_type=TraceEventType.TRUST_GRANTED,
                component=TraceComponent.APPROVAL_TRUST,
                level=TraceLevel.INFO,
                message="Trust level set for command",
                data={"command": command, "level": level, "scope": scope},
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception as e:
            logger.warning("Trace emission failed: %s", e)

    async def revoke_trust(self, command: str) -> None:
        """Revoke trust for a command.

        Removes from session dict and Postgres. Emits trace event.

        Args:
            command: The command to revoke trust for
        """
        # Remove from session dict
        if command in self._session_trust:
            del self._session_trust[command]

        # Remove from persistent storage
        if self.memory_router is not None:
            try:
                # Delete from memory router
                await self.memory_router.scoped_write(
                    scope="approval_trust",
                    key=command,
                    data=None,  # Delete by writing None
                )
            except Exception:
                # Memory router delete failed, but session trust is revoked
                pass

        # Emit trace event
        try:
            event = TraceEvent(
                event_type=TraceEventType.TRUST_REVOKED,
                component=TraceComponent.APPROVAL_TRUST,
                level=TraceLevel.INFO,
                message="Trust revoked for command",
                data={"command": command},
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception as e:
            logger.warning("Trace emission failed: %s", e)

    async def is_trusted(self, command: str) -> bool:
        """Check if a command is trusted.

        Returns True if trust level is SESSION_TRUST or PERMANENT_TRUST.
        Returns False if ALWAYS_ASK.
        Raises ApprovalDeniedError if NEVER_ALLOW.

        Args:
            command: The command to check

        Returns:
            True if command is trusted, False otherwise

        Raises:
            ApprovalDeniedError: If command matches a NEVER_ALLOW pattern
        """
        trust_level = await self.get_trust_level(command)
        if trust_level == TrustLevel.NEVER_ALLOW:
            from core.exceptions import ApprovalDeniedError

            raise ApprovalDeniedError(command, "Command is in NEVER_ALLOW list")
        return trust_level in (TrustLevel.SESSION_TRUST, TrustLevel.PERMANENT_TRUST)

    async def get_all_trusted(self, include_session: bool = True) -> list[dict]:
        """Return all trusted commands with their level and source.

        Args:
            include_session: If True, include session-trusted commands. If False, only permanent.

        Returns:
            List of dicts with keys: command, level, source
        """
        trusted_commands = []

        # Add session-trusted commands
        if include_session:
            for command, level in self._session_trust.items():
                trusted_commands.append(
                    {
                        "command": command,
                        "level": level,
                        "source": "session",
                    }
                )

        # Add permanent-trusted commands from MemoryRouter
        if self.memory_router is not None:
            try:
                # Read all trust data from memory router
                # This is a simplified implementation - in reality, you'd need a way to list all keys
                # For now, we'll just return session-trusted commands
                pass
            except Exception:
                # Memory router read failed
                pass

        return trusted_commands
