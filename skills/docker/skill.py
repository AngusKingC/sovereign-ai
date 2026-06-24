"""Docker skill for container management operations."""

import asyncio
import json
from typing import Any
from datetime import datetime, timedelta, timezone
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


class DockerSkill:
    """Docker skill for container management operations."""

    def __init__(
        self,
        emitter: TraceEmitter | None = None,
        approval_gate: ApprovalGate | None = None,
        timeout: int = 30,
    ) -> None:
        """Initialize the Docker skill.

        Args:
            emitter: Trace emitter for observability
            approval_gate: Approval gate for write operations
            timeout: Timeout for subprocess execution in seconds
        """
        self._emitter = emitter or MemoryTraceEmitter()
        self._approval_gate = approval_gate
        self.timeout = timeout

    async def list_containers(self, all: bool = False) -> list[dict[str, Any]]:
        """List Docker containers.

        Args:
            all: If True, list all containers including stopped ones

        Returns:
            List of container dicts with at least id, name, status, image.
        """
        start_time = asyncio.get_event_loop().time()

        try:
            event = TraceEvent(
                event_type=TraceEventType.DOCKER_COMMAND,
                component=TraceComponent.DOCKER_SKILL,
                level=TraceLevel.INFO,
                message="docker ps",
                data={"command": "ps", "all": all},
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        args = ["ps", "--format", "json"]
        if all:
            args.insert(1, "--all")

        stdout, stderr, returncode = await self._run_docker(args)

        duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

        try:
            event = TraceEvent(
                event_type=TraceEventType.DOCKER_COMMAND,
                component=TraceComponent.DOCKER_SKILL,
                level=TraceLevel.INFO,
                message="docker ps completed",
                data={"command": "ps", "returncode": returncode},
                duration_ms=duration_ms,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        # Parse JSON output
        if stdout.strip():
            containers = json.loads(stdout)
        else:
            containers = []

        return containers

    async def start(self, container_id: str) -> dict[str, Any]:
        """Start a Docker container.

        Args:
            container_id: Container ID or name

        Returns:
            Dict with success and output.
        """
        if self._approval_gate:
            request = ApprovalRequest(
                request_id=str(uuid4()),
                task_id=str(uuid4()),
                session_id="default",
                action_type=ApprovalActionType.SHELL_COMMAND,
                action_description="docker start",
                action_parameters={"container_id": container_id},
                risk_level="medium",
                reason_for_approval="Docker start requires approval per policy",
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=300),
            )
            response = await self._approval_gate.request_approval(request)
            approved = response.approved
            if not approved:
                return {
                    "success": False,
                    "output": "Start denied by approval gate",
                }

        start_time = asyncio.get_event_loop().time()

        try:
            event = TraceEvent(
                event_type=TraceEventType.DOCKER_COMMAND,
                component=TraceComponent.DOCKER_SKILL,
                level=TraceLevel.INFO,
                message="docker start",
                data={"command": "start", "container_id": container_id},
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        stdout, stderr, returncode = await self._run_docker(["start", container_id])

        duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

        try:
            event = TraceEvent(
                event_type=TraceEventType.DOCKER_COMMAND,
                component=TraceComponent.DOCKER_SKILL,
                level=TraceLevel.INFO,
                message="docker start completed",
                data={"command": "start", "returncode": returncode},
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

    async def stop(self, container_id: str) -> dict[str, Any]:
        """Stop a Docker container.

        Args:
            container_id: Container ID or name

        Returns:
            Dict with success and output.
        """
        if self._approval_gate:
            request = ApprovalRequest(
                request_id=str(uuid4()),
                task_id=str(uuid4()),
                session_id="default",
                action_type=ApprovalActionType.SHELL_COMMAND,
                action_description="docker stop",
                action_parameters={"container_id": container_id},
                risk_level="medium",
                reason_for_approval="Docker stop requires approval per policy",
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=300),
            )
            response = await self._approval_gate.request_approval(request)
            approved = response.approved
            if not approved:
                return {
                    "success": False,
                    "output": "Stop denied by approval gate",
                }

        start_time = asyncio.get_event_loop().time()

        try:
            event = TraceEvent(
                event_type=TraceEventType.DOCKER_COMMAND,
                component=TraceComponent.DOCKER_SKILL,
                level=TraceLevel.INFO,
                message="docker stop",
                data={"command": "stop", "container_id": container_id},
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        stdout, stderr, returncode = await self._run_docker(["stop", container_id])

        duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

        try:
            event = TraceEvent(
                event_type=TraceEventType.DOCKER_COMMAND,
                component=TraceComponent.DOCKER_SKILL,
                level=TraceLevel.INFO,
                message="docker stop completed",
                data={"command": "stop", "returncode": returncode},
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

    async def logs(self, container_id: str, tail: int = 100) -> str:
        """Get Docker container logs.

        Args:
            container_id: Container ID or name
            tail: Number of lines to show from end of logs

        Returns:
            Log string.
        """
        start_time = asyncio.get_event_loop().time()

        try:
            event = TraceEvent(
                event_type=TraceEventType.DOCKER_COMMAND,
                component=TraceComponent.DOCKER_SKILL,
                level=TraceLevel.INFO,
                message="docker logs",
                data={"command": "logs", "container_id": container_id, "tail": tail},
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        stdout, stderr, returncode = await self._run_docker(["logs", "--tail", str(tail), container_id])

        duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

        try:
            event = TraceEvent(
                event_type=TraceEventType.DOCKER_COMMAND,
                component=TraceComponent.DOCKER_SKILL,
                level=TraceLevel.INFO,
                message="docker logs completed",
                data={"command": "logs", "returncode": returncode},
                duration_ms=duration_ms,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        return stdout

    async def exec_command(self, container_id: str, command: str) -> dict[str, Any]:
        """Execute a command in a Docker container.

        Args:
            container_id: Container ID or name
            command: Command to execute

        Returns:
            Dict with success, stdout, and stderr.
        """
        if self._approval_gate:
            request = ApprovalRequest(
                request_id=str(uuid4()),
                task_id=str(uuid4()),
                session_id="default",
                action_type=ApprovalActionType.SHELL_COMMAND,
                action_description="docker exec",
                action_parameters={"container_id": container_id, "command": command},
                risk_level="high",
                reason_for_approval="Docker exec requires approval per policy",
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=300),
            )
            response = await self._approval_gate.request_approval(request)
            approved = response.approved
            if not approved:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "Exec denied by approval gate",
                }

        start_time = asyncio.get_event_loop().time()

        try:
            event = TraceEvent(
                event_type=TraceEventType.DOCKER_COMMAND,
                component=TraceComponent.DOCKER_SKILL,
                level=TraceLevel.INFO,
                message="docker exec",
                data={"command": "exec", "container_id": container_id},
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        stdout, stderr, returncode = await self._run_docker(["exec", container_id, command])

        duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

        try:
            event = TraceEvent(
                event_type=TraceEventType.DOCKER_COMMAND,
                component=TraceComponent.DOCKER_SKILL,
                level=TraceLevel.INFO,
                message="docker exec completed",
                data={"command": "exec", "returncode": returncode},
                duration_ms=duration_ms,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        return {
            "success": returncode == 0,
            "stdout": stdout,
            "stderr": stderr,
        }

    async def _run_docker(self, args: list[str]) -> tuple[str, str, int]:
        """Run docker command as subprocess.

        Args:
            args: Docker command arguments

        Returns:
            Tuple of (stdout, stderr, returncode)

        Raises:
            RuntimeError: On timeout
        """
        process = await asyncio.create_subprocess_exec(
            "docker",
            *args,
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
            raise RuntimeError(f"Docker command timed out after {self.timeout} seconds")

        stdout_str = stdout.decode("utf-8", errors="replace")
        stderr_str = stderr.decode("utf-8", errors="replace")

        return stdout_str, stderr_str, process.returncode or 0
