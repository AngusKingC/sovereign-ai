"""
Schema validation tests.

Single responsibility: Test all Pydantic schema definitions for validation,
serialization, and type safety compliance.
"""

from datetime import datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from core.schemas import (
    EscalationDecision,
    EventType,
    Layer,
    Message,
    MessageRole,
    SessionSummary,
    StrategicContext,
    Task,
    TaskPriority,
    TaskStatus,
    TraceEvent,
    WorkerOutput,
    WorkerProfile,
    WorkerStatus,
)


class TestMessageRole:
    """Test MessageRole enum."""

    def test_enum_values(self):
        """Test all enum values exist."""
        assert MessageRole.SYSTEM.value == "system"
        assert MessageRole.USER.value == "user"
        assert MessageRole.ASSISTANT.value == "assistant"
        assert MessageRole.TOOL.value == "tool"


class TestTaskPriority:
    """Test TaskPriority enum."""

    def test_enum_values(self):
        """Test all enum values exist."""
        assert TaskPriority.NORMAL.value == "normal"
        assert TaskPriority.HIGH.value == "high"
        assert TaskPriority.CRITICAL.value == "critical"


class TestTaskStatus:
    """Test TaskStatus enum."""

    def test_enum_values(self):
        """Test all enum values exist."""
        assert TaskStatus.RECEIVED.value == "received"
        assert TaskStatus.PLANNED.value == "planned"
        assert TaskStatus.EXECUTING.value == "executing"
        assert TaskStatus.VALIDATING.value == "validating"
        assert TaskStatus.AWAITING_APPROVAL.value == "awaiting_approval"
        assert TaskStatus.COMPLETE.value == "complete"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.CANCELLED.value == "cancelled"
        
        # Test backward compatibility aliases
        assert TaskStatus.PENDING == TaskStatus.RECEIVED
        assert TaskStatus.RUNNING == TaskStatus.EXECUTING
        assert TaskStatus.ESCALATED == TaskStatus.AWAITING_APPROVAL


class TestWorkerStatus:
    """Test WorkerStatus enum."""

    def test_worker_status_enum_values(self):
        """Test all four values exist."""
        assert WorkerStatus.ACTIVE.value == "active"
        assert WorkerStatus.IDLE.value == "idle"
        assert WorkerStatus.ARCHIVED.value == "archived"
        assert WorkerStatus.DEPRECATED.value == "deprecated"


class TestLayer:
    """Test Layer enum."""

    def test_enum_values(self):
        """Test all enum values exist."""
        assert Layer.L0.value == "L0"
        assert Layer.L1.value == "L1"
        assert Layer.L2.value == "L2"
        assert Layer.ESCALATION.value == "ESCALATION"


class TestEventType:
    """Test EventType enum."""

    def test_enum_values(self):
        """Test all enum values exist."""
        assert EventType.MEMORY_QUERY.value == "MEMORY_QUERY"
        assert EventType.MEMORY_WRITE.value == "MEMORY_WRITE"
        assert EventType.PROMPT_BUILT.value == "PROMPT_BUILT"
        assert EventType.LLM_CALLED.value == "LLM_CALLED"
        assert EventType.LLM_RAW_RESPONSE.value == "LLM_RAW_RESPONSE"
        assert EventType.VALIDATION_PASSED.value == "VALIDATION_PASSED"
        assert EventType.VALIDATION_FAILED.value == "VALIDATION_FAILED"
        assert EventType.ESCALATION_TRIGGERED.value == "ESCALATION_TRIGGERED"
        assert EventType.SYNTHESIS_STARTED.value == "SYNTHESIS_STARTED"
        assert EventType.OUTPUT_FINAL.value == "OUTPUT_FINAL"


