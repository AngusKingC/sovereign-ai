"""
Notes Skill - Postgres-backed notes via MemoryRouter.

Single responsibility: Manage notes stored in MemoryRouter with approval gating.
"""

import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from core.approval_gate import ApprovalActionType, ApprovalGate, ApprovalRequest
from core.exceptions import SkillExecutionError
from core.memory_router import MemoryRouter
from core.observability import (
    MemoryTraceEmitter,
    TraceComponent,
    TraceEmitter,
    TraceEvent,
    TraceEventType,
    TraceLevel,
)

logger = logging.getLogger(__name__)


class NotesSkill:
    """Skill for notes operations via MemoryRouter."""

    def __init__(
        self,
        memory_router: MemoryRouter,
        emitter: TraceEmitter | None = None,
        approval_gate: ApprovalGate | None = None,
    ) -> None:
        """Initialize the notes skill.

        Args:
            memory_router: MemoryRouter for persistence
            emitter: Trace emitter for observability
            approval_gate: Optional approval gate for create/update/delete operations
        """
        self._emitter = emitter or MemoryTraceEmitter()
        self._approval_gate = approval_gate
        self._memory_router = memory_router

    async def create(
        self, title: str, content: str, tags: list[str] | None = None
    ) -> str:
        """
        Create a new note.

        Args:
            title: Note title
            content: Note content
            tags: Optional list of tags (default [])

        Returns:
            The note ID

        Raises:
            SkillExecutionError: On storage failure or approval denial
        """
        start_time = 0.0
        try:
            import asyncio

            start_time = asyncio.get_event_loop().time()
        except Exception as e:
            # Event loop timing failure - non-critical, continue
            logger.warning("AR18: event loop timing failed: %s", e, exc_info=True)

        try:
            await self._emitter.emit(
                TraceEvent(
                    event_type=TraceEventType.COMPONENT_START,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.INFO,
                    message="Notes create started",
                    data={"title": title, "tags": tags or []},
                    duration_ms=0,
                )
            )
        except Exception as e:
            # Trace emission failure - non-critical, continue
            logger.warning("AR18: trace emission failed: %s", e, exc_info=True)

        # Request approval if gate is present
        if self._approval_gate is not None:
            try:
                request = ApprovalRequest(
                    request_id=str(uuid4()),
                    task_id=str(uuid4()),
                    session_id="default",
                    action_type=ApprovalActionType.FILE_WRITE,
                    action_description=f"Create note: {title}",
                    action_parameters={"title": title, "tags": tags or []},
                    risk_level="low",
                    reason_for_approval="Note creation is low-risk but requires tracking",
                    expires_at=datetime.now(timezone.utc) + timedelta(seconds=300),
                )
                response = await self._approval_gate.request_approval(request)
                if not response.approved:
                    duration_ms = 0
                    try:
                        duration_ms = int(
                            (asyncio.get_event_loop().time() - start_time) * 1000
                        )
                    except Exception:
                        # Event loop timing failure - non-critical, continue
                        pass

                    try:
                        await self._emitter.emit(
                            TraceEvent(
                                event_type=TraceEventType.OPERATION_COMPLETE,
                                component=TraceComponent.WORKER,
                                level=TraceLevel.WARNING,
                                message="Notes create denied by approval gate",
                                data={
                                    "title": title,
                                    "reason": response.decision_reason,
                                },
                                duration_ms=duration_ms,
                            )
                        )
                    except Exception:
                        # Trace emission failure - non-critical, continue
                        pass

                    raise SkillExecutionError(
                        f"Approval denied: {response.decision_reason}"
                    )
            except SkillExecutionError:
                raise
            except Exception as e:
                duration_ms = 0
                try:
                    duration_ms = int(
                        (asyncio.get_event_loop().time() - start_time) * 1000
                    )
                except Exception:
                    # Event loop timing failure - non-critical, continue
                    pass

                try:
                    await self._emitter.emit(
                        TraceEvent(
                            event_type=TraceEventType.OPERATION_ERROR,
                            component=TraceComponent.WORKER,
                            level=TraceLevel.ERROR,
                            message="Notes create approval request failed",
                            data={"error": str(e)},
                            duration_ms=duration_ms,
                        )
                    )
                except Exception:
                    # Trace emission failure - non-critical, continue
                    pass

                raise SkillExecutionError(f"Approval request failed: {str(e)}")

        try:
            note_id = str(uuid4())
            note = {
                "id": note_id,
                "title": title,
                "content": content,
                "tags": tags or [],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

            await self._memory_router.scoped_write("notes", f"notes:{note_id}", note)

            duration_ms = 0
            try:
                duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            except Exception:
                # Event loop timing failure - non-critical, continue
                pass

            try:
                await self._emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.OPERATION_COMPLETE,
                        component=TraceComponent.WORKER,
                        level=TraceLevel.INFO,
                        message="Notes create completed",
                        data={"title": title},
                        duration_ms=duration_ms,
                    )
                )
            except Exception:
                # Trace emission failure - non-critical, continue
                pass

            return note_id

        except Exception as e:
            duration_ms = 0
            try:
                duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            except Exception:
                # Event loop timing failure - non-critical, continue
                pass

            try:
                await self._emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.WORKER,
                        level=TraceLevel.ERROR,
                        message="Notes create failed",
                        data={"error": str(e)},
                        duration_ms=duration_ms,
                    )
                )
            except Exception:
                # Trace emission failure - non-critical, continue
                pass

            raise SkillExecutionError(f"Failed to create note: {str(e)}")

    async def list_all(self) -> list[dict]:
        """
        List all notes.

        Returns:
            List of note dicts sorted by updated_at descending

        Raises:
            SkillExecutionError: On storage failure
        """
        start_time = 0.0
        try:
            import asyncio

            start_time = asyncio.get_event_loop().time()
        except Exception as e:
            # Event loop timing failure - non-critical, continue
            logger.warning("AR18: event loop timing failed: %s", e, exc_info=True)

        try:
            await self._emitter.emit(
                TraceEvent(
                    event_type=TraceEventType.COMPONENT_START,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.INFO,
                    message="Notes list_all started",
                    data={},
                    duration_ms=0,
                )
            )
        except Exception as e:
            # Trace emission failure - non-critical, continue
            logger.warning("AR18: trace emission failed: %s", e, exc_info=True)

        try:
            notes = await self._memory_router.scoped_read("notes", "notes:*")

            # Narrow type: scoped_read returns dict | list | None, but list_all expects list
            if not isinstance(notes, list):
                notes = []

            # Sort by updated_at descending
            notes.sort(key=lambda n: n["updated_at"], reverse=True)

            duration_ms = 0
            try:
                duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            except Exception:
                # Event loop timing failure - non-critical, continue
                pass

            try:
                await self._emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.OPERATION_COMPLETE,
                        component=TraceComponent.WORKER,
                        level=TraceLevel.INFO,
                        message="Notes list_all completed",
                        data={"note_count": len(notes)},
                        duration_ms=duration_ms,
                    )
                )
            except Exception:
                # Trace emission failure - non-critical, continue
                pass

            return notes

        except Exception as e:
            duration_ms = 0
            try:
                duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            except Exception:
                # Event loop timing failure - non-critical, continue
                pass

            try:
                await self._emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.WORKER,
                        level=TraceLevel.ERROR,
                        message="Notes list_all failed",
                        data={"error": str(e)},
                        duration_ms=duration_ms,
                    )
                )
            except Exception:
                # Trace emission failure - non-critical, continue
                pass

            raise SkillExecutionError(f"Failed to list notes: {str(e)}")

    async def get(self, note_id: str) -> dict | None:
        """
        Get a note by ID.

        Args:
            note_id: Note ID to retrieve

        Returns:
            Note dict or None if not found

        Raises:
            SkillExecutionError: On storage failure
        """
        start_time = 0.0
        try:
            import asyncio

            start_time = asyncio.get_event_loop().time()
        except Exception as e:
            # Event loop timing failure - non-critical, continue
            logger.warning("AR18: event loop timing failed: %s", e, exc_info=True)

        try:
            await self._emitter.emit(
                TraceEvent(
                    event_type=TraceEventType.COMPONENT_START,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.INFO,
                    message="Notes get started",
                    data={"note_id": note_id},
                    duration_ms=0,
                )
            )
        except Exception as e:
            # Trace emission failure - non-critical, continue
            logger.warning("AR18: trace emission failed: %s", e, exc_info=True)

        try:
            note = await self._memory_router.scoped_read("notes", f"notes:{note_id}")

            # Narrow type: scoped_read returns dict | list | None, but get expects dict | None
            if isinstance(note, list):
                note = None

            duration_ms = 0
            try:
                duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            except Exception:
                # Event loop timing failure - non-critical, continue
                pass

            try:
                await self._emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.OPERATION_COMPLETE,
                        component=TraceComponent.WORKER,
                        level=TraceLevel.INFO,
                        message="Notes get completed",
                        data={"note_id": note_id, "found": note is not None},
                        duration_ms=duration_ms,
                    )
                )
            except Exception:
                # Trace emission failure - non-critical, continue
                pass

            return note

        except Exception as e:
            duration_ms = 0
            try:
                duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            except Exception:
                # Event loop timing failure - non-critical, continue
                pass

            try:
                await self._emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.WORKER,
                        level=TraceLevel.ERROR,
                        message="Notes get failed",
                        data={"error": str(e)},
                        duration_ms=duration_ms,
                    )
                )
            except Exception:
                # Trace emission failure - non-critical, continue
                pass

            raise SkillExecutionError(f"Failed to get note: {str(e)}")

    async def update(
        self,
        note_id: str,
        title: str | None = None,
        content: str | None = None,
        tags: list[str] | None = None,
    ) -> bool:
        """
        Update a note.

        Args:
            note_id: Note ID to update
            title: New title (optional)
            content: New content (optional)
            tags: New tags (optional)

        Returns:
            True if found and updated, False if not found

        Raises:
            SkillExecutionError: On storage failure or approval denial
        """
        start_time = 0.0
        try:
            import asyncio

            start_time = asyncio.get_event_loop().time()
        except Exception as e:
            # Event loop timing failure - non-critical, continue
            logger.warning("AR18: event loop timing failed: %s", e, exc_info=True)

        try:
            await self._emitter.emit(
                TraceEvent(
                    event_type=TraceEventType.COMPONENT_START,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.INFO,
                    message="Notes update started",
                    data={"note_id": note_id},
                    duration_ms=0,
                )
            )
        except Exception as e:
            # Trace emission failure - non-critical, continue
            logger.warning("AR18: trace emission failed: %s", e, exc_info=True)

        # Request approval if gate is present
        if self._approval_gate is not None:
            try:
                request = ApprovalRequest(
                    request_id=str(uuid4()),
                    task_id=str(uuid4()),
                    session_id="default",
                    action_type=ApprovalActionType.FILE_WRITE,
                    action_description=f"Update note: {note_id}",
                    action_parameters={
                        "note_id": note_id,
                        "title": title,
                        "tags": tags,
                    },
                    risk_level="low",
                    reason_for_approval="Note update is low-risk but requires tracking",
                    expires_at=datetime.now(timezone.utc) + timedelta(seconds=300),
                )
                response = await self._approval_gate.request_approval(request)
                if not response.approved:
                    duration_ms = 0
                    try:
                        duration_ms = int(
                            (asyncio.get_event_loop().time() - start_time) * 1000
                        )
                    except Exception:
                        # Event loop timing failure - non-critical, continue
                        pass

                    try:
                        await self._emitter.emit(
                            TraceEvent(
                                event_type=TraceEventType.OPERATION_COMPLETE,
                                component=TraceComponent.WORKER,
                                level=TraceLevel.WARNING,
                                message="Notes update denied by approval gate",
                                data={
                                    "note_id": note_id,
                                    "reason": response.decision_reason,
                                },
                                duration_ms=duration_ms,
                            )
                        )
                    except Exception:
                        # Trace emission failure - non-critical, continue
                        pass

                    raise SkillExecutionError(
                        f"Approval denied: {response.decision_reason}"
                    )
            except SkillExecutionError:
                raise
            except Exception as e:
                duration_ms = 0
                try:
                    duration_ms = int(
                        (asyncio.get_event_loop().time() - start_time) * 1000
                    )
                except Exception:
                    # Event loop timing failure - non-critical, continue
                    pass

                try:
                    await self._emitter.emit(
                        TraceEvent(
                            event_type=TraceEventType.OPERATION_ERROR,
                            component=TraceComponent.WORKER,
                            level=TraceLevel.ERROR,
                            message="Notes update approval request failed",
                            data={"error": str(e)},
                            duration_ms=duration_ms,
                        )
                    )
                except Exception:
                    # Trace emission failure - non-critical, continue
                    pass

                raise SkillExecutionError(f"Approval request failed: {str(e)}")

        try:
            note = await self._memory_router.scoped_read("notes", f"notes:{note_id}")

            if not note:
                duration_ms = 0
                try:
                    duration_ms = int(
                        (asyncio.get_event_loop().time() - start_time) * 1000
                    )
                except Exception:
                    # Event loop timing failure - non-critical, continue
                    pass

                try:
                    await self._emitter.emit(
                        TraceEvent(
                            event_type=TraceEventType.OPERATION_COMPLETE,
                            component=TraceComponent.WORKER,
                            level=TraceLevel.INFO,
                            message="Notes update completed",
                            data={"note_id": note_id, "found": False},
                            duration_ms=duration_ms,
                        )
                    )
                except Exception:
                    # Trace emission failure - non-critical, continue
                    pass

                return False

            # Ensure note is dict for dict-style access
            if isinstance(note, list):
                note = note[0] if note else {"id": note_id}

            if title is not None:
                note["title"] = title
            if content is not None:
                note["content"] = content
            if tags is not None:
                note["tags"] = tags
            note["updated_at"] = datetime.now(timezone.utc).isoformat()

            await self._memory_router.scoped_write("notes", f"notes:{note_id}", note)

            duration_ms = 0
            try:
                duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            except Exception:
                # Event loop timing failure - non-critical, continue
                pass

            try:
                await self._emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.OPERATION_COMPLETE,
                        component=TraceComponent.WORKER,
                        level=TraceLevel.INFO,
                        message="Notes update completed",
                        data={"note_id": note_id, "found": True},
                        duration_ms=duration_ms,
                    )
                )
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
                await self._emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.WORKER,
                        level=TraceLevel.ERROR,
                        message="Notes update failed",
                        data={"error": str(e)},
                        duration_ms=duration_ms,
                    )
                )
            except Exception:
                # Trace emission failure - non-critical, continue
                pass

            raise SkillExecutionError(f"Failed to update note: {str(e)}")

    async def delete(self, note_id: str) -> bool:
        """
        Delete a note.

        Args:
            note_id: Note ID to delete

        Returns:
            True if found and deleted, False if not found

        Raises:
            SkillExecutionError: On storage failure or approval denial
        """
        start_time = 0.0
        try:
            import asyncio

            start_time = asyncio.get_event_loop().time()
        except Exception as e:
            # Event loop timing failure - non-critical, continue
            logger.warning("AR18: event loop timing failed: %s", e, exc_info=True)

        try:
            await self._emitter.emit(
                TraceEvent(
                    event_type=TraceEventType.COMPONENT_START,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.INFO,
                    message="Notes delete started",
                    data={"note_id": note_id},
                    duration_ms=0,
                )
            )
        except Exception as e:
            # Trace emission failure - non-critical, continue
            logger.warning("AR18: trace emission failed: %s", e, exc_info=True)

        # Request approval if gate is present
        if self._approval_gate is not None:
            try:
                request = ApprovalRequest(
                    request_id=str(uuid4()),
                    task_id=str(uuid4()),
                    session_id="default",
                    action_type=ApprovalActionType.FILE_WRITE,
                    action_description=f"Delete note: {note_id}",
                    action_parameters={"note_id": note_id},
                    risk_level="medium",
                    reason_for_approval="Note deletion is destructive",
                    expires_at=datetime.now(timezone.utc) + timedelta(seconds=300),
                )
                response = await self._approval_gate.request_approval(request)
                if not response.approved:
                    duration_ms = 0
                    try:
                        duration_ms = int(
                            (asyncio.get_event_loop().time() - start_time) * 1000
                        )
                    except Exception:
                        # Event loop timing failure - non-critical, continue
                        pass

                    try:
                        await self._emitter.emit(
                            TraceEvent(
                                event_type=TraceEventType.OPERATION_COMPLETE,
                                component=TraceComponent.WORKER,
                                level=TraceLevel.WARNING,
                                message="Notes delete denied by approval gate",
                                data={
                                    "note_id": note_id,
                                    "reason": response.decision_reason,
                                },
                                duration_ms=duration_ms,
                            )
                        )
                    except Exception:
                        # Trace emission failure - non-critical, continue
                        pass

                    raise SkillExecutionError(
                        f"Approval denied: {response.decision_reason}"
                    )
            except SkillExecutionError:
                raise
            except Exception as e:
                duration_ms = 0
                try:
                    duration_ms = int(
                        (asyncio.get_event_loop().time() - start_time) * 1000
                    )
                except Exception:
                    # Event loop timing failure - non-critical, continue
                    pass

                try:
                    await self._emitter.emit(
                        TraceEvent(
                            event_type=TraceEventType.OPERATION_ERROR,
                            component=TraceComponent.WORKER,
                            level=TraceLevel.ERROR,
                            message="Notes delete approval request failed",
                            data={"error": str(e)},
                            duration_ms=duration_ms,
                        )
                    )
                except Exception:
                    # Trace emission failure - non-critical, continue
                    pass

                raise SkillExecutionError(f"Approval request failed: {str(e)}")

        try:
            note = await self._memory_router.scoped_read("notes", f"notes:{note_id}")

            if not note:
                duration_ms = 0
                try:
                    duration_ms = int(
                        (asyncio.get_event_loop().time() - start_time) * 1000
                    )
                except Exception:
                    # Event loop timing failure - non-critical, continue
                    pass

                try:
                    await self._emitter.emit(
                        TraceEvent(
                            event_type=TraceEventType.OPERATION_COMPLETE,
                            component=TraceComponent.WORKER,
                            level=TraceLevel.INFO,
                            message="Notes delete completed",
                            data={"note_id": note_id, "found": False},
                            duration_ms=duration_ms,
                        )
                    )
                except Exception:
                    # Trace emission failure - non-critical, continue
                    pass

                return False

            # scoped_delete not available, use scoped_write with None
            await self._memory_router.scoped_write("notes", f"notes:{note_id}", None)

            duration_ms = 0
            try:
                duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            except Exception:
                # Event loop timing failure - non-critical, continue
                pass

            try:
                await self._emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.OPERATION_COMPLETE,
                        component=TraceComponent.WORKER,
                        level=TraceLevel.INFO,
                        message="Notes delete completed",
                        data={"note_id": note_id, "found": True},
                        duration_ms=duration_ms,
                    )
                )
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
                await self._emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.WORKER,
                        level=TraceLevel.ERROR,
                        message="Notes delete failed",
                        data={"error": str(e)},
                        duration_ms=duration_ms,
                    )
                )
            except Exception:
                # Trace emission failure - non-critical, continue
                pass

            raise SkillExecutionError(f"Failed to delete note: {str(e)}")

    async def search_by_tag(self, tag: str) -> list[dict]:
        """
        Search notes by tag.

        Args:
            tag: Tag to search for

        Returns:
            List of note dicts containing the tag, sorted by updated_at descending

        Raises:
            SkillExecutionError: On storage failure
        """
        try:
            notes = await self.list_all()

            matching = [n for n in notes if tag in n.get("tags", [])]

            return matching

        except Exception as e:
            raise SkillExecutionError(f"Failed to search notes by tag: {str(e)}")
