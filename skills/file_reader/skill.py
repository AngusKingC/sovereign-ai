"""
File Reader Skill - reads local file contents with configurable encoding.

Single responsibility: Read file contents from local filesystem.
"""

from typing import Any

from core.observability import (
    TraceComponent,
    TraceEventType,
    TraceLevel,
    TraceEvent,
    TraceEmitter,
    MemoryTraceEmitter,
)


class FileReaderSkill:
    """Skill for reading local file contents."""

    def __init__(self, emitter: TraceEmitter | None = None) -> None:
        """Initialize the file reader skill."""
        self._emitter = emitter or MemoryTraceEmitter()

    async def execute(self, path: str, encoding: str = "utf-8") -> str:
        """
        Read file contents.

        Args:
            path: Path to the file to read
            encoding: File encoding, defaults to utf-8

        Returns:
            File content as a string

        Raises:
            ValueError: If path is invalid or empty
            FileNotFoundError: If file does not exist
            IOError: If file cannot be read
        """
        if not path or not isinstance(path, str):
            raise ValueError("Path must be a non-empty string")

        try:
            import aiofiles

            async with aiofiles.open(path, mode="r", encoding=encoding) as file:
                content = await file.read()

            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.INFO,
                    message="File reading completed",
                    data={
                        "skill": "file_reader",
                        "path": path,
                        "encoding": encoding,
                        "content_length": len(content),
                    },
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception:
                pass

            return content

        except FileNotFoundError as e:
            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.ERROR,
                    message="File not found",
                    data={
                        "skill": "file_reader",
                        "path": path,
                        "error": str(e),
                    },
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception:
                pass
            raise
        except IOError as e:
            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.ERROR,
                    message="File read failed",
                    data={
                        "skill": "file_reader",
                        "path": path,
                        "error": str(e),
                    },
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception:
                pass
            raise