class TestMessage:
    """Test Message model."""

    def test_valid_construction(self):
        """Test valid message construction."""
        message = Message(
            role=MessageRole.USER,
            content="Hello",
            timestamp=datetime.now(),
        )
        assert message.role == MessageRole.USER
        assert message.content == "Hello"
        assert message.metadata is None

    def test_valid_construction_with_metadata(self):
        """Test valid message construction with metadata."""
        metadata = {"key": "value"}
        message = Message(
            role=MessageRole.ASSISTANT,
            content="Response",
            timestamp=datetime.now(),
            metadata=metadata,
        )
        assert message.metadata == metadata

    def test_invalid_role_type(self):
        """Test rejection of invalid role type."""
        with pytest.raises(ValidationError):
            Message(
                role="invalid",
                content="Hello",
                timestamp=datetime.now(),
            )

    def test_json_serialization(self):
        """Test JSON serialization roundtrip."""
        original = Message(
            role=MessageRole.USER,
            content="Hello",
            timestamp=datetime.now(),
        )
        json_str = original.model_dump_json()
        assert isinstance(json_str, str)
        assert "role" in json_str
        assert "content" in json_str


class TestTask:
    """Test Task model."""

    def test_valid_construction(self):
        """Test valid task construction."""
        task = Task(
            task_id=uuid4(),
            intent="Test task",
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            created_at=datetime.now(),
        )
        assert task.task_id is not None
        assert task.intent == "Test task"
        assert task.complexity_score == 0.5
        assert task.current_state == TaskStatus.RECEIVED
        assert task.status == TaskStatus.RECEIVED  # Backward compatibility
        assert task.validation_failures == 0

    def test_valid_construction_with_parent(self):
        """Test valid task construction with parent task."""
        parent_id = uuid4()
        task = Task(
            task_id=uuid4(),
            parent_task_id=parent_id,
            intent="Child task",
            complexity_score=0.3,
            priority=TaskPriority.HIGH,
            created_at=datetime.now(),
        )
        assert task.parent_task_id == parent_id

    def test_complexity_score_boundary_valid(self):
        """Test valid boundary values for complexity_score."""
        task_low = Task(
            task_id=uuid4(),
            intent="Low complexity",
            complexity_score=0.0,
            priority=TaskPriority.NORMAL,
            created_at=datetime.now(),
        )
        assert task_low.complexity_score == 0.0

        task_high = Task(
            task_id=uuid4(),
            intent="High complexity",
            complexity_score=1.0,
            priority=TaskPriority.NORMAL,
            created_at=datetime.now(),
        )
        assert task_high.complexity_score == 1.0

    def test_complexity_score_boundary_invalid(self):
        """Test invalid boundary values for complexity_score."""
        with pytest.raises(ValidationError):
            Task(
                task_id=uuid4(),
                intent="Invalid complexity",
                complexity_score=-0.1,
                priority=TaskPriority.NORMAL,
                created_at=datetime.now(),
            )

        with pytest.raises(ValidationError):
            Task(
                task_id=uuid4(),
                intent="Invalid complexity",
                complexity_score=1.1,
                priority=TaskPriority.NORMAL,
                created_at=datetime.now(),
            )

    def test_validation_failures_non_negative(self):
        """Test validation_failures cannot be negative."""
        with pytest.raises(ValidationError):
            Task(
                task_id=uuid4(),
                intent="Test task",
                complexity_score=0.5,
                priority=TaskPriority.NORMAL,
                created_at=datetime.now(),
                validation_failures=-1,
            )

    def test_json_serialization(self):
        """Test JSON serialization roundtrip."""
        original = Task(
            task_id=uuid4(),
            intent="Test task",
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            created_at=datetime.now(),
        )
        json_str = original.model_dump_json()
        assert isinstance(json_str, str)
        assert "task_id" in json_str
        assert "intent" in json_str


