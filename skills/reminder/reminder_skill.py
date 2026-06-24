"""
Reminder Skill - Postgres-backed reminders via MemoryRouter.

Single responsibility: Manage reminders stored in MemoryRouter with approval gating.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from core.observability import (
    TraceComponent,
    TraceEventType,
    TraceLevel,
    TraceEvent,
    TraceEmitter,
    MemoryTraceEmitter,
)
from core.approval_gate import ApprovalGate, ApprovalRequest, ApprovalActionType
from core.memory_router import MemoryRouter
from core.exceptions import SkillExecutionError


class ReminderSkill:
    """Skill for reminder operations via MemoryRouter."""

    def __init__(
        self,
        memory_router: MemoryRouter,
        emitter: TraceEmitter | None = None,
        approval_gate: ApprovalGate | None = None,
    ) -> None:
        """Initialize the reminder skill.

        Args:
            memory_router: MemoryRouter for persistence
            emitter: Trace emitter for observability
            approval_gate: Optional approval gate for create operations
        """
        self._emitter = emitter or MemoryTraceEmitter()
        self._approval_gate = approval_gate
        self._memory_router = memory_router

    async def create(self, text: str, due_at: str, channel: str = "console") -> str:
        """
        Create a new reminder.

        Args:
            text: Reminder message
            due_at: Due time as ISO 8601 string
            channel: Delivery channel ("telegram" or "console", default "console")

        Returns:
            The reminder ID

        Raises:
            SkillExecutionError: On storage failure
        """
        start_time = 0.0
        try:
            import asyncio
            start_time = asyncio.get_event_loop().time()
        except Exception:
            # Event loop timing failure - non-critical, continue
            pass

        try:
            await self._emitter.emit(TraceEvent(
                event_type=TraceEventType.COMPONENT_START,
                component=TraceComponent.WORKER,
                level=TraceLevel.INFO,
                message="Reminder create started",
                data={"due_at": due_at, "channel": channel},
                duration_ms=0,
            ))
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        # Request approval if gate is present (optional for create)
        if self._approval_gate is not None:
            try:
                request = ApprovalRequest(
                    request_id=str(uuid4()),
                    task_id=str(uuid4()),
                    session_id="default",
                    action_type=ApprovalActionType.FILE_WRITE,
                    action_description=f"Create reminder: {text}",
                    action_parameters={"text": text, "due_at": due_at, "channel": channel},
                    risk_level="low",
                    reason_for_approval="Reminder creation is low-risk but requires tracking",
                    expires_at=datetime.now(timezone.utc) + timedelta(seconds=300),
                )
                response = await self._approval_gate.request_approval(request)
                if not response.approved:
                    duration_ms = 0
                    try:
                        duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
                    except Exception:
                        # Event loop timing failure - non-critical, continue
                        pass
                    
                    try:
                        await self._emitter.emit(TraceEvent(
                            event_type=TraceEventType.OPERATION_COMPLETE,
                            component=TraceComponent.WORKER,
                            level=TraceLevel.WARNING,
                            message="Reminder create denied by approval gate",
                            data={"text": text, "reason": response.decision_reason},
                            duration_ms=duration_ms,
                        ))
                    except Exception:
                        # Trace emission failure - non-critical, continue
                        pass
                    
                    raise SkillExecutionError(f"Approval denied: {response.decision_reason}")
            except SkillExecutionError:
                raise
            except Exception as e:
                duration_ms = 0
                try:
                    duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
                except Exception:
                    # Event loop timing failure - non-critical, continue
                    pass
                
                try:
                    await self._emitter.emit(TraceEvent(
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.WORKER,
                        level=TraceLevel.ERROR,
                        message="Reminder create approval request failed",
                        data={"error": str(e)},
                        duration_ms=duration_ms,
                    ))
                except Exception:
                    # Trace emission failure - non-critical, continue
                    pass
                
                raise SkillExecutionError(f"Approval request failed: {str(e)}")

        try:
            reminder_id = str(uuid4())
            reminder = {
                "id": reminder_id,
                "text": text,
                "due_at": due_at,
                "delivered": False,
                "channel": channel,
            }
            
            await self._memory_router.scoped_write("reminders", f"reminders:{reminder_id}", reminder)
            
            duration_ms = 0
            try:
                duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            except Exception:
                # Event loop timing failure - non-critical, continue
                pass
            
            try:
                await self._emitter.emit(TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.INFO,
                    message="Reminder create completed",
                    data={"due_at": due_at, "channel": channel},
                    duration_ms=duration_ms,
                ))
            except Exception:
                # Trace emission failure - non-critical, continue
                pass
            
            return reminder_id
            
        except Exception as e:
            duration_ms = 0
            try:
                duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            except Exception:
                # Event loop timing failure - non-critical, continue
                pass
            
            try:
                await self._emitter.emit(TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.ERROR,
                    message="Reminder create failed",
                    data={"error": str(e)},
                    duration_ms=duration_ms,
                ))
            except Exception:
                # Trace emission failure - non-critical, continue
                pass
            
            raise SkillExecutionError(f"Failed to create reminder: {str(e)}")

    async def list_pending(self) -> list[dict]:
        """
        List all pending (undelivered) reminders.

        Returns:
            List of reminder dicts sorted by due_at ascending

        Raises:
            SkillExecutionError: On storage failure
        """
        start_time = 0.0
        try:
            import asyncio
            start_time = asyncio.get_event_loop().time()
        except Exception:
            # Event loop timing failure - non-critical, continue
            pass

        try:
            await self._emitter.emit(TraceEvent(
                event_type=TraceEventType.COMPONENT_START,
                component=TraceComponent.WORKER,
                level=TraceLevel.INFO,
                message="Reminder list_pending started",
                data={},
                duration_ms=0,
            ))
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        try:
            reminders = await self._memory_router.scoped_read("reminders", "reminders:*")
            
            # Narrow type: scoped_read returns dict | list | None, but list_pending expects list
            if not isinstance(reminders, list):
                reminders = []
            
            # Filter to undelivered reminders
            pending = [r for r in reminders if isinstance(r, dict) and not r.get("delivered", False)]
            
            # Sort by due_at
            pending.sort(key=lambda r: r["due_at"])
            
            duration_ms = 0
            try:
                duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            except Exception:
                # Event loop timing failure - non-critical, continue
                pass
            
            try:
                await self._emitter.emit(TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.INFO,
                    message="Reminder list_pending completed",
                    data={"pending_count": len(pending)},
                    duration_ms=duration_ms,
                ))
            except Exception:
                # Trace emission failure - non-critical, continue
                pass
            
            return pending
            
        except Exception as e:
            duration_ms = 0
            try:
                duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            except Exception:
                # Event loop timing failure - non-critical, continue
                pass
            
            try:
                await self._emitter.emit(TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.ERROR,
                    message="Reminder list_pending failed",
                    data={"error": str(e)},
                    duration_ms=duration_ms,
                ))
            except Exception:
                # Trace emission failure - non-critical, continue
                pass
            
            raise SkillExecutionError(f"Failed to list reminders: {str(e)}")

    async def mark_delivered(self, reminder_id: str) -> bool:
        """
        Mark a reminder as delivered.

        Args:
            reminder_id: Reminder ID to mark as delivered

        Returns:
            True if found and marked, False if not found

        Raises:
            SkillExecutionError: On storage failure
        """
        start_time = 0.0
        try:
            import asyncio
            start_time = asyncio.get_event_loop().time()
        except Exception:
            # Event loop timing failure - non-critical, continue
            pass

        try:
            await self._emitter.emit(TraceEvent(
                event_type=TraceEventType.COMPONENT_START,
                component=TraceComponent.WORKER,
                level=TraceLevel.INFO,
                message="Reminder mark_delivered started",
                data={"reminder_id": reminder_id},
                duration_ms=0,
            ))
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        try:
            reminder = await self._memory_router.scoped_read("reminders", f"reminders:{reminder_id}")
            
            # Narrow type: scoped_read returns dict | list | None, but mark_delivered expects dict | None
            if isinstance(reminder, list):
                reminder = None
            
            if not reminder:
                duration_ms = 0
                try:
                    duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
                except Exception:
                    # Event loop timing failure - non-critical, continue
                    pass
                
                try:
                    await self._emitter.emit(TraceEvent(
                        event_type=TraceEventType.OPERATION_COMPLETE,
                        component=TraceComponent.WORKER,
                        level=TraceLevel.INFO,
                        message="Reminder mark_delivered completed",
                        data={"reminder_id": reminder_id, "found": False},
                        duration_ms=duration_ms,
                    ))
                except Exception:
                    # Trace emission failure - non-critical, continue
                    pass
                
                return False
            
            # Ensure reminder is dict for dict-style access
            if isinstance(reminder, list):
                reminder = reminder[0] if reminder else {"id": reminder_id}
            
            reminder["delivered"] = True
            await self._memory_router.scoped_write("reminders", f"reminders:{reminder_id}", reminder)
            
            duration_ms = 0
            try:
                duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            except Exception:
                # Event loop timing failure - non-critical, continue
                pass
            
            try:
                await self._emitter.emit(TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.INFO,
                    message="Reminder mark_delivered completed",
                    data={"reminder_id": reminder_id, "found": True},
                    duration_ms=duration_ms,
                ))
            except Exception:
                # Trace emission failure - non-critical, continue
                pass
            
            return True
            
        except Exception as e:
            duration_ms = 0
            try:
                duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            except Exception:
                # Event loop timing failure - non-critical, continue
                pass
            
            try:
                await self._emitter.emit(TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.ERROR,
                    message="Reminder mark_delivered failed",
                    data={"error": str(e)},
                    duration_ms=duration_ms,
                ))
            except Exception:
                # Trace emission failure - non-critical, continue
                pass
            
            raise SkillExecutionError(f"Failed to mark reminder delivered: {str(e)}")

    async def get_due(self) -> list[dict]:
        """
        Get all pending reminders that are due (due_at <= now).

        Returns:
            List of reminder dicts that are due and not yet delivered

        Raises:
            SkillExecutionError: On storage failure
        """
        try:
            reminders = await self.list_pending()
            
            now = datetime.now(timezone.utc).isoformat()
            due = [r for r in reminders if r["due_at"] <= now]
            
            return due
            
        except Exception as e:
            raise SkillExecutionError(f"Failed to get due reminders: {str(e)}")
