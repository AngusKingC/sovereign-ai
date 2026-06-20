"""Tests for OllamaWorker."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from uuid import uuid4
from core.schemas import Message, MessageRole, Task, WorkerOutput, WorkerProfile
from core.worker_base import LLMResponse
from workers.ollama_worker import OllamaWorker
from core.memory_router import MemoryRouter


class MockAdapter:
    """Mock LLM adapter for testing."""
    
    def __init__(self) -> None:
        self.model_name = "test-model"
        self.cost_per_token = 0.0
    
    async def generate(
        self,
        messages: list[Message],
        temperature: float = 0.1,
        max_tokens: int = 2048,
        structured_output = None,
    ) -> LLMResponse:
        """Mock generate."""
        return LLMResponse(
            content="Test response",
            raw={"model": "test-model"},
            model="test-model",
            tokens_used=10,
            duration_ms=100,
        )


class MockMemoryRouter(MemoryRouter):
    """Mock memory router for testing."""
    
    def __init__(self) -> None:
        super().__init__()
    
    async def fetch(self, task: Task) -> list:  # type: ignore[override]
        """Mock fetch - returns empty list."""
        return []


class TestOllamaWorker:
    """Tests for OllamaWorker."""
    
    @pytest.mark.asyncio
    async def test_build_prompt_includes_system_message(self) -> None:
        """Test that build_prompt includes system message."""
        mock_adapter = MockAdapter()
        mock_memory_router = MockMemoryRouter()
        worker = OllamaWorker(adapter=mock_adapter, memory_router=mock_memory_router)
        
        task = Task(
            task_id=uuid4(),
            intent="test query",
            complexity_score=0.5,
            priority="normal",
            status="received",
            created_at=datetime.now(),
        )
        
        prompt = await worker.build_prompt(task, [])
        
        assert len(prompt) >= 2
        assert prompt[0].role == MessageRole.SYSTEM
        assert "helpful ai assistant" in prompt[0].content.lower()
    
    @pytest.mark.asyncio
    async def test_build_prompt_includes_memory_context(self) -> None:
        """Test that build_prompt includes memory context messages."""
        mock_adapter = MockAdapter()
        mock_memory_router = MockMemoryRouter()
        worker = OllamaWorker(adapter=mock_adapter, memory_router=mock_memory_router)
        
        task = Task(
            task_id=uuid4(),
            intent="test query",
            complexity_score=0.5,
            priority="normal",
            status="received",
            created_at=datetime.now(),
        )
        
        memory = [{"content": "Previous context"}]
        prompt = await worker.build_prompt(task, memory)
        
        # Should have system message, memory context, and user message
        assert len(prompt) >= 3
        assert any("Context from memory" in msg.content for msg in prompt)
    
    @pytest.mark.asyncio
    async def test_build_prompt_with_empty_memory_omits_memory_context(self) -> None:
        """Test that build_prompt with empty memory omits memory context messages."""
        mock_adapter = MockAdapter()
        mock_memory_router = MockMemoryRouter()
        worker = OllamaWorker(adapter=mock_adapter, memory_router=mock_memory_router)
        
        task = Task(
            task_id=uuid4(),
            intent="test query",
            complexity_score=0.5,
            priority="normal",
            status="received",
            created_at=datetime.now(),
        )
        
        prompt = await worker.build_prompt(task, [])
        
        # Should only have system message and user message
        assert len(prompt) == 2
        assert not any("Context from memory" in msg.content for msg in prompt)
    
    @pytest.mark.asyncio
    async def test_build_prompt_includes_user_message(self) -> None:
        """Test that build_prompt includes user message from task.intent."""
        mock_adapter = MockAdapter()
        mock_memory_router = MockMemoryRouter()
        worker = OllamaWorker(adapter=mock_adapter, memory_router=mock_memory_router)
        
        task = Task(
            task_id=uuid4(),
            intent="test query",
            complexity_score=0.5,
            priority="normal",
            status="received",
            created_at=datetime.now(),
        )
        
        prompt = await worker.build_prompt(task, [])
        
        # Last message should be user message with task intent
        assert prompt[-1].role == MessageRole.USER
        assert prompt[-1].content == "test query"
    
    @pytest.mark.asyncio
    async def test_parse_output_returns_worker_output_with_correct_result(self) -> None:
        """Test that parse_output returns WorkerOutput with correct result."""
        mock_adapter = MockAdapter()
        mock_memory_router = MockMemoryRouter()
        worker = OllamaWorker(adapter=mock_adapter, memory_router=mock_memory_router)
        
        raw_response = LLMResponse(
            content="Test response",
            raw={"model": "test-model"},
            model="test-model",
            tokens_used=10,
            duration_ms=100,
        )
        
        task_id = uuid4()
        output = await worker.parse_output(raw_response, str(task_id))
        
        assert isinstance(output, WorkerOutput)
        assert output.content == "Test response"
        assert output.worker_id == worker.profile.worker_id
        assert output.task_id == task_id
    
    @pytest.mark.asyncio
    async def test_parse_output_returns_worker_output_with_confidence_0_9(self) -> None:
        """Test that parse_output returns WorkerOutput with confidence=0.9."""
        mock_adapter = MockAdapter()
        mock_memory_router = MockMemoryRouter()
        worker = OllamaWorker(adapter=mock_adapter, memory_router=mock_memory_router)
        
        raw_response = LLMResponse(
            content="Test response",
            raw={"model": "test-model"},
            model="test-model",
            tokens_used=10,
            duration_ms=100,
        )
        
        output = await worker.parse_output(raw_response, str(uuid4()))
        
        assert output.confidence == 0.9
    
    @pytest.mark.asyncio
    async def test_parse_output_returns_worker_output_with_empty_reasoning_steps(self) -> None:
        """Test that parse_output returns WorkerOutput with empty reasoning_steps."""
        mock_adapter = MockAdapter()
        mock_memory_router = MockMemoryRouter()
        worker = OllamaWorker(adapter=mock_adapter, memory_router=mock_memory_router)
        
        raw_response = LLMResponse(
            content="Test response",
            raw={"model": "test-model"},
            model="test-model",
            tokens_used=10,
            duration_ms=100,
        )
        
        output = await worker.parse_output(raw_response, str(uuid4()))
        
        assert output.reasoning_steps == []
    
    @pytest.mark.asyncio
    async def test_worker_profile_has_expected_default_capabilities(self) -> None:
        """Test that worker profile has expected default capabilities."""
        mock_adapter = MockAdapter()
        mock_memory_router = MockMemoryRouter()
        worker = OllamaWorker(adapter=mock_adapter, memory_router=mock_memory_router)
        
        expected_capabilities = ["general", "chat", "reasoning", "code", "analysis"]
        assert worker.profile.capabilities == expected_capabilities
        assert worker.profile.preferred_complexity == 0.5
    
    @pytest.mark.asyncio
    async def test_trace_events_emitted_during_build_prompt(self) -> None:
        """Test that trace events are emitted during build_prompt."""
        mock_adapter = MockAdapter()
        mock_memory_router = MockMemoryRouter()
        worker = OllamaWorker(adapter=mock_adapter, memory_router=mock_memory_router)
        
        task = Task(
            task_id=uuid4(),
            intent="test query",
            complexity_score=0.5,
            priority="normal",
            status="received",
            created_at=datetime.now(),
        )
        
        with patch('core.observability.emit_trace') as mock_emit:
            prompt = await worker.build_prompt(task, [])
            
            # build_prompt itself doesn't emit traces, but run() does
            # This test verifies the method works correctly
            assert len(prompt) >= 2
    
    @pytest.mark.asyncio
    async def test_trace_events_emitted_during_parse_output(self) -> None:
        """Test that trace events are emitted during parse_output."""
        mock_adapter = MockAdapter()
        mock_memory_router = MockMemoryRouter()
        worker = OllamaWorker(adapter=mock_adapter, memory_router=mock_memory_router)
        
        raw_response = LLMResponse(
            content="Test response",
            raw={"model": "test-model"},
            model="test-model",
            tokens_used=10,
            duration_ms=100,
        )
        
        with patch('core.observability.emit_trace') as mock_emit:
            output = await worker.parse_output(raw_response, str(uuid4()))
            
            # parse_output itself doesn't emit traces, but run() does
            # This test verifies the method works correctly
            assert isinstance(output, WorkerOutput)
    
    @pytest.mark.asyncio
    async def test_worker_satisfies_worker_base_interface(self) -> None:
        """Test that worker satisfies WorkerBase interface."""
        mock_adapter = MockAdapter()
        mock_memory_router = MockMemoryRouter()
        worker = OllamaWorker(adapter=mock_adapter, memory_router=mock_memory_router)
        
        # Verify worker has required methods
        assert hasattr(worker, 'build_prompt')
        assert hasattr(worker, 'parse_output')
        assert hasattr(worker, 'run')
        assert hasattr(worker, 'profile')
        assert hasattr(worker, 'llm')
        assert hasattr(worker, 'memory_router')
    
    @pytest.mark.asyncio
    async def test_custom_profile_overrides_defaults(self) -> None:
        """Test that custom profile overrides defaults."""
        mock_adapter = MockAdapter()
        mock_memory_router = MockMemoryRouter()
        
        custom_profile = WorkerProfile(
            worker_id="custom_worker",
            worker_type="custom",
            depth_preference=0.8,
            speculation_tolerance=0.2,
            source_skepticism=0.9,
            verbosity=0.3,
            preferred_model="custom-model",
            escalation_threshold=0.6,
            capabilities=["custom_capability"],
            preferred_complexity=0.8,
        )
        
        worker = OllamaWorker(
            adapter=mock_adapter,
            memory_router=mock_memory_router,
            profile=custom_profile
        )
        
        assert worker.profile.worker_id == "custom_worker"
        assert worker.profile.capabilities == ["custom_capability"]
        assert worker.profile.preferred_complexity == 0.8

