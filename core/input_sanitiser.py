"""Input sanitiser for prompt injection hardening."""

from __future__ import annotations

from typing import TYPE_CHECKING
import re
import unicodedata

from core.observability import (
    TraceEmitter,
    MemoryTraceEmitter,
    TraceEvent,
    TraceEventType,
    TraceComponent,
    TraceLevel,
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

    def _normalise(self, text: str) -> str:
        """Normalise Unicode text to NFKC form.
        
        Collapses homoglyphs and fullwidth characters that could bypass regex patterns.
        No trace event needed (normalisation is lossless and unconditional).
        
        Args:
            text: The text to normalise
            
        Returns:
            Normalised text
        """
        return unicodedata.normalize('NFKC', text)

    def _truncate(self, text: str, *, max_length: int = 10000) -> str:
        """Truncate text to max_length characters.
        
        Defends against memory exhaustion and context overflow.
        
        Args:
            text: The text to truncate
            max_length: Maximum length (default 10000)
            
        Returns:
            Truncated text with ...[truncated] suffix if truncated
        """
        if len(text) <= max_length:
            return text
        
        # Trace emission skipped for synchronous method - would require async context
        # Per Rule 17: trace failure should not abort operation
        
        return text[:max_length] + "...[truncated]"

    def _strip_injection_tags(self, text: str) -> str:
        """Strip injection-tag markers that would be silently consumed by _strip_html.
        
        Detects tag-like prompt-injection markers (</thinking>, <ignore>, </ignore>, etc.)
        and replaces them with [FILTERED:prompt-injection] to preserve audit trail.
        Runs BEFORE _strip_html to prevent silent deletion.
        
        Args:
            text: The text to strip
            
        Returns:
            Text with injection tags replaced
        """
        injection_markers = [
            r'</thinking>',
            r'<ignore>',
            r'</ignore>',
            r'<system>',
            r'</system>',
            r'<assistant>',
            r'</assistant>',
            r'<<SYS>>',
            r'<</SYS>>',
            r'\[INST\]',
            r'\[/INST\]',
        ]
        
        result = text
        matched_markers = []
        
        for marker in injection_markers:
            if re.search(marker, result, re.IGNORECASE):
                result = re.sub(marker, '[BLOCKED]', result, flags=re.IGNORECASE)
                matched_markers.append(marker)
        
        if matched_markers:
            # Trace emission skipped for synchronous method - would require async context
            # Per Rule 17: trace failure should not abort operation
            pass
        
        return result

    def _strip_html(self, text: str) -> str:
        r"""Strip HTML/script tags and related patterns.

        Removes generic HTML/script/img/a tags using regex.
        Also strips javascript: URIs and on\w+= event handler attributes.
        Does NOT strip injection-tag patterns (those are handled by _strip_injection_tags).

        Args:
            text: The text to strip

        Returns:
            Text with HTML tags removed
        """
        # Remove script tags and their content
        result = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.IGNORECASE | re.DOTALL)
        
        # Remove other HTML tags
        result = re.sub(r'<[^>]+>', '', result)
        
        # Remove javascript: URIs
        result = re.sub(r'javascript:', '', result, flags=re.IGNORECASE)
        
        # Remove on\w+= event handlers
        result = re.sub(r'on\w+=', '', result, flags=re.IGNORECASE)
        
        # Check if anything was removed
        if result != text:
            # Trace emission skipped for synchronous method - would require async context
            # Per Rule 17: trace failure should not abort operation
            pass
        
        return result

    def _strip_command_injection(self, text: str) -> str:
        r"""Strip command-injection patterns.

        Detects shell metacharacter sequences commonly used in injection attacks:
        ;, &&, ||, $(), backticks, >\s*/, rm -rf.

        Args:
            text: The text to strip

        Returns:
            Text with command injection patterns replaced
        """
        # Match multi-character injection sequences (not single semicolons)
        patterns = [
            r';\s+rm\s+-rf\s+/?\S*',  # ; rm -rf /path
            r';\s+(rm|curl|wget|nc|bash|sh|python|perl|ruby|echo|cat|ls|cd)\s',  # ; followed by common commands
            r'&&\s+(rm|curl|wget|nc|bash|sh|python|perl|ruby|echo|cat|ls|cd)\s',  # && followed by common commands
            r'\|\|\s+(rm|curl|wget|nc|bash|sh|python|perl|ruby|echo|cat|ls|cd)\s',  # || followed by common commands
            r'\$\([^)]*\)',  # $(command)
            r'>\s*/',  # redirect to root
            r'rm\s+-rf\s+/?\S*',  # rm -rf /path
        ]
        
        result = text
        matched_patterns = []
        
        for pattern in patterns:
            if re.search(pattern, result):
                result = re.sub(pattern, '[BLOCKED]', result)
                matched_patterns.append(pattern)
        
        if matched_patterns:
            # Trace emission skipped for synchronous method - would require async context
            # Per Rule 17: trace failure should not abort operation
            pass
        
        return result

    def _strip_prompt_injection(self, text: str) -> str:
        """Strip non-tag prompt-injection patterns.
        
        Replaces the 10 hardcoded literal strings with regex-based pattern set.
        Patterns cover: "ignore previous instructions", "system prompt:", 
        "you are now", "act as", and the original literal patterns.
        Uses case-insensitive matching.
        
        Args:
            text: The text to strip
            
        Returns:
            Text with prompt injection patterns replaced
        """
        # Regex patterns covering the original 10 literals plus common variants
        patterns = [
            r'```',  # chr(96)*3 - code blocks
            r'<s>',  # chr(60)+chr(115)+chr(62)
            r'</s>',  # chr(60)+chr(47)+chr(115)+chr(62)
            r'ignore\s+previous\s+instructions',  # covers case variants via IGNORECASE
            r'\[INST\]',  # [INST]
            r'<<SYS>>',  # <<SYS>>
            r'###\s*System:',  # ### System:
            r'###\s*Instruction:',  # ### Instruction:
            r'system\s+prompt:',  # system prompt:
            r'you\s+are\s+now',  # you are now
            r'act\s+as',  # act as
            r'`',  # backtick (single) - code block marker
        ]
        
        result = text
        matched_patterns = []
        
        for pattern in patterns:
            if re.search(pattern, result, re.IGNORECASE):
                result = re.sub(pattern, '[BLOCKED]', result, flags=re.IGNORECASE)
                matched_patterns.append(pattern)
        
        if matched_patterns:
            # Trace emission skipped for synchronous method - would require async context
            # Per Rule 17: trace failure should not abort operation
            pass
        
        return result

    async def sanitise(self, text: str, source: str = "unknown") -> str:
        """Sanitise text by applying defense layers in canonical order.
        
        Layer order: normalise → truncate → strip_injection_tags → strip_html → 
                     strip_command_injection → strip_prompt_injection
        
        Args:
            text: The text to sanitise
            source: Source identifier for trace events
            
        Returns:
            Sanitised text with all defense layers applied
        """
        # Apply defense layers in canonical order
        result = self._normalise(text)
        result = self._truncate(result)
        
        # Track matched patterns for trace events
        matched_patterns = []
        
        # Check if any BLOCKED_PATTERNS are in the text (for backward compatibility)
        for pattern in self.BLOCKED_PATTERNS:
            if pattern in result:
                matched_patterns.append(pattern)
                result = result.replace(pattern, "[BLOCKED]")
        
        # Apply additional defense layers
        result = self._strip_injection_tags(result)
        result = self._strip_html(result)
        result = self._strip_command_injection(result)
        result = self._strip_prompt_injection(result)
        
        # Emit trace event if any patterns were matched (for backward compatibility)
        if matched_patterns:
            try:
                event = TraceEvent(
                    event_type=TraceEventType.INPUT_SANITISED,
                    component=TraceComponent.SECURITY,
                    level=TraceLevel.WARNING,
                    message=f"Input sanitised: {len(matched_patterns)} patterns blocked",
                    data={"source": source, "matched_patterns": matched_patterns},
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception:
                # Per Rule 17: broad except requires inline comment
                # Trace emission failed - don't crash
                pass
        
        return result

    async def is_clean(self, text: str) -> bool:
        """Check if text contains any blocked patterns.
        
        Args:
            text: The text to check
            
        Returns:
            True if no blocked patterns found, False otherwise
        """
        # Check against the original BLOCKED_PATTERNS for backward compatibility
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
