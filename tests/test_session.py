"""Tests for SessionManager."""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from core.session import SessionManager
from core.schemas import Message, MessageRole


class TestSessionManager:
    """Tests for SessionManager class."""
    
    @pytest.mark.asyncio
    async def test_create_session_returns_valid_uuid_string(self) -> None:
        """Test that create_session() returns a valid UUID string."""
        manager = SessionManager()
        session_id = await manager.create_session()
        
        assert isinstance(session_id, str)
        assert len(session_id) == 36  # UUID string length
        assert session_id.count('-') == 4  # UUID format
    
    @pytest.mark.asyncio
    async def test_get_history_returns_empty_list_for_new_session(self) -> None:
        """Test that get_history() returns empty list for new session."""
        manager = SessionManager()
        session_id = await manager.create_session()
        
        history = await manager.get_history(session_id)
        
        assert isinstance(history, list)
        assert len(history) == 0
    
    @pytest.mark.asyncio
    async def test_append_adds_messages_in_order(self) -> None:
        """Test that append() adds messages in order."""
        manager = SessionManager()
        session_id = await manager.create_session()
        
        msg1 = Message(role=MessageRole.USER, content="First", timestamp=datetime.now(timezone.utc))
        msg2 = Message(role=MessageRole.ASSISTANT, content="Second", timestamp=datetime.now(timezone.utc))
        
        await manager.append(session_id, msg1)
        await manager.append(session_id, msg2)
        
        history = await manager.get_history(session_id)
        
        assert len(history) == 2
        assert history[0].content == "First"
        assert history[1].content == "Second"
    
    @pytest.mark.asyncio
    async def test_get_history_returns_messages_in_chronological_order(self) -> None:
        """Test that get_history() returns messages in chronological order."""
        manager = SessionManager()
        session_id = await manager.create_session()
        
        # Add messages with specific timestamps
        t1 = datetime(2024, 1, 1, 10, 0, 0)
        t2 = datetime(2024, 1, 1, 10, 0, 1)
        t3 = datetime(2024, 1, 1, 10, 0, 2)
        
        msg1 = Message(role=MessageRole.USER, content="A", timestamp=t1)
        msg2 = Message(role=MessageRole.ASSISTANT, content="B", timestamp=t2)
        msg3 = Message(role=MessageRole.USER, content="C", timestamp=t3)
        
        await manager.append(session_id, msg1)
        await manager.append(session_id, msg2)
        await manager.append(session_id, msg3)
        
        history = await manager.get_history(session_id)
        
        assert len(history) == 3
        assert history[0].timestamp == t1
        assert history[1].timestamp == t2
        assert history[2].timestamp == t3
    
    @pytest.mark.asyncio
    async def test_append_raises_value_error_for_unknown_session_id(self) -> None:
        """Test that append() raises ValueError for unknown session ID."""
        manager = SessionManager()
        fake_session_id = str(uuid4())
        
        msg = Message(role=MessageRole.USER, content="Test", timestamp=datetime.now(timezone.utc))
        
        with pytest.raises(ValueError) as exc_info:
            await manager.append(fake_session_id, msg)
        
        assert "does not exist" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_summarize_returns_correct_message_count_start_end_time(self) -> None:
        """Test that summarize() returns correct session summary."""
        manager = SessionManager()
        session_id = await manager.create_session()
        
        t1 = datetime(2024, 1, 1, 10, 0, 0)
        t2 = datetime(2024, 1, 1, 10, 0, 1)
        t3 = datetime(2024, 1, 1, 10, 0, 2)
        
        msg1 = Message(role=MessageRole.USER, content="A", timestamp=t1)
        msg2 = Message(role=MessageRole.ASSISTANT, content="B", timestamp=t2)
        msg3 = Message(role=MessageRole.USER, content="C", timestamp=t3)
        
        await manager.append(session_id, msg1)
        await manager.append(session_id, msg2)
        await manager.append(session_id, msg3)
        
        summary = await manager.summarize(session_id)
        
        assert str(summary.session_id) == session_id
        assert summary.closed_at == t3
        assert summary.escalations == 0
        assert summary.total_tokens == 0
    
    @pytest.mark.asyncio
    async def test_summarize_raises_value_error_for_unknown_session_id(self) -> None:
        """Test that summarize() raises ValueError for unknown session ID."""
        manager = SessionManager()
        fake_session_id = str(uuid4())
        
        with pytest.raises(ValueError) as exc_info:
            await manager.summarize(fake_session_id)
        
        assert "not found or empty" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_summarize_raises_value_error_for_empty_session(self) -> None:
        """Test that summarize() raises ValueError for empty session."""
        manager = SessionManager()
        session_id = await manager.create_session()
        
        with pytest.raises(ValueError) as exc_info:
            await manager.summarize(session_id)
        
        assert "not found or empty" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_in_memory_backend_works_without_external_dependencies(self) -> None:
        """Test that in-memory backend works without any external dependencies."""
        manager = SessionManager(backend=None)  # Explicitly None
        
        session_id = await manager.create_session()
        msg = Message(role=MessageRole.USER, content="Test", timestamp=datetime.now(timezone.utc))
        
        await manager.append(session_id, msg)
        history = await manager.get_history(session_id)
        
        assert len(history) == 1
        assert history[0].content == "Test"
    
    @pytest.mark.asyncio
    async def test_multiple_sessions_are_isolated_from_each_other(self) -> None:
        """Test that multiple sessions are isolated from each other."""
        manager = SessionManager()
        
        session1 = await manager.create_session()
        session2 = await manager.create_session()
        
        msg1 = Message(role=MessageRole.USER, content="Session 1", timestamp=datetime.now(timezone.utc))
        msg2 = Message(role=MessageRole.USER, content="Session 2", timestamp=datetime.now(timezone.utc))
        
        await manager.append(session1, msg1)
        await manager.append(session2, msg2)
        
        history1 = await manager.get_history(session1)
        history2 = await manager.get_history(session2)
        
        assert len(history1) == 1
        assert len(history2) == 1
        assert history1[0].content == "Session 1"
        assert history2[0].content == "Session 2"

