"""Git skill for version control operations."""

import asyncio
from typing import Any
from datetime import datetime, timedelta
from uuid import uuid4

from core.approval_gate import ApprovalGate, ApprovalRequest, ApprovalActionType
from core.observability import (
    TraceEventType,
    TraceComponent,
    TraceLevel,
    TraceEvent,
    TraceEmitter,
    MemoryTraceEmitter,
)


class GitSkill:
    """Git skill for version control operations."""

    def __init__(
        self,
        emitter: TraceEmitter | None = None,
        approval_gate: ApprovalGate | None = None,
        working_dir: str = ".",
        timeout: int = 30,
    ) -> None:
        """Initialize the Git skill.

        Args:
            emitter: Trace emitter for observability
            approval_gate: Approval gate for write operations
            working_dir: Working directory for git operations
            timeout: Timeout for subprocess execution in seconds
        """
        self._emitter = emitter or MemoryTraceEmitter()
        self._approval_gate = approval_gate
        self.working_dir = working_dir
        self.timeout = timeout

    async def status(self) -> dict[str, Any]:
        """Get git status.

        Returns:
            Dict with staged, unstaged, and untracked file lists.
        """
        start_time = asyncio.get_event_loop().time()

        try:
            event = TraceEvent(
                event_type=TraceEventType.GIT_COMMAND,
                component=TraceComponent.GIT_SKILL,
                level=TraceLevel.INFO,
                message="git status",
                data={"command": "status"},
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        stdout, stderr, returncode = await self._run_git(["status", "--porcelain"])

        duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

        try:
            event = TraceEvent(
                event_type=TraceEventType.GIT_COMMAND,
                component=TraceComponent.GIT_SKILL,
                level=TraceLevel.INFO,
                message="git status completed",
                data={"command": "status", "returncode": returncode},
                duration_ms=duration_ms,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        # Parse git status output
        staged = []
        unstaged = []
        untracked = []

        for line in stdout.splitlines():
            if line.startswith(" M"):
                # Index clean, working tree modified = unstaged only
                unstaged.append(line[2:].strip())
            elif line.startswith("M "):
                # Index modified, working tree clean = staged only
                staged.append(line[2:].strip())
            elif line.startswith("MM"):
                # Index modified, working tree modified = both
                staged.append(line[2:].strip())
                unstaged.append(line[2:].strip())
            elif line.startswith("A "):
                # Added in index (staged)
                staged.append(line[2:].strip())
            elif line.startswith("??"):
                # Untracked
                untracked.append(line[3:].strip())

        return {
            "staged": staged,
            "unstaged": unstaged,
            "untracked": untracked,
        }

    async def diff(self, staged: bool = False) -> str:
        """Get git diff.

        Args:
            staged: If True, get staged diff (--cached)

        Returns:
            Raw diff string.
        """
        start_time = asyncio.get_event_loop().time()

        try:
            event = TraceEvent(
                event_type=TraceEventType.GIT_COMMAND,
                component=TraceComponent.GIT_SKILL,
                level=TraceLevel.INFO,
                message="git diff",
                data={"command": "diff", "staged": staged},
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        args = ["diff"]
        if staged:
            args.append("--cached")

        stdout, stderr, returncode = await self._run_git(args)

        duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

        try:
            event = TraceEvent(
                event_type=TraceEventType.GIT_COMMAND,
                component=TraceComponent.GIT_SKILL,
                level=TraceLevel.INFO,
                message="git diff completed",
                data={"command": "diff", "staged": staged, "returncode": returncode},
                duration_ms=duration_ms,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        return stdout

    async def commit(self, message: str) -> dict[str, Any]:
        """Commit changes.

        Args:
            message: Commit message

        Returns:
            Dict with success, hash, and message.
        """
        if self._approval_gate:
            request = ApprovalRequest(
                request_id=str(uuid4()),
                task_id=str(uuid4()),
                session_id="default",
                action_type=ApprovalActionType.SHELL_COMMAND,
                action_description="git commit",
                action_parameters={"message": message},
                risk_level="medium",
                reason_for_approval="Git commit requires approval per policy",
                expires_at=datetime.utcnow() + timedelta(seconds=300),
            )
            response = await self._approval_gate.request_approval(request)
            approved = response.approved
            if not approved:
                return {
                    "success": False,
                    "hash": "",
                    "message": "Commit denied by approval gate",
                }

        start_time = asyncio.get_event_loop().time()

        try:
            event = TraceEvent(
                event_type=TraceEventType.GIT_COMMAND,
                component=TraceComponent.GIT_SKILL,
                level=TraceLevel.INFO,
                message="git commit",
                data={"command": "commit", "message": message},
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        stdout, stderr, returncode = await self._run_git(["commit", "-m", message])

        duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

        try:
            event = TraceEvent(
                event_type=TraceEventType.GIT_COMMAND,
                component=TraceComponent.GIT_SKILL,
                level=TraceLevel.INFO,
                message="git commit completed",
                data={"command": "commit", "returncode": returncode},
                duration_ms=duration_ms,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        # Extract commit hash from output
        commit_hash = ""
        for line in stdout.splitlines():
            if line.startswith("[") and "master" in line:
                parts = line.split()
                if len(parts) >= 2:
                    commit_hash = parts[1].rstrip("]")

        return {
            "success": returncode == 0,
            "hash": commit_hash,
            "message": message,
        }

    async def push(self, remote: str = "origin", branch: str = "HEAD") -> dict[str, Any]:
        """Push changes to remote.

        Args:
            remote: Remote name
            branch: Branch name

        Returns:
            Dict with success and output.
        """
        if self._approval_gate:
            request = ApprovalRequest(
                request_id=str(uuid4()),
                task_id=str(uuid4()),
                session_id="default",
                action_type=ApprovalActionType.SHELL_COMMAND,
                action_description="git push",
                action_parameters={"remote": remote, "branch": branch},
                risk_level="medium",
                reason_for_approval="Git push requires approval per policy",
                expires_at=datetime.utcnow() + timedelta(seconds=300),
            )
            response = await self._approval_gate.request_approval(request)
            approved = response.approved
            if not approved:
                return {
                    "success": False,
                    "output": "Push denied by approval gate",
                }

        start_time = asyncio.get_event_loop().time()

        try:
            event = TraceEvent(
                event_type=TraceEventType.GIT_COMMAND,
                component=TraceComponent.GIT_SKILL,
                level=TraceLevel.INFO,
                message="git push",
                data={"command": "push", "remote": remote, "branch": branch},
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        stdout, stderr, returncode = await self._run_git(["push", remote, branch])

        duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

        try:
            event = TraceEvent(
                event_type=TraceEventType.GIT_COMMAND,
                component=TraceComponent.GIT_SKILL,
                level=TraceLevel.INFO,
                message="git push completed",
                data={"command": "push", "returncode": returncode},
                duration_ms=duration_ms,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        return {
            "success": returncode == 0,
            "output": stdout + stderr,
        }

    async def pull(self, remote: str = "origin", branch: str = "") -> dict[str, Any]:
        """Pull changes from remote.

        Args:
            remote: Remote name
            branch: Branch name (empty for current branch)

        Returns:
            Dict with success and output.
        """
        if self._approval_gate:
            request = ApprovalRequest(
                request_id=str(uuid4()),
                task_id=str(uuid4()),
                session_id="default",
                action_type=ApprovalActionType.SHELL_COMMAND,
                action_description="git pull",
                action_parameters={"remote": remote, "branch": branch},
                risk_level="medium",
                reason_for_approval="Git pull requires approval per policy",
                expires_at=datetime.utcnow() + timedelta(seconds=300),
            )
            response = await self._approval_gate.request_approval(request)
            approved = response.approved
            if not approved:
                return {
                    "success": False,
                    "output": "Pull denied by approval gate",
                }

        start_time = asyncio.get_event_loop().time()

        try:
            event = TraceEvent(
                event_type=TraceEventType.GIT_COMMAND,
                component=TraceComponent.GIT_SKILL,
                level=TraceLevel.INFO,
                message="git pull",
                data={"command": "pull", "remote": remote, "branch": branch},
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        args = ["pull", remote]
        if branch:
            args.append(branch)

        stdout, stderr, returncode = await self._run_git(args)

        duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

        try:
            event = TraceEvent(
                event_type=TraceEventType.GIT_COMMAND,
                component=TraceComponent.GIT_SKILL,
                level=TraceLevel.INFO,
                message="git pull completed",
                data={"command": "pull", "returncode": returncode},
                duration_ms=duration_ms,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        return {
            "success": returncode == 0,
            "output": stdout + stderr,
        }

    async def log(self, n: int = 10) -> list[dict[str, Any]]:
        """Get git log.

        Args:
            n: Number of commits to show

        Returns:
            List of dicts with hash and message.
        """
        start_time = asyncio.get_event_loop().time()

        try:
            event = TraceEvent(
                event_type=TraceEventType.GIT_COMMAND,
                component=TraceComponent.GIT_SKILL,
                level=TraceLevel.INFO,
                message="git log",
                data={"command": "log", "n": n},
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        stdout, stderr, returncode = await self._run_git(["log", "--oneline", f"-n{n}"])

        duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

        try:
            event = TraceEvent(
                event_type=TraceEventType.GIT_COMMAND,
                component=TraceComponent.GIT_SKILL,
                level=TraceLevel.INFO,
                message="git log completed",
                data={"command": "log", "returncode": returncode},
                duration_ms=duration_ms,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        # Parse log output
        commits = []
        for line in stdout.splitlines():
            if line:
                parts = line.split(maxsplit=1)
                if len(parts) >= 2:
                    commits.append({"hash": parts[0], "message": parts[1]})
                elif len(parts) == 1:
                    commits.append({"hash": parts[0], "message": ""})

        return commits

    async def branch_list(self) -> list[str]:
        """List all branches.

        Returns:
            List of branch names.
        """
        start_time = asyncio.get_event_loop().time()

        try:
            event = TraceEvent(
                event_type=TraceEventType.GIT_COMMAND,
                component=TraceComponent.GIT_SKILL,
                level=TraceLevel.INFO,
                message="git branch",
                data={"command": "branch"},
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        stdout, stderr, returncode = await self._run_git(["branch"])

        duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

        try:
            event = TraceEvent(
                event_type=TraceEventType.GIT_COMMAND,
                component=TraceComponent.GIT_SKILL,
                level=TraceLevel.INFO,
                message="git branch completed",
                data={"command": "branch", "returncode": returncode},
                duration_ms=duration_ms,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        # Parse branch output
        branches = []
        for line in stdout.splitlines():
            if line.startswith("*"):
                branches.append(line[2:].strip())
            elif line.startswith("  "):
                branches.append(line[2:].strip())

        return branches

    async def _run_git(self, args: list[str]) -> tuple[str, str, int]:
        """Run git command as subprocess.

        Args:
            args: Git command arguments

        Returns:
            Tuple of (stdout, stderr, returncode)

        Raises:
            RuntimeError: On timeout
        """
        process = await asyncio.create_subprocess_exec(
            "git",
            *args,
            cwd=self.working_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.timeout,
            )
        except asyncio.TimeoutError:
            process.kill()
            raise RuntimeError(f"Git command timed out after {self.timeout} seconds")

        stdout_str = stdout.decode("utf-8", errors="replace")
        stderr_str = stderr.decode("utf-8", errors="replace")

        return stdout_str, stderr_str, process.returncode
