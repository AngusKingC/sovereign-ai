"""
Tests for Code Execution Skill.
"""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from core.approval_gate import ApprovalGate, ApprovalResponse
from core.observability import (
    MemoryTraceEmitter,
    TraceComponent,
    TraceEventType,
    TraceLevel,
)
from skills.code_execution.skill import CodeExecutionSkill


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
        gate.request_approval = AsyncMock(
            return_value=ApprovalResponse(
                request_id=str(uuid4()),
                task_id=str(uuid4()),
                approved=True,
                approved_by="test_user",
            )
        )
        return gate

    @pytest.fixture
    def mock_sandbox_executor(self):
        """Create a mock SandboxExecutor for testing."""
        from core.sandbox import SandboxResult

        sandbox = AsyncMock()
        sandbox.execute_python = AsyncMock(
            return_value=SandboxResult(
                success=True,
                stdout="hello world\n",
                stderr="",
                return_code=0,
                error=None,
                sandboxed=True,
            )
        )
        return sandbox

    @pytest.fixture
    def skill(self, emitter, mock_sandbox_executor):
        """Create a CodeExecutionSkill instance for testing."""
        return CodeExecutionSkill(
            emitter=emitter, sandbox_executor=mock_sandbox_executor
        )

    @pytest.mark.asyncio
    async def test_successful_code_execution_captures_stdout(self, skill):
        """Test that successful code execution captures stdout."""
        result = await skill.execute("print('hello world')")

        assert result["success"] is True
        assert "hello world" in result["stdout"]
        assert result["return_code"] == 0
        assert result["error"] is None
        assert result["sandboxed"] is True

    @pytest.mark.asyncio
    async def test_syntax_error_captured_in_stderr_with_non_zero_return_code(
        self, mock_sandbox_executor
    ):
        """Test that syntax error is captured in stderr with non-zero return code."""
        from core.sandbox import SandboxResult

        mock_sandbox_executor.execute_python = AsyncMock(
            return_value=SandboxResult(
                success=False,
                stdout="",
                stderr="SyntaxError: EOL while scanning string literal",
                return_code=1,
                error="SyntaxError: EOL while scanning string literal",
                sandboxed=True,
            )
        )
        skill = CodeExecutionSkill(sandbox_executor=mock_sandbox_executor)
        result = await skill.execute("print('missing quote")

        assert result["success"] is False
        assert result["return_code"] != 0
        assert len(result["stderr"]) > 0
        assert result["error"] is not None

    @pytest.mark.asyncio
    async def test_approval_gate_called_before_execution(
        self, mock_approval_gate, emitter, mock_sandbox_executor
    ):
        """Test that approval gate is called before execution."""
        skill = CodeExecutionSkill(
            approval_gate=mock_approval_gate,
            emitter=emitter,
            sandbox_executor=mock_sandbox_executor,
        )
        await skill.execute("print('test')")

        mock_approval_gate.request_approval.assert_called_once()
        call_args = mock_approval_gate.request_approval.call_args
        assert call_args is not None

    @pytest.mark.asyncio
    async def test_approval_denied_returns_success_false_without_executing(
        self, mock_approval_gate, emitter, mock_sandbox_executor
    ):
        """Test that approval denied returns success=False without executing."""
        mock_approval_gate.request_approval = AsyncMock(
            return_value=ApprovalResponse(
                request_id=str(uuid4()),
                task_id=str(uuid4()),
                approved=False,
                decision_reason="Test denial",
                approved_by="test_user",
            )
        )
        skill = CodeExecutionSkill(
            approval_gate=mock_approval_gate,
            emitter=emitter,
            sandbox_executor=mock_sandbox_executor,
        )
        result = await skill.execute("print('test')")

        assert result["success"] is False
        assert result["error"] == "Approval denied"
        assert result["stdout"] == ""
        assert result["stderr"] == ""

    @pytest.mark.asyncio
    async def test_timeout_returns_success_false_with_timeout_error(
        self, mock_sandbox_executor
    ):
        """Test that timeout returns success=False with timeout error."""
        from core.sandbox import SandboxResult

        mock_sandbox_executor.execute_python = AsyncMock(
            return_value=SandboxResult(
                success=False,
                stdout="",
                stderr="Execution timed out after 30s",
                return_code=124,
                error="timeout",
                sandboxed=True,
            )
        )
        skill = CodeExecutionSkill(sandbox_executor=mock_sandbox_executor, timeout=1)
        result = await skill.execute("import time; time.sleep(10)")

        assert result["success"] is False
        assert result["error"] == "timeout"
        assert result["return_code"] == 124

    @pytest.mark.asyncio
    async def test_multiline_code_executes_correctly(self, mock_sandbox_executor):
        """Test that multiline code executes correctly."""
        from core.sandbox import SandboxResult

        mock_sandbox_executor.execute_python = AsyncMock(
            return_value=SandboxResult(
                success=True,
                stdout="15\n",
                stderr="",
                return_code=0,
                error=None,
                sandboxed=True,
            )
        )
        skill = CodeExecutionSkill(sandbox_executor=mock_sandbox_executor)
        code = "x = 5; y = 10; print(x + y)"
        result = await skill.execute(code)

        assert result["success"] is True
        assert "15" in result["stdout"]

    @pytest.mark.asyncio
    async def test_trace_events_emitted_on_execution_start_and_complete(
        self, skill, emitter
    ):
        """Test that trace events are emitted on execution start and complete."""
        await skill.execute("print('test')")

        events = emitter.get_events()
        assert len(events) >= 2

        start_events = [
            e for e in events if e.event_type == TraceEventType.COMPONENT_START
        ]
        assert len(start_events) >= 1
        assert start_events[0].component == TraceComponent.WORKER
        assert "Code execution started" in start_events[0].message

        complete_events = [
            e for e in events if e.event_type == TraceEventType.OPERATION_COMPLETE
        ]
        assert len(complete_events) >= 1
        assert complete_events[0].component == TraceComponent.WORKER
        assert "Code execution completed" in complete_events[0].message

    @pytest.mark.asyncio
    async def test_trace_events_emitted_on_error(self, emitter, mock_sandbox_executor):
        """Test that trace events are emitted on error."""
        from core.sandbox import SandboxResult

        mock_sandbox_executor.execute_python = AsyncMock(
            return_value=SandboxResult(
                success=False,
                stdout="",
                stderr="Execution timed out after 30s",
                return_code=124,
                error="timeout",
                sandboxed=True,
            )
        )
        skill = CodeExecutionSkill(
            emitter=emitter, sandbox_executor=mock_sandbox_executor, timeout=1
        )
        await skill.execute("import time; time.sleep(10)")

        events = emitter.get_events()
        error_events = [
            e for e in events if e.event_type == TraceEventType.OPERATION_ERROR
        ]
        assert len(error_events) >= 1
        assert error_events[0].component == TraceComponent.WORKER
        assert (
            "Code execution completed" in error_events[0].message
            or "Code execution failed" in error_events[0].message
        )
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

    @pytest.mark.asyncio
    async def test_sandbox_executor_used_for_execution(self, mock_sandbox_executor):
        """Test that sandbox executor is used for code execution."""
        skill = CodeExecutionSkill(sandbox_executor=mock_sandbox_executor)
        await skill.execute("print('test')")

        mock_sandbox_executor.execute_python.assert_called_once_with("print('test')")

    @pytest.mark.asyncio
    async def test_sandboxed_flag_in_result(self, mock_sandbox_executor):
        """Test that sandboxed flag is present in result."""
        from core.sandbox import SandboxResult

        mock_sandbox_executor.execute_python = AsyncMock(
            return_value=SandboxResult(
                success=True,
                stdout="test\n",
                stderr="",
                return_code=0,
                error=None,
                sandboxed=True,
            )
        )
        skill = CodeExecutionSkill(sandbox_executor=mock_sandbox_executor)
        result = await skill.execute("print('test')")

        assert "sandboxed" in result
        assert result["sandboxed"] is True
