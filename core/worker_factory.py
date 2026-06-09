"""
Worker Factory - dynamic creation of specialist workers from natural language description.

Single responsibility: Analyze task descriptions and dynamically create workers
with appropriate capabilities by matching against the SkillRegistry.
"""

import asyncio
import re
from typing import TYPE_CHECKING, Any
from uuid import uuid4
from datetime import datetime

from pydantic import BaseModel, Field

from core.schemas import WorkerProfile, Task, Message, WorkerStatus
from core.observability import (
    TraceComponent,
    TraceEventType,
    TraceLevel,
    TraceEmitter,
    TraceEvent,
    NullTraceEmitter,
)
from core.exceptions import WorkerNotFoundError
from core.worker_base import WorkerBase

if TYPE_CHECKING:
    from core.skill_registry import SkillRegistry
    from core.orchestrator import Orchestrator
    from core.memory_router import MemoryRouter
    from system.worker_persistence import WorkerPersistence


class DynamicWorkerProfile(BaseModel):
    """Extended profile for dynamically generated workers."""
    worker_id: str
    worker_type: str
    name: str
    description: str
    purpose: str = ""
    capabilities: list[str] = Field(default_factory=list)
    complexity_min: float = Field(default=0.0, ge=0.0, le=1.0)
    complexity_max: float = Field(default=1.0, ge=0.0, le=1.0)
    preferred_complexity: float = Field(default=0.5, ge=0.0, le=1.0)
    depth_preference: float = Field(default=0.5, ge=0.0, le=1.0)
    speculation_tolerance: float = Field(default=0.5, ge=0.0, le=1.0)
    source_skepticism: float = Field(default=0.5, ge=0.0, le=1.0)
    verbosity: float = Field(default=0.5, ge=0.0, le=1.0)
    standing_instructions: list[str] = Field(default_factory=list)
    preferred_model: str = "default"
    preferred_models: list[str] = Field(default_factory=list)
    escalation_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    tasks_completed: int = Field(default=0, ge=0)
    avg_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    performance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    active_tasks: int = Field(default=0, ge=0)
    version: int = Field(default=1, ge=1)
    status: WorkerStatus = Field(default=WorkerStatus.ACTIVE)
    creation_date: datetime = Field(default_factory=datetime.utcnow)
    instruction_file_ref: str | None = None


