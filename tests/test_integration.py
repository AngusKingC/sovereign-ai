"""
Integration tests for full pipeline.

Single responsibility: Test orchestrator-worker-memory integration
to ensure components work together correctly.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from core.memory_router import MemoryRouter
from core.orchestrator import Orchestrator
from core.schemas import Task, TaskPriority, WorkerProfile
from memory.obsidian import ObsidianBackend
from core.observability import MemoryTraceEmitter
from workers.echo_worker import EchoWorker, MockLLMAdapter


class TestIntegration:
    """Test full pipeline integration."""

    @pytest.fixture
    def temp_vault(self, tmp_path):
        """Create a temporary vault for testing."""
        return str(tmp_path / "test_vault")

    @pytest.fixture
    def obsidian_backend(self, temp_vault):
        """Create an Obsidian backend."""
        return ObsidianBackend(temp_vault)

    @pytest.fixture
    def memory_router(self, obsidian_backend):
        """Create a memory router with obsidian backend."""
        return MemoryRouter(
            backends={"obsidian": obsidian_backend},
        )

    @pytest.fixture
    def trace_emitter(self):
        """Create a memory trace emitter."""
        return MemoryTraceEmitter()

    @pytest.fixture
    def orchestrator(self, memory_router):
        """Create an orchestrator."""
        return Orchestrator(
            memory_router=memory_router,
        )

    @pytest.fixture
    def echo_worker(self, memory_router):
        """Create an echo worker."""
        profile = WorkerProfile(
            worker_id="echo_worker",
            worker_type="echo",
            depth_preference=0.5,
            speculation_tolerance=0.5,
            source_skepticism=0.5,
            verbosity=0.5,
            preferred_model="mock-model",
            escalation_threshold=0.8,
            capabilities=["echo", "test", "debug"],
            preferred_complexity=0.2,
        )
        llm = MockLLMAdapter()
        return EchoWorker(
            profile=profile,
            llm=llm,
            memory_router=memory_router,
        )

    @pytest.fixture
    def sample_task(self):
        """Create a sample task."""
        return Task(
            task_id=uuid4(),
            intent="Test task for integration",
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            created_at=datetime.now(timezone.utc),
        )

    def test_worker_uses_memory(self, echo_worker, sample_task):
        """Test that worker successfully uses memory router."""
        import asyncio

        # Write some memory first
        import asyncio

        data = {"content": "Test memory entry", "source": "integration_test"}
        asyncio.run(echo_worker.memory_router.write(data))

        # Run the worker
        output = asyncio.run(echo_worker.run(sample_task))

        assert output.worker_id == "echo_worker"
        assert "Echo:" in output.content
        assert output.confidence == 1.0

    def test_orchestrator_registers_worker(self, orchestrator, echo_worker):
        """Test that orchestrator can register workers."""
        orchestrator.register_worker("echo_worker", echo_worker)

        assert "echo_worker" in orchestrator.workers
        assert orchestrator.workers["echo_worker"] == echo_worker

    def test_orchestrator_processes_task(self, orchestrator, echo_worker, sample_task):
        """Test that orchestrator can process tasks through workers."""
        orchestrator.register_worker("echo_worker", echo_worker)

        import asyncio

        output = asyncio.run(orchestrator.process_task(sample_task, "echo_worker"))

        assert output.worker_id == "echo_worker"
        assert output.content is not None

    def test_orchestrator_routes_task(self, orchestrator, echo_worker, sample_task):
        """Test that orchestrator can route tasks to workers."""
        orchestrator.register_worker("echo_worker", echo_worker)

        import asyncio

        output = asyncio.run(orchestrator.route_task(sample_task))

        assert output.worker_id == "echo_worker"
        assert output.content is not None

    def test_full_pipeline_with_memory(self, orchestrator, echo_worker, sample_task, obsidian_backend):
        """Test full pipeline: orchestrator -> worker -> memory -> back."""
        orchestrator.register_worker("echo_worker", echo_worker)

        import asyncio

        # Write some memory
        data = {"content": "Integration test memory", "test": True}
        asyncio.run(echo_worker.memory_router.write(data))

        # Process task through full pipeline
        output = asyncio.run(orchestrator.route_task(sample_task))

        # Verify worker used memory
        assert output.worker_id == "echo_worker"
        assert output.content is not None

        # Verify memory was written
        import asyncio

        memory = asyncio.run(obsidian_backend.fetch(sample_task))
        assert len(memory) > 0

    def test_tracing_emitted_during_pipeline(self, orchestrator, echo_worker, sample_task, trace_emitter):
        """Test that trace events are emitted during pipeline execution."""
        from core.observability import set_trace_emitter
        set_trace_emitter(trace_emitter)
        
        # Set the worker's emitter to the trace emitter
        echo_worker.emitter = trace_emitter
        
        orchestrator.register_worker("echo_worker", echo_worker)

        import asyncio

        output = asyncio.run(orchestrator.route_task(sample_task))

        # Check that trace emitter captured events
        events = trace_emitter.get_events()
        assert len(events) > 0

        # Verify we have data read and adapter call events
        event_types = [str(event.event_type) for event in events]
        assert "data_read" in event_types
        assert "adapter_call" in event_types

    def test_worker_with_empty_memory(self, echo_worker, sample_task):
        """Test that worker works correctly with empty memory."""
        import asyncio

        output = asyncio.run(echo_worker.run(sample_task))

        assert output.worker_id == "echo_worker"
        assert output.content is not None

    def test_orchestrator_error_handling(self, orchestrator, sample_task):
        """Test that orchestrator handles errors gracefully."""
        import asyncio
        from core.exceptions import WorkerNotFoundError

        # Try to process task with non-existent worker
        with pytest.raises(WorkerNotFoundError, match="not found"):
            asyncio.run(orchestrator.process_task(sample_task, "nonexistent"))

    def test_orchestrator_no_workers_error(self, orchestrator, sample_task):
        """Test that orchestrator raises error when no workers registered."""
        import asyncio
        from core.exceptions import WorkerNotFoundError

        with pytest.raises(WorkerNotFoundError, match="No workers registered"):
            asyncio.run(orchestrator.route_task(sample_task))

    def test_end_to_end_pipeline_with_ollama_worker(self, trace_emitter):
        """Test full pipeline: Orchestrator -> OllamaWorker -> OllamaAdapter -> LLMResponse with mocked HTTP."""
        import asyncio
        from unittest.mock import patch, AsyncMock
        from core.orchestrator import Orchestrator
        from core.memory_router import MemoryRouter
        from workers.ollama_worker import OllamaWorker
        from adapters.ollama import OllamaAdapter
        from core.schemas import Task, TaskPriority
        from datetime import datetime, timezone, timezone
        from uuid import uuid4

        # Create memory router with empty backends
        memory_router = MemoryRouter(backends={}, emitter=trace_emitter)

        # Create OllamaAdapter with mocked HTTP
        ollama_adapter = OllamaAdapter(model_name="qwen2.5-coder:7b", emitter=trace_emitter)

        # Mock the HTTP call to Ollama
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = lambda: {
            "model": "qwen2.5-coder:7b",
            "message": {
                "content": "Mocked LLM response",
                "role": "assistant"
            },
            "done": True,
            "eval_count": 10,
            "prompt_eval_count": 5,
        }
        mock_response.raise_for_status = lambda: None

        with patch('httpx.AsyncClient.post', return_value=mock_response):
            # Construct OllamaWorker with constructor-injected emitter
            ollama_worker = OllamaWorker(
                adapter=ollama_adapter,
                memory_router=memory_router,
                profile=None,  # Use default profile
            )
            ollama_worker.emitter = trace_emitter  # Constructor injection

            # Construct Orchestrator with constructor-injected emitter
            orchestrator = Orchestrator(
                memory_router=memory_router,
                improvement_loop=None,
                cloud_fallback_model="gpt-4o",
                approval_gate=None,
                escalation_engine=None,
                fallback_chain=None,
                a2a_router=None,
                emitter=trace_emitter,
            )

            # Register the worker with the Orchestrator
            orchestrator.register_worker("ollama_worker", ollama_worker)

            # Create a task
            task = Task(
                task_id=uuid4(),
                intent="Test task for end-to-end integration",
                complexity_score=0.5,
                priority=TaskPriority.NORMAL,
                created_at=datetime.now(timezone.utc),
            )

            # Submit task via Orchestrator.route()
            output = asyncio.run(orchestrator.route_task(task))

            # Assert a real LLMResponse is returned (not None, not a stub)
            assert output is not None
            assert output.worker_id == "ollama_worker"
            assert output.content is not None
            assert output.content != ""
            assert output.confidence > 0.0
            assert output.model_used is not None

            # Assert at least one trace event was emitted
            events = trace_emitter.get_events()
            assert len(events) > 0

