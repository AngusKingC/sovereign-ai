"""
Tests for Code Execution Skill.
"""

import pytest
from unittest.mock import AsyncMock
from uuid import uuid4

from skills.code_execution.skill import CodeExecutionSkill
from core.observability import (
    TraceEventType,
    TraceLevel,
    TraceComponent,
    MemoryTraceEmitter,
)
from core.approval_gate import ApprovalGate, ApprovalResponse


class TestCodeExecutionSkill:
    """Test suite for CodeExecutionSkill."""

    @pytest.fixture
    def emitter(self):
        """Create a memory trace emitter for testing."""
        return MemoryTraceEmitter()

    @pytest.fixture
    def mock_approval_gate(self):
        """Create a mock approval gate."""
        gate = AsyncMock(spec=ApprovalGate)
        gate.request_approval = AsyncMock(return_value=ApprovalResponse(
            request_id=str(uuid4()),
            task_id=str(uuid4()),
            approved=True,
            approved_by="test_user",
        ))
        return gate

    @pytest.fixture
    def skill(self, emitter):
        """Create a CodeExecutionSkill instance for testing."""
        return CodeExecutionSkill(emitter=emitter)

    @pytest.mark.asyncio
    async def test_successful_code_execution_captures_stdout(self, skill):
        """Test that successful code execution captures stdout."""
        result = await skill.execute("print('hello world')")

        assert result["success"] is True
        assert "hello world" in result["stdout"]
        assert result["return_code"] == 0
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_syntax_error_captured_in_stderr_with_non_zero_return_code(self, skill):
        """Test that syntax error is captured in stderr with non-zero return code."""
        result = await skill.execute("print('missing quote")

        assert result["success"] is False
        assert result["return_code"] != 0
        assert len(result["stderr"]) > 0
        assert result["error"] is not None

    @pytest.mark.asyncio
    async def test_approval_gate_called_before_execution(self, mock_approval_gate, emitter):
        """Test that approval gate is called before execution."""
        skill = CodeExecutionSkill(approval_gate=mock_approval_gate, emitter=emitter)
        await skill.execute("print('test')")

        mock_approval_gate.request_approval.assert_called_once()
        call_args = mock_approval_gate.request_approval.call_args
        assert call_args is not None

    @pytest.mark.asyncio
    async def test_approval_denied_returns_success_false_without_executing(self, mock_approval_gate, emitter):
        """Test that approval denied returns success=False without executing."""
        mock_approval_gate.request_approval = AsyncMock(return_value=ApprovalResponse(
            request_id=str(uuid4()),
            task_id=str(uuid4()),
            approved=False,
            decision_reason="Test denial",
            approved_by="test_user",
        ))
        skill = CodeExecutionSkill(approval_gate=mock_approval_gate, emitter=emitter)
        result = await skill.execute("print('test')")

        assert result["success"] is False
        assert result["error"] == "Approval denied"
        assert result["stdout"] == ""
        assert result["stderr"] == ""

    @pytest.mark.asyncio
    async def test_timeout_returns_success_false_with_timeout_error(self, emitter):
        """Test that timeout returns success=False with timeout error."""
        skill = CodeExecutionSkill(emitter=emitter, timeout=1)
        result = await skill.execute("import time; time.sleep(10)")

        assert result["success"] is False
        assert result["error"] == "Execution timed out"
        assert result["return_code"] == -1

    @pytest.mark.asyncio
    async def test_multiline_code_executes_correctly(self, skill):
        """Test that multiline code executes correctly."""
        code = "x = 5; y = 10; print(x + y)"
        result = await skill.execute(code)

        assert result["success"] is True
        assert "15" in result["stdout"]

    @pytest.mark.asyncio
    async def test_trace_events_emitted_on_execution_start_and_complete(self, skill, emitter):
        """Test that trace events are emitted on execution start and complete."""
        await skill.execute("print('test')")

        events = emitter.get_events()
        assert len(events) >= 2

        start_events = [e for e in events if e.event_type == TraceEventType.COMPONENT_START]
        assert len(start_events) >= 1
        assert start_events[0].component == TraceComponent.WORKER
        assert "Code execution started" in start_events[0].message

        complete_events = [e for e in events if e.event_type == TraceEventType.OPERATION_COMPLETE]
        assert len(complete_events) >= 1
        assert complete_events[0].component == TraceComponent.WORKER
        assert "Code execution completed" in complete_events[0].message

    @pytest.mark.asyncio
    async def test_trace_events_emitted_on_error(self, emitter):
        """Test that trace events are emitted on error."""
        skill = CodeExecutionSkill(emitter=emitter, timeout=1)
        await skill.execute("import time; time.sleep(10)")

        events = emitter.get_events()
        error_events = [e for e in events if e.event_type == TraceEventType.OPERATION_ERROR]
        assert len(error_events) >= 1
        assert error_events[0].component == TraceComponent.WORKER
        assert "Code execution timed out" in error_events[0].message
        assert error_events[0].level == TraceLevel.ERROR

    @pytest.mark.asyncio
    async def test_empty_code_raises_value_error(self, skill):
        """Test that empty code raises ValueError."""
        with pytest.raises(ValueError, match="Code must be a non-empty string"):
            await skill.execute("")

    @pytest.mark.asyncio
    async def test_non_string_code_raises_value_error(self, skill):
        """Test that non-string code raises ValueError."""
        with pytest.raises(ValueError, match="Code must be a non-empty string"):
            await skill.execute(123)

    @pytest.mark.asyncio
    async def test_trace_event_fields_are_correct(self, skill, emitter):
        """Test that TraceEvent fields are correct (event_type, component, level, message, data, duration_ms)."""
        await skill.execute("print('test')")

        events = emitter.get_events()
        for event in events:
            assert hasattr(event, "event_type")
            assert hasattr(event, "component")
            assert hasattr(event, "level")
            assert hasattr(event, "message")
            assert hasattr(event, "data")
            assert hasattr(event, "duration_ms")
            # Should NOT have these fields from the incorrect schema
            assert not hasattr(event, "layer")
            assert not hasattr(event, "payload")
            assert not hasattr(event, "success")
