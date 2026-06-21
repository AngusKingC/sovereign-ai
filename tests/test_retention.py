"""Tests for data retention and memory housekeeping."""

import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from core.retention import RetentionRule, RetentionReport, RetentionEngine
from system.retention_daemon import RetentionDaemon
from core.observability import MemoryTraceEmitter


@pytest.mark.asyncio
class TestRetentionRule:
    """Tests for RetentionRule model."""

    async def test_retention_rule_constructs_with_required_fields_and_correct_defaults(self) -> None:
        """Test that RetentionRule constructs with required fields and correct defaults."""
        rule = RetentionRule(
            scope="global",
            data_type="task",
            ttl_seconds=3600,
        )
        
        assert rule.scope == "global"
        assert rule.data_type == "task"
        assert rule.ttl_seconds == 3600
        assert rule.archive is True

    async def test_retention_rule_archive_defaults_to_true(self) -> None:
        """Test that RetentionRule.archive defaults to True."""
        rule = RetentionRule(
            scope="global",
            data_type="task",
            ttl_seconds=3600,
        )
        
        assert rule.archive is True


@pytest.mark.asyncio
class TestRetentionReport:
    """Tests for RetentionReport model."""

    async def test_retention_report_constructs_with_correct_defaults(self) -> None:
        """Test that RetentionReport constructs with correct defaults."""
        report = RetentionReport(
            run_at=datetime.now(timezone.utc),
            rules_applied=1,
            records_expired=10,
            records_archived=5,
            records_deleted=5,
        )
        
        assert report.run_at is not None
        assert report.rules_applied == 1
        assert report.records_expired == 10
        assert report.records_archived == 5
        assert report.records_deleted == 5

    async def test_retention_report_errors_defaults_to_empty_list(self) -> None:
        """Test that RetentionReport.errors defaults to empty list."""
        report = RetentionReport(
            run_at=datetime.now(timezone.utc),
            rules_applied=0,
            records_expired=0,
            records_archived=0,
            records_deleted=0,
        )
        
        assert report.errors == []


