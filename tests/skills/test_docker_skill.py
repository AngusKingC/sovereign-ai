"""Docker skill tests."""

import pytest
import asyncio
import gc
from unittest.mock import Mock, AsyncMock, patch

from skills.docker.skill import DockerSkill
from core.approval_gate import ApprovalGate
from core.observability import MemoryTraceEmitter, TraceEventType, TraceComponent


@pytest.fixture(autouse=True)
def cleanup_subprocess_transports():
    """Force-close any lingering subprocess transports after each test.
    
    Workaround for pytest-asyncio/Windows interaction where event loop closes
    before subprocess transports (asyncio.create_subprocess_exec) are cleaned up.
    Per Plan 38.5 Step 4 — not a code bug, a test-fixture cleanup gap.
    """
    yield
    # Force garbage collection to trigger transport cleanup
    gc.collect()
    # Close any remaining event loops
    try:
        loop = asyncio.get_event_loop()
        if not loop.is_closed():
            # Run pending tasks to allow transports to close
            loop.run_until_complete(asyncio.sleep(0.1))
    except RuntimeError:
        # Event loop already closed — nothing to do
        pass


class TestDockerSkill:
    """Test DockerSkill functionality."""

    @pytest.fixture
    def docker_skill(self):
        """Create a docker skill for testing."""
        return DockerSkill(
            emitter=MemoryTraceEmitter(),
            approval_gate=None,
            timeout=30,
        )

    @pytest.mark.asyncio
    async def test_list_containers_returns_parsed_list(self, docker_skill):
        """Test list_containers() returns parsed list."""
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b'[{"id": "abc123", "name": "test", "status": "running", "image": "nginx"}]\n', b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await docker_skill.list_containers()

        assert len(result) == 1
        assert result[0]["id"] == "abc123"
        assert result[0]["name"] == "test"
        assert result[0]["status"] == "running"
        assert result[0]["image"] == "nginx"

    @pytest.mark.asyncio
    async def test_list_containers_all_true_passes_all_flag(self, docker_skill):
        """Test list_containers(all=True) passes --all flag."""
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b'[]\n', b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
            await docker_skill.list_containers(all=True)

            # Verify --all flag was passed
            call_args = mock_exec.call_args
            assert "--all" in call_args[0]

        # Give event loop time to clean up subprocess transports
        import asyncio
        await asyncio.sleep(0.1)

    @pytest.mark.asyncio
    async def test_start_requires_approval_returns_success(self):
        """Test start() requires approval, returns success."""
        mock_approval_gate = Mock(spec=ApprovalGate)
        mock_approval_gate.request_approval = AsyncMock(return_value=True)

        docker_skill = DockerSkill(
            emitter=MemoryTraceEmitter(),
            approval_gate=mock_approval_gate,
            timeout=30,
        )

        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"container started\n", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await docker_skill.start("abc123")

        assert result["success"] is True
        mock_approval_gate.request_approval.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_denied_by_approval_gate_no_subprocess(self):
        """Test start() denied by approval gate — no subprocess call made."""
        mock_approval_gate = Mock(spec=ApprovalGate)
        mock_approval_gate.request_approval = AsyncMock(return_value=False)

        docker_skill = DockerSkill(
            emitter=MemoryTraceEmitter(),
            approval_gate=mock_approval_gate,
            timeout=30,
        )

        result = await docker_skill.start("abc123")

        assert result["success"] is False
        assert "denied" in result["output"].lower()

    @pytest.mark.asyncio
    async def test_stop_requires_approval(self):
        """Test stop() requires approval."""
        mock_approval_gate = Mock(spec=ApprovalGate)
        mock_approval_gate.request_approval = AsyncMock(return_value=True)

        docker_skill = DockerSkill(
            emitter=MemoryTraceEmitter(),
            approval_gate=mock_approval_gate,
            timeout=30,
        )

        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"container stopped\n", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await docker_skill.stop("abc123")

        assert result["success"] is True
        mock_approval_gate.request_approval.assert_called_once()

    @pytest.mark.asyncio
    async def test_logs_returns_string_no_approval_required(self, docker_skill):
        """Test logs() returns string, no approval required."""
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"log line 1\nlog line 2\n", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await docker_skill.logs("abc123", tail=100)

        assert result == "log line 1\nlog line 2\n"

    @pytest.mark.asyncio
    async def test_exec_command_requires_approval(self):
        """Test exec_command() requires approval."""
        mock_approval_gate = Mock(spec=ApprovalGate)
        mock_approval_gate.request_approval = AsyncMock(return_value=True)

        docker_skill = DockerSkill(
            emitter=MemoryTraceEmitter(),
            approval_gate=mock_approval_gate,
            timeout=30,
        )

        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"output\n", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await docker_skill.exec_command("abc123", "ls")

        assert result["success"] is True
        mock_approval_gate.request_approval.assert_called_once()

    @pytest.mark.asyncio
    async def test_trace_event_emitted_on_command(self, docker_skill):
        """Test trace event emitted on command (verify enum values)."""
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b'[]\n', b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            await docker_skill.list_containers()

        events = docker_skill._emitter.get_events()
        assert len(events) > 0
        assert any(event.event_type == TraceEventType.DOCKER_COMMAND for event in events)
        assert any(event.component == TraceComponent.DOCKER_SKILL for event in events)

    @pytest.mark.asyncio
    async def test_error_case_non_zero_exit_code_handled(self, docker_skill):
        """Test error case: non-zero exit code handled."""
        mock_process = Mock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(return_value=(b"", b"error output\n"))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await docker_skill.list_containers()

        # Should return result even with non-zero exit code
        assert result == []
