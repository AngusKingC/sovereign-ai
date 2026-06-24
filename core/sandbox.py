"""
Sandbox Executor - Docker-isolated code and command execution.

Single responsibility: Execute code and commands in a Docker container
with resource limits, preventing host system damage.

This is the ONLY module that should be used for code/command execution
outside of skills/docker/skill.py (container management) and test fixtures.
See AR19.
"""

import asyncio
import logging
import os
import tempfile
from dataclasses import dataclass
from typing import Any

from core.observability import (
    MemoryTraceEmitter,
    TraceComponent,
    TraceEmitter,
    TraceEvent,
    TraceEventType,
    TraceLevel,
)

logger = logging.getLogger(__name__)


@dataclass
class SandboxConfig:
    """Configuration for SandboxExecutor."""

    image: str = "python:3.12-slim"
    memory_limit: str = "512m"
    cpu_limit: str = "1.0"
    network_disabled: bool = True
    read_only_fs: bool = True
    timeout: int = 30
    sandbox_policy: str = (
        "strict"  # "strict" (default, secure) or "fallback" (opt-in, approval-gated subprocess)
    )


@dataclass
class SandboxResult:
    """Result of sandboxed execution."""

    success: bool
    stdout: str
    stderr: str
    return_code: int
    error: str | None = None
    sandboxed: bool = False
    container_id: str | None = None


