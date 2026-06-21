"""
Tests for Worker Factory.
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from core.worker_factory import WorkerFactory, DynamicWorkerProfile, PlaceholderWorker
from core.schemas import Task, TaskStatus, TaskPriority, WorkerProfile, WorkerStatus
from core.observability import MemoryTraceEmitter, TraceEventType
from core.exceptions import WorkerNotFoundError


class MockSkillRegistry:
    """Mock skill registry for testing."""
    
    def __init__(self):
        self._skills = {}
    
    def query_by_capability(self, capability: str):
        """Return mock skills for a capability."""
        # Return mock skill metadata
        class MockSkill:
            def __init__(self, name):
                self.name = name
        
        if capability == "write":
            return [MockSkill("file_writer")]
        elif capability == "web":
            return [MockSkill("web_scraper")]
        return []


class MockOrchestrator:
    """Mock orchestrator for testing."""
    
    def __init__(self):
        self.workers = {}
    
    def register_worker(self, worker_id, worker):
        """Register a worker."""
        self.workers[worker_id] = worker
    
    def deregister_worker(self, worker_id):
        """Deregister a worker."""
        if worker_id not in self.workers:
            raise WorkerNotFoundError(worker_id)
        del self.workers[worker_id]


class MockMemoryRouter:
    """Mock memory router for testing."""
    
    def __init__(self):
        self._data = {}
    
    async def write(self, collection, document_id, document):
        """Write a document."""
        self._data[f"{collection}:{document_id}"] = document
    
    async def fetch(self, task):
        """Fetch memory for a task."""
        return []
    
    async def fetch_by_filter(self, filter: dict, collection: str | None, limit: int | None):
        """Mock fetch_by_filter."""
        return []
    
    async def write_to_collection(self, data: dict, collection: str, document_id: str | None):
        """Mock write_to_collection."""
        self._data[f"{collection}:{document_id}"] = data
    
    async def get_global_context(self, caller_id: str = "orchestrator"):
        """Mock get_global_context."""
        return None
    
    async def set_global_context(self, context, caller_id: str = "orchestrator"):
        """Mock set_global_context."""
        pass


class TestWorkerFactory:
    """Test cases for WorkerFactory."""
    
    @pytest.fixture
    def skill_registry(self):
        """Create mock skill registry."""
        return MockSkillRegistry()
    
    @pytest.fixture
    def orchestrator(self):
        """Create mock orchestrator."""
        return MockOrchestrator()
    
    @pytest.fixture
    def memory_router(self):
        """Create mock memory router."""
        return MockMemoryRouter()
    
    @pytest.fixture
    def emitter(self):
        """Create memory trace emitter."""
        return MemoryTraceEmitter()
    
    @pytest.fixture
    def factory(self, skill_registry, orchestrator, memory_router, emitter):
        """Create worker factory."""
        return WorkerFactory(skill_registry, orchestrator, memory_router, emitter)
    
    @pytest.fixture
    def task(self):
        """Create a test task."""
        return Task(
            task_id=uuid4(),
            intent="Write a file",
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            current_state=TaskStatus.RECEIVED,
            created_at=datetime.now(timezone.utc),
        )
    
    @pytest.mark.asyncio
    async def test_create_worker_generates_correct_worker_profile_from_description(self, factory, task):
        """Test create_worker generates correct WorkerProfile from description."""
        description = "file writer"
        worker = await factory.create_worker(description, task)
        
        assert worker is not None
        assert hasattr(worker, 'profile')
        assert worker.profile.worker_id == "file_writer"
        assert worker.profile.worker_type == "file_worker"
    
    @pytest.mark.asyncio
    async def test_create_worker_matches_skills_from_skill_registry(self, factory, task):
        """Test create_worker matches skills from SkillRegistry."""
        description = "file writer"
        worker = await factory.create_worker(description, task)
        
        # Should have matched file_writer skill
        assert "write" in worker.profile.capabilities
    
    @pytest.mark.asyncio
    async def test_create_worker_registers_worker_in_orchestrator(self, factory, task, orchestrator):
        """Test create_worker registers worker in orchestrator."""
        description = "file writer"
        worker = await factory.create_worker(description, task)
        
        assert "file_writer" in orchestrator.workers
        assert orchestrator.workers["file_writer"] == worker
    
    @pytest.mark.asyncio
    async def test_create_worker_persists_worker_to_memory(self, factory, task, memory_router):
        """Test create_worker persists worker to memory."""
        description = "file writer"
        await factory.create_worker(description, task)
        
        assert "workers:file_writer" in memory_router._data
        assert memory_router._data["workers:file_writer"]["type"] == "worker_profile"
    
    @pytest.mark.asyncio
    async def test_create_worker_emits_trace_events(self, factory, task, emitter):
        """Test create_worker emits trace events."""
        description = "file writer"
        await factory.create_worker(description, task)
        
        events = emitter.get_events()
        assert len(events) > 0
        assert any(event.event_type == TraceEventType.ORCHESTRATOR_WORKER_REGISTERED for event in events)
    
    @pytest.mark.asyncio
    async def test_can_route_returns_true_when_matching_worker_exists(self, factory, task, orchestrator):
        """Test can_route returns True when matching worker exists."""
        # Register a worker
        description = "file writer"
        await factory.create_worker(description, task)
        
        can_route = await factory.can_route(task)
        assert can_route is True
    
    @pytest.mark.asyncio
    async def test_can_route_returns_false_when_no_matching_worker_exists(self, factory, task, orchestrator):
        """Test can_route returns False when no matching worker exists."""
        # No workers registered
        can_route = await factory.can_route(task)
        assert can_route is False
    
    @pytest.mark.asyncio
    async def test_get_or_create_worker_returns_existing_worker_when_can_route_is_true(self, factory, task):
        """Test get_or_create_worker returns existing worker when can_route is True."""
        # Create a worker first
        description = "file writer"
        created_worker = await factory.create_worker(description, task)
        
        # Get or create should return existing worker
        worker = await factory.get_or_create_worker(task)
        assert worker is not None
    
    @pytest.mark.asyncio
    async def test_get_or_create_worker_creates_new_worker_when_can_route_is_false(self, factory, task, orchestrator):
        """Test get_or_create_worker creates new worker when can_route is False."""
        # Clear any existing workers
        orchestrator.workers.clear()
        
        # Get or create should create new worker
        worker = await factory.get_or_create_worker(task)
        assert worker is not None
        assert len(orchestrator.workers) > 0
    
    @pytest.mark.asyncio
    async def test_list_workers_returns_all_registered_profiles(self, factory, task):
        """Test list_workers returns all registered profiles."""
        # Create multiple workers
        await factory.create_worker("file writer", task)
        await factory.create_worker("web scraper", task)
        
        profiles = await factory.list_workers()
        assert len(profiles) >= 2
    
    @pytest.mark.asyncio
    async def test_deregister_worker_removes_worker_from_orchestrator(self, factory, task, orchestrator):
        """Test deregister_worker removes worker from orchestrator."""
        description = "file writer"
        await factory.create_worker(description, task)
        
        assert "file_writer" in orchestrator.workers
        
        await factory.deregister_worker("file_writer")
        
        assert "file_writer" not in orchestrator.workers
    
    @pytest.mark.asyncio
    async def test_deregister_worker_raises_worker_not_found_error_for_unknown_worker_id(self, factory):
        """Test deregister_worker raises WorkerNotFoundError for unknown worker_id."""
        with pytest.raises(WorkerNotFoundError):
            await factory.deregister_worker("nonexistent_worker")
    
    def test_worker_id_slug_generation_from_description(self, factory):
        """Test worker_id slug generation from description."""
        description = "Video Script Writer"
        worker_id = factory._slugify(description)
        
        assert worker_id == "video_script_writer"
        assert worker_id.islower()
        assert " " not in worker_id
    
    def test_orchestrator_deregister_worker_raises_worker_not_found_error(self, orchestrator):
        """Test orchestrator deregister_worker raises WorkerNotFoundError."""
        with pytest.raises(WorkerNotFoundError):
            orchestrator.deregister_worker("nonexistent_worker")


class TestDynamicWorkerProfile:
    """Test cases for DynamicWorkerProfile."""
    
    def test_dynamic_worker_profile_creation(self):
        """Test DynamicWorkerProfile can be created with required fields."""
        profile = DynamicWorkerProfile(
            worker_id="test_worker",
            worker_type="general_worker",
            name="Test Worker",
            description="A test worker",
        )
        
        assert profile.worker_id == "test_worker"
        assert profile.worker_type == "general_worker"
        assert profile.capabilities == []
        assert profile.complexity_min == 0.0
        assert profile.complexity_max == 1.0
    
    def test_created_worker_has_active_status_by_default(self):
        """Test created worker has ACTIVE status by default."""
        profile = DynamicWorkerProfile(
            worker_id="test_worker",
            worker_type="general_worker",
            name="Test Worker",
            description="A test worker",
        )
        
        assert profile.status == WorkerStatus.ACTIVE
    
    def test_dynamic_worker_profile_has_all_required_fields(self):
        """Test DynamicWorkerProfile has all required fields."""
        profile = DynamicWorkerProfile(
            worker_id="test_worker",
            worker_type="general_worker",
            name="Test Worker",
            description="A test worker",
            purpose="Test purpose",
            capabilities=["code", "reasoning"],
            preferred_models=["ollama/llama3.2:3b"],
            performance_score=0.85,
            active_tasks=2,
            version=1,
            status=WorkerStatus.ACTIVE,
            instruction_file_ref="instructions.md",
        )
        
        assert profile.worker_id == "test_worker"
        assert profile.name == "Test Worker"
        assert profile.purpose == "Test purpose"
        assert profile.capabilities == ["code", "reasoning"]
        assert profile.preferred_models == ["ollama/llama3.2:3b"]
        assert profile.performance_score == 0.85
        assert profile.active_tasks == 2
        assert profile.version == 1
        assert profile.status == WorkerStatus.ACTIVE
        assert profile.instruction_file_ref == "instructions.md"
        assert profile.creation_date is not None
    
    def test_dynamic_worker_profile_instruction_file_ref_defaults_to_none(self):
        """Test DynamicWorkerProfile instruction_file_ref defaults to None."""
        profile = DynamicWorkerProfile(
            worker_id="test_worker",
            worker_type="general_worker",
            name="Test Worker",
            description="A test worker",
        )
        
        assert profile.instruction_file_ref is None


class TestPlaceholderWorker:
    """Test cases for PlaceholderWorker."""
    
    @pytest.fixture
    def worker_profile(self):
        """Create a test worker profile."""
        return WorkerProfile(
            worker_id="placeholder_worker",
            worker_type="general_worker",
            depth_preference=0.5,
            speculation_tolerance=0.5,
            source_skepticism=0.5,
            verbosity=0.5,
            preferred_model="default",
            escalation_threshold=0.8,
            capabilities=[],
            preferred_complexity=0.5,
        )
    
    @pytest.fixture
    def memory_router(self):
        """Create mock memory router."""
        return MockMemoryRouter()
    
    @pytest.fixture
    def emitter(self):
        """Create memory trace emitter."""
        return MemoryTraceEmitter()
    
    @pytest.fixture
    def placeholder_worker(self, worker_profile, memory_router, emitter):
        """Create placeholder worker."""
        return PlaceholderWorker(worker_profile, memory_router, emitter)
    
    @pytest.fixture
    def task(self):
        """Create a test task."""
        return Task(
            task_id=uuid4(),
            intent="Test task",
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            current_state=TaskStatus.RECEIVED,
            created_at=datetime.now(timezone.utc),
        )
    
    @pytest.mark.asyncio
    async def test_placeholder_worker_build_prompt(self, placeholder_worker, task):
        """Test placeholder worker can build prompt."""
        messages = await placeholder_worker.build_prompt(task, [])
        
        assert len(messages) > 0
        assert len(messages) == 2  # system and user messages
    
    @pytest.mark.asyncio
    async def test_placeholder_worker_parse_output(self, placeholder_worker, task):
        """Test placeholder worker can parse output."""
        from core.worker_base import LLMResponse
        
        llm_response = LLMResponse(
            content="Test output",
            raw={},
            model="mock",
            tokens_used=0,
            duration_ms=0,
        )
        
        output = await placeholder_worker.parse_output(llm_response, str(task.task_id))
        
        assert output.worker_id == placeholder_worker.profile.worker_id
        assert output.content == "Test output"
