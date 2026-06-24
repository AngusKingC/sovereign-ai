"""
Terminal Skill - executes shell commands via subprocess.

Single responsibility: Execute terminal commands with approval gating and timeout handling.
"""

import asyncio
from typing import Any

from core.approval_gate import ApprovalActionType, ApprovalGate, ApprovalRequest
from core.observability import (
    MemoryTraceEmitter,
    TraceComponent,
    TraceEmitter,
    TraceEvent,
    TraceEventType,
    TraceLevel,
)


class TerminalSkill:
    """Skill for executing terminal commands."""

    def __init__(
        self,
        approval_gate: ApprovalGate | None = None,
        emitter: TraceEmitter | None = None,
        working_dir: str | None = None,
        timeout: int = 30,
        sandbox_executor: Any = None,
    ) -> None:
        """Initialize the terminal skill.

        Args:
            approval_gate: Optional approval gate for command execution authorization
            emitter: Trace emitter for observability
            working_dir: Optional working directory for command execution
            timeout: Command execution timeout in seconds (default 30)
            sandbox_executor: Optional SandboxExecutor for DI (testing)
        """
        self._emitter = emitter or MemoryTraceEmitter()
        self._approval_gate = approval_gate
        self._working_dir = working_dir
        self._timeout = timeout
        self._sandbox_executor = sandbox_executor

    async def execute(self, command: str, **_kwargs) -> dict[str, Any]:
        """
        Execute a terminal command.

        Args:
            command: The command to execute
            **kwargs: Additional parameters (not used)

        Returns:
            SkillResult dict with success, stdout, stderr, return_code, error fields

        Raises:
            ValueError: If command is empty
        """
        if not command or not isinstance(command, str):
            raise ValueError("Command must be a non-empty string")

        start_time = asyncio.get_event_loop().time()

        try:
            await self._emitter.emit(
                TraceEvent(
                    event_type=TraceEventType.COMPONENT_START,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.INFO,
                    message="Terminal execution started",
                    data={
                        "skill": "terminal",
                        "command": command,
                        "working_dir": self._working_dir,
                    },
                    duration_ms=0,
                )
            )
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        # Request approval if gate is present
        if self._approval_gate is not None:
            try:
                from datetime import datetime, timedelta, timezone
                from uuid import uuid4

                request = ApprovalRequest(
                    request_id=str(uuid4()),
                    task_id=str(uuid4()),
                    session_id="default",
                    action_type=ApprovalActionType.SHELL_COMMAND,
                    action_description=f"Execute command: {command}",
                    action_parameters={
                        "command": command,
                        "working_dir": self._working_dir,
                    },
                    risk_level="high",
                    reason_for_approval="Shell commands can modify system state",
                    expires_at=datetime.now(timezone.utc) + timedelta(seconds=300),
                )
                response = await self._approval_gate.request_approval(request)
                if not response.approved:
                    try:
                        await self._emitter.emit(
                            TraceEvent(
                                event_type=TraceEventType.OPERATION_COMPLETE,
                                component=TraceComponent.WORKER,
                                level=TraceLevel.WARNING,
                                message="Terminal execution denied by approval gate",
                                data={
                                    "skill": "terminal",
                                    "command": command,
                                    "reason": response.decision_reason,
                                },
                                duration_ms=int(
                                    (asyncio.get_event_loop().time() - start_time)
                                    * 1000
                                ),
                            )
                        )
                    except Exception:
                        # Trace emission failure - non-critical, continue
                        pass
                    return {
                        "success": False,
                        "stdout": "",
                        "stderr": "",
                        "return_code": -1,
                        "error": "Approval denied",
                    }
            except Exception:
                # If approval request fails, log and proceed (or deny based on policy)
                # For now, we'll deny on approval failure
                try:
                    await self._emitter.emit(
                        TraceEvent(
                            event_type=TraceEventType.OPERATION_ERROR,
                            component=TraceComponent.WORKER,
                            level=TraceLevel.ERROR,
                            message="Terminal execution approval request failed",
                            data={
                                "skill": "terminal",
                                "command": command,
                            },
                            duration_ms=int(
                                (asyncio.get_event_loop().time() - start_time) * 1000
                            ),
                        )
                    )
                except Exception:
                    # Trace emission failure - non-critical, continue
                    pass
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "",
                    "return_code": -1,
                    "error": "Approval request failed",
                }

        # Execute command in sandbox (AR19: no direct subprocess for command execution)
        try:
            from core.sandbox import SandboxConfig, SandboxExecutor

            if self._sandbox_executor is None:
                sandbox = SandboxExecutor(
                    config=SandboxConfig(timeout=self._timeout),
                    emitter=self._emitter,
                    approval_gate=self._approval_gate,
                )
            else:
                sandbox = self._sandbox_executor

            result = await sandbox.execute_command(
                command, working_dir=self._working_dir
            )

            duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

            try:
                await self._emitter.emit(
                    TraceEvent(
                        event_type=(
                            TraceEventType.OPERATION_COMPLETE
                            if result.success
                            else TraceEventType.OPERATION_ERROR
                        ),
                        component=TraceComponent.WORKER,
                        level=TraceLevel.INFO if result.success else TraceLevel.ERROR,
                        message="Terminal execution completed",
                        data={
                            "skill": "terminal",
                            "command": command,
                            "return_code": result.return_code,
                            "stdout_length": len(result.stdout),
                            "stderr_length": len(result.stderr),
                            "sandboxed": result.sandboxed,
                        },
                        duration_ms=duration_ms,
                    )
                )
            except Exception:
                # Trace emission failure - non-critical, continue
                pass

            return {
                "success": result.success,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.return_code,
                "error": result.error,
                "sandboxed": result.sandboxed,
            }

        except Exception as e:
            try:
                await self._emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.WORKER,
                        level=TraceLevel.ERROR,
                        message="Terminal execution failed",
                        data={
                            "skill": "terminal",
                            "command": command,
                            "error": str(e),
                        },
                        duration_ms=int(
                            (asyncio.get_event_loop().time() - start_time) * 1000
                        ),
                    )
                )
            except Exception:
                # Trace emission failure - non-critical, continue
                pass
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "return_code": -1,
                "error": str(e),
            }
