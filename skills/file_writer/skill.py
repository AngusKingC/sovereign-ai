"""
File Writer Skill - writes content to local files with configurable mode.

Single responsibility: Write content to local filesystem with approval gate.
"""

from typing import TYPE_CHECKING
from uuid import uuid4
from datetime import datetime, timezone

from core.observability import (
    TraceComponent,
    TraceEventType,
    TraceLevel,
    TraceEmitter,
    TraceEvent,
    NullTraceEmitter,
)
from core.approval_gate import ApprovalGate, ApprovalRequest, ApprovalActionType

if TYPE_CHECKING:
    pass


class FileWriterSkill:
    """Skill for writing content to local files."""

    def __init__(
        self,
        approval_gate: ApprovalGate | None = None,
        emitter: TraceEmitter | None = None,
    ) -> None:
        """Initialize the file writer skill.
        
        Args:
            approval_gate: ApprovalGate instance for authorization
            emitter: TraceEmitter for observability
        """
        self.approval_gate = approval_gate
        self.emitter = emitter if emitter is not None else NullTraceEmitter()

    async def execute(
        self,
        path: str,
        content: str,
        mode: str = "write",
        session_id: str = "default",
        task_id: str = "unknown",
    ) -> tuple[bool, int]:
        """
        Write content to file.

        Args:
            path: Path to the file to write
            content: Content to write to the file
            mode: File write mode, defaults to 'write'
            session_id: Session identifier for approval scope checking
            task_id: Task identifier for approval requests

        Returns:
            Tuple of (success: bool, bytes_written: int)

        Raises:
            ValueError: If path or content is invalid
            IOError: If file cannot be written
        """
        if not path or not isinstance(path, str):
            raise ValueError("Path must be a non-empty string")
        if not isinstance(content, str):
            raise ValueError("Content must be a string")

        # Check approval scope first
        if self.approval_gate:
            has_scope = await self.approval_gate.check_scope(
                session_id=session_id,
                action_type="file_write",
                parameters={"path": path}
            )
            
            if not has_scope:
                # Request approval
                from datetime import timedelta
                
                request = ApprovalRequest(
                    request_id=f"apr_{uuid4().hex}",
                    task_id=task_id,
                    session_id=session_id,
                    action_type=ApprovalActionType.FILE_WRITE,
                    action_description=f"Write to file: {path}",
                    action_parameters={"path": path, "mode": mode},
                    risk_level="medium",
                    reason_for_approval="File write requires approval",
                    expires_at=datetime.now(timezone.utc) + timedelta(seconds=300),
                )
                
                try:
                    response = await self.approval_gate.request_approval(request)
                    if not response.approved:
                        try:
                            await self.emitter.emit(TraceEvent(
                                event_id=uuid4(),
                                timestamp=datetime.now(timezone.utc),
                                event_type=TraceEventType.OPERATION_COMPLETE,
                                component=TraceComponent.WORKER,
                                level=TraceLevel.WARNING,
                                message="File write approval denied",
                                data={
                                    "skill": "file_writer",
                                    "path": path,
                                    "mode": mode,
                                    "error": "Approval denied",
                                },
                                duration_ms=0,
                            ))
                        except Exception:
                            # Trace emission failure - non-critical, continue
                            pass
                        return False, 0
                except Exception:
                    # Approval gate error - deny by default
                    try:
                        await self.emitter.emit(TraceEvent(
                            event_id=uuid4(),
                            timestamp=datetime.now(timezone.utc),
                            event_type=TraceEventType.OPERATION_ERROR,
                            component=TraceComponent.WORKER,
                            level=TraceLevel.ERROR,
                            message="File write approval gate error",
                            data={
                                "skill": "file_writer",
                                "path": path,
                                "mode": mode,
                                "error": "Approval gate error",
                            },
                            duration_ms=0,
                        ))
                    except Exception:
                        # Trace emission failure - non-critical, continue
                        pass
                    return False, 0

        try:
            import aiofiles

            write_mode = "w" if mode == "write" else "a"
            async with aiofiles.open(path, mode=write_mode, encoding="utf-8") as file:
                bytes_written = await file.write(content)

            try:
                await self.emitter.emit(TraceEvent(
                    event_id=uuid4(),
                    timestamp=datetime.now(timezone.utc),
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.INFO,
                    message=f"File write successful: {path}",
                    data={
                        "skill": "file_writer",
                        "path": path,
                        "mode": mode,
                        "bytes_written": bytes_written,
                    },
                    duration_ms=0,
                ))
            except Exception:
                # Trace emission failure - non-critical, continue
                pass

            return True, bytes_written

        except IOError as e:
            try:
                await self.emitter.emit(TraceEvent(
                    event_id=uuid4(),
                    timestamp=datetime.now(timezone.utc),
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.ERROR,
                    message=f"File write failed: {str(e)}",
                    data={
                        "skill": "file_writer",
                        "path": path,
                        "error": str(e),
                    },
                    duration_ms=0,
                ))
            except Exception:
                # Trace emission failure - non-critical, continue
                pass
            raise
