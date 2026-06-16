"""
TrajectoryExporter — exports completed task trajectories in ShareGPT format for fine-tuning.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
import json
import aiofiles
import asyncio
from pathlib import Path

from core.observability import MemoryTraceEmitter, TraceEvent, TraceEventType, TraceComponent, TraceLevel
from core.schemas import Task, WorkerOutput, TaskStatus

if TYPE_CHECKING:
    from core.observability import TraceEmitter
    from core.memory_router import MemoryRouter


class TrajectoryExporter:
    """
    Exports completed task trajectories in ShareGPT format for fine-tuning.
    system/ layer: imports from core/ and system/ only.
    """

    def __init__(
        self,
        memory_router: MemoryRouter,
        emitter: TraceEmitter | None = None,
        export_path: str = "exports/trajectories.jsonl",
    ) -> None:
        self._router = memory_router
        self._emitter = emitter or MemoryTraceEmitter()
        self._export_path = export_path

    async def export(self, min_rating: float = 0.5) -> int:
        """
        Export completed tasks with rating >= min_rating to ShareGPT JSONL format.

        Fetches completed tasks from memory where status == "completed" and complexity_score >= min_rating.
        For each task, retrieves its associated WorkerOutput from memory.
        Converts each (Task, WorkerOutput) pair to ShareGPT format.
        Writes all records as JSONL (one JSON object per line) to self._export_path.
        Creates the export directory if it does not exist.

        Args:
            min_rating: Minimum complexity_score threshold for export (default 4.0, but note complexity_score is 0-1)

        Returns:
            Number of records written.
        """
        await self._emitter.emit(TraceEvent(
            event_type=TraceEventType.OPERATION_START,
            component=TraceComponent.ORCHESTRATOR,
            level=TraceLevel.INFO,
            message="Trajectory export started",
            data={"min_rating": min_rating, "export_path": self._export_path},
            duration_ms=0,
        ))

        # Fetch completed tasks with complexity_score >= min_rating
        # Note: complexity_score is 0-1, so min_rating should be interpreted as a threshold in that range
        tasks = await self._router.fetch(Task, filter_func=lambda t: t.current_state == TaskStatus.COMPLETE and t.complexity_score >= min_rating)

        records = []
        for task in tasks:
            # Fetch associated WorkerOutput for this task
            outputs = await self._router.fetch(WorkerOutput, filter_func=lambda o: o.task_id == task.task_id)
            if outputs:
                output = outputs[0]  # Take first output if multiple exist
                sharegpt_record = self._to_sharegpt(task, output)
                records.append(sharegpt_record)

        # Create export directory if it does not exist
        export_file = Path(self._export_path)
        export_file.parent.mkdir(parents=True, exist_ok=True)

        # Write records as JSONL
        async with aiofiles.open(self._export_path, mode="w") as f:
            for record in records:
                await f.write(json.dumps(record) + "\n")

        await self._emitter.emit(TraceEvent(
            event_type=TraceEventType.OPERATION_COMPLETE,
            component=TraceComponent.ORCHESTRATOR,
            level=TraceLevel.INFO,
            message="Trajectory export complete",
            data={"record_count": len(records), "export_path": self._export_path},
            duration_ms=0,
        ))

        return len(records)

    def _to_sharegpt(self, task: Task, output: WorkerOutput) -> dict:
        """
        Convert a Task + WorkerOutput pair to ShareGPT format.

        Args:
            task: The task to convert.
            output: The worker output for the task.

        Returns:
            Dictionary in ShareGPT format with conversations array.
        """
        return {
            "conversations": [
                {"from": "human", "value": task.intent},
                {"from": "gpt", "value": output.content}
            ]
        }
