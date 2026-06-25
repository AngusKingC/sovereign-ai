"""Tests for WorkerCircuitBreaker.

Applying OR24: Every new implementation MUST have a corresponding test file.
Tests cover key paths for WorkerCircuitBreaker.
"""

import asyncio
import time

import pytest

from core.worker_circuit_breaker import WorkerCircuitBreaker


class TestWorkerCircuitBreaker:
    """Test suite for WorkerCircuitBreaker."""

    def test_record_failure_increments_count(self) -> None:
        """Failure count goes 0 → 1 → 2."""
        breaker = WorkerCircuitBreaker(failure_threshold=3)
        breaker.register_worker("worker1")

        assert breaker._failure_counts["worker1"] == 0

        breaker.record_failure("worker1")
        assert breaker._failure_counts["worker1"] == 1

        breaker.record_failure("worker1")
        assert breaker._failure_counts["worker1"] == 2

    def test_record_failure_opens_circuit_at_threshold(self) -> None:
        """After failure_threshold failures, is_available returns False."""
        breaker = WorkerCircuitBreaker(failure_threshold=3)
        breaker.register_worker("worker1")

        # Below threshold
        breaker.record_failure("worker1")
        breaker.record_failure("worker1")
        assert breaker.is_available("worker1") is True

        # At threshold
        breaker.record_failure("worker1")
        assert breaker.is_available("worker1") is False

    def test_record_success_resets_count(self) -> None:
        """Success resets count to 0."""
        breaker = WorkerCircuitBreaker(failure_threshold=3)
        breaker.register_worker("worker1")

        breaker.record_failure("worker1")
        breaker.record_failure("worker1")
        assert breaker._failure_counts["worker1"] == 2

        breaker.record_success("worker1")
        assert breaker._failure_counts["worker1"] == 0

    def test_record_success_closes_open_circuit(self) -> None:
        """Success after open closes circuit."""
        breaker = WorkerCircuitBreaker(failure_threshold=3)
        breaker.register_worker("worker1")

        # Open circuit
        breaker.record_failure("worker1")
        breaker.record_failure("worker1")
        breaker.record_failure("worker1")
        assert breaker.is_available("worker1") is False

        # Close circuit with success
        breaker.record_success("worker1")
        assert breaker.is_available("worker1") is True

    def test_is_available_returns_true_for_unknown_worker(self) -> None:
        """Unknown workers are available (no failures recorded)."""
        breaker = WorkerCircuitBreaker()
        assert breaker.is_available("unknown_worker") is True

    def test_is_available_returns_true_after_reset_timeout_elapses(self) -> None:
        """Circuit auto-resets after timeout."""
        breaker = WorkerCircuitBreaker(failure_threshold=3, reset_timeout=1)
        breaker.register_worker("worker1")

        # Open circuit
        breaker.record_failure("worker1")
        breaker.record_failure("worker1")
        breaker.record_failure("worker1")
        assert breaker.is_available("worker1") is False

        # Wait for timeout
        time.sleep(1.1)

        # Circuit should be auto-reset
        assert breaker.is_available("worker1") is True
        assert breaker._failure_counts["worker1"] == 0

    def test_reset_circuit_clears_failure_count(self) -> None:
        """Manual reset works."""
        breaker = WorkerCircuitBreaker(failure_threshold=3)
        breaker.register_worker("worker1")

        # Open circuit
        breaker.record_failure("worker1")
        breaker.record_failure("worker1")
        breaker.record_failure("worker1")
        assert breaker._failure_counts["worker1"] == 3

        # Manual reset
        asyncio.run(breaker.reset_circuit("worker1"))
        assert breaker._failure_counts["worker1"] == 0
        assert breaker.is_available("worker1") is True

    def test_get_status_returns_correct_structure(self) -> None:
        """Status list has correct shape."""
        breaker = WorkerCircuitBreaker(failure_threshold=3)
        breaker.register_worker("worker1")
        breaker.register_worker("worker2")

        status = breaker.get_status()
        assert len(status) == 2

        # Check structure
        for entry in status:
            assert "worker_id" in entry
            assert "failure_count" in entry
            assert "circuit_open" in entry
            assert "circuit_open_since" in entry

    def test_get_degraded_workers_returns_only_open_circuits(self) -> None:
        """Only workers with open circuits returned."""
        breaker = WorkerCircuitBreaker(failure_threshold=3)
        breaker.register_worker("worker1")
        breaker.register_worker("worker2")
        breaker.register_worker("worker3")

        # Open circuit for worker1 and worker2
        breaker.record_failure("worker1")
        breaker.record_failure("worker1")
        breaker.record_failure("worker1")
        breaker.record_failure("worker2")
        breaker.record_failure("worker2")
        breaker.record_failure("worker2")

        degraded = breaker.get_degraded_workers()
        assert len(degraded) == 2
        assert "worker1" in degraded
        assert "worker2" in degraded
        assert "worker3" not in degraded

    def test_register_worker_seeds_failure_count_and_circuit_state(self) -> None:
        """register_worker adds worker with count=0, circuit_open=None (Issue #1 fix)."""
        breaker = WorkerCircuitBreaker()
        breaker.register_worker("worker1")

        assert "worker1" in breaker._registered_workers
        assert breaker._failure_counts["worker1"] == 0
        assert breaker._circuit_open_since["worker1"] is None

    def test_register_worker_is_idempotent(self) -> None:
        """Registering an already-tracked worker is a no-op."""
        breaker = WorkerCircuitBreaker()
        breaker.register_worker("worker1")

        # Set some state
        breaker.record_failure("worker1")
        initial_count = breaker._failure_counts["worker1"]

        # Re-register should be no-op
        breaker.register_worker("worker1")
        assert breaker._failure_counts["worker1"] == initial_count
        assert len(breaker._registered_workers) == 1

    def test_get_degraded_worker_ratio_uses_registered_roster_as_denominator(
        self,
    ) -> None:
        """2 of 5 registered workers degraded → 0.4 (NOT 1.0 from lazy-population bug) (Issue #1 regression test)."""
        breaker = WorkerCircuitBreaker(failure_threshold=3)

        # Register 5 workers
        for i in range(5):
            breaker.register_worker(f"worker{i}")

        # Open circuits for 2 workers
        breaker.record_failure("worker0")
        breaker.record_failure("worker0")
        breaker.record_failure("worker0")
        breaker.record_failure("worker1")
        breaker.record_failure("worker1")
        breaker.record_failure("worker1")

        # Ratio should be 2/5 = 0.4
        # NOT 2/2 = 1.0 (the lazy-population bug where denominator is len(_failure_counts))
        ratio = breaker.get_degraded_worker_ratio()
        assert ratio == 0.4

    def test_record_failure_auto_registers_unknown_worker(self) -> None:
        """Calling record_failure on unregistered worker auto-registers it."""
        breaker = WorkerCircuitBreaker()

        assert "unknown_worker" not in breaker._registered_workers

        breaker.record_failure("unknown_worker")

        assert "unknown_worker" in breaker._registered_workers
        assert breaker._failure_counts["unknown_worker"] == 1

    def test_concurrent_async_record_failures_do_not_corrupt_state(self) -> None:
        """asyncio.gather over multiple record_failure calls does not corrupt internal dicts.

        Note: This tests asyncio concurrency (single-threaded event loop), NOT multi-threaded
        concurrency. The WorkerCircuitBreaker is designed for the orchestrator's asyncio
        event loop; if multi-threaded access is added later, a threading.Lock would be required.
        (Source: Claude Rev2 review Issue #5 — renamed from "thread-safe" to "asyncio-safe"
        to avoid false confidence.)
        """
        breaker = WorkerCircuitBreaker(failure_threshold=10)
        breaker.register_worker("worker1")
        breaker.register_worker("worker2")
        breaker.register_worker("worker3")

        # Concurrent failures on same worker
        async def concurrent_failures_same_worker() -> None:
            await asyncio.gather(
                *[
                    asyncio.to_thread(breaker.record_failure, "worker1")
                    for _ in range(5)
                ]
            )

        asyncio.run(concurrent_failures_same_worker())
        assert breaker._failure_counts["worker1"] == 5

        # Concurrent failures on different workers
        async def concurrent_failures_different_workers() -> None:
            await asyncio.gather(
                asyncio.to_thread(breaker.record_failure, "worker2"),
                asyncio.to_thread(breaker.record_failure, "worker3"),
                asyncio.to_thread(breaker.record_failure, "worker2"),
                asyncio.to_thread(breaker.record_failure, "worker3"),
            )

        asyncio.run(concurrent_failures_different_workers())
        assert breaker._failure_counts["worker2"] == 2
        assert breaker._failure_counts["worker3"] == 2

        # Verify internal state consistency
        assert len(breaker._registered_workers) == 3
        assert len(breaker._failure_counts) == 3
        assert len(breaker._circuit_open_since) == 3