@pytest.mark.asyncio
class TestRetentionEngine:
    """Tests for RetentionEngine class."""

    async def test_retention_engine_run_returns_retention_report(self) -> None:
        """Test that RetentionEngine.run() returns RetentionReport."""
        emitter = MemoryTraceEmitter()
        mock_router = Mock()
        mock_router.fetch = AsyncMock(return_value=[])
        
        rules = [RetentionRule(scope="global", data_type="task", ttl_seconds=3600)]
        engine = RetentionEngine(mock_router, rules, emitter=emitter)
        
        report = await engine.run()
        
        assert isinstance(report, RetentionReport)
        assert report.run_at is not None

    async def test_retention_engine_run_applies_all_rules(self) -> None:
        """Test that RetentionEngine.run() applies all rules."""
        emitter = MemoryTraceEmitter()
        mock_router = Mock()
        mock_router.fetch = AsyncMock(return_value=[])
        
        rules = [
            RetentionRule(scope="global", data_type="task", ttl_seconds=3600),
            RetentionRule(scope="worker:*", data_type="trace", ttl_seconds=7200),
        ]
        engine = RetentionEngine(mock_router, rules, emitter=emitter)
        
        report = await engine.run()
        
        assert report.rules_applied == 2

    async def test_retention_engine_run_archives_record_when_rule_archive_true(self) -> None:
        """Test that RetentionEngine.run() archives record when rule.archive=True."""
        emitter = MemoryTraceEmitter()
        mock_router = Mock()
        mock_router.fetch = AsyncMock(return_value=[
            {
                "id": str(uuid4()),
                "scope": "global",
                "data_type": "task",
                "created_at": datetime.now(timezone.utc) - timedelta(days=2),
            }
        ])
        mock_router.write = AsyncMock()
        
        rules = [RetentionRule(scope="global", data_type="task", ttl_seconds=3600, archive=True)]
        engine = RetentionEngine(mock_router, rules, emitter=emitter)
        
        report = await engine.run()
        
        assert report.records_archived == 1

    async def test_retention_engine_run_hard_deletes_without_archiving_when_rule_archive_false(self) -> None:
        """Test that RetentionEngine.run() hard deletes without archiving when rule.archive=False."""
        emitter = MemoryTraceEmitter()
        mock_router = Mock()
        mock_router.fetch = AsyncMock(return_value=[
            {
                "id": str(uuid4()),
                "scope": "global",
                "data_type": "task",
                "created_at": datetime.now(timezone.utc) - timedelta(days=2),
            }
        ])
        mock_router.write = AsyncMock()
        
        rules = [RetentionRule(scope="global", data_type="task", ttl_seconds=3600, archive=False)]
        engine = RetentionEngine(mock_router, rules, emitter=emitter)
        
        report = await engine.run()
        
        assert report.records_archived == 0
        assert report.records_deleted == 1

    async def test_retention_engine_run_emits_trace_event_on_start(self) -> None:
        """Test that RetentionEngine.run() emits trace event on start."""
        emitter = MemoryTraceEmitter()
        mock_router = Mock()
        mock_router.fetch = AsyncMock(return_value=[])
        
        rules = [RetentionRule(scope="global", data_type="task", ttl_seconds=3600)]
        engine = RetentionEngine(mock_router, rules, emitter=emitter)
        
        await engine.run()
        
        events = emitter.get_events()
        start_events = [e for e in events if e.event_type == "retention_run_started"]
        assert len(start_events) > 0

    async def test_retention_engine_run_emits_trace_event_on_completion_with_counts_in_data(self) -> None:
        """Test that RetentionEngine.run() emits trace event on completion with counts in data."""
        emitter = MemoryTraceEmitter()
        mock_router = Mock()
        mock_router.fetch = AsyncMock(return_value=[])
        
        rules = [RetentionRule(scope="global", data_type="task", ttl_seconds=3600)]
        engine = RetentionEngine(mock_router, rules, emitter=emitter)
        
        await engine.run()
        
        events = emitter.get_events()
        complete_events = [e for e in events if e.event_type == "retention_run_completed"]
        assert len(complete_events) > 0
        assert "rules_applied" in complete_events[0].data

    async def test_retention_engine_run_catches_per_record_errors_and_appends_to_report_errors(self) -> None:
        """Test that RetentionEngine.run() catches per-record errors and appends to report.errors."""
        emitter = MemoryTraceEmitter()
        mock_router = Mock()
        mock_router.fetch = AsyncMock(return_value=[
            {
                "id": str(uuid4()),
                "scope": "global",
                "data_type": "task",
                "created_at": datetime.now(timezone.utc) - timedelta(days=2),
            }
        ])
        mock_router.write = AsyncMock(side_effect=Exception("write error"))
        
        rules = [RetentionRule(scope="global", data_type="task", ttl_seconds=3600)]
        engine = RetentionEngine(mock_router, rules, emitter=emitter)
        
        report = await engine.run()
        
        assert len(report.errors) > 0

    async def test_retention_engine_run_never_aborts_entire_run_due_to_single_record_failure(self) -> None:
        """Test that RetentionEngine.run() never aborts entire run due to single record failure."""
        emitter = MemoryTraceEmitter()
        mock_router = Mock()
        mock_router.fetch = AsyncMock(return_value=[
            {
                "id": str(uuid4()),
                "scope": "global",
                "data_type": "task",
                "created_at": datetime.now(timezone.utc) - timedelta(days=2),
            },
            {
                "id": str(uuid4()),
                "scope": "global",
                "data_type": "task",
                "created_at": datetime.now(timezone.utc) - timedelta(days=2),
            }
        ])
        mock_router.write = AsyncMock(side_effect=Exception("write error"))
        
        rules = [RetentionRule(scope="global", data_type="task", ttl_seconds=3600)]
        engine = RetentionEngine(mock_router, rules, emitter=emitter)
        
        report = await engine.run()
        
        # Run should complete despite errors
        assert report.rules_applied == 1
        assert len(report.errors) == 2  # Both records failed

    async def test_retention_engine_scan_filters_records_older_than_ttl(self) -> None:
        """Test that RetentionEngine._scan() filters records older than TTL."""
        emitter = MemoryTraceEmitter()
        mock_router = Mock()
        mock_router.fetch = AsyncMock(return_value=[
            {
                "id": str(uuid4()),
                "scope": "global",
                "data_type": "task",
                "created_at": datetime.now(timezone.utc) - timedelta(days=2),
            },
            {
                "id": str(uuid4()),
                "scope": "global",
                "data_type": "task",
                "created_at": datetime.now(timezone.utc) - timedelta(minutes=30),
            }
        ])
        
        rules = [RetentionRule(scope="global", data_type="task", ttl_seconds=3600)]
        engine = RetentionEngine(mock_router, rules, emitter=emitter)
        
        expired = await engine._scan(rules[0])
        
        assert len(expired) == 1  # Only the 2-day-old record

    async def test_retention_engine_scan_returns_empty_list_when_no_records_exceed_ttl(self) -> None:
        """Test that RetentionEngine._scan() returns empty list when no records exceed TTL."""
        emitter = MemoryTraceEmitter()
        mock_router = Mock()
        mock_router.fetch = AsyncMock(return_value=[
            {
                "id": str(uuid4()),
                "scope": "global",
                "data_type": "task",
                "created_at": datetime.now(timezone.utc) - timedelta(minutes=30),
            }
        ])
        
        rules = [RetentionRule(scope="global", data_type="task", ttl_seconds=3600)]
        engine = RetentionEngine(mock_router, rules, emitter=emitter)
        
        expired = await engine._scan(rules[0])
        
        assert len(expired) == 0

    async def test_retention_engine_archive_writes_to_archive_key_with_correct_prefix(self) -> None:
        """Test that RetentionEngine._archive() writes to archive key with correct prefix."""
        emitter = MemoryTraceEmitter()
        mock_router = Mock()
        mock_router.write = AsyncMock()
        
        rules = [RetentionRule(scope="global", data_type="task", ttl_seconds=3600)]
        engine = RetentionEngine(mock_router, rules, emitter=emitter)
        
        record = {
            "id": str(uuid4()),
            "scope": "global",
            "data_type": "task",
            "created_at": datetime.now(timezone.utc),
        }
        
        await engine._archive(record)
        
        mock_router.write.assert_called_once()
        call_args = mock_router.write.call_args[0][0]
        assert call_args["key"].startswith("archive:global:task:")

    async def test_retention_engine_add_rule_appends_rule_and_emits_trace_event(self) -> None:
        """Test that RetentionEngine.add_rule() appends rule and emits trace event."""
        emitter = MemoryTraceEmitter()
        mock_router = Mock()
        
        rules = [RetentionRule(scope="global", data_type="task", ttl_seconds=3600)]
        engine = RetentionEngine(mock_router, rules, emitter=emitter)
        
        new_rule = RetentionRule(scope="worker:*", data_type="trace", ttl_seconds=7200)
        await engine.add_rule(new_rule)
        
        assert len(engine._rules) == 2
        
        events = emitter.get_events()
        rule_events = [e for e in events if e.event_type == "retention_rule_added"]
        assert len(rule_events) > 0

    async def test_retention_engine_get_rules_returns_copy_of_rules_list(self) -> None:
        """Test that RetentionEngine.get_rules() returns copy of rules list."""
        emitter = MemoryTraceEmitter()
        mock_router = Mock()
        
        rules = [RetentionRule(scope="global", data_type="task", ttl_seconds=3600)]
        engine = RetentionEngine(mock_router, rules, emitter=emitter)
        
        returned_rules = await engine.get_rules()
        
        assert returned_rules == rules
        assert returned_rules is not rules  # Should be a copy


