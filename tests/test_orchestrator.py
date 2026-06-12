"""
Orchestrator tests.

Single responsibility: Test worker routing logic, scoring algorithm,
and task dispatch to appropriate workers.
"""

from datetime import datetime
from uuid import uuid4

import pytest

from core.memory_router import MemoryBackend, MemoryRouter
from core.orchestrator import Orchestrator
from core.schemas import Task, TaskPriority, WorkerProfile, WorkerStatus
from core.observability import MemoryTraceEmitter, TraceEvent
from workers.echo_worker import EchoWorker, MockLLMAdapter


class MockMemoryBackend(MemoryBackend):
    """Mock memory backend for testing."""

    def __init__(self) -> None:
        self.storage: list[dict] = []

    async def fetch(self, task: Task) -> list[dict]:
        """Fetch memory - returns empty list."""
        return []

    async def write(self, data: dict) -> None:
        """Write data to storage."""
        self.storage.append(data)

    async def list_keys(self, prefix: str) -> list[str]:
        """List all keys matching the given prefix."""
        # Stub implementation - returns empty list for now
        return []


class MockWorkerProfileWithStatus:
    """Mock worker profile with status attribute for testing."""
    
    def __init__(self, base_profile: WorkerProfile, status: WorkerStatus):
        self._base_profile = base_profile
        self.status = status
    
    def __getattr__(self, name):
        """Delegate all other attributes to the base profile."""
        return getattr(self._base_profile, name)