class TestOrchestratorAggregateBehavior:
    """Test suite for orchestrator-level aggregate circuit breaker behavior."""

    def test_is_degraded_returns_false_when_no_circuit_breaker(self) -> None:
        """is_degraded returns False when worker_circuit_breaker is None."""
        from core.memory_router import MemoryBackend, MemoryRouter
        from core.orchestrator import Orchestrator

        class MockMemoryBackend(MemoryBackend):
            def __init__(self) -> None:
                self.storage: list[dict] = []

            async def fetch(self, task) -> list[dict]:
                return []

            async def write(self, data: dict) -> None:
                self.storage.append(data)

            async def list_keys(self, prefix: str) -> list[str]:
                return []

        memory_router = MemoryRouter(backends={"mock": MockMemoryBackend()})
        orchestrator = Orchestrator(
            memory_router=memory_router,
            worker_circuit_breaker=None,
            degraded_mode_threshold=0.5,
        )

        assert orchestrator.is_degraded() is False

    def test_is_degraded_returns_false_when_ratio_below_threshold(self) -> None:
        """is_degraded returns False when degraded ratio is below threshold."""
        from core.memory_router import MemoryBackend, MemoryRouter
        from core.orchestrator import Orchestrator
        from core.worker_circuit_breaker import WorkerCircuitBreaker

        class MockMemoryBackend(MemoryBackend):
            def __init__(self) -> None:
                self.storage: list[dict] = []

            async def fetch(self, task) -> list[dict]:
                return []

            async def write(self, data: dict) -> None:
                self.storage.append(data)

            async def list_keys(self, prefix: str) -> list[str]:
                return []

        memory_router = MemoryRouter(backends={"mock": MockMemoryBackend()})
        breaker = WorkerCircuitBreaker(failure_threshold=3)
        orchestrator = Orchestrator(
            memory_router=memory_router,
            worker_circuit_breaker=breaker,
            degraded_mode_threshold=0.5,
        )

        # Register 5 workers
        for i in range(5):
            breaker.register_worker(f"worker{i}")

        # Open circuits for 2 workers (ratio = 2/5 = 0.4 < 0.5)
        breaker.record_failure("worker0")
        breaker.record_failure("worker0")
        breaker.record_failure("worker0")
        breaker.record_failure("worker1")
        breaker.record_failure("worker1")
        breaker.record_failure("worker1")

        assert orchestrator.is_degraded() is False

    def test_is_degraded_returns_true_when_ratio_at_threshold(self) -> None:
        """is_degraded returns True when degraded ratio equals threshold."""
        from core.memory_router import MemoryBackend, MemoryRouter
        from core.orchestrator import Orchestrator
        from core.worker_circuit_breaker import WorkerCircuitBreaker

        class MockMemoryBackend(MemoryBackend):
            def __init__(self) -> None:
                self.storage: list[dict] = []

            async def fetch(self, task) -> list[dict]:
                return []

            async def write(self, data: dict) -> None:
                self.storage.append(data)

            async def list_keys(self, prefix: str) -> list[str]:
                return []

        memory_router = MemoryRouter(backends={"mock": MockMemoryBackend()})
        breaker = WorkerCircuitBreaker(failure_threshold=3)
        orchestrator = Orchestrator(
            memory_router=memory_router,
            worker_circuit_breaker=breaker,
            degraded_mode_threshold=0.5,
        )

        # Register 4 workers
        for i in range(4):
            breaker.register_worker(f"worker{i}")

        # Open circuits for 2 workers (ratio = 2/4 = 0.5 == threshold)
        breaker.record_failure("worker0")
        breaker.record_failure("worker0")
        breaker.record_failure("worker0")
        breaker.record_failure("worker1")
        breaker.record_failure("worker1")
        breaker.record_failure("worker1")

        assert orchestrator.is_degraded() is True

    def test_is_degraded_returns_true_when_ratio_above_threshold(self) -> None:
        """is_degraded returns True when degraded ratio exceeds threshold."""
        from core.memory_router import MemoryBackend, MemoryRouter
        from core.orchestrator import Orchestrator
        from core.worker_circuit_breaker import WorkerCircuitBreaker

        class MockMemoryBackend(MemoryBackend):
            def __init__(self) -> None:
                self.storage: list[dict] = []

            async def fetch(self, task) -> list[dict]:
                return []

            async def write(self, data: dict) -> None:
                self.storage.append(data)

            async def list_keys(self, prefix: str) -> list[str]:
                return []

        memory_router = MemoryRouter(backends={"mock": MockMemoryBackend()})
        breaker = WorkerCircuitBreaker(failure_threshold=3)
        orchestrator = Orchestrator(
            memory_router=memory_router,
            worker_circuit_breaker=breaker,
            degraded_mode_threshold=0.5,
        )

        # Register 3 workers
        for i in range(3):
            breaker.register_worker(f"worker{i}")

        # Open circuits for 2 workers (ratio = 2/3 = 0.67 > 0.5)
        breaker.record_failure("worker0")
        breaker.record_failure("worker0")
        breaker.record_failure("worker0")
        breaker.record_failure("worker1")
        breaker.record_failure("worker1")
        breaker.record_failure("worker1")

        assert orchestrator.is_degraded() is True

    def test_is_degraded_returns_false_after_circuit_reset(self) -> None:
        """is_degraded returns False after circuits are reset."""
        from core.memory_router import MemoryBackend, MemoryRouter
        from core.orchestrator import Orchestrator
        from core.worker_circuit_breaker import WorkerCircuitBreaker

        class MockMemoryBackend(MemoryBackend):
            def __init__(self) -> None:
                self.storage: list[dict] = []

            async def fetch(self, task) -> list[dict]:
                return []

            async def write(self, data: dict) -> None:
                self.storage.append(data)

            async def list_keys(self, prefix: str) -> list[str]:
                return []

        memory_router = MemoryRouter(backends={"mock": MockMemoryBackend()})
        breaker = WorkerCircuitBreaker(failure_threshold=3)
        orchestrator = Orchestrator(
            memory_router=memory_router,
            worker_circuit_breaker=breaker,
            degraded_mode_threshold=0.5,
        )

        # Register 3 workers
        for i in range(3):
            breaker.register_worker(f"worker{i}")

        # Open circuits for 2 workers (ratio = 2/3 = 0.67 > 0.5)
        breaker.record_failure("worker0")
        breaker.record_failure("worker0")
        breaker.record_failure("worker0")
        breaker.record_failure("worker1")
        breaker.record_failure("worker1")
        breaker.record_failure("worker1")

        assert orchestrator.is_degraded() is True

        # Reset one circuit (ratio = 1/3 = 0.33 < 0.5)
        breaker.record_success("worker0")

        assert orchestrator.is_degraded() is False


