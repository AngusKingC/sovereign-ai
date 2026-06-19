"""
Code Execution Skill - executes Python code in a subprocess.

Single responsibility: Execute Python code with approval gating and timeout handling.
"""

import asyncio
from typing import Any

from core.observability import (
    TraceComponent,
    TraceEventType,
    TraceLevel,
    TraceEvent,
    TraceEmitter,
    MemoryTraceEmitter,
)
from core.approval_gate import ApprovalGate, ApprovalRequest, ApprovalResponse, ApprovalActionType


class CodeExecutionSkill:
    """Skill for executing Python code."""

    def __init__(
        self,
        approval_gate: ApprovalGate | None = None,
        emitter: TraceEmitter | None = None,
        timeout: int = 30,
    ) -> None:
        """Initialize the code execution skill.

        Args:
            approval_gate: Optional approval gate for code execution authorization
            emitter: Trace emitter for observability
            timeout: Code execution timeout in seconds (default 30)
        """
        self._emitter = emitter or MemoryTraceEmitter()
        self._approval_gate = approval_gate
        self._timeout = timeout

    async def execute(self, code: str, **kwargs) -> dict[str, Any]:
        """
        Execute Python code.

        Args:
            code: The Python code to execute
            **kwargs: Additional parameters (not used)

        Returns:
            SkillResult dict with success, stdout, stderr, return_code, error fields

        Raises:
            ValueError: If code is empty
        """
        if not code or not isinstance(code, str):
            raise ValueError("Code must be a non-empty string")

        start_time = asyncio.get_event_loop().time()

        try:
            await self._emitter.emit(TraceEvent(
                event_type=TraceEventType.COMPONENT_START,
                component=TraceComponent.WORKER,
                level=TraceLevel.INFO,
                message="Code execution started",
                data={
                    "skill": "code_execution",
                    "code_length": len(code),
                },
                duration_ms=0,
            ))
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        # Request approval if gate is present
        if self._approval_gate is not None:
            try:
                from datetime import datetime, timedelta
                from uuid import uuid4

                request = ApprovalRequest(
                    request_id=str(uuid4()),
                    task_id=str(uuid4()),
                    session_id="default",
                    action_type=ApprovalActionType.SHELL_COMMAND,
                    action_description=f"Execute Python code",
                    action_parameters={"code_length": len(code)},
                    risk_level="high",
                    reason_for_approval="Code execution can modify system state",
                    expires_at=datetime.utcnow() + timedelta(seconds=300),
                )
                response = await self._approval_gate.request_approval(request)
                if not response.approved:
                    try:
                        await self._emitter.emit(TraceEvent(
                            event_type=TraceEventType.OPERATION_COMPLETE,
                            component=TraceComponent.WORKER,
                            level=TraceLevel.WARNING,
                            message="Code execution denied by approval gate",
                            data={
                                "skill": "code_execution",
                                "reason": response.decision_reason,
                            },
                            duration_ms=int((asyncio.get_event_loop().time() - start_time) * 1000),
                        ))
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
                # If approval request fails, deny execution
                try:
                    await self._emitter.emit(TraceEvent(
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.WORKER,
                        level=TraceLevel.ERROR,
                        message="Code execution approval request failed",
                        data={
                            "skill": "code_execution",
                        },
                        duration_ms=int((asyncio.get_event_loop().time() - start_time) * 1000),
                    ))
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

        # Execute code in subprocess
        try:
            process = await asyncio.create_subprocess_shell(
                "python -c \"" + code.replace('"', '\\"') + "\"",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self._timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                try:
                    await self._emitter.emit(TraceEvent(
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.WORKER,
                        level=TraceLevel.ERROR,
                        message="Code execution timed out",
                        data={
                            "skill": "code_execution",
                            "timeout": self._timeout,
                        },
                        duration_ms=int((asyncio.get_event_loop().time() - start_time) * 1000),
                    ))
                except Exception:
                    # Trace emission failure - non-critical, continue
                    pass
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "",
                    "return_code": -1,
                    "error": "Execution timed out",
                }

            stdout_text = stdout.decode("utf-8", errors="replace")
            stderr_text = stderr.decode("utf-8", errors="replace")
            return_code = process.returncode

            duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

            try:
                await self._emitter.emit(TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.INFO,
                    message="Code execution completed",
                    data={
                        "skill": "code_execution",
                        "return_code": return_code,
                        "stdout_length": len(stdout_text),
                        "stderr_length": len(stderr_text),
                    },
                    duration_ms=duration_ms,
                ))
            except Exception:
                # Trace emission failure - non-critical, continue
                pass

            return {
                "success": return_code == 0,
                "stdout": stdout_text,
                "stderr": stderr_text,
                "return_code": return_code,
                "error": None if return_code == 0 else f"Code failed with return code {return_code}",
            }

        except Exception as e:
            try:
                await self._emitter.emit(TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.ERROR,
                    message="Code execution failed",
                    data={
                        "skill": "code_execution",
                        "error": str(e),
                    },
                    duration_ms=int((asyncio.get_event_loop().time() - start_time) * 1000),
                ))
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