class TestOrchestrator:
    """Test Orchestrator routing logic."""

    @pytest.fixture
    def memory_router(self):
        """Create a memory router."""
        return MemoryRouter(backends={"mock": MockMemoryBackend()})

    @pytest.fixture
    def trace_emitter(self):
        """Create a memory trace emitter."""
        return MemoryTraceEmitter()

    @pytest.fixture
    def orchestrator(self, memory_router, trace_emitter):
        """Create an orchestrator."""
        return Orchestrator(memory_router=memory_router, emitter=trace_emitter)

    @pytest.fixture
    def sample_task(self):
        """Create a sample task."""
        return Task(
            task_id=uuid4(),
            intent="Test task for routing",
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            created_at=datetime.now(),
        )

    def test_route_task_raises_value_error_with_no_workers(self, orchestrator, sample_task):
        """Test that route_task raises WorkerNotFoundError when no workers are registered."""
        import asyncio
        from core.exceptions import WorkerNotFoundError

        with pytest.raises(WorkerNotFoundError, match="No workers registered"):
            asyncio.run(orchestrator.route_task(sample_task))

    def test_single_registered_worker_is_always_selected(self, orchestrator, memory_router, sample_task):
        """Test that a single registered worker is always selected."""
        profile = WorkerProfile(
            worker_id="worker1",
            worker_type="test",
            depth_preference=0.5,
            speculation_tolerance=0.5,
            source_skepticism=0.5,
            verbosity=0.5,
            preferred_model="mock-model",
            escalation_threshold=0.8,
            capabilities=["test"],
            preferred_complexity=0.5,
        )
        llm = MockLLMAdapter()
        worker = EchoWorker(profile=profile, llm=llm, memory_router=memory_router)

        orchestrator.register_worker("worker1", worker)

        import asyncio

        output = asyncio.run(orchestrator.route_task(sample_task))
        assert output.worker_id == "worker1"

    def test_worker_with_matching_complexity_scores_higher(self, orchestrator, memory_router, sample_task):
        """Test that worker with matching complexity scores higher."""
        # Create two workers with different preferred complexity
        profile1 = WorkerProfile(
            worker_id="worker1",
            worker_type="test",
            depth_preference=0.5,
            speculation_tolerance=0.5,
            source_skepticism=0.5,
            verbosity=0.5,
            preferred_model="mock-model",
            escalation_threshold=0.8,
            capabilities=["test"],
            preferred_complexity=0.5,  # Matches task.complexity_score=0.5
        )
        profile2 = WorkerProfile(
            worker_id="worker2",
            worker_type="test",
            depth_preference=0.5,
            speculation_tolerance=0.5,
            source_skepticism=0.5,
            verbosity=0.5,
            preferred_model="mock-model",
            escalation_threshold=0.8,
            capabilities=["test"],
            preferred_complexity=0.9,  # Does not match
        )

        llm1 = MockLLMAdapter()
        llm2 = MockLLMAdapter()
        worker1 = EchoWorker(profile=profile1, llm=llm1, memory_router=memory_router)
        worker2 = EchoWorker(profile=profile2, llm=llm2, memory_router=memory_router)

        orchestrator.register_worker("worker2", worker2)  # Register second first
        orchestrator.register_worker("worker1", worker1)  # Register matching complexity second

        import asyncio

        output = asyncio.run(orchestrator.route_task(sample_task))
        assert output.worker_id == "worker1"  # Should win due to complexity match

    def test_worker_with_matching_capability_keywords_scores_higher(self, orchestrator, memory_router):
        """Test that worker with matching capability keywords scores higher."""
        task = Task(
            task_id=uuid4(),
            intent="debug this code",
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            created_at=datetime.now(),
        )

        profile1 = WorkerProfile(
            worker_id="worker1",
            worker_type="test",
            depth_preference=0.5,
            speculation_tolerance=0.5,
            source_skepticism=0.5,
            verbosity=0.5,
            preferred_model="mock-model",
            escalation_threshold=0.8,
            capabilities=["echo"],  # No match
            preferred_complexity=0.5,
        )
        profile2 = WorkerProfile(
            worker_id="worker2",
            worker_type="test",
            depth_preference=0.5,
            speculation_tolerance=0.5,
            source_skepticism=0.5,
            verbosity=0.5,
            preferred_model="mock-model",
            escalation_threshold=0.8,
            capabilities=["debug", "test"],  # Matches "debug"
            preferred_complexity=0.5,
        )

        llm1 = MockLLMAdapter()
        llm2 = MockLLMAdapter()
        worker1 = EchoWorker(profile=profile1, llm=llm1, memory_router=memory_router)
        worker2 = EchoWorker(profile=profile2, llm=llm2, memory_router=memory_router)

        orchestrator.register_worker("worker1", worker1)
        orchestrator.register_worker("worker2", worker2)

        import asyncio

        output = asyncio.run(orchestrator.route_task(task))
        assert output.worker_id == "worker2"  # Should win due to capability match

    def test_worker_with_both_matching_complexity_and_capabilities_wins(self, orchestrator, memory_router):
        """Test that worker with both matching complexity and capabilities wins over partial matches."""
        task = Task(
            task_id=uuid4(),
            intent="debug this code",
            complexity_score=0.2,
            priority=TaskPriority.NORMAL,
            created_at=datetime.now(),
        )

        profile1 = WorkerProfile(
            worker_id="worker1",
            worker_type="test",
            depth_preference=0.5,
            speculation_tolerance=0.5,
            source_skepticism=0.5,
            verbosity=0.5,
            preferred_model="mock-model",
            escalation_threshold=0.8,
            capabilities=["debug"],  # Matches capability
            preferred_complexity=0.9,  # No complexity match
        )
        profile2 = WorkerProfile(
            worker_id="worker2",
            worker_type="test",
            depth_preference=0.5,
            speculation_tolerance=0.5,
            source_skepticism=0.5,
            verbosity=0.5,
            preferred_model="mock-model",
            escalation_threshold=0.8,
            capabilities=["debug"],  # Matches capability
            preferred_complexity=0.2,  # Matches complexity
        )

        llm1 = MockLLMAdapter()
        llm2 = MockLLMAdapter()
        worker1 = EchoWorker(profile=profile1, llm=llm1, memory_router=memory_router)
        worker2 = EchoWorker(profile=profile2, llm=llm2, memory_router=memory_router)

        orchestrator.register_worker("worker1", worker1)
        orchestrator.register_worker("worker2", worker2)

        import asyncio

        output = asyncio.run(orchestrator.route_task(task))
        assert output.worker_id == "worker2"  # Should win with both matches (score 3 vs score 1)

    def test_tie_broken_by_registration_order(self, orchestrator, memory_router, sample_task):
        """Test that tie is broken by registration order (first registered wins)."""
        profile1 = WorkerProfile(
            worker_id="worker1",
            worker_type="test",
            depth_preference=0.5,
            speculation_tolerance=0.5,
            source_skepticism=0.5,
            verbosity=0.5,
            preferred_model="mock-model",
            escalation_threshold=0.8,
            capabilities=["test"],
            preferred_complexity=0.5,
        )
        profile2 = WorkerProfile(
            worker_id="worker2",
            worker_type="test",
            depth_preference=0.5,
            speculation_tolerance=0.5,
            source_skepticism=0.5,
            verbosity=0.5,
            preferred_model="mock-model",
            escalation_threshold=0.8,
            capabilities=["test"],
            preferred_complexity=0.5,
        )

        llm1 = MockLLMAdapter()
        llm2 = MockLLMAdapter()
        worker1 = EchoWorker(profile=profile1, llm=llm1, memory_router=memory_router)
        worker2 = EchoWorker(profile=profile2, llm=llm2, memory_router=memory_router)

        orchestrator.register_worker("worker1", worker1)  # Registered first
        orchestrator.register_worker("worker2", worker2)  # Registered second

        import asyncio

        output = asyncio.run(orchestrator.route_task(sample_task))
        assert output.worker_id == "worker1"  # Should win due to registration order

    def test_process_task_with_explicit_worker_id_still_works(self, orchestrator, memory_router, sample_task):
        """Test that process_task with explicit worker ID still works."""
        profile = WorkerProfile(
            worker_id="worker1",
            worker_type="test",
            depth_preference=0.5,
            speculation_tolerance=0.5,
            source_skepticism=0.5,
            verbosity=0.5,
            preferred_model="mock-model",
            escalation_threshold=0.8,
            capabilities=["test"],
            preferred_complexity=0.5,
        )
        llm = MockLLMAdapter()
        worker = EchoWorker(profile=profile, llm=llm, memory_router=memory_router)

        orchestrator.register_worker("worker1", worker)

        import asyncio

        output = asyncio.run(orchestrator.process_task(sample_task, "worker1"))
        assert output.worker_id == "worker1"

    def test_process_task_raises_value_error_for_unknown_worker_id(self, orchestrator, sample_task):
        """Test that process_task raises WorkerNotFoundError for unknown worker ID."""
        import asyncio
        from core.exceptions import WorkerNotFoundError

        with pytest.raises(WorkerNotFoundError, match="not found"):
            asyncio.run(orchestrator.process_task(sample_task, "nonexistent"))

    def test_trace_events_emitted_during_routing(self, orchestrator, memory_router, sample_task, trace_emitter):
        """Test that trace events are emitted during routing."""
        profile = WorkerProfile(
            worker_id="worker1",
            worker_type="test",
            depth_preference=0.5,
            speculation_tolerance=0.5,
            source_skepticism=0.5,
            verbosity=0.5,
            preferred_model="mock-model",
            escalation_threshold=0.8,
            capabilities=["test"],
            preferred_complexity=0.5,
        )
        llm = MockLLMAdapter()
        worker = EchoWorker(profile=profile, llm=llm, memory_router=memory_router, emitter=trace_emitter)

        orchestrator.register_worker("worker1", worker)

        import asyncio

        asyncio.run(orchestrator.route_task(sample_task))

        events = trace_emitter.get_events()
        assert len(events) > 0

        # Check for orchestrator routing events
        event_types = [str(event.event_type) for event in events]
        assert "orchestrator_routing_start" in event_types
        assert "orchestrator_routing_complete" in event_types
        assert "operation_complete" in event_types

    def test_multiple_workers_with_no_overlap_first_registered_wins(self, orchestrator, memory_router):
        """Test that with multiple workers with no overlap, first registered wins."""
        task = Task(
            task_id=uuid4(),
            intent="random task",
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            created_at=datetime.now(),
        )

        profile1 = WorkerProfile(
            worker_id="worker1",
            worker_type="test",
            depth_preference=0.5,
            speculation_tolerance=0.5,
            source_skepticism=0.5,
            verbosity=0.5,
            preferred_model="mock-model",
            escalation_threshold=0.8,
            capabilities=["echo"],  # No match
            preferred_complexity=0.9,  # No match
        )
        profile2 = WorkerProfile(
            worker_id="worker2",
            worker_type="test",
            depth_preference=0.5,
            speculation_tolerance=0.5,
            source_skepticism=0.5,
            verbosity=0.5,
            preferred_model="mock-model",
            escalation_threshold=0.8,
            capabilities=["debug"],  # No match
            preferred_complexity=0.1,  # No match
        )

        llm1 = MockLLMAdapter()
        llm2 = MockLLMAdapter()
        worker1 = EchoWorker(profile=profile1, llm=llm1, memory_router=memory_router)
        worker2 = EchoWorker(profile=profile2, llm=llm2, memory_router=memory_router)

        orchestrator.register_worker("worker1", worker1)  # Registered first
        orchestrator.register_worker("worker2", worker2)  # Registered second

        import asyncio

        output = asyncio.run(orchestrator.route_task(task))
        assert output.worker_id == "worker1"  # Should win due to registration order (both score 0)

    def test_deprecated_worker_excluded_from_routing(self, orchestrator, memory_router):
        """Test that deprecated workers are excluded from routing."""
        task = Task(
            task_id=uuid4(),
            intent="test task",
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            created_at=datetime.now(),
        )

        # Create a worker profile with DEPRECATED status
        base_profile = WorkerProfile(
            worker_id="deprecated_worker",
            worker_type="test",
            depth_preference=0.5,
            speculation_tolerance=0.5,
            source_skepticism=0.5,
            verbosity=0.5,
            preferred_model="mock-model",
            escalation_threshold=0.8,
            capabilities=["test"],
            preferred_complexity=0.5,
        )
        # Wrap in mock profile with status attribute
        profile = MockWorkerProfileWithStatus(base_profile, WorkerStatus.DEPRECATED)

        llm = MockLLMAdapter()
        worker = EchoWorker(profile=profile, llm=llm, memory_router=memory_router)

        orchestrator.register_worker("deprecated_worker", worker)

        import asyncio

        # Should raise WorkerNotFoundError since the only worker is deprecated
        from core.exceptions import WorkerNotFoundError
        with pytest.raises(WorkerNotFoundError, match="No workers registered"):
            asyncio.run(orchestrator.route_task(task))

    def test_archived_worker_excluded_from_routing(self, orchestrator, memory_router):
        """Test that archived workers are excluded from routing."""
        task = Task(
            task_id=uuid4(),
            intent="test task",
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            created_at=datetime.now(),
        )

        # Create a worker profile with ARCHIVED status
        base_profile = WorkerProfile(
            worker_id="archived_worker",
            worker_type="test",
            depth_preference=0.5,
            speculation_tolerance=0.5,
            source_skepticism=0.5,
            verbosity=0.5,
            preferred_model="mock-model",
            escalation_threshold=0.8,
            capabilities=["test"],
            preferred_complexity=0.5,
        )
        # Wrap in mock profile with status attribute
        profile = MockWorkerProfileWithStatus(base_profile, WorkerStatus.ARCHIVED)

        llm = MockLLMAdapter()
        worker = EchoWorker(profile=profile, llm=llm, memory_router=memory_router)

        orchestrator.register_worker("archived_worker", worker)

        import asyncio

        # Should raise WorkerNotFoundError since the only worker is archived
        from core.exceptions import WorkerNotFoundError
        with pytest.raises(WorkerNotFoundError, match="No workers registered"):
            asyncio.run(orchestrator.route_task(task))

    def test_active_worker_included_in_routing(self, orchestrator, memory_router):
        """Test that active workers are included in routing."""
        task = Task(
            task_id=uuid4(),
            intent="test task",
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            created_at=datetime.now(),
        )

        # Create a worker profile with ACTIVE status
        base_profile = WorkerProfile(
            worker_id="active_worker",
            worker_type="test",
            depth_preference=0.5,
            speculation_tolerance=0.5,
            source_skepticism=0.5,
            verbosity=0.5,
            preferred_model="mock-model",
            escalation_threshold=0.8,
            capabilities=["test"],
            preferred_complexity=0.5,
        )
        # Wrap in mock profile with status attribute
        profile = MockWorkerProfileWithStatus(base_profile, WorkerStatus.ACTIVE)

        llm = MockLLMAdapter()
        worker = EchoWorker(profile=profile, llm=llm, memory_router=memory_router)

        orchestrator.register_worker("active_worker", worker)

        import asyncio

        output = asyncio.run(orchestrator.route_task(task))
        assert output.worker_id == "active_worker"

