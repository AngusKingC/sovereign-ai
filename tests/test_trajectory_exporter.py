"""
Tests for trajectory exporter module.
"""

import pytest
import json
from datetime import datetime
from uuid import uuid4
from unittest.mock import AsyncMock, patch

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
            created_at=datetime.now(),
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
            created_at=datetime.now(),
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
            created_at=datetime.now(),
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
        task_high = Task(
            task_id=uuid4(),
            intent="high quality task",
            complexity_score=0.9,
            priority=TaskPriority.NORMAL,
            current_state=TaskStatus.COMPLETE,
            created_at=datetime.now(),
        )
        task_low = Task(
            task_id=uuid4(),
            intent="low quality task",
            complexity_score=0.3,
            priority=TaskPriority.NORMAL,
            current_state=TaskStatus.COMPLETE,
            created_at=datetime.now(),
        )
        output = WorkerOutput(
            worker_id="worker-1",
            task_id=task_high.task_id,
            content="response",
            confidence=0.9,
            model_used="gpt-4",
        )

        # Mock fetch to return both tasks initially
        self.memory_router.fetch.side_effect = [
            [task_high, task_low],  # tasks fetch
            [output],  # output fetch for high task
            [],  # output fetch for low task (no output)
        ]

        result = await self.exporter.export(min_rating=0.5)

        # Only high quality task should be exported
        assert result == 1

    @pytest.mark.asyncio
    async def test_export_writes_correct_jsonl_to_export_file(self, tmp_path):
        """export() writes correct JSONL to export file."""
        task = Task(
            task_id=uuid4(),
            intent="hello world",
            complexity_score=0.8,
            priority=TaskPriority.NORMAL,
            current_state=TaskStatus.COMPLETE,
            created_at=datetime.now(),
        )
        output = WorkerOutput(
            worker_id="worker-1",
            task_id=task.task_id,
            content="response text",
            confidence=0.9,
            model_used="gpt-4",
        )

        export_path = tmp_path / "export.jsonl"
        exporter = TrajectoryExporter(
            memory_router=self.memory_router,
            emitter=self.emitter,
            export_path=str(export_path),
        )

        self.memory_router.fetch.side_effect = [
            [task],
            [output],
        ]

        await exporter.export(min_rating=0.5)

        # Verify file was written
        assert export_path.exists()
        content = export_path.read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 1

        # Verify JSON structure
        record = json.loads(lines[0])
        assert "conversations" in record
        assert len(record["conversations"]) == 2
        assert record["conversations"][0]["from"] == "human"
        assert record["conversations"][0]["value"] == "hello world"
        assert record["conversations"][1]["from"] == "gpt"
        assert record["conversations"][1]["value"] == "response text"

    @pytest.mark.asyncio
    async def test_export_creates_export_directory_if_it_does_not_exist(self, tmp_path):
        """export() creates export directory if it does not exist."""
        task = Task(
            task_id=uuid4(),
            intent="hello world",
            complexity_score=0.8,
            priority=TaskPriority.NORMAL,
            current_state=TaskStatus.COMPLETE,
            created_at=datetime.now(),
        )
        output = WorkerOutput(
            worker_id="worker-1",
            task_id=task.task_id,
            content="response text",
            confidence=0.9,
            model_used="gpt-4",
        )

        export_path = tmp_path / "subdir" / "export.jsonl"
        exporter = TrajectoryExporter(
            memory_router=self.memory_router,
            emitter=self.emitter,
            export_path=str(export_path),
        )

        self.memory_router.fetch.side_effect = [
            [task],
            [output],
        ]

        await exporter.export(min_rating=0.5)

        # Verify directory was created
        assert export_path.parent.exists()
        assert export_path.exists()

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
        task = Task(
            task_id=uuid4(),
            intent="hello world",
            complexity_score=0.8,
            priority=TaskPriority.NORMAL,
            current_state=TaskStatus.COMPLETE,
            created_at=datetime.now(),
        )
        output = WorkerOutput(
            worker_id="worker-1",
            task_id=task.task_id,
            content="response text",
            confidence=0.9,
            model_used="gpt-4",
        )

        self.memory_router.fetch.side_effect = [
            [task],
            [output],
        ]

        await self.exporter.export(min_rating=0.5)

        events = self.emitter.get_events()
        assert len(events) == 2
        assert events[1].event_type == "operation_complete"
        assert events[1].data["record_count"] == 1
        assert events[1].data["export_path"] == "exports/trajectories.jsonl"

    @pytest.mark.asyncio
    async def test_export_returns_the_count_of_records_written(self):
        """export() returns the count of records written."""
        task1 = Task(
            task_id=uuid4(),
            intent="task 1",
            complexity_score=0.8,
            priority=TaskPriority.NORMAL,
            current_state=TaskStatus.COMPLETE,
            created_at=datetime.now(),
        )
        task2 = Task(
            task_id=uuid4(),
            intent="task 2",
            complexity_score=0.9,
            priority=TaskPriority.NORMAL,
            current_state=TaskStatus.COMPLETE,
            created_at=datetime.now(),
        )
        output1 = WorkerOutput(
            worker_id="worker-1",
            task_id=task1.task_id,
            content="response 1",
            confidence=0.9,
            model_used="gpt-4",
        )
        output2 = WorkerOutput(
            worker_id="worker-1",
            task_id=task2.task_id,
            content="response 2",
            confidence=0.9,
            model_used="gpt-4",
        )

        self.memory_router.fetch.side_effect = [
            [task1, task2],
            [output1],
            [output2],
        ]

        result = await self.exporter.export(min_rating=0.5)

        assert result == 2

    @pytest.mark.asyncio
    async def test_export_with_custom_min_rating_argument_uses_that_threshold_not_the_default(self):
        """export() with custom min_rating argument uses that threshold (not the default)."""
        task_low = Task(
            task_id=uuid4(),
            intent="low quality task",
            complexity_score=0.3,
            priority=TaskPriority.NORMAL,
            current_state=TaskStatus.COMPLETE,
            created_at=datetime.now(),
        )
        output = WorkerOutput(
            worker_id="worker-1",
            task_id=task_low.task_id,
            content="response",
            confidence=0.9,
            model_used="gpt-4",
        )

        # Make the mock actually execute the filter_func
        async def mock_fetch(model_type, filter_func=None):
            if model_type == Task:
                tasks = [task_low]
                if filter_func:
                    tasks = [t for t in tasks if filter_func(t)]
                return tasks
            elif model_type == WorkerOutput:
                outputs = [output]
                if filter_func:
                    outputs = [o for o in outputs if filter_func(o)]
                return outputs
            return []

        self.memory_router.fetch.side_effect = mock_fetch

        # With default min_rating (0.5), this task should not be exported
        result_default = await self.exporter.export()
        assert result_default == 0

        # Reset emitter
        self.emitter.clear()

        # With custom min_rating (0.2), this task should be exported
        result_custom = await self.exporter.export(min_rating=0.2)
        assert result_custom == 1