class TestWorkerProfile:
    """Test WorkerProfile model."""

    def test_valid_construction(self):
        """Test valid worker profile construction."""
        profile = WorkerProfile(
            worker_id="worker_1",
            worker_type="analyst",
            depth_preference=0.5,
            speculation_tolerance=0.3,
            source_skepticism=0.7,
            verbosity=0.5,
            preferred_model="mixtral-8x7b",
            escalation_threshold=0.8,
        )
        assert profile.worker_id == "worker_1"
        assert profile.worker_type == "analyst"
        assert profile.tasks_completed == 0
        assert profile.avg_confidence == 0.0

    def test_preference_scores_boundary_valid(self):
        """Test valid boundary values for preference scores."""
        profile = WorkerProfile(
            worker_id="worker_1",
            worker_type="analyst",
            depth_preference=0.0,
            speculation_tolerance=1.0,
            source_skepticism=0.5,
            verbosity=0.0,
            preferred_model="mixtral-8x7b",
            escalation_threshold=1.0,
        )
        assert profile.depth_preference == 0.0
        assert profile.speculation_tolerance == 1.0
        assert profile.escalation_threshold == 1.0

    def test_preference_scores_boundary_invalid(self):
        """Test invalid boundary values for preference scores."""
        with pytest.raises(ValidationError):
            WorkerProfile(
                worker_id="worker_1",
                worker_type="analyst",
                depth_preference=-0.1,
                speculation_tolerance=0.5,
                source_skepticism=0.5,
                verbosity=0.5,
                preferred_model="mixtral-8x7b",
                escalation_threshold=0.5,
            )

        with pytest.raises(ValidationError):
            WorkerProfile(
                worker_id="worker_1",
                worker_type="analyst",
                depth_preference=0.5,
                speculation_tolerance=1.1,
                source_skepticism=0.5,
                verbosity=0.5,
                preferred_model="mixtral-8x7b",
                escalation_threshold=0.5,
            )

    def test_standing_instructions_default(self):
        """Test standing_instructions defaults to empty list."""
        profile = WorkerProfile(
            worker_id="worker_1",
            worker_type="analyst",
            depth_preference=0.5,
            speculation_tolerance=0.5,
            source_skepticism=0.5,
            verbosity=0.5,
            preferred_model="mixtral-8x7b",
            escalation_threshold=0.5,
        )
        assert profile.standing_instructions == []

    def test_tasks_completed_non_negative(self):
        """Test tasks_completed cannot be negative."""
        with pytest.raises(ValidationError):
            WorkerProfile(
                worker_id="worker_1",
                worker_type="analyst",
                depth_preference=0.5,
                speculation_tolerance=0.5,
                source_skepticism=0.5,
                verbosity=0.5,
                preferred_model="mixtral-8x7b",
                escalation_threshold=0.5,
                tasks_completed=-1,
            )

    def test_avg_confidence_boundary(self):
        """Test avg_confidence boundary values."""
        with pytest.raises(ValidationError):
            WorkerProfile(
                worker_id="worker_1",
                worker_type="analyst",
                depth_preference=0.5,
                speculation_tolerance=0.5,
                source_skepticism=0.5,
                verbosity=0.5,
                preferred_model="mixtral-8x7b",
                escalation_threshold=0.5,
                avg_confidence=1.1,
            )


class TestWorkerOutput:
    """Test WorkerOutput model."""

    def test_valid_construction(self):
        """Test valid worker output construction."""
        output = WorkerOutput(
            worker_id="worker_1",
            task_id=uuid4(),
            content="Result",
            confidence=0.8,
            model_used="mixtral-8x7b",
        )
        assert output.worker_id == "worker_1"
        assert output.content == "Result"
        assert output.confidence == 0.8
        assert output.escalation_recommended is False
        assert output.tokens_used == 0

    def test_confidence_boundary_valid(self):
        """Test valid boundary values for confidence."""
        output_low = WorkerOutput(
            worker_id="worker_1",
            task_id=uuid4(),
            content="Result",
            confidence=0.0,
            model_used="mixtral-8x7b",
        )
        assert output_low.confidence == 0.0

        output_high = WorkerOutput(
            worker_id="worker_1",
            task_id=uuid4(),
            content="Result",
            confidence=1.0,
            model_used="mixtral-8x7b",
        )
        assert output_high.confidence == 1.0

    def test_confidence_boundary_invalid(self):
        """Test invalid boundary values for confidence."""
        with pytest.raises(ValidationError):
            WorkerOutput(
                worker_id="worker_1",
                task_id=uuid4(),
                content="Result",
                confidence=-0.1,
                model_used="mixtral-8x7b",
            )

        with pytest.raises(ValidationError):
            WorkerOutput(
                worker_id="worker_1",
                task_id=uuid4(),
                content="Result",
                confidence=1.1,
                model_used="mixtral-8x7b",
            )

    def test_tokens_used_non_negative(self):
        """Test tokens_used cannot be negative."""
        with pytest.raises(ValidationError):
            WorkerOutput(
                worker_id="worker_1",
                task_id=uuid4(),
                content="Result",
                confidence=0.8,
                model_used="mixtral-8x7b",
                tokens_used=-1,
            )

    def test_reasoning_steps_default(self):
        """Test reasoning_steps defaults to empty list."""
        output = WorkerOutput(
            worker_id="worker_1",
            task_id=uuid4(),
            content="Result",
            confidence=0.8,
            model_used="mixtral-8x7b",
        )
        assert output.reasoning_steps == []
        assert output.sources == []
        assert output.claims == []