class WorkerFactory:
    """Factory for dynamically creating workers from natural language descriptions."""

    def __init__(
        self,
        skill_registry: "SkillRegistry",
        orchestrator: "Orchestrator",
        memory_router: "MemoryRouter",
        emitter: TraceEmitter | None = None,
        persistence: "WorkerPersistence | None" = None,
    ) -> None:
        """Initialize the worker factory with dependencies.
        
        Args:
            skill_registry: Registry of available skills
            orchestrator: Orchestrator for worker registration
            memory_router: Memory router for persistence
            emitter: TraceEmitter for observability
            persistence: Optional worker persistence for saving/loading workers
        """
        self.emitter = emitter if emitter is not None else NullTraceEmitter()
        self.skill_registry = skill_registry
        self.orchestrator = orchestrator
        self.memory_router = memory_router
        self.persistence = persistence
        
        # Cache for generated worker profiles
        self._worker_profiles: dict[str, DynamicWorkerProfile] = {}
        
        # Load workers from persistence if provided
        if self.persistence:
            asyncio.create_task(self.load_workers_from_persistence())

    async def create_worker(self, description: str, task: Task) -> "WorkerBase":
        """
        Create a worker from a natural language description.
        
        Args:
            description: Natural language description of the worker
            task: Task to use for complexity analysis
            
        Returns:
            Created worker instance
            
        Raises:
            ValueError: If description is invalid
        """
        # Generate worker profile from description
        profile = self._generate_profile(description, task)
        
        # Store profile in cache
        self._worker_profiles[profile.worker_id] = profile
        
        # Convert to WorkerProfile
        worker_profile = WorkerProfile(
            worker_id=profile.worker_id,
            worker_type=profile.worker_type,
            depth_preference=profile.depth_preference,
            speculation_tolerance=profile.speculation_tolerance,
            source_skepticism=profile.source_skepticism,
            verbosity=profile.verbosity,
            standing_instructions=profile.standing_instructions,
            preferred_model=profile.preferred_model,
            escalation_threshold=profile.escalation_threshold,
            tasks_completed=profile.tasks_completed,
            avg_confidence=profile.avg_confidence,
            capabilities=profile.capabilities,
            preferred_complexity=profile.preferred_complexity,
        )
        
        # Create worker instance
        # For now, we'll create a placeholder worker since actual worker creation
        # requires LLM adapter and other dependencies that are not available in this prompt
        # This will be implemented in a future prompt
        from core.worker_base import WorkerBase
        from core.observability import NullTraceEmitter
        
        # Create a minimal worker for testing purposes
        # In production, this would use the profile to configure a real worker
        worker = PlaceholderWorker(
            profile=worker_profile,
            memory_router=self.memory_router,
            emitter=self.emitter,
        )
        
        # Register worker in orchestrator
        self.orchestrator.register_worker(profile.worker_id, worker)
        
        # Persist worker definition using WorkerPersistence if available
        if self.persistence:
            try:
                await self.persistence.save(profile)
            except Exception as e:
                try:
                    await self.emitter.emit(TraceEvent(
                        event_id=uuid4(),
                        timestamp=datetime.utcnow(),
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.ORCHESTRATOR,
                        level=TraceLevel.ERROR,
                        message=f"Failed to persist worker profile: {str(e)}",
                        data={"error": str(e), "worker_id": profile.worker_id},
                        duration_ms=0,
                    ))
                except Exception:
                    pass
        else:
            # Fallback to memory_router.write for backward compatibility
            try:
                await self.memory_router.write(
                    collection="workers",
                    document_id=profile.worker_id,
                    document={
                        "type": "worker_profile",
                        "worker_id": profile.worker_id,
                        "worker_type": profile.worker_type,
                        "name": profile.name,
                        "description": profile.description,
                        "capabilities": profile.capabilities,
                        "complexity_min": profile.complexity_min,
                        "complexity_max": profile.complexity_max,
                        "preferred_complexity": profile.preferred_complexity,
                        "created_at": datetime.utcnow().isoformat(),
                    }
                )
            except Exception as e:
                try:
                    await self.emitter.emit(TraceEvent(
                        event_id=uuid4(),
                        timestamp=datetime.utcnow(),
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.ORCHESTRATOR,
                        level=TraceLevel.ERROR,
                        message=f"Failed to persist worker profile: {str(e)}",
                        data={"error": str(e), "worker_id": profile.worker_id},
                        duration_ms=0,
                    ))
                except Exception:
                    pass
        
        # Emit trace event
        try:
            await self.emitter.emit(TraceEvent(
                event_id=uuid4(),
                timestamp=datetime.utcnow(),
                event_type=TraceEventType.ORCHESTRATOR_WORKER_REGISTERED,
                component=TraceComponent.ORCHESTRATOR,
                level=TraceLevel.INFO,
                message=f"Worker created from description: {profile.name}",
                data={
                    "worker_id": profile.worker_id,
                    "worker_type": profile.worker_type,
                    "capabilities": profile.capabilities,
                    "description": description,
                },
                duration_ms=0,
            ))
        except Exception:
            pass
        
        return worker

    async def can_route(self, task: Task) -> bool:
        """
        Check if the orchestrator has a worker that can handle the task.
        
        Args:
            task: Task to check
            
        Returns:
            True if a matching worker exists, False otherwise
        """
        # Check if orchestrator has any workers
        if not self.orchestrator.workers:
            return False
        
        # Simple check: if there are workers, assume one can handle the task
        # In production, this would use the orchestrator's routing logic
        return True

    async def get_or_create_worker(self, task: Task) -> "WorkerBase":
        """
        Get an existing worker or create a new one if needed.
        
        Args:
            task: Task to get or create worker for
            
        Returns:
            Worker instance
        """
        # Check if we can route to an existing worker
        if await self.can_route(task):
            # Return best matching worker from orchestrator
            # For now, return the first available worker
            worker_id = next(iter(self.orchestrator.workers.keys()))
            return self.orchestrator.workers[worker_id]
        else:
            # Create new worker from task intent
            return await self.create_worker(task.intent, task)

    async def list_workers(self) -> list[WorkerProfile]:
        """
        List all registered worker profiles.
        
        Returns:
            List of worker profiles
        """
        profiles = []
        for worker_id, worker in self.orchestrator.workers.items():
            if hasattr(worker, 'profile'):
                profiles.append(worker.profile)
        
        return profiles

    async def deregister_worker(self, worker_id: str) -> None:
        """
        Remove a worker from the orchestrator registry.
        
        Args:
            worker_id: The worker ID to deregister
        """
        # Remove from orchestrator
        self.orchestrator.deregister_worker(worker_id)
        
        # Remove from cache
        if worker_id in self._worker_profiles:
            del self._worker_profiles[worker_id]
        
        # Emit trace event
        try:
            await self.emitter.emit(TraceEvent(
                event_id=uuid4(),
                timestamp=datetime.utcnow(),
                event_type=TraceEventType.ORCHESTRATOR_WORKER_DEREGISTERED,
                component=TraceComponent.ORCHESTRATOR,
                level=TraceLevel.INFO,
                message=f"Worker deregistered: {worker_id}",
                data={"worker_id": worker_id},
                duration_ms=0,
            ))
        except Exception:
            pass
    
    async def load_workers_from_persistence(self) -> int:
        """
        Load all persisted workers from PostgreSQL and register them with the orchestrator.
        
        Returns:
            Number of workers loaded
        """
        if not self.persistence:
            return 0
        
        try:
            profiles = await self.persistence.load_all()
            count = 0
            
            for profile in profiles:
                # Only register ACTIVE workers with the orchestrator
                if profile.status == WorkerStatus.ACTIVE:
                    # Create placeholder worker for each persisted profile
                    worker = PlaceholderWorker(
                        profile=profile,
                        memory_router=self.memory_router,
                        emitter=self.emitter,
                    )
                    
                    # Register worker in orchestrator
                    self.orchestrator.register_worker(profile.worker_id, worker)
                    
                    # Cache profile
                    self._worker_profiles[profile.worker_id] = profile
                    
                    count += 1
            
            await self.emitter.emit(TraceEvent(
                event_id=uuid4(),
                timestamp=datetime.utcnow(),
                event_type=TraceEventType.OPERATION_COMPLETE,
                component=TraceComponent.ORCHESTRATOR,
                level=TraceLevel.INFO,
                message=f"Loaded {count} workers from persistence",
                data={"count": count},
                duration_ms=0,
            ))
            
            return count
        except Exception as e:
            try:
                await self.emitter.emit(TraceEvent(
                    event_id=uuid4(),
                    timestamp=datetime.utcnow(),
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.ORCHESTRATOR,
                    level=TraceLevel.ERROR,
                    message=f"Failed to load workers from persistence: {str(e)}",
                    data={"error": str(e)},
                    duration_ms=0,
                ))
            except Exception:
                pass
            return 0

    def _generate_profile(self, description: str, task: Task) -> DynamicWorkerProfile:
        """
        Generate a worker profile from a description (rule-based, no LLM).
        
        Args:
            description: Natural language description
            task: Task for complexity analysis
            
        Returns:
            Generated worker profile
        """
        # Generate worker_id as slug from description
        worker_id = self._slugify(description)
        
        # Parse capability keywords from description
        capabilities = self._parse_capabilities(description)
        
        # Match against SkillRegistry capabilities
        matched_skills = []
        for capability in capabilities:
            skills = self.skill_registry.query_by_capability(capability)
            if skills:
                matched_skills.extend([skill.name for skill in skills])
        
        # Set complexity based on task complexity
        complexity = task.complexity_score
        complexity_min = max(0.0, complexity - 0.2)
        complexity_max = min(1.0, complexity + 0.2)
        
        # Determine worker type from description
        worker_type = self._determine_worker_type(description)
        
        return DynamicWorkerProfile(
            worker_id=worker_id,
            worker_type=worker_type,
            name=description,
            description=description,
            capabilities=list(set(capabilities + matched_skills)),
            complexity_min=complexity_min,
            complexity_max=complexity_max,
            preferred_complexity=complexity,
        )

    def _slugify(self, text: str) -> str:
        """
        Convert text to a slug format.
        
        Args:
            text: Text to slugify
            
        Returns:
            Slugified text
        """
        # Convert to lowercase and replace spaces with underscores
        slug = text.lower().replace(" ", "_")
        # Remove special characters
        slug = re.sub(r"[^a-z0-9_]", "", slug)
        # Remove consecutive underscores
        slug = re.sub(r"_+", "_", slug)
        # Remove leading/trailing underscores
        slug = slug.strip("_")
        return slug

    def _parse_capabilities(self, description: str) -> list[str]:
        """
        Parse capability keywords from description.
        
        Args:
            description: Description to parse
            
        Returns:
            List of capability keywords
        """
        # Simple keyword extraction based on common capability terms
        capability_keywords = [
            "write", "read", "file", "data", "text", "code", "script",
            "web", "scrape", "api", "network", "database", "storage",
            "image", "video", "audio", "media", "process", "transform",
            "analyze", "search", "query", "compute", "calculate",
        ]
        
        description_lower = description.lower()
        capabilities = []
        
        for keyword in capability_keywords:
            if keyword in description_lower:
                capabilities.append(keyword)
        
        return capabilities

    def _determine_worker_type(self, description: str) -> str:
        """
        Determine worker type from description.
        
        Args:
            description: Description to analyze
            
        Returns:
            Worker type string
        """
        description_lower = description.lower()
        
        if any(word in description_lower for word in ["file", "write", "read"]):
            return "file_worker"
        elif any(word in description_lower for word in ["web", "scrape", "api"]):
            return "web_worker"
        elif any(word in description_lower for word in ["data", "database", "storage"]):
            return "data_worker"
        elif any(word in description_lower for word in ["image", "video", "audio", "media"]):
            return "media_worker"
        elif any(word in description_lower for word in ["code", "script", "program"]):
            return "code_worker"
        else:
            return "general_worker"