@pytest.mark.asyncio
class TestRetentionDaemon:
    """Tests for RetentionDaemon class."""

    async def test_retention_daemon_run_once_calls_engine_run_and_returns_report(self) -> None:
        """Test that RetentionDaemon.run_once() calls engine.run() and returns report."""
        emitter = MemoryTraceEmitter()
        mock_engine = Mock()
        mock_engine.run = AsyncMock()
        
        mock_report = RetentionReport(
            run_at=datetime.now(timezone.utc),
            rules_applied=1,
            records_expired=0,
            records_archived=0,
            records_deleted=0,
        )
        mock_engine.run.return_value = mock_report
        
        daemon = RetentionDaemon(mock_engine, emitter=emitter)
        
        report = await daemon.run_once()
        
        mock_engine.run.assert_called_once()
        assert report == mock_report

    async def test_retention_daemon_start_sets_running_true_and_launches_loop_task(self) -> None:
        """Test that RetentionDaemon.start() sets running=True and launches loop task."""
        emitter = MemoryTraceEmitter()
        mock_engine = Mock()
        mock_engine.run = AsyncMock()
        
        daemon = RetentionDaemon(mock_engine, emitter=emitter)
        
        await daemon.start()
        
        assert daemon._running is True
        assert daemon._task is not None

    async def test_retention_daemon_stop_sets_running_false_and_cancels_task(self) -> None:
        """Test that RetentionDaemon.stop() sets running=False and cancels task."""
        emitter = MemoryTraceEmitter()
        mock_engine = Mock()
        mock_engine.run = AsyncMock()
        
        daemon = RetentionDaemon(mock_engine, emitter=emitter)
        
        await daemon.start()
        await daemon.stop()
        
        assert daemon._running is False
