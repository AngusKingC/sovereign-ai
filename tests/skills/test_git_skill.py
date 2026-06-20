"""Git skill tests."""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from skills.git.skill import GitSkill
from core.approval_gate import ApprovalGate, ApprovalResponse
from core.observability import MemoryTraceEmitter, TraceEventType, TraceComponent


pytestmark = pytest.mark.asyncio


class TestGitSkill:
    """Test GitSkill functionality."""

    @pytest.fixture
    def git_skill(self):
        """Create a git skill for testing."""
        return GitSkill(
            emitter=MemoryTraceEmitter(),
            approval_gate=None,
            working_dir=".",
            timeout=30,
        )

    async def test_status_returns_correctly_parsed_dict(self, git_skill):
        """Test status() returns correctly parsed dict with staged/unstaged/untracked lists."""
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b" M file1\nM  file2\n?? file3\n", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await git_skill.status()

        assert "staged" in result
        assert "unstaged" in result
        assert "untracked" in result
        assert "file2" in result["staged"]
        assert "file1" in result["unstaged"]
        assert "file3" in result["untracked"]

    async def test_diff_returns_diff_string(self, git_skill):
        """Test diff() returns diff string."""
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"diff output\n", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await git_skill.diff()

        assert result == "diff output\n"

    async def test_diff_staged_true_passes_cached_flag(self, git_skill):
        """Test diff(staged=True) passes --cached flag."""
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"staged diff\n", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
            await git_skill.diff(staged=True)

            # Verify --cached flag was passed
            call_args = mock_exec.call_args
            assert "--cached" in call_args[0]

    async def test_commit_requires_approval_gate_and_returns_success(self):
        """Test commit() requires and passes approval gate, returns success dict."""
        mock_approval_gate = Mock(spec=ApprovalGate)
        mock_response = ApprovalResponse(
            request_id="test-request-id",
            task_id="test-task-id",
            approved=True,
            approved_by="test-user",
        )
        mock_approval_gate.request_approval = AsyncMock(return_value=mock_response)

        git_skill = GitSkill(
            emitter=MemoryTraceEmitter(),
            approval_gate=mock_approval_gate,
            working_dir=".",
            timeout=30,
        )

        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"[master abc123] Commit message\n", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await git_skill.commit("Test commit")

        assert result["success"] is True
        assert result["hash"] == "abc123"
        assert result["message"] == "Test commit"
        mock_approval_gate.request_approval.assert_called_once()

    async def test_commit_denied_by_approval_gate_returns_failure(self):
        """Test commit() denied by approval gate returns failure dict without executing subprocess."""
        mock_approval_gate = Mock(spec=ApprovalGate)
        mock_response = ApprovalResponse(
            request_id="test-request-id",
            task_id="test-task-id",
            approved=False,
            approved_by="test-user",
            decision_reason="Test denial",
        )
        mock_approval_gate.request_approval = AsyncMock(return_value=mock_response)

        git_skill = GitSkill(
            emitter=MemoryTraceEmitter(),
            approval_gate=mock_approval_gate,
            working_dir=".",
            timeout=30,
        )

        result = await git_skill.commit("Test commit")

        assert result["success"] is False
        assert result["hash"] == ""
        assert "denied" in result["message"].lower()

    async def test_push_requires_approval_gate(self):
        """Test push() requires approval gate."""
        mock_approval_gate = Mock(spec=ApprovalGate)
        mock_response = ApprovalResponse(
            request_id="test-request-id",
            task_id="test-task-id",
            approved=True,
            approved_by="test-user",
        )
        mock_approval_gate.request_approval = AsyncMock(return_value=mock_response)

        git_skill = GitSkill(
            emitter=MemoryTraceEmitter(),
            approval_gate=mock_approval_gate,
            working_dir=".",
            timeout=30,
        )

        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"push output\n", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await git_skill.push()

        assert result["success"] is True
        mock_approval_gate.request_approval.assert_called_once()

    async def test_pull_requires_approval_gate(self):
        """Test pull() requires approval gate."""
        mock_approval_gate = Mock(spec=ApprovalGate)
        mock_response = ApprovalResponse(
            request_id="test-request-id",
            task_id="test-task-id",
            approved=True,
            approved_by="test-user",
        )
        mock_approval_gate.request_approval = AsyncMock(return_value=mock_response)

        git_skill = GitSkill(
            emitter=MemoryTraceEmitter(),
            approval_gate=mock_approval_gate,
            working_dir=".",
            timeout=30,
        )

        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"pull output\n", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await git_skill.pull()

        assert result["success"] is True
        mock_approval_gate.request_approval.assert_called_once()

    async def test_log_returns_correct_list_structure(self, git_skill):
        """Test log() returns correct list structure."""
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"abc123 First commit\ndef456 Second commit\n", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await git_skill.log(n=10)

        assert len(result) == 2
        assert result[0]["hash"] == "abc123"
        assert result[0]["message"] == "First commit"
        assert result[1]["hash"] == "def456"
        assert result[1]["message"] == "Second commit"

    async def test_branch_list_returns_list_of_strings(self, git_skill):
        """Test branch_list() returns list of strings."""
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"* master\n  dev\n  feature\n", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await git_skill.branch_list()

        assert len(result) == 3
        assert "master" in result
        assert "dev" in result
        assert "feature" in result

    async def test_trace_event_emitted_on_command_execution(self, git_skill):
        """Test trace event emitted on command execution (verify enum values)."""
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            await git_skill.status()

        events = git_skill._emitter.get_events()
        assert len(events) > 0
        assert any(event.event_type == TraceEventType.GIT_COMMAND for event in events)
        assert any(event.component == TraceComponent.GIT_SKILL for event in events)

    async def test_error_case_non_zero_exit_code_handled(self, git_skill):
        """Test error case: subprocess returns non-zero exit code."""
        mock_process = Mock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(return_value=(b"", b"error output\n"))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await git_skill.status()

        # Should return result even with non-zero exit code
        assert "staged" in result
        assert "unstaged" in result
        assert "untracked" in result