class PlaceholderWorker(WorkerBase):
    """Placeholder worker for testing WorkerFactory.
    
    This is a minimal implementation that satisfies the WorkerBase interface
    but does not perform actual work. In a future prompt, this will be replaced
    with a real dynamically generated worker.
    """
    
    def __init__(
        self,
        profile: WorkerProfile,
        memory_router: "MemoryRouter",
        emitter: TraceEmitter | None = None,
    ) -> None:
        """Initialize placeholder worker."""
        # Create a mock LLM adapter for testing
        from core.worker_base import LLMAdapter, LLMResponse
        from core.schemas import Message
        
        class MockLLMAdapter(LLMAdapter):
            def __init__(self):
                self._model_name = "mock"
                self._cost_per_token = 0.0
            
            async def generate(
                self,
                messages: list[Message],
                temperature: float = 0.1,
                max_tokens: int = 2048,
                structured_output: type[BaseModel] | None = None,
            ) -> LLMResponse:
                return LLMResponse(
                    content="Placeholder response",
                    raw={},
                    model="mock",
                    tokens_used=0,
                    duration_ms=0,
                )
            
            @property
            def model_name(self) -> str:
                return self._model_name
            
            @property
            def cost_per_token(self) -> float:
                return self._cost_per_token
        
        super().__init__(
            profile=profile,
            llm=MockLLMAdapter(),
            memory_router=memory_router,
            emitter=emitter,
        )
    
    async def build_prompt(self, task: Task, memory: list) -> list[Message]:
        """Build prompt (placeholder)."""
        from core.schemas import Message, MessageRole
        return [
            Message(
                role=MessageRole.SYSTEM,
                content="Placeholder system message",
                timestamp=datetime.utcnow(),
            ),
            Message(
                role=MessageRole.USER,
                content=task.intent,
                timestamp=datetime.utcnow(),
            ),
        ]
    
    async def parse_output(self, raw: "LLMResponse", task_id: str) -> "WorkerOutput":
        """Parse output (placeholder)."""
        from core.schemas import WorkerOutput
        return WorkerOutput(
            worker_id=self.profile.worker_id,
            task_id=task_id,
            content=raw.content,
            confidence=0.5,
            model_used=raw.model,
            tokens_used=raw.tokens_used,
        )
