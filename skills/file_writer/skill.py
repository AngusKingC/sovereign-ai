"""
File Writer Skill - writes content to local files with configurable mode.

Single responsibility: Write content to local filesystem with approval gate.
"""

from typing import Any

from core.observability import (
    TraceComponent,
    TraceEventType,
    TraceLevel,
    TraceEmitter,
    emit_trace,
)


class FileWriterSkill:
    """Skill for writing content to local files."""

    def __init__(self, emitter: TraceEmitter | None = None) -> None:
        """Initialize the file writer skill."""
        self.emitter = emitter
        # For now, use the global emitter as fallback
        # This will be replaced with NullTraceEmitter in Prompt 13.5

    async def execute(self, path: str, content: str, mode: str = "write") -> tuple[bool, int]:
        """
        Write content to file.

        Args:
            path: Path to the file to write
            content: Content to write to the file
            mode: File write mode, defaults to 'write'

        Returns:
            Tuple of (success: bool, bytes_written: int)

        Raises:
            ValueError: If path or content is invalid
            IOError: If file cannot be written
        """
        if not path or not isinstance(path, str):
            raise ValueError("Path must be a non-empty string")
        if not isinstance(content, str):
            raise ValueError("Content must be a string")

        # Approval gate - stubbed for now
        # Full implementation comes in Prompt 14
        print("APPROVAL REQUIRED")
        approved = True

        if not approved:
            await emit_trace(
                event_type=TraceEventType.OPERATION_COMPLETE,
                component=TraceComponent.WORKER,
                level=TraceLevel.WARNING,
                layer="layer_2",
                payload={
                    "skill": "file_writer",
                    "path": path,
                    "mode": mode,
                    "error": "Approval denied",
                },
                duration_ms=0,
                success=False,
            )
            return False, 0

        try:
            import aiofiles

            write_mode = "w" if mode == "write" else "a"
            async with aiofiles.open(path, mode=write_mode, encoding="utf-8") as file:
                bytes_written = await file.write(content)

            await emit_trace(
                event_type=TraceEventType.OPERATION_COMPLETE,
                component=TraceComponent.WORKER,
                level=TraceLevel.INFO,
                layer="layer_2",
                payload={
                    "skill": "file_writer",
                    "path": path,
                    "mode": mode,
                    "bytes_written": bytes_written,
                },
                duration_ms=0,
                success=True,
            )

            return True, bytes_written

        except IOError as e:
            await emit_trace(
                event_type=TraceEventType.OPERATION_COMPLETE,
                component=TraceComponent.WORKER,
                level=TraceLevel.ERROR,
                layer="layer_2",
                payload={
                    "skill": "file_writer",
                    "path": path,
                    "error": str(e),
                },
                duration_ms=0,
                success=False,
            )
            raise
