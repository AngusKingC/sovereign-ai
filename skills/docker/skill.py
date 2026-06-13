"""Docker skill for container management operations."""

import asyncio
import json
from typing import Any

from core.approval_gate import ApprovalGate
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
            approved = await self._approval_gate.request_approval(
                action="docker start",
                context={"container_id": container_id},
            )
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
            approved = await self._approval_gate.request_approval(
                action="docker stop",
                context={"container_id": container_id},
            )
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
            approved = await self._approval_gate.request_approval(
                action="docker exec",
                context={"container_id": container_id, "command": command},
            )
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

        return stdout_str, stderr_str, process.returncode