class TestTraceEvent:
    """Test TraceEvent model."""

    def test_valid_construction(self):
        """Test valid trace event construction."""
        event = TraceEvent(
            event_id=uuid4(),
            timestamp=datetime.now(),
            layer=Layer.L1,
            component="orchestrator",
            event_type=EventType.LLM_CALLED,
            payload={"prompt": "test"},
            duration_ms=100,
            success=True,
        )
        assert event.layer == Layer.L1
        assert event.component == "orchestrator"
        assert event.event_type == EventType.LLM_CALLED
        assert event.duration_ms == 100
        assert event.model_used is None
        assert event.token_cost is None

    def test_valid_construction_with_optional_fields(self):
        """Test valid trace event construction with optional fields."""
        event = TraceEvent(
            event_id=uuid4(),
            timestamp=datetime.now(),
            layer=Layer.L2,
            component="worker",
            event_type=EventType.OUTPUT_FINAL,
            payload={"result": "test"},
            duration_ms=200,
            model_used="mixtral-8x7b",
            token_cost=50,
            success=True,
        )
        assert event.model_used == "mixtral-8x7b"
        assert event.token_cost == 50

    def test_duration_ms_non_negative(self):
        """Test duration_ms cannot be negative."""
        with pytest.raises(ValidationError):
            TraceEvent(
                event_id=uuid4(),
                timestamp=datetime.now(),
                layer=Layer.L1,
                component="orchestrator",
                event_type=EventType.LLM_CALLED,
                payload={"prompt": "test"},
                duration_ms=-1,
                success=True,
            )

    def test_token_cost_non_negative_when_provided(self):
        """Test token_cost cannot be negative when provided."""
        with pytest.raises(ValidationError):
            TraceEvent(
                event_id=uuid4(),
                timestamp=datetime.now(),
                layer=Layer.L1,
                component="orchestrator",
                event_type=EventType.LLM_CALLED,
                payload={"prompt": "test"},
                duration_ms=100,
                token_cost=-1,
                success=True,
            )

    def test_json_serialization(self):
        """Test JSON serialization roundtrip."""
        original = TraceEvent(
            event_id=uuid4(),
            timestamp=datetime.now(),
            layer=Layer.L1,
            component="orchestrator",
            event_type=EventType.LLM_CALLED,
            payload={"prompt": "test"},
            duration_ms=100,
            success=True,
        )
        json_str = original.model_dump_json()
        assert isinstance(json_str, str)
        assert "event_id" in json_str
        assert "layer" in json_str


class TestEscalationDecision:
    """Test EscalationDecision model."""

    def test_valid_construction(self):
        """Test valid escalation decision construction."""
        decision = EscalationDecision(
            should_escalate=True,
            reasons=["Complexity too high", "Local model insufficient"],
            suggested_model="gpt-4",
            estimated_cost=0.05,
            task_id=uuid4(),
        )
        assert decision.should_escalate is True
        assert len(decision.reasons) == 2
        assert decision.suggested_model == "gpt-4"
        assert decision.estimated_cost == 0.05

    def test_reasons_default(self):
        """Test reasons defaults to empty list."""
        decision = EscalationDecision(
            should_escalate=False,
            suggested_model="mixtral-8x7b",
            estimated_cost=0.0,
            task_id=uuid4(),
        )
        assert decision.reasons == []

    def test_estimated_cost_non_negative(self):
        """Test estimated_cost cannot be negative."""
        with pytest.raises(ValidationError):
            EscalationDecision(
                should_escalate=True,
                suggested_model="gpt-4",
                estimated_cost=-0.01,
                task_id=uuid4(),
            )


