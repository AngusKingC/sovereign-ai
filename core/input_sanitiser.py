"""Input sanitiser for prompt injection hardening."""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.observability import (
    TraceComponent,
    TraceEventType,
    TraceLevel,
    TraceEvent,
    TraceEmitter,
    MemoryTraceEmitter,
)

if TYPE_CHECKING:
    from core.observability import TraceEmitter


class InputSanitiser:
    """Sanitises input to prevent prompt injection attacks."""

    BLOCKED_PATTERNS = [
        chr(96) + chr(96) + chr(96),
        chr(60) + chr(115) + chr(62),
        chr(60) + chr(47) + chr(115) + chr(62),
        "IGNORE PREVIOUS INSTRUCTIONS",
        "ignore previous instructions",
        "Ignore previous instructions",
        "[INST]",
        "<<SYS>>",
        "### System:",
        "### Instruction:",
    ]

    def __init__(self, emitter: TraceEmitter | None = None):
        self._emitter = emitter or MemoryTraceEmitter()

    async def sanitise(self, text: str, source: str = "unknown") -> str:
        """Sanitise text by replacing blocked patterns.
        
        Args:
            text: The text to sanitise
            source: Source identifier for trace events
            
        Returns:
            Sanitised text with blocked patterns replaced
        """
        result = text
        matched_patterns = []
        
        for pattern in self.BLOCKED_PATTERNS:
            if pattern in result:
                result = result.replace(pattern, "[BLOCKED]")
                matched_patterns.append(pattern)
        
        if matched_patterns:
            try:
                event = TraceEvent(
                    event_type=TraceEventType.INPUT_SANITISED,
                    component=TraceComponent.SECURITY,
                    level=TraceLevel.WARNING,
                    message=f"Input sanitised: {len(matched_patterns)} patterns blocked",
                    data={
                        "source": source,
                        "matched_patterns": matched_patterns,
                    },
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception:
                pass  # Trace failure should not abort operation
        
        return result

    async def is_clean(self, text: str) -> bool:
        """Check if text contains any blocked patterns.
        
        Args:
            text: The text to check
            
        Returns:
            True if no blocked patterns found, False otherwise
        """
        for pattern in self.BLOCKED_PATTERNS:
            if pattern in text:
                return False
        return True

    def add_pattern(self, pattern: str) -> None:
        """Add a new pattern to the blocked patterns list.
        
        Args:
            pattern: The pattern to add
        """
        self.BLOCKED_PATTERNS.append(pattern)
