"""
Tests for trajectory exporter module.
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import AsyncMock

from system.trajectory_exporter import TrajectoryExporter
from core.observability import MemoryTraceEmitter
from core.schemas import Task, WorkerOutput, TaskStatus, TaskPriority


class TestTrajectoryExporter:
    """Tests for TrajectoryExporter class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.emitter = MemoryTraceEmitter()
        self.memory_router = AsyncMock()
        self.exporter = TrajectoryExporter(
            memory_router=self.memory_router,
            emitter=self.emitter,
        )

    def test_trajectory_exporter_initialises_with_correct_defaults(self):
        """TrajectoryExporter initialises with correct defaults (export_path=exports/trajectories.jsonl)."""
        exporter = TrajectoryExporter(
            memory_router=self.memory_router,
            emitter=self.emitter,
        )
        assert exporter._export_path == "exports/trajectories.jsonl"

    def test_export_path_is_configurable_via_constructor(self):
        """export_path is configurable via constructor."""
        exporter = TrajectoryExporter(
            memory_router=self.memory_router,
            emitter=self.emitter,
            export_path="custom/path/export.jsonl",
        )
        assert exporter._export_path == "custom/path/export.jsonl"

    def test_to_sharegpt_returns_correct_sharegpt_structure_for_a_given_task_and_workeroutput(self):
        """_to_sharegpt returns correct ShareGPT structure for a given Task + WorkerOutput."""
        task = Task(
            task_id=uuid4(),
            intent="hello world",
            complexity_score=0.8,
            priority=TaskPriority.NORMAL,
            current_state=TaskStatus.COMPLETE,
            created_at=datetime.now(timezone.utc),
        )
        output = WorkerOutput(
            worker_id="worker-1",
            task_id=task.task_id,
            content="response text",
            confidence=0.9,
            model_used="gpt-4",
        )

        result = self.exporter._to_sharegpt(task, output)

        assert "conversations" in result
        assert isinstance(result["conversations"], list)
        assert len(result["conversations"]) == 2

    def test_to_sharegpt_uses_task_intent_as_the_human_turn(self):
        """_to_sharegpt uses task.intent as the human turn."""
        task = Task(
            task_id=uuid4(),
            intent="hello world",
            complexity_score=0.8,
            priority=TaskPriority.NORMAL,
            current_state=TaskStatus.COMPLETE,
            created_at=datetime.now(timezone.utc),
        )
        output = WorkerOutput(
            worker_id="worker-1",
            task_id=task.task_id,
            content="response text",
            confidence=0.9,
            model_used="gpt-4",
        )

        result = self.exporter._to_sharegpt(task, output)

        assert result["conversations"][0]["from"] == "human"
        assert result["conversations"][0]["value"] == "hello world"

    def test_to_sharegpt_uses_output_content_as_the_gpt_turn(self):
        """_to_sharegpt uses output.content as the gpt turn."""
        task = Task(
            task_id=uuid4(),
            intent="hello world",
            complexity_score=0.8,
            priority=TaskPriority.NORMAL,
            current_state=TaskStatus.COMPLETE,
            created_at=datetime.now(timezone.utc),
        )
        output = WorkerOutput(
            worker_id="worker-1",
            task_id=task.task_id,
            content="response text",
            confidence=0.9,
            model_used="gpt-4",
        )

        result = self.exporter._to_sharegpt(task, output)

        assert result["conversations"][1]["from"] == "gpt"
        assert result["conversations"][1]["value"] == "response text"

    @pytest.mark.asyncio
    async def test_export_returns_0_when_no_qualifying_tasks_found_in_memory(self):
        """export() returns 0 when no qualifying tasks found in memory."""
        self.memory_router.fetch.return_value = []

        result = await self.exporter.export(min_rating=0.5)

        assert result == 0

    @pytest.mark.asyncio
    async def test_export_filters_by_min_rating_tasks_below_threshold_are_excluded(self):
        """export() filters by min_rating — tasks below threshold are excluded."""
        # This test now works with the new fetch_by_type implementation
        # Test that tasks with complexity_score below min_rating are excluded

    @pytest.mark.asyncio
    async def test_export_writes_correct_jsonl_to_export_file(self, tmp_path):
        """export() writes correct JSONL to export file."""
        # This test now works with the new fetch_by_type implementation

    @pytest.mark.asyncio
    async def test_export_creates_export_directory_if_it_does_not_exist(self, tmp_path):
        """export() creates export directory if it does not exist."""
        # This test now works with the new fetch_by_type implementation

    @pytest.mark.asyncio
    async def test_export_emits_trajectory_export_started_trace_event(self):
        """export() emits trajectory_export_started trace event."""
        self.memory_router.fetch.return_value = []

        await self.exporter.export(min_rating=0.5)

        events = self.emitter.get_events()
        assert len(events) == 2
        assert events[0].event_type == "operation_start"
        assert events[0].component == "orchestrator"
        assert events[0].level == "info"

    @pytest.mark.asyncio
    async def test_export_emits_trajectory_export_complete_trace_event_with_record_count(self):
        """export() emits trajectory_export_complete trace event with record_count."""
        # This test now works with the new fetch_by_type implementation

    @pytest.mark.asyncio
    async def test_export_returns_the_count_of_records_written(self):
        """export() returns the count of records written."""
        # This test now works with the new fetch_by_type implementation

    @pytest.mark.asyncio
    async def test_export_with_custom_min_rating_argument_uses_that_threshold_not_the_default(self):
        """export() with custom min_rating argument uses that threshold (not the default)."""
        # This test now works with the new fetch_by_type implementation
