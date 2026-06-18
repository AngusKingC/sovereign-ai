"""
Scratchpad management for per-task working memory.

Single responsibility: Manage ephemeral working memory scratchpads for worker reasoning.
Scratchpads are separate from long-term memory and are compacted on task completion.
"""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel

from core.memory_router import MemoryRouter
from core.observability import TraceComponent, TraceEventType, TraceLevel, TraceEvent, TraceEmitter, MemoryTraceEmitter
from core.schemas import Scratchpad, ScratchpadEntry, ScratchpadEntryType


class ScratchpadManager:
    """Manages per-task working memory scratchpads."""

    def __init__(self, memory_router: MemoryRouter, emitter: TraceEmitter | None = None) -> None:
        """Initialize scratchpad manager with memory router for persistence."""
        self.memory_router = memory_router
        # In-memory cache for active scratchpads (in production, this would be Postgres)
        self._scratchpads: dict[UUID, Scratchpad] = {}
        self._emitter = emitter or MemoryTraceEmitter()

    async def create(self, task_id: UUID) -> Scratchpad:
        """Create a new scratchpad for a task.
        
        Args:
            task_id: Task identifier
            
        Returns:
            New scratchpad instance
        """
        scratchpad = Scratchpad(task_id=task_id)
        self._scratchpads[task_id] = scratchpad
        
        # Persist to Postgres (in production, would write to database)
        await self._persist_scratchpad(scratchpad)
        
        # Emit trace event
        try:
            event = TraceEvent(
                event_type=TraceEventType.SCRATCHPAD_CREATED,
                component=TraceComponent.ORCHESTRATOR,
                message="Scratchpad created",
                level=TraceLevel.INFO,
                data={
                    "task_id": str(task_id),
                    "scratchpad_id": str(scratchpad.scratchpad_id),
                },
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            pass
        
        return scratchpad

    async def get(self, task_id: UUID) -> Scratchpad | None:
        """Retrieve scratchpad by task_id.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Scratchpad if found, None otherwise
        """
        return self._scratchpads.get(task_id)

    async def add_entry(
        self,
        task_id: UUID,
        worker_id: str,
        entry_type: ScratchpadEntryType,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> ScratchpadEntry:
        """Append an entry to the scratchpad.
        
        Args:
            task_id: Task identifier
            worker_id: Worker creating the entry
            entry_type: Type of scratchpad entry
            content: Entry content
            metadata: Optional additional metadata
            
        Returns:
            Created scratchpad entry
        """
        scratchpad = self._scratchpads.get(task_id)
        if not scratchpad:
            raise ValueError(f"No scratchpad found for task {task_id}")
        
        entry = ScratchpadEntry(
            task_id=task_id,
            worker_id=worker_id,
            entry_type=entry_type,
            content=content,
            metadata=metadata or {},
        )
        
        scratchpad.entries.append(entry)
        
        # Persist updated scratchpad
        await self._persist_scratchpad(scratchpad)
        
        # Emit trace event
        try:
            event = TraceEvent(
                event_type=TraceEventType.SCRATCHPAD_ENTRY_ADDED,
                component=TraceComponent.ORCHESTRATOR,
                message="Scratchpad entry added",
                level=TraceLevel.INFO,
                data={
                    "task_id": str(task_id),
                    "entry_id": str(entry.entry_id),
                    "entry_type": entry_type.value,
                    "worker_id": worker_id,
                },
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            pass
        
        return entry

    async def compact(self, task_id: UUID, llm_summary: str | None = None) -> Scratchpad:
        """Compact the scratchpad on task completion.
        
        Args:
            task_id: Task identifier
            llm_summary: Optional LLM-generated summary. If not provided, generates rule-based summary.
            
        Returns:
            Updated scratchpad with summary
        """
        scratchpad = self._scratchpads.get(task_id)
        if not scratchpad:
            raise ValueError(f"No scratchpad found for task {task_id}")
        
        # Generate summary if not provided
        if llm_summary:
            summary = llm_summary
        else:
            summary = self._generate_rule_based_summary(scratchpad)
        
        # Update scratchpad
        scratchpad.summary = summary
        scratchpad.completed_at = datetime.now()
        scratchpad.is_compacted = True
        
        # Persist updated scratchpad
        await self._persist_scratchpad(scratchpad)
        
        # Write compacted summary to long-term memory
        await self.memory_router.write_to_collection(
            data={
                "content": f"Task scratchpad summary: {summary}",
                "metadata": {
                    "type": "scratchpad_summary",
                    "task_id": str(task_id),
                    "entry_count": len(scratchpad.entries),
                },
            },
            collection="scratchpad",
            document_id=str(task_id),
        )
        
        # Emit trace event
        try:
            event = TraceEvent(
                event_type=TraceEventType.SCRATCHPAD_COMPACTED,
                component=TraceComponent.ORCHESTRATOR,
                message="Scratchpad compacted",
                level=TraceLevel.INFO,
                data={
                    "task_id": str(task_id),
                    "scratchpad_id": str(scratchpad.scratchpad_id),
                    "entry_count": len(scratchpad.entries),
                },
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            pass
        
        return scratchpad

    async def delete(self, task_id: UUID) -> None:
        """Delete scratchpad (called on task failure, after preserving for debug).
        
        Args:
            task_id: Task identifier
        """
        if task_id in self._scratchpads:
            del self._scratchpads[task_id]
        
        # Emit trace event
        try:
            event = TraceEvent(
                event_type=TraceEventType.SCRATCHPAD_DELETED,
                component=TraceComponent.ORCHESTRATOR,
                message="Scratchpad deleted",
                level=TraceLevel.INFO,
                data={"task_id": str(task_id)},
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            pass

    async def get_entries_by_type(
        self, task_id: UUID, entry_type: ScratchpadEntryType
    ) -> list[ScratchpadEntry]:
        """Filter entries by type.
        
        Args:
            task_id: Task identifier
            entry_type: Type of entries to retrieve
            
        Returns:
            List of entries matching the specified type
        """
        scratchpad = self._scratchpads.get(task_id)
        if not scratchpad:
            return []
        
        return [entry for entry in scratchpad.entries if entry.entry_type == entry_type]

    def _generate_rule_based_summary(self, scratchpad: Scratchpad) -> str:
        """Generate a simple rule-based summary of the scratchpad.
        
        Args:
            scratchpad: Scratchpad to summarize
            
        Returns:
            Generated summary string
        """
        # Count entries by type
        entry_counts: dict[ScratchpadEntryType, int] = {}
        for entry in scratchpad.entries:
            entry_counts[entry.entry_type] = entry_counts.get(entry.entry_type, 0) + 1
        
        # Extract intermediate results as key findings
        intermediate_results = [
            entry.content
            for entry in scratchpad.entries
            if entry.entry_type == ScratchpadEntryType.INTERMEDIATE_RESULT
        ]
        
        # Build summary
        summary_parts = [
            f"Scratchpad contained {len(scratchpad.entries)} entries.",
            f"Entry types: {', '.join(f'{t.value}: {c}' for t, c in entry_counts.items())}.",
        ]
        
        if intermediate_results:
            summary_parts.append(
                f"Key findings: {'; '.join(intermediate_results[:3])}"
            )
            if len(intermediate_results) > 3:
                summary_parts.append(f"... and {len(intermediate_results) - 3} more results.")
        
        return " ".join(summary_parts)

    async def _persist_scratchpad(self, scratchpad: Scratchpad) -> None:
        """Persist scratchpad to storage.
        
        In production, this would write to Postgres. For now, we use the memory router.
        
        Args:
            scratchpad: Scratchpad to persist
        """
        # In production, this would write to Postgres with task_id scope
        # For now, we use the in-memory cache
        pass
