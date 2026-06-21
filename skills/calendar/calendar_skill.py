"""
Calendar Skill - ICS file operations for local calendar management.

Single responsibility: Read and write ICS calendar files with approval gating.
"""

import os
from datetime import datetime, timedelta
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
from core.exceptions import SkillExecutionError


class CalendarSkill:
    """Skill for calendar operations via ICS files."""

    def __init__(
        self,
        emitter: TraceEmitter | None = None,
        approval_gate: ApprovalGate | None = None,
        calendar_path: str | None = None,
    ) -> None:
        """Initialize the calendar skill.

        Args:
            emitter: Trace emitter for observability
            approval_gate: Optional approval gate for write operations
            calendar_path: Path to ICS file (loaded from CALENDAR_ICS_PATH env var if None)
        """
        self._emitter = emitter or MemoryTraceEmitter()
        self._approval_gate = approval_gate
        self._calendar_path = calendar_path or os.getenv("CALENDAR_ICS_PATH")

    async def get_upcoming(self, days: int = 7) -> list[dict]:
        """
        Get upcoming events from the ICS file.

        Args:
            days: Number of days to look ahead (default 7)

        Returns:
            List of event dicts with keys: uid, summary, start, end, location, description

        Raises:
            SkillExecutionError: If file not found or parse fails
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
                message="Calendar get_upcoming started",
                data={"days": days},
                duration_ms=0,
            ))
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        if not self._calendar_path:
            raise SkillExecutionError("CALENDAR_ICS_PATH environment variable not set")

        try:
            import asyncio
            from icalendar import Calendar

            loop = asyncio.get_event_loop()
            
            # Read ICS file
            ics_content = await loop.run_in_executor(
                None,
                lambda: open(self._calendar_path, "rb").read()
            )
            
            # Parse ICS
            calendar = await loop.run_in_executor(
                None,
                lambda: Calendar.from_ical(ics_content)
            )
            
            # Get current time and end time
            now = datetime.utcnow().replace(tzinfo=None)
            end_time = now + timedelta(days=days)
            
            # Extract events
            events = []
            for component in calendar.walk():
                if component.name == "VEVENT":
                    start_dt = component.get("dtstart").dt
                    end_dt = component.get("dtend").dt
                    
                    # Handle timezone-aware datetimes by stripping timezone info
                    if hasattr(start_dt, 'tzinfo') and start_dt.tzinfo is not None:
                        start_dt = start_dt.replace(tzinfo=None)
                    if hasattr(end_dt, 'tzinfo') and end_dt.tzinfo is not None:
                        end_dt = end_dt.replace(tzinfo=None)
                    
                    # Filter to events within the time window
                    if start_dt >= now and start_dt <= end_time:
                        events.append({
                            "uid": str(component.get("uid")),
                            "summary": str(component.get("summary", "")),
                            "start": start_dt.isoformat(),
                            "end": end_dt.isoformat(),
                            "location": str(component.get("location", "")),
                            "description": str(component.get("description", "")),
                        })
            
            # Sort by start time
            events.sort(key=lambda e: e["start"])
            
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
                    message="Calendar get_upcoming completed",
                    data={"days": days, "event_count": len(events)},
                    duration_ms=duration_ms,
                ))
            except Exception:
                # Trace emission failure - non-critical, continue
                pass
            
            return events
            
        except FileNotFoundError:
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
                    message="Calendar get_upcoming failed",
                    data={"error": "File not found"},
                    duration_ms=duration_ms,
                ))
            except Exception:
                # Trace emission failure - non-critical, continue
                pass
            
            raise SkillExecutionError(f"Calendar file not found: {self._calendar_path}")
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
                    message="Calendar get_upcoming failed",
                    data={"error": str(e)},
                    duration_ms=duration_ms,
                ))
            except Exception:
                # Trace emission failure - non-critical, continue
                pass
            
            raise SkillExecutionError(f"Failed to parse calendar: {str(e)}")

    async def create_event(self, summary: str, start: str, end: str, location: str = "", description: str = "") -> str:
        """
        Create a new event in the ICS file.

        Args:
            summary: Event summary/title
            start: Start time as ISO 8601 string
            end: End time as ISO 8601 string
            location: Event location (default "")
            description: Event description (default "")

        Returns:
            The new event's UID

        Raises:
            SkillExecutionError: On write failure or approval denial
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
                message="Calendar create_event started",
                data={"summary": summary, "start": start},
                duration_ms=0,
            ))
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        # Check approval gate
        if self._approval_gate is None:
            raise SkillExecutionError("Approval gate not injected — writing without approval is not permitted")
        
        # Request approval
        try:
            request = ApprovalRequest(
                request_id=str(uuid4()),
                task_id=str(uuid4()),
                session_id="default",
                action_type=ApprovalActionType.FILE_WRITE,
                action_description=f"Create calendar event: {summary}",
                action_parameters={"summary": summary, "start": start, "end": end},
                risk_level="medium",
                reason_for_approval="Calendar events modify stored data",
                expires_at=datetime.utcnow() + timedelta(seconds=300),
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
                        message="Calendar create_event denied by approval gate",
                        data={"summary": summary, "reason": response.decision_reason},
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
                    message="Calendar create_event approval request failed",
                    data={"error": str(e)},
                    duration_ms=duration_ms,
                ))
            except Exception:
                # Trace emission failure - non-critical, continue
                pass
            
            raise SkillExecutionError(f"Approval request failed: {str(e)}")

        if not self._calendar_path:
            raise SkillExecutionError("CALENDAR_ICS_PATH environment variable not set")

        try:
            import asyncio
            from icalendar import Calendar, Event

            loop = asyncio.get_event_loop()
            
            # Read existing ICS file or create new
            try:
                ics_content = await loop.run_in_executor(
                    None,
                    lambda: open(self._calendar_path, "rb").read()
                )
                calendar = await loop.run_in_executor(
                    None,
                    lambda: Calendar.from_ical(ics_content)
                )
            except FileNotFoundError:
                calendar = Calendar()
                calendar.add("prodid", "-//Sovereign AI//Calendar Skill//EN")
                calendar.add("version", "2.0")
            
            # Create new event
            event = Event()
            event.add("uid", str(uuid4()))
            event.add("summary", summary)
            event.add("dtstart", datetime.fromisoformat(start))
            event.add("dtend", datetime.fromisoformat(end))
            if location:
                event.add("location", location)
            if description:
                event.add("description", description)
            event.add("dtstamp", datetime.utcnow())
            
            # Add to calendar
            calendar.add_component(event)
            
            # Write back to file
            ics_content = calendar.to_ical()
            await loop.run_in_executor(
                None,
                lambda: open(self._calendar_path, "wb").write(ics_content)
            )
            
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
                    message="Calendar create_event completed",
                    data={"summary": summary, "start": start},
                    duration_ms=duration_ms,
                ))
            except Exception:
                # Trace emission failure - non-critical, continue
                pass
            
            return str(event.get("uid"))
            
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
                    message="Calendar create_event failed",
                    data={"error": str(e)},
                    duration_ms=duration_ms,
                ))
            except Exception:
                # Trace emission failure - non-critical, continue
                pass
            
            raise SkillExecutionError(f"Failed to create event: {str(e)}")

    async def cancel_event(self, uid: str) -> bool:
        """
        Cancel an event by setting its STATUS to CANCELLED.

        Args:
            uid: Event UID to cancel

        Returns:
            True if found and cancelled, False if UID not found

        Raises:
            SkillExecutionError: On write failure or approval denial
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
                message="Calendar cancel_event started",
                data={"uid": uid},
                duration_ms=0,
            ))
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        # Check approval gate
        if self._approval_gate is None:
            raise SkillExecutionError("Approval gate not injected — modifying without approval is not permitted")
        
        # Request approval
        try:
            request = ApprovalRequest(
                request_id=str(uuid4()),
                task_id=str(uuid4()),
                session_id="default",
                action_type=ApprovalActionType.FILE_WRITE,
                action_description=f"Cancel calendar event: {uid}",
                action_parameters={"uid": uid},
                risk_level="medium",
                reason_for_approval="Calendar events modify stored data",
                expires_at=datetime.utcnow() + timedelta(seconds=300),
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
                        message="Calendar cancel_event denied by approval gate",
                        data={"uid": uid, "reason": response.decision_reason},
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
                    message="Calendar cancel_event approval request failed",
                    data={"error": str(e)},
                    duration_ms=duration_ms,
                ))
            except Exception:
                # Trace emission failure - non-critical, continue
                pass
            
            raise SkillExecutionError(f"Approval request failed: {str(e)}")

        if not self._calendar_path:
            raise SkillExecutionError("CALENDAR_ICS_PATH environment variable not set")

        try:
            import asyncio
            from icalendar import Calendar

            loop = asyncio.get_event_loop()
            
            # Read ICS file
            ics_content = await loop.run_in_executor(
                None,
                lambda: open(self._calendar_path, "rb").read()
            )
            
            calendar = await loop.run_in_executor(
                None,
                lambda: Calendar.from_ical(ics_content)
            )
            
            # Find and cancel event
            found = False
            for component in calendar.walk():
                if component.name == "VEVENT":
                    if str(component.get("uid")) == uid:
                        component.add("status", "CANCELLED")
                        found = True
                        break
            
            if not found:
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
                        message="Calendar cancel_event completed",
                        data={"uid": uid, "found": False},
                        duration_ms=duration_ms,
                    ))
                except Exception:
                    # Trace emission failure - non-critical, continue
                    pass
                
                return False
            
            # Write back to file
            ics_content = calendar.to_ical()
            await loop.run_in_executor(
                None,
                lambda: open(self._calendar_path, "wb").write(ics_content)
            )
            
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
                    message="Calendar cancel_event completed",
                    data={"uid": uid, "found": True},
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
                    message="Calendar cancel_event failed",
                    data={"error": str(e)},
                    duration_ms=duration_ms,
                ))
            except Exception:
                # Trace emission failure - non-critical, continue
                pass
            
            raise SkillExecutionError(f"Failed to cancel event: {str(e)}")