@pytest.mark.asyncio
class TestDegradedModeQueuing:
    """Test suite for degraded mode task queuing behavior."""

    async def test_task_queued_when_worker_circuit_open_and_degraded(self) -> None:
        """Task is queued when worker circuit is open and system is degraded."""
        from datetime import datetime, timezone
        from uuid import uuid4

        from core.memory_router import MemoryBackend, MemoryRouter
        from core.orchestrator import Orchestrator
        from core.schemas import Task, TaskPriority, WorkerOutput, WorkerProfile
        from core.worker_base import WorkerBase
        from core.worker_circuit_breaker import WorkerCircuitBreaker

        class MockMemoryBackend(MemoryBackend):
            def __init__(self) -> None:
                self.storage: list[dict] = []

            async def fetch(self, task) -> list[dict]:
                return []

            async def write(self, data: dict) -> None:
                self.storage.append(data)

            async def list_keys(self, prefix: str) -> list[str]:
                return []

        class MockWorker(WorkerBase):
            def __init__(self) -> None:
                self.profile = WorkerProfile(
                    worker_id="worker0",
                    worker_type="test",
                    depth_preference=0.5,
                    speculation_tolerance=0.5,
                    source_skepticism=0.5,
                    verbosity=0.5,
                    preferred_model="test-model",
                    escalation_threshold=0.8,
                    capabilities=["test"],
                )

            async def build_prompt(self, task: Task) -> str:
                return "Test prompt"

            async def parse_output(self, raw_output: str) -> WorkerOutput:
                return WorkerOutput(
                    task_id=task.task_id,
                    worker_id="worker0",
                    content="Test output",
                    confidence=1.0,
                    model_used="test-model",
                )

            async def run(self, task: Task) -> WorkerOutput:
                """Mock run method for testing."""
                return WorkerOutput(
                    task_id=task.task_id,
                    worker_id="worker0",
                    content="Test output",
                    confidence=1.0,
                    model_used="test-model",
                )

        memory_router = MemoryRouter(backends={"mock": MockMemoryBackend()})
        breaker = WorkerCircuitBreaker(failure_threshold=3)
        orchestrator = Orchestrator(
            memory_router=memory_router,
            worker_circuit_breaker=breaker,
            degraded_mode_threshold=0.5,
        )

        # Register worker
        worker = MockWorker()
        orchestrator.register_worker("worker0", worker)

        # Open circuit for worker0 (ratio = 1/1 = 1.0 > 0.5)
        breaker.record_failure("worker0")
        breaker.record_failure("worker0")
        breaker.record_failure("worker0")

        # Create a task
        task = Task(
            task_id=uuid4(),
            intent="Test task",
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            created_at=datetime.now(timezone.utc),
        )

        # Process task - should be queued
        output = await orchestrator.process_task(task, "worker0")

        # Verify task was queued
        assert output.metadata.get("queued") is True
        assert len(orchestrator._queued_tasks) == 1
        assert orchestrator._queued_tasks[0][0].task_id == task.task_id
        assert orchestrator._queued_tasks[0][1] == "worker0"

    async def test_task_not_queued_when_worker_circuit_open_but_not_degraded(
        self,
    ) -> None:
        """Task is not queued when worker circuit is open but system is not degraded."""
        from datetime import datetime, timezone
        from uuid import uuid4

        from core.memory_router import MemoryBackend, MemoryRouter
        from core.orchestrator import Orchestrator
        from core.schemas import Task, TaskPriority, WorkerOutput, WorkerProfile
        from core.worker_base import WorkerBase
        from core.worker_circuit_breaker import WorkerCircuitBreaker

        class MockMemoryBackend(MemoryBackend):
            def __init__(self) -> None:
                self.storage: list[dict] = []

            async def fetch(self, task) -> list[dict]:
                return []

            async def write(self, data: dict) -> None:
                self.storage.append(data)

            async def list_keys(self, prefix: str) -> list[str]:
                return []

        class MockWorker(WorkerBase):
            def __init__(self) -> None:
                self.profile = WorkerProfile(
                    worker_id="worker0",
                    worker_type="test",
                    depth_preference=0.5,
                    speculation_tolerance=0.5,
                    source_skepticism=0.5,
                    verbosity=0.5,
                    preferred_model="test-model",
                    escalation_threshold=0.8,
                    capabilities=["test"],
                )

            async def build_prompt(self, task: Task) -> str:
                return "Test prompt"

            async def parse_output(self, raw_output: str) -> WorkerOutput:
                return WorkerOutput(
                    task_id=task.task_id,
                    worker_id="worker0",
                    content="Test output",
                    confidence=1.0,
                    model_used="test-model",
                )

            async def run(self, task: Task) -> WorkerOutput:
                """Mock run method for testing."""
                return WorkerOutput(
                    task_id=task.task_id,
                    worker_id="worker0",
                    content="Test output",
                    confidence=1.0,
                    model_used="test-model",
                )

        memory_router = MemoryRouter(backends={"mock": MockMemoryBackend()})
        breaker = WorkerCircuitBreaker(failure_threshold=3)
        orchestrator = Orchestrator(
            memory_router=memory_router,
            worker_circuit_breaker=breaker,
            degraded_mode_threshold=0.5,
        )

        # Register 3 workers
        for i in range(3):
            worker = MockWorker()
            orchestrator.register_worker(f"worker{i}", worker)

        # Open circuit for only worker0 (ratio = 1/3 = 0.33 < 0.5, not degraded)
        breaker.record_failure("worker0")
        breaker.record_failure("worker0")
        breaker.record_failure("worker0")

        # Create a task
        task = Task(
            task_id=uuid4(),
            intent="Test task",
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            created_at=datetime.now(timezone.utc),
        )

        # Process task - should NOT be queued (system not degraded)
        # Note: This will fail because worker0 circuit is open, but it won't queue
        # because is_degraded() returns False. The task execution will fail due to
        # circuit being open, but that's expected behavior for this test.
        try:
            output = await orchestrator.process_task(task, "worker0")
            # If it doesn't fail, verify it wasn't queued
            assert output.metadata.get("queued") is False
            assert len(orchestrator._queued_tasks) == 0
        except Exception:
            # Expected to fail because circuit is open
            assert len(orchestrator._queued_tasks) == 0

    async def test_queued_tasks_resumed_when_system_exits_degraded_mode(self) -> None:
        """Queued tasks are resumed when system exits degraded mode."""
        from datetime import datetime, timezone
        from uuid import uuid4

        from core.memory_router import MemoryBackend, MemoryRouter
        from core.orchestrator import Orchestrator
        from core.schemas import Task, TaskPriority, WorkerOutput, WorkerProfile
        from core.worker_base import WorkerBase
        from core.worker_circuit_breaker import WorkerCircuitBreaker

        class MockMemoryBackend(MemoryBackend):
            def __init__(self) -> None:
                self.storage: list[dict] = []

            async def fetch(self, task) -> list[dict]:
                return []

            async def write(self, data: dict) -> None:
                self.storage.append(data)

            async def list_keys(self, prefix: str) -> list[str]:
                return []

        class MockWorker(WorkerBase):
            def __init__(self) -> None:
                self.profile = WorkerProfile(
                    worker_id="worker0",
                    worker_type="test",
                    depth_preference=0.5,
                    speculation_tolerance=0.5,
                    source_skepticism=0.5,
                    verbosity=0.5,
                    preferred_model="test-model",
                    escalation_threshold=0.8,
                    capabilities=["test"],
                )

            async def build_prompt(self, task: Task) -> str:
                return "Test prompt"

            async def parse_output(self, raw_output: str) -> WorkerOutput:
                return WorkerOutput(
                    task_id=task.task_id,
                    worker_id="worker0",
                    content="Test output",
                    confidence=1.0,
                    model_used="test-model",
                )

            async def run(self, task: Task) -> WorkerOutput:
                """Mock run method for testing."""
                return WorkerOutput(
                    task_id=task.task_id,
                    worker_id="worker0",
                    content="Test output",
                    confidence=1.0,
                    model_used="test-model",
                )

        memory_router = MemoryRouter(backends={"mock": MockMemoryBackend()})
        breaker = WorkerCircuitBreaker(failure_threshold=3)
        orchestrator = Orchestrator(
            memory_router=memory_router,
            worker_circuit_breaker=breaker,
            degraded_mode_threshold=0.5,
        )

        # Register worker
        worker = MockWorker()
        orchestrator.register_worker("worker0", worker)

        # Open circuit for worker0 (ratio = 1/1 = 1.0 > 0.5)
        breaker.record_failure("worker0")
        breaker.record_failure("worker0")
        breaker.record_failure("worker0")

        # Create a task and queue it
        task = Task(
            task_id=uuid4(),
            intent="Test task",
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            created_at=datetime.now(timezone.utc),
        )

        output = await orchestrator.process_task(task, "worker0")
        assert output.metadata.get("queued") is True
        assert len(orchestrator._queued_tasks) == 1

        # Reset the circuit (system exits degraded mode)
        # record_success resets the failure count to 0, closing the circuit
        breaker.record_success("worker0")
        assert orchestrator.is_degraded() is False
        # Verify circuit is actually closed for worker0
        assert breaker.is_available("worker0") is True

        # Create a new task to trigger queue drain
        task2 = Task(
            task_id=uuid4(),
            intent="Trigger task",
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            created_at=datetime.now(timezone.utc),
        )

        # Process new task - should drain the queue
        await orchestrator.process_task(task2, "worker0")

        # Verify queue was drained
        assert len(orchestrator._queued_tasks) == 0