class SandboxExecutor:
    """Executes code and commands in a Docker container."""

    def __init__(
        self,
        config: SandboxConfig | None = None,
        emitter: TraceEmitter | None = None,
        approval_gate: Any = None,
    ) -> None:
        self._config = config or SandboxConfig()
        self._emitter = emitter or MemoryTraceEmitter()
        self._approval_gate = approval_gate
        self._docker_available_cache: bool | None = None
        self._docker_available_cache_time: float = 0

    async def execute_python(self, code: str, **_kwargs: Any) -> SandboxResult:
        """Execute Python code in a Docker container."""
        asyncio.create_task(
            self._emitter.emit(
                TraceEvent(
                    component=TraceComponent.SANDBOX,
                    event_type=TraceEventType.COMPONENT_START,
                    level=TraceLevel.INFO,
                    message="Starting Python code execution in sandbox",
                    data={"code_length": len(code), "image": self._config.image},
                )
            )
        )

        temp_file_path: str | None = None

        try:
            # Check Docker availability
            if not await self._check_docker_available():
                if self._config.sandbox_policy == "strict":
                    error_msg = "Docker unavailable and sandbox_policy is 'strict'. Set sandbox_policy='fallback' to allow approval-gated subprocess execution."
                    asyncio.create_task(
                        self._emitter.emit(
                            TraceEvent(
                                component=TraceComponent.SANDBOX,
                                event_type=TraceEventType.OPERATION_ERROR,
                                level=TraceLevel.ERROR,
                                message=error_msg,
                                data={"policy": self._config.sandbox_policy},
                            )
                        )
                    )
                    return SandboxResult(
                        success=False,
                        stdout="",
                        stderr=error_msg,
                        return_code=1,
                        error=error_msg,
                        sandboxed=False,
                    )
                else:
                    # Fallback to subprocess with approval
                    return await self._fallback_subprocess(code, is_python=True)

            # Write code to temp file
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write(code)
                temp_file_path = f.name

            # Build docker run command
            docker_args = [
                "docker",
                "run",
                "--rm",
                "--network",
                "none" if self._config.network_disabled else "bridge",
                "--read-only" if self._config.read_only_fs else "",
                "--memory",
                self._config.memory_limit,
                "--cpus",
                self._config.cpu_limit,
                "-v",
                f"{temp_file_path}:/tmp/script.py:ro",
                "-v",
                "/tmp:/tmp:rw",
                self._config.image,
                "python",
                "/tmp/script.py",
            ]
            docker_args = [arg for arg in docker_args if arg]  # Remove empty strings

            stdout, stderr, return_code = await asyncio.wait_for(
                self._run_docker(docker_args, self._config.timeout),
                timeout=self._config.timeout,
            )

            success = return_code == 0

            asyncio.create_task(
                self._emitter.emit(
                    TraceEvent(
                        component=TraceComponent.SANDBOX,
                        event_type=(
                            TraceEventType.OPERATION_COMPLETE
                            if success
                            else TraceEventType.OPERATION_ERROR
                        ),
                        level=TraceLevel.INFO if success else TraceLevel.ERROR,
                        message="Python code execution completed",
                        data={
                            "success": success,
                            "return_code": return_code,
                            "sandboxed": True,
                        },
                    )
                )
            )

            return SandboxResult(
                success=success,
                stdout=stdout,
                stderr=stderr,
                return_code=return_code,
                sandboxed=True,
            )

        except asyncio.TimeoutError:
            asyncio.create_task(
                self._emitter.emit(
                    TraceEvent(
                        component=TraceComponent.SANDBOX,
                        event_type=TraceEventType.OPERATION_ERROR,
                        level=TraceLevel.WARNING,
                        message="Python code execution timed out",
                        data={"timeout": self._config.timeout},
                    )
                )
            )
            return SandboxResult(
                success=False,
                stdout="",
                stderr=f"Execution timed out after {self._config.timeout}s",
                return_code=124,
                error="timeout",
                sandboxed=True,
            )
        except asyncio.CancelledError:
            # Re-raise cancellation - finally block will still run
            raise
        except Exception as e:
            # AR18: inline comment + WARNING trace
            asyncio.create_task(
                self._emitter.emit(
                    TraceEvent(
                        component=TraceComponent.SANDBOX,
                        event_type=TraceEventType.OPERATION_ERROR,
                        level=TraceLevel.WARNING,
                        message=f"Python code execution failed: {e}",
                        data={"error": str(e)},
                    )
                )
            )
            return SandboxResult(
                success=False,
                stdout="",
                stderr=str(e),
                return_code=1,
                error=str(e),
                sandboxed=True,
            )
        finally:
            # Temp file cleanup - MUST run even on timeout/cancellation
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except Exception:
                    # Best effort cleanup - log but don't fail
                    pass

    async def execute_command(
        self, command: str, working_dir: str | None = None, **_kwargs: Any
    ) -> SandboxResult:
        """Execute a shell command in a Docker container."""
        asyncio.create_task(
            self._emitter.emit(
                TraceEvent(
                    component=TraceComponent.SANDBOX,
                    event_type=TraceEventType.COMPONENT_START,
                    level=TraceLevel.INFO,
                    message="Starting command execution in sandbox",
                    data={"command": command[:100], "image": self._config.image},
                )
            )
        )

        try:
            # Check Docker availability
            if not await self._check_docker_available():
                if self._config.sandbox_policy == "strict":
                    error_msg = "Docker unavailable and sandbox_policy is 'strict'. Set sandbox_policy='fallback' to allow approval-gated subprocess execution."
                    asyncio.create_task(
                        self._emitter.emit(
                            TraceEvent(
                                component=TraceComponent.SANDBOX,
                                event_type=TraceEventType.OPERATION_ERROR,
                                level=TraceLevel.ERROR,
                                message=error_msg,
                                data={"policy": self._config.sandbox_policy},
                            )
                        )
                    )
                    return SandboxResult(
                        success=False,
                        stdout="",
                        stderr=error_msg,
                        return_code=1,
                        error=error_msg,
                        sandboxed=False,
                    )
                else:
                    # Fallback to subprocess with approval
                    return await self._fallback_subprocess(command, is_python=False)

            # Build docker run command
            docker_args = [
                "docker",
                "run",
                "--rm",
                "--network",
                "none" if self._config.network_disabled else "bridge",
                "--read-only" if self._config.read_only_fs else "",
                "--memory",
                self._config.memory_limit,
                "--cpus",
                self._config.cpu_limit,
                "-v",
                "/tmp:/tmp:rw",
            ]

            if working_dir:
                docker_args.extend(["-w", working_dir])

            docker_args.extend(
                [
                    self._config.image,
                    "sh",
                    "-c",
                    command,
                ]
            )
            docker_args = [arg for arg in docker_args if arg]  # Remove empty strings

            stdout, stderr, return_code = await asyncio.wait_for(
                self._run_docker(docker_args, self._config.timeout),
                timeout=self._config.timeout,
            )

            success = return_code == 0

            asyncio.create_task(
                self._emitter.emit(
                    TraceEvent(
                        component=TraceComponent.SANDBOX,
                        event_type=(
                            TraceEventType.OPERATION_COMPLETE
                            if success
                            else TraceEventType.OPERATION_ERROR
                        ),
                        level=TraceLevel.INFO if success else TraceLevel.ERROR,
                        message="Command execution completed",
                        data={
                            "success": success,
                            "return_code": return_code,
                            "sandboxed": True,
                        },
                    )
                )
            )

            return SandboxResult(
                success=success,
                stdout=stdout,
                stderr=stderr,
                return_code=return_code,
                sandboxed=True,
            )

        except asyncio.TimeoutError:
            asyncio.create_task(
                self._emitter.emit(
                    TraceEvent(
                        component=TraceComponent.SANDBOX,
                        event_type=TraceEventType.OPERATION_ERROR,
                        level=TraceLevel.WARNING,
                        message="Command execution timed out",
                        data={"timeout": self._config.timeout},
                    )
                )
            )
            return SandboxResult(
                success=False,
                stdout="",
                stderr=f"Execution timed out after {self._config.timeout}s",
                return_code=124,
                error="timeout",
                sandboxed=True,
            )
        except Exception as e:
            # AR18: inline comment + WARNING trace
            asyncio.create_task(
                self._emitter.emit(
                    TraceEvent(
                        component=TraceComponent.SANDBOX,
                        event_type=TraceEventType.OPERATION_ERROR,
                        level=TraceLevel.WARNING,
                        message=f"Command execution failed: {e}",
                        data={"error": str(e)},
                    )
                )
            )
            return SandboxResult(
                success=False,
                stdout="",
                stderr=str(e),
                return_code=1,
                error=str(e),
                sandboxed=True,
            )

    async def _run_docker(self, args: list[str], timeout: int) -> tuple[str, str, int]:
        """Run docker CLI command via subprocess."""
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()
        return (
            stdout.decode("utf-8", errors="replace"),
            stderr.decode("utf-8", errors="replace"),
            process.returncode or 0,
        )

    async def _check_docker_available(self) -> bool:
        """Check if Docker is available and running."""
        import time

        current_time = time.time()
        # Cache for 60 seconds
        if (
            self._docker_available_cache is not None
            and (current_time - self._docker_available_cache_time) < 60
        ):
            return self._docker_available_cache

        try:
            process = await asyncio.create_subprocess_exec(
                "docker",
                "info",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()
            available = process.returncode == 0
            self._docker_available_cache = available
            self._docker_available_cache_time = current_time

            if not available:
                # User-facing warning (not just trace event)
                warning_msg = "Docker unavailable. sandbox_policy='strict' — execution will fail. Set sandbox_policy='fallback' to allow approval-gated subprocess execution, or start Docker Desktop."
                logger.warning(warning_msg)
                asyncio.create_task(
                    self._emitter.emit(
                        TraceEvent(
                            component=TraceComponent.SANDBOX,
                            event_type=TraceEventType.OPERATION_ERROR,
                            level=TraceLevel.WARNING,
                            message=warning_msg,
                            data={"policy": self._config.sandbox_policy},
                        )
                    )
                )

            return available
        except FileNotFoundError:
            self._docker_available_cache = False
            self._docker_available_cache_time = current_time
            warning_msg = "Docker unavailable. sandbox_policy='strict' — execution will fail. Set sandbox_policy='fallback' to allow approval-gated subprocess execution, or start Docker Desktop."
            logger.warning(warning_msg)
            asyncio.create_task(
                self._emitter.emit(
                    TraceEvent(
                        component=TraceComponent.SANDBOX,
                        event_type=TraceEventType.OPERATION_ERROR,
                        level=TraceLevel.WARNING,
                        message=warning_msg,
                        data={"policy": self._config.sandbox_policy},
                    )
                )
            )
            return False

    async def _fallback_subprocess(
        self, code_or_command: str, is_python: bool
    ) -> SandboxResult:
        """Fallback to subprocess when Docker unavailable. Requires approval."""
        # Per AR19: fallback requires explicit approval
        if self._approval_gate is None:
            error_msg = "Docker unavailable and no approval gate for fallback"
            asyncio.create_task(
                self._emitter.emit(
                    TraceEvent(
                        component=TraceComponent.SANDBOX,
                        event_type=TraceEventType.OPERATION_ERROR,
                        level=TraceLevel.ERROR,
                        message=error_msg,
                    )
                )
            )
            return SandboxResult(
                success=False,
                stdout="",
                stderr=error_msg,
                return_code=1,
                error=error_msg,
                sandboxed=False,
            )

        # Request approval
        approval_granted = False
        try:
            # This is a placeholder - actual approval gate interface may differ
            if hasattr(self._approval_gate, "request_approval"):
                approval_granted = await self._approval_gate.request_approval(
                    action="execute_unsandboxed",
                    details={
                        "code_or_command": code_or_command[:100],
                        "is_python": is_python,
                    },
                )
            else:
                # If approval gate doesn't have request_approval, deny by default
                approval_granted = False
        except Exception:
            approval_granted = False

        if not approval_granted:
            error_msg = "Approval denied for unsandboxed execution"
            asyncio.create_task(
                self._emitter.emit(
                    TraceEvent(
                        component=TraceComponent.SANDBOX,
                        event_type=TraceEventType.OPERATION_ERROR,
                        level=TraceLevel.ERROR,
                        message=error_msg,
                    )
                )
            )
            return SandboxResult(
                success=False,
                stdout="",
                stderr=error_msg,
                return_code=1,
                error=error_msg,
                sandboxed=False,
            )

        # Execute via subprocess (the ONLY place this is allowed per AR19)
        try:
            if is_python:
                escaped_code = code_or_command.replace('"', '\\"')
                cmd = f'python -c "{escaped_code}"'
            else:
                cmd = code_or_command

            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self._config.timeout,
            )

            success = process.returncode == 0

            asyncio.create_task(
                self._emitter.emit(
                    TraceEvent(
                        component=TraceComponent.SANDBOX,
                        event_type=(
                            TraceEventType.OPERATION_COMPLETE
                            if success
                            else TraceEventType.OPERATION_ERROR
                        ),
                        level=TraceLevel.INFO if success else TraceLevel.ERROR,
                        message="Fallback subprocess execution completed",
                        data={
                            "success": success,
                            "return_code": process.returncode,
                            "sandboxed": False,
                        },
                    )
                )
            )

            return SandboxResult(
                success=success,
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                return_code=process.returncode or 0,
                sandboxed=False,
            )
        except asyncio.TimeoutError:
            return SandboxResult(
                success=False,
                stdout="",
                stderr=f"Execution timed out after {self._config.timeout}s",
                return_code=124,
                error="timeout",
                sandboxed=False,
            )
        except Exception as e:
            # AR18: inline comment + WARNING trace
            asyncio.create_task(
                self._emitter.emit(
                    TraceEvent(
                        component=TraceComponent.SANDBOX,
                        event_type=TraceEventType.OPERATION_ERROR,
                        level=TraceLevel.WARNING,
                        message=f"Fallback subprocess execution failed: {e}",
                        data={"error": str(e)},
                    )
                )
            )
            return SandboxResult(
                success=False,
                stdout="",
                stderr=str(e),
                return_code=1,
                error=str(e),
                sandboxed=False,
            )