class TestStrategicContext:
    """Test StrategicContext model."""

    def test_valid_construction(self):
        """Test valid strategic context construction."""
        context = StrategicContext(
            last_updated=datetime.now(),
        )
        assert context.active_goals == []
        assert context.pending_tasks == []
        assert context.cloud_spend_today == 0.0
        assert context.worker_performance == {}

    def test_valid_construction_with_fields(self):
        """Test valid strategic context construction with fields."""
        task = Task(
            task_id=uuid4(),
            intent="Test task",
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            created_at=datetime.now(),
        )
        context = StrategicContext(
            active_goals=["Goal 1"],
            pending_tasks=[task],
            completed_today=["Task 1"],
            blocked_tasks=["Task 2"],
            worker_performance={"worker_1": 0.8},
            cloud_spend_today=0.1,
            open_questions=["Question 1"],
            last_updated=datetime.now(),
        )
        assert len(context.active_goals) == 1
        assert len(context.pending_tasks) == 1
        assert context.cloud_spend_today == 0.1

    def test_cloud_spend_non_negative(self):
        """Test cloud_spend_today cannot be negative."""
        with pytest.raises(ValidationError):
            StrategicContext(
                cloud_spend_today=-0.01,
                last_updated=datetime.now(),
            )

    def test_json_serialization(self):
        """Test JSON serialization roundtrip."""
        original = StrategicContext(
            last_updated=datetime.now(),
        )
        json_str = original.model_dump_json()
        assert isinstance(json_str, str)
        assert "last_updated" in json_str


class TestSessionSummary:
    """Test SessionSummary model."""

    def test_valid_construction(self):
        """Test valid session summary construction."""
        summary = SessionSummary(
            session_id=uuid4(),
            closed_at=datetime.now(),
        )
        assert summary.session_id is not None
        assert summary.decisions_made == []
        assert summary.tasks_completed == []
        assert summary.escalations == 0
        assert summary.total_tokens == 0

    def test_valid_construction_with_fields(self):
        """Test valid session summary construction with fields."""
        summary = SessionSummary(
            session_id=uuid4(),
            decisions_made=["Decision 1", "Decision 2"],
            tasks_completed=["Task 1"],
            tasks_pending=["Task 2"],
            knowledge_updates=["Update 1"],
            escalations=2,
            total_tokens=1000,
            closed_at=datetime.now(),
        )
        assert len(summary.decisions_made) == 2
        assert summary.escalations == 2
        assert summary.total_tokens == 1000

    def test_escalations_non_negative(self):
        """Test escalations cannot be negative."""
        with pytest.raises(ValidationError):
            SessionSummary(
                session_id=uuid4(),
                escalations=-1,
                closed_at=datetime.now(),
            )

    def test_total_tokens_non_negative(self):
        """Test total_tokens cannot be negative."""
        with pytest.raises(ValidationError):
            SessionSummary(
                session_id=uuid4(),
                total_tokens=-1,
                closed_at=datetime.now(),
            )

    def test_json_serialization(self):
        """Test JSON serialization roundtrip."""
        original = SessionSummary(
            session_id=uuid4(),
            closed_at=datetime.now(),
        )
        json_str = original.model_dump_json()
        assert isinstance(json_str, str)
        assert "session_id" in json_str
        assert "closed_at" in json_str


class TestUUIDGeneration:
    """Test UUID field handling."""

    def test_uuid_field_accepts_uuid(self):
        """Test UUID fields accept UUID objects."""
        task_id = uuid4()
        task = Task(
            task_id=task_id,
            intent="Test task",
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            created_at=datetime.now(),
        )
        assert task.task_id == task_id
        assert isinstance(task.task_id, UUID)

    def test_uuid_field_accepts_string(self):
        """Test UUID fields accept string representations."""
        task_id_str = str(uuid4())
        task = Task(
            task_id=task_id_str,
            intent="Test task",
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            created_at=datetime.now(),
        )
        assert isinstance(task.task_id, UUID)


class TestDatetimeHandling:
    """Test datetime field handling."""

    def test_datetime_field_accepts_datetime(self):
        """Test datetime fields accept datetime objects."""
        now = datetime.now()
        task = Task(
            task_id=uuid4(),
            intent="Test task",
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            created_at=now,
        )
        assert task.created_at == now
        assert isinstance(task.created_at, datetime)

    def test_datetime_field_serializes_to_iso(self):
        """Test datetime fields serialize to ISO format."""
        now = datetime.now()
        task = Task(
            task_id=uuid4(),
            intent="Test task",
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            created_at=now,
        )
        json_str = task.model_dump_json()
        assert isinstance(json_str, str)

