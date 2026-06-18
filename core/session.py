"""
Session management for conversation history.

Single responsibility: Manage conversation sessions and message history.
Provides PostgreSQL persistence via PostgresBackend when configured,
with in-memory fallback when no DB is available.
"""

import os
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4, UUID

from core.memory_router import MemoryBackend
from core.schemas import Message, SessionSummary


class SessionManager:
    """Manager for conversation sessions and message history."""
    
    def __init__(
        self,
        backend: MemoryBackend | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
        session_expiry_days: int = 30,
    ) -> None:
        """Initialize the session manager.
        
        Args:
            backend: Optional memory backend for persistence.
                     If None, uses in-memory storage (dict).
            session_id: Optional session ID to load on startup.
            user_id: Optional user ID for the session.
            session_expiry_days: Days before sessions expire (default: 30).
        """
        self.backend = backend
        self._in_memory: dict[str, list[Message]] = {}
        self.session_expiry_days = session_expiry_days
        self.user_id = user_id
        
        # Load existing session if session_id provided
        if session_id:
            self._load_session(session_id)
    
    def _load_session(self, session_id: str) -> None:
        """Load an existing session into memory (synchronous for initialization).
        
        Args:
            session_id: Session ID to load
        """
        # For now, this is a placeholder. In a full implementation,
        # this would load the session from the backend asynchronously.
        # Since __init__ is synchronous, we'll defer actual loading
        # to an async method that can be called after initialization.
        pass
    
    async def load_session_async(self, session_id: str) -> bool:
        """Load an existing session asynchronously.
        
        Args:
            session_id: Session ID to load
            
        Returns:
            True if session was loaded, False if not found
        """
        history = await self.get_history(session_id)
        if history:
            self._in_memory[session_id] = history
            return True
        return False
    
    async def create_session(self) -> str:
        """Create a new session and return its ID.
        
        Returns:
            UUID string for the new session
        """
        session_id = str(uuid4())
        created_at = datetime.now()
        
        if self.backend:
            # Store session in backend with user_id and created_at
            await self.backend.write({
                "type": "session",
                "session_id": session_id,
                "user_id": self.user_id,
                "created_at": created_at.isoformat(),
                "messages": [],
                "expires_at": (created_at + timedelta(days=self.session_expiry_days)).isoformat(),
            })
        else:
            # Store in memory
            self._in_memory[session_id] = []
        
        return session_id
    
    async def get_history(self, session_id: str) -> list[Message]:
        """Get message history for a session.
        
        Args:
            session_id: UUID of the session
            
        Returns:
            List of messages in chronological order, empty list if session not found
        """
        if self.backend:
            # Fetch from backend
            try:
                from core.schemas import Task
                task = Task(
                    task_id=uuid4(),
                    intent=f"session:{session_id}",
                    complexity_score=0.0,
                    priority="normal",
                    current_state="received",
                    created_at=datetime.now(),
                )
                results = await self.backend.fetch(task)
                if results:
                    # Extract messages from the first result
                    data = results[0].get("content", {})
                    messages_data = data.get("messages", [])
                    return [Message(**msg) for msg in messages_data]
                return []
            except Exception:
                return []
        else:
            # Fetch from memory
            return self._in_memory.get(session_id, [])
    
    async def append(self, session_id: str, message: Message) -> None:
        """Append a message to a session's history.
        
        Args:
            session_id: UUID of the session
            message: Message to append
            
        Raises:
            ValueError: If session ID does not exist
        """
        if self.backend:
            # Check if session exists
            history = await self.get_history(session_id)
            if not history and session_id not in self._in_memory:
                raise ValueError(f"Session {session_id} does not exist")
            
            # Append to backend
            history.append(message)
            await self.backend.write({
                "type": "session",
                "session_id": session_id,
                "user_id": self.user_id,
                "created_at": datetime.now().isoformat(),
                "messages": [msg.model_dump() for msg in history],
                "expires_at": (datetime.now() + timedelta(days=self.session_expiry_days)).isoformat(),
            })
        else:
            # Append to memory
            if session_id not in self._in_memory:
                raise ValueError(f"Session {session_id} does not exist")
            self._in_memory[session_id].append(message)
    
    async def summarize(self, session_id: str) -> SessionSummary:
        """Generate a summary of a session.
        
        Args:
            session_id: UUID of the session
            
        Returns:
            SessionSummary with session metadata
            
        Raises:
            ValueError: If session not found or empty
        """
        history = await self.get_history(session_id)
        
        if not history:
            raise ValueError(f"Session {session_id} not found or empty")
        
        summary = SessionSummary(
            session_id=UUID(session_id),
            decisions_made=[],
            tasks_completed=[],
            tasks_pending=[],
            knowledge_updates=[],
            escalations=0,
            total_tokens=0,
            closed_at=history[-1].timestamp,
        )
        
        # Persist summary if backend is available
        if self.backend:
            await self.backend.write({
                "type": "session_summary",
                "session_id": session_id,
                "user_id": self.user_id,
                "summary": summary.model_dump(),
                "created_at": datetime.now().isoformat(),
            })
        
        return summary
    
    async def query_sessions(
        self,
        session_id: str | None = None,
        user_id: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Query sessions by session_id, user_id, and/or date range.
        
        Args:
            session_id: Optional session ID to filter by
            user_id: Optional user ID to filter by
            date_from: Optional start date for date range filter
            date_to: Optional end date for date range filter
            
        Returns:
            List of session metadata dictionaries
        """
        if not self.backend:
            # For in-memory fallback, return empty list
            # (in-memory sessions are not queryable by metadata)
            return []
        
        try:
            # Build query intent
            intent_parts = ["session"]
            if session_id:
                intent_parts.append(f"id:{session_id}")
            if user_id:
                intent_parts.append(f"user:{user_id}")
            intent = ":".join(intent_parts)
            
            # Fetch sessions matching filter
            task = Task(
                task_id=uuid4(),
                intent=intent,
                complexity_score=0.0,
                priority="normal",
                current_state="received",
                created_at=datetime.now(),
            )
            results = await self.backend.fetch(task)
            
            # Filter by date range if specified
            if date_from or date_to:
                filtered_results = []
                for result in results:
                    content = result.get("content", {})
                    created_at_str = content.get("created_at")
                    if created_at_str:
                        try:
                            created_at = datetime.fromisoformat(created_at_str)
                            if date_from and created_at < date_from:
                                continue
                            if date_to and created_at > date_to:
                                continue
                            filtered_results.append(result)
                        except (ValueError, TypeError):
                            pass
                results = filtered_results
            
            return results
        except Exception:
            return []
    
    async def archive_expired_sessions(self) -> int:
        """Archive sessions that have expired.
        
        Returns:
            Number of sessions archived
        """
        if not self.backend:
            return 0
        
        try:
            # Get all sessions
            task = Task(
                task_id=uuid4(),
                intent="session:all",
                complexity_score=0.0,
                priority="normal",
                current_state="received",
                created_at=datetime.now(),
            )
            all_sessions = await self.backend.fetch(task)
            
            archived_count = 0
            cutoff_date = datetime.now() - timedelta(days=self.session_expiry_days)
            
            for session in all_sessions:
                content = session.get("content", {})
                created_at_str = content.get("created_at")
                session_id = content.get("session_id")
                
                if created_at_str and session_id:
                    try:
                        created_at = datetime.fromisoformat(created_at_str)
                        if created_at < cutoff_date:
                            # Archive the session (mark as archived)
                            await self.backend.write({
                                "type": "session_archived",
                                "session_id": session_id,
                                "archived_at": datetime.now().isoformat(),
                                "original_data": content,
                            })
                            archived_count += 1
                    except (ValueError, TypeError):
                        pass
            
            return archived_count
        except Exception:
            return 0
    
    async def close(self) -> None:
        """Close the session manager and backend."""
        if self.backend and hasattr(self.backend, 'close'):
            await self.backend.close()
        self._in_memory.clear()

