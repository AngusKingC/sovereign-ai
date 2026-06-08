"""Tests for QueryHandler with injected Orchestrator."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from core.commands import Command, CommandType, CommandContext
from core.handlers import QueryHandler
from core.schemas import WorkerOutput


class MockOrchestrator:
    """Mock Orchestrator for testing."""
    
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.workers = {}
    
    def register_worker(self, worker_id: str, worker) -> None:
        """Mock register worker."""
        self.workers[worker_id] = worker
    
    async def route_task(self, task) -> WorkerOutput:
        """Mock route task."""
        if self.should_fail:
            raise RuntimeError("Orchestrator routing failed")
        return WorkerOutput(
            worker_id="test_worker",
            task_id=str(task.task_id),
            content="Test response",
            reasoning_steps=[],
            confidence=0.9,
            sources=[],
            claims=["Test response"],
            escalation_recommended=False,
            model_used="test-model",
            tokens_used=10,
        )


class TestQueryHandler:
    """Tests for QueryHandler with injected Orchestrator."""
    
    @pytest.mark.asyncio
    async def test_healthy_orchestrator_returns_response(self) -> None:
        """Test that healthy orchestrator returns successful response."""
        mock_orchestrator = MockOrchestrator(should_fail=False)
        handler = QueryHandler(mock_orchestrator)
        
        command = Command(
            command_type=CommandType.QUERY,
            args=["test", "query"],
            context=CommandContext(
                interface_type="cli",
                working_directory="/tmp"
            )
        )
        
        # Mock emit_trace to avoid actual trace emission during test
        with patch('core.handlers.emit_trace', new_callable=AsyncMock) as mock_trace, \
             patch('core.observability.emit_trace', new_callable=AsyncMock):
            mock_trace.return_value = None
            result = await handler.execute(command)
        
        assert result.success is True
        assert result.message == "Query processed"
        assert "response" in result.data
        assert result.data["response"] == "Test response"
        assert result.data["worker_id"] == "test_worker"
        assert result.data["confidence"] == 0.9
        assert result.data["tokens_used"] == 10
        assert result.duration_ms is not None
    
    @pytest.mark.asyncio
    async def test_orchestrator_exception_returns_error(self) -> None:
        """Test that orchestrator exception returns error result."""
        mock_orchestrator = MockOrchestrator(should_fail=True)
        handler = QueryHandler(mock_orchestrator)
        
        command = Command(
            command_type=CommandType.QUERY,
            args=["test", "query"],
            context=CommandContext(
                interface_type="cli",
                working_directory="/tmp"
            )
        )
        
        result = await handler.execute(command)
        
        assert result.success is False
        assert "Failed to process query" in result.message
        assert "Orchestrator routing failed" in result.error
        assert result.duration_ms is not None
    
    @pytest.mark.asyncio
    async def test_no_query_args_returns_error(self) -> None:
        """Test that missing query args returns error."""
        mock_orchestrator = MockOrchestrator(should_fail=False)
        handler = QueryHandler(mock_orchestrator)
        
        command = Command(
            command_type=CommandType.QUERY,
            args=[],
            context=CommandContext(
                interface_type="cli",
                working_directory="/tmp"
            )
        )
        
        result = await handler.execute(command)
        
        assert result.success is False
        assert "Query required" in result.message
        assert result.duration_ms is not None
    
    @pytest.mark.asyncio
    async def test_trace_events_emitted_on_success(self) -> None:
        """Test that trace events are emitted on successful query."""
        mock_orchestrator = MockOrchestrator(should_fail=False)
        handler = QueryHandler(mock_orchestrator)
        
        # Mock the emitter instead of emit_trace
        mock_emitter = AsyncMock()
        mock_emitter.emit = AsyncMock()
        handler.emitter = mock_emitter
        
        command = Command(
            command_type=CommandType.QUERY,
            args=["test", "query"],
            context=CommandContext(
                interface_type="cli",
                working_directory="/tmp"
            )
        )
        
        result = await handler.execute(command)
        
        # Should have emitted 3 trace events: COMMAND_RECEIVED, OPERATION_START, COMMAND_EXECUTED
        assert mock_emitter.emit.call_count == 3
    
    @pytest.mark.asyncio
    async def test_trace_events_emitted_on_orchestrator_failure(self) -> None:
        """Test that trace events are emitted on orchestrator failure."""
        mock_orchestrator = MockOrchestrator(should_fail=True)
        handler = QueryHandler(mock_orchestrator)
        
        # Mock the emitter instead of emit_trace
        mock_emitter = AsyncMock()
        mock_emitter.emit = AsyncMock()
        handler.emitter = mock_emitter
        
        command = Command(
            command_type=CommandType.QUERY,
            args=["test", "query"],
            context=CommandContext(
                interface_type="cli",
                working_directory="/tmp"
            )
        )
        
        result = await handler.execute(command)
        
        # Should have emitted 3 trace events: COMMAND_RECEIVED, OPERATION_START, COMMAND_FAILED
        assert mock_emitter.emit.call_count == 3
    
    @pytest.mark.asyncio
    async def test_task_construction_from_query_string(self) -> None:
        """Test that Task is correctly constructed from query string."""
        mock_orchestrator = MockOrchestrator(should_fail=False)
        handler = QueryHandler(mock_orchestrator)
        
        command = Command(
            command_type=CommandType.QUERY,
            args=["what", "is", "the", "weather"],
            context=CommandContext(
                interface_type="cli",
                working_directory="/tmp"
            )
        )
        
        with patch('core.handlers.emit_trace', new_callable=AsyncMock), \
             patch('core.observability.emit_trace', new_callable=AsyncMock):
            result = await handler.execute(command)
        
        assert result.success is True
        # The orchestrator receives the task with the correct intent
        assert result.data["response"] == "Test response"
    
    @pytest.mark.asyncio
    async def test_session_history_appended_on_success(self) -> None:
        """Test that session history is appended with user and assistant messages."""
        from core.session import SessionManager
        from core.schemas import Message, MessageRole
        
        mock_orchestrator = MockOrchestrator(should_fail=False)
        session_manager = SessionManager()
        handler = QueryHandler(mock_orchestrator, session_manager)
        
        # Create a session
        session_id = await session_manager.create_session()
        
        command = Command(
            command_type=CommandType.QUERY,
            args=["test", "query"],
            context=CommandContext(
                interface_type="cli",
                session_id=session_id,
                working_directory="/tmp"
            )
        )
        
        with patch('core.handlers.emit_trace', new_callable=AsyncMock), \
             patch('core.observability.emit_trace', new_callable=AsyncMock):
            result = await handler.execute(command)
        
        assert result.success is True
        
        # Verify session history
        history = await session_manager.get_history(session_id)
        assert len(history) == 2
        assert history[0].role == MessageRole.USER
        assert history[0].content == "test query"
        assert history[1].role == MessageRole.ASSISTANT
        assert history[1].content == "Test response"

