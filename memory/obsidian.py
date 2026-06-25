"""
Obsidian markdown vault integration.

Single responsibility: Read and write markdown files to Obsidian vaults,
providing persistent, human-readable memory storage.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.memory_router import MemoryBackend
from core.observability import (
    MemoryTraceEmitter,
    TraceComponent,
    TraceEmitter,
    TraceEvent,
    TraceEventType,
    TraceLevel,
)
from core.schemas import Task

logger = logging.getLogger(__name__)


class ObsidianBackend(MemoryBackend):
    """Memory backend for Obsidian markdown vaults."""

    def __init__(self, vault_path: str, emitter: TraceEmitter | None = None) -> None:
        """Initialize the Obsidian backend with a vault path."""
        self.vault_path = Path(vault_path)
        self.vault_path.mkdir(parents=True, exist_ok=True)
        self._emitter = emitter or MemoryTraceEmitter()

    async def fetch(self, task: Task) -> list[dict[str, Any]]:
        """
        Fetch memory relevant to the task from the Obsidian vault.

        Simple implementation: reads all .md files and returns their content.
        """
        start_time = time.perf_counter()
        memory: list[dict[str, Any]] = []

        try:
            # Emit fetch start event
            try:
                event = TraceEvent(
                    event_type=TraceEventType.MEMORY_FETCH,
                    component=TraceComponent.MEMORY_ROUTER,
                    message="Obsidian memory fetch started",
                    level=TraceLevel.INFO,
                    data={
                        "backend_type": "obsidian",
                        "task_id": str(task.task_id),
                        "vault_path": str(self.vault_path),
                    },
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception as e:
                logger.warning("Trace emission failed: %s", e)

            if not self.vault_path.exists():
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                try:
                    event = TraceEvent(
                        event_type=TraceEventType.MEMORY_FETCH,
                        component=TraceComponent.MEMORY_ROUTER,
                        message="Obsidian memory fetch completed (vault not found)",
                        level=TraceLevel.INFO,
                        data={
                            "backend_type": "obsidian",
                            "task_id": str(task.task_id),
                            "records_fetched": 0,
                        },
                        duration_ms=duration_ms,
                    )
                    await self._emitter.emit(event)
                except Exception as e:
                    logger.warning("Trace emission failed: %s", e)
                return memory

            # Run file I/O in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            for md_file in self.vault_path.glob("*.md"):
                try:
                    content = await loop.run_in_executor(
                        None, md_file.read_text, "utf-8"
                    )
                    memory.append(
                        {
                            "source": "obsidian",
                            "file": md_file.name,
                            "content": content,
                            "path": str(md_file),
                        }
                    )
                except Exception:
                    # Skip files that can't be read
                    continue

            duration_ms = int((time.perf_counter() - start_time) * 1000)

            # Emit fetch complete event
            try:
                event = TraceEvent(
                    event_type=TraceEventType.MEMORY_FETCH,
                    component=TraceComponent.MEMORY_ROUTER,
                    message="Obsidian memory fetch completed",
                    level=TraceLevel.INFO,
                    data={
                        "backend_type": "obsidian",
                        "task_id": str(task.task_id),
                        "records_fetched": len(memory),
                    },
                    duration_ms=duration_ms,
                )
                await self._emitter.emit(event)
            except Exception as e:
                logger.warning("Trace emission failed: %s", e)

            return memory
        except Exception as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            # Emit error event (wrapped to avoid crashing main path)
            try:
                event = TraceEvent(
                    event_type=TraceEventType.MEMORY_FETCH,
                    component=TraceComponent.MEMORY_ROUTER,
                    message="Obsidian memory fetch failed",
                    level=TraceLevel.ERROR,
                    data={
                        "backend_type": "obsidian",
                        "task_id": str(task.task_id),
                    },
                    duration_ms=duration_ms,
                    error_type=type(e).__name__,
                    error_message=str(e),
                )
                await self._emitter.emit(event)
            except Exception as e2:
                logger.warning(
                    "Trace emission failed: %s", e2
                )  # Trace failure should not crash main path
            raise

    async def write(self, data: dict[str, Any]) -> None:
        """
        Write data to the Obsidian vault as a markdown file.

        Creates a file with a timestamp-based name and markdown content.
        """
        start_time = time.perf_counter()

        try:
            # Emit write start event
            try:
                event = TraceEvent(
                    event_type=TraceEventType.MEMORY_WRITE,
                    component=TraceComponent.MEMORY_ROUTER,
                    message="Obsidian memory write started",
                    level=TraceLevel.INFO,
                    data={
                        "backend_type": "obsidian",
                        "vault_path": str(self.vault_path),
                    },
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception as e:
                logger.warning("Trace emission failed: %s", e)

            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid4())[:8]
            filename = f"{timestamp}_{unique_id}.md"
            filepath = self.vault_path / filename

            # Build markdown content from data
            content = self._data_to_markdown(data)

            # Run file I/O in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, filepath.write_text, content, "utf-8")

            duration_ms = int((time.perf_counter() - start_time) * 1000)

            # Emit write complete event
            try:
                event = TraceEvent(
                    event_type=TraceEventType.MEMORY_WRITE,
                    component=TraceComponent.MEMORY_ROUTER,
                    message="Obsidian memory write completed",
                    level=TraceLevel.INFO,
                    data={
                        "backend_type": "obsidian",
                        "filename": filename,
                        "records_written": 1,
                    },
                    duration_ms=duration_ms,
                )
                await self._emitter.emit(event)
            except Exception as e:
                logger.warning("Trace emission failed: %s", e)
        except Exception as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            # Emit error event (wrapped to avoid crashing main path)
            try:
                event = TraceEvent(
                    event_type=TraceEventType.MEMORY_WRITE,
                    component=TraceComponent.MEMORY_ROUTER,
                    message="Obsidian memory write failed",
                    level=TraceLevel.ERROR,
                    data={
                        "backend_type": "obsidian",
                    },
                    duration_ms=duration_ms,
                    error_type=type(e).__name__,
                    error_message=str(e),
                )
                await self._emitter.emit(event)
            except Exception as e2:
                logger.warning(
                    "Trace emission failed: %s", e2
                )  # Trace failure should not crash main path
            raise

    async def list_keys(self, prefix: str) -> list[str]:
        """List all keys matching the given prefix."""
        # Stub implementation - returns empty list for now
        return []

    def _data_to_markdown(self, data: dict[str, Any]) -> str:
        """Convert data dictionary to markdown format."""
        lines = ["# Memory Entry\n"]

        for key, value in data.items():
            if isinstance(value, (list, dict)):
                lines.append(f"\n## {key}\n")
                lines.append(f"```json\n{value}\n```")
            else:
                lines.append(f"\n**{key}**: {value}")

        return "\n".join(lines)
