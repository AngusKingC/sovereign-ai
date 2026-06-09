"""
Core schema definitions.

Single responsibility: Define all Pydantic models and type schemas used across the framework.
Ensures type safety and validation at all boundaries.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, field_serializer


class MessageRole(str, Enum):
    """Role of a message sender."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class TaskPriority(str, Enum):
    """Priority levels for tasks."""
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class TaskStatus(str, Enum):
    """Status of task execution."""
    RECEIVED = "received"
    PLANNED = "planned"
    EXECUTING = "executing"
    VALIDATING = "validating"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DENIED = "denied"
    
    # Backward compatibility aliases
    PENDING = "received"  # Maps to RECEIVED
    RUNNING = "executing"  # Maps to EXECUTING
    ESCALATED = "awaiting_approval"  # Maps to AWAITING_APPROVAL


class WorkerStatus(str, Enum):
    """Status of a worker instance."""
    ACTIVE = "active"
    IDLE = "idle"
    ARCHIVED = "archived"
    DEPRECATED = "deprecated"


class ScratchpadEntryType(str, Enum):
    """Types of scratchpad entries for worker reasoning."""
    REASONING = "reasoning"
    INTERMEDIATE_RESULT = "intermediate_result"
    DEAD_END = "dead_end"
    OBSERVATION = "observation"
    PLAN_STEP = "plan_step"


class Layer(str, Enum):
    """Architecture layer identifier."""
    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    ESCALATION = "ESCALATION"


class EventType(str, Enum):
    """Types of trace events."""
    MEMORY_QUERY = "MEMORY_QUERY"
    MEMORY_WRITE = "MEMORY_WRITE"
    PROMPT_BUILT = "PROMPT_BUILT"
    LLM_CALLED = "LLM_CALLED"
    LLM_RAW_RESPONSE = "LLM_RAW_RESPONSE"
    VALIDATION_PASSED = "VALIDATION_PASSED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    ESCALATION_TRIGGERED = "ESCALATION_TRIGGERED"
    SYNTHESIS_STARTED = "SYNTHESIS_STARTED"
    OUTPUT_FINAL = "OUTPUT_FINAL"


class Message(BaseModel):
    """A message in the conversation flow."""
    role: MessageRole
    content: str
    timestamp: datetime
    metadata: Optional[dict[str, Any]] = None

    @field_serializer('timestamp')
    def serialize_timestamp(self, value: datetime) -> str:
        return value.isoformat()


class TaskStateTransition(BaseModel):
    """A state transition for a task."""
    task_id: UUID = Field(description="Task identifier")
    from_state: TaskStatus = Field(description="Previous state")
    to_state: TaskStatus = Field(description="New state")
    timestamp: datetime = Field(default_factory=datetime.now, description="When transition occurred")
    reason: str | None = Field(default=None, description="Reason for transition")
    actor: str = Field(description="Which component triggered the transition")

    @field_serializer('timestamp')
    def serialize_timestamp(self, value: datetime) -> str:
        return value.isoformat()


class Task(BaseModel):
    """A task to be processed by the agent framework."""
    task_id: UUID
    parent_task_id: Optional[UUID] = None
    intent: str
    complexity_score: float = Field(ge=0.0, le=1.0)
    priority: TaskPriority
    status: TaskStatus = Field(default=TaskStatus.RECEIVED, description="Current task status (use current_state for new code)")
    current_state: TaskStatus = Field(default=TaskStatus.RECEIVED, description="Current task state")
    state_history: list[TaskStateTransition] = Field(default_factory=list, description="History of state transitions")
    created_at: datetime
    validation_failures: int = Field(default=0, ge=0)

    @field_validator("complexity_score")
    @classmethod
    def validate_complexity(cls, v: float) -> float:
        """Ensure complexity score is between 0 and 1."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("complexity_score must be between 0 and 1")
        return v
    
    @field_serializer("status")
    def serialize_status(self, value: TaskStatus) -> str:
        """Serialize status for backward compatibility."""
        return value.value
    
    @field_serializer("current_state")
    def serialize_current_state(self, value: TaskStatus) -> str:
        """Serialize current_state."""
        return value.value
    
    @field_serializer('created_at')
    def serialize_created_at(self, value: datetime) -> str:
        return value.isoformat()


class WorkerProfile(BaseModel):
    """Profile defining a worker's behavior and preferences."""
    worker_id: str
    worker_type: str
    depth_preference: float = Field(ge=0.0, le=1.0)
    speculation_tolerance: float = Field(ge=0.0, le=1.0)
    source_skepticism: float = Field(ge=0.0, le=1.0)
    verbosity: float = Field(ge=0.0, le=1.0)
    standing_instructions: list[str] = Field(default_factory=list)
    preferred_model: str
    escalation_threshold: float = Field(ge=0.0, le=1.0)
    tasks_completed: int = Field(default=0, ge=0)
    avg_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    capabilities: list[str] = Field(default_factory=list, description="List of capability keywords for worker routing")
    preferred_complexity: float = Field(default=0.5, ge=0.0, le=1.0, description="Preferred task complexity score (0.0-1.0)")

    @field_validator("depth_preference", "speculation_tolerance", "source_skepticism", "verbosity", "escalation_threshold", "preferred_complexity")
    @classmethod
    def validate_preference(cls, v: float) -> float:
        """Ensure preference scores are between 0 and 1."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("preference scores must be between 0 and 1")
        return v


class WorkerOutput(BaseModel):
    """Output produced by a worker after processing a task."""
    worker_id: str
    task_id: UUID
    content: str
    reasoning_steps: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    sources: list[str] = Field(default_factory=list)
    claims: list[str] = Field(default_factory=list)
    escalation_recommended: bool = False
    model_used: str
    tokens_used: int = Field(default=0, ge=0)

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Ensure confidence is between 0 and 1."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        return v


class TraceEvent(BaseModel):
    """An event tracing execution flow across components."""
    event_id: UUID
    timestamp: datetime
    layer: Layer
    component: str
    event_type: EventType
    payload: dict[str, Any]
    duration_ms: int = Field(ge=0)
    model_used: Optional[str] = None
    token_cost: Optional[int] = Field(default=None, ge=0)
    success: bool

    @field_serializer('timestamp')
    def serialize_timestamp(self, value: datetime) -> str:
        return value.isoformat()


class EscalationDecision(BaseModel):
    """Decision regarding whether to escalate to cloud models."""
    should_escalate: bool
    reasons: list[str] = Field(default_factory=list)
    suggested_model: str
    estimated_cost: float = Field(ge=0.0)
    task_id: UUID


class StrategicContext(BaseModel):
    """High-level context about the agent's current state and goals."""
    active_goals: list[str] = Field(default_factory=list)
    pending_tasks: list[Task] = Field(default_factory=list)
    completed_today: list[str] = Field(default_factory=list)
    blocked_tasks: list[str] = Field(default_factory=list)
    worker_performance: dict[str, float] = Field(default_factory=dict)
    cloud_spend_today: float = Field(default=0.0, ge=0.0)
    open_questions: list[str] = Field(default_factory=list)
    last_updated: datetime

    @field_serializer('last_updated')
    def serialize_last_updated(self, value: datetime) -> str:
        return value.isoformat()


class SessionSummary(BaseModel):
    """Summary of a complete agent session."""
    session_id: UUID
    decisions_made: list[str] = Field(default_factory=list)
    tasks_completed: list[str] = Field(default_factory=list)
    tasks_pending: list[str] = Field(default_factory=list)
    knowledge_updates: list[str] = Field(default_factory=list)
    escalations: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    closed_at: datetime

    @field_serializer('closed_at')
    def serialize_closed_at(self, value: datetime) -> str:
        return value.isoformat()


class GPUInfo(BaseModel):
    """GPU hardware information."""
    model_name: str = "unknown"
    total_vram_mb: int = Field(default=0, ge=0)
    available_vram_mb: int = Field(default=0, ge=0)
    cuda_support: bool = False
    rocm_support: bool = False
    metal_support: bool = False
    driver_version: str = "unknown"


class CPUInfo(BaseModel):
    """CPU hardware information."""
    model_name: str = "unknown"
    physical_cores: int = Field(default=0, ge=0)
    logical_threads: int = Field(default=0, ge=0)
    architecture: str = "unknown"
    base_clock_ghz: float = Field(default=0.0, ge=0.0)


class RAMInfo(BaseModel):
    """RAM information."""
    total_mb: int = Field(default=0, ge=0)
    available_mb: int = Field(default=0, ge=0)
    usage_percent: float = Field(default=0.0, ge=0.0, le=100.0)


class StorageInfo(BaseModel):
    """Storage partition information."""
    mount_point: str
    total_mb: int = Field(default=0, ge=0)
    available_mb: int = Field(default=0, ge=0)
    filesystem_type: str = "unknown"


class OSInfo(BaseModel):
    """Operating system information."""
    name: str = "unknown"
    version: str = "unknown"
    kernel_build: str = "unknown"
    python_version: str = "unknown"
    docker_available: bool = False
    nvidia_drivers_present: bool = False


class NetworkInfo(BaseModel):
    """Network connectivity information."""
    internet_available: bool = False
    bandwidth_category: str = "none"  # none, low, medium, high


class OllamaModelInfo(BaseModel):
    """Ollama model information."""
    name: str
    size_on_disk_mb: int = Field(default=0, ge=0)
    loaded_in_vram: bool = False


class OllamaInfo(BaseModel):
    """Ollama service information."""
    running: bool = False
    models_downloaded: list[OllamaModelInfo] = Field(default_factory=list)
    models_loaded: list[str] = Field(default_factory=list)


class SystemProfile(BaseModel):
    """Complete system hardware and software profile."""
    gpu: GPUInfo = Field(default_factory=GPUInfo)
    cpu: CPUInfo = Field(default_factory=CPUInfo)
    ram: RAMInfo = Field(default_factory=RAMInfo)
    storage: list[StorageInfo] = Field(default_factory=list)
    os: OSInfo = Field(default_factory=OSInfo)
    network: NetworkInfo = Field(default_factory=NetworkInfo)
    ollama: OllamaInfo = Field(default_factory=OllamaInfo)
    profiled_at: datetime = Field(default_factory=datetime.now)

    @field_serializer('profiled_at')
    def serialize_profiled_at(self, value: datetime) -> str:
        return value.isoformat()


class ModelSource(str, Enum):
    """Source of a model."""
    OLLAMA = "ollama"
    HUGGINGFACE = "huggingface"
    LM_STUDIO = "lm_studio"
    LLAMA_CPP = "llama_cpp"
    API = "api"


class DownloadStatus(str, Enum):
    """Download status of a model."""
    NOT_DOWNLOADED = "not_downloaded"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    FAILED = "failed"


class QuantisationVariant(BaseModel):
    """Quantisation variant information for a model."""
    name: str = Field(description="Quantisation name (e.g. Q4_K_M, Q8_0, fp16)")
    size_on_disk_gb: float = Field(ge=0.0, description="Size on disk in GB")
    vram_required_gb: float = Field(ge=0.0, description="VRAM required in GB")
    ram_required_gb: float = Field(ge=0.0, description="RAM required in GB for CPU offload")
    quality_score: float = Field(ge=0.0, le=1.0, description="Quality score (0.0-1.0, higher is better)")
    speed_score: float = Field(ge=0.0, le=1.0, description="Speed score (0.0-1.0, higher is faster)")


class ModelEntry(BaseModel):
    """Registry entry for a model."""
    model_id: str = Field(description="Unique identifier (e.g. ollama/qwen2.5-coder:7b)")
    name: str = Field(description="Human readable name")
    source: ModelSource = Field(description="Model source")
    adapter_compatibility: list[str] = Field(default_factory=list, description="Adapter names that can run this model")
    task_tags: list[str] = Field(default_factory=list, description="Task suitability tags (e.g. code, reasoning, chat)")
    quantisation_variants: list[QuantisationVariant] = Field(default_factory=list, description="Available quantisation variants")
    download_status: DownloadStatus = Field(default=DownloadStatus.NOT_DOWNLOADED, description="Download status")
    downloaded_quantisation: str | None = Field(default=None, description="Which variant is currently downloaded")
    last_updated: datetime = Field(default_factory=datetime.now, description="Last updated timestamp")
    license: str = Field(default="", description="Model license")
    description: str = Field(default="", description="Model description")

    @field_serializer('last_updated')
    def serialize_last_updated(self, value: datetime) -> str:
        return value.isoformat()


class LoadedModel(BaseModel):
    """Information about a currently loaded model."""
    model_id: str = Field(description="Model identifier")
    adapter_name: str = Field(description="Adapter managing this model")
    quantisation: str = Field(description="Quantisation variant loaded")
    vram_used_gb: float = Field(ge=0.0, description="VRAM used in GB")
    ram_used_gb: float = Field(ge=0.0, description="RAM used in GB")
    loaded_at: datetime = Field(default_factory=datetime.now, description="When model was loaded")
    last_used_at: datetime = Field(default_factory=datetime.now, description="Last time model was used")
    is_pinned: bool = Field(default=False, description="Whether model is pinned (never auto-evicted)")
    task_priority: TaskPriority = Field(default=TaskPriority.NORMAL, description="Task priority for eviction decisions")

    @field_serializer('loaded_at')
    def serialize_loaded_at(self, value: datetime) -> str:
        return value.isoformat()
    
    @field_serializer('last_used_at')
    def serialize_last_used_at(self, value: datetime) -> str:
        return value.isoformat()


class ResourceSnapshot(BaseModel):
    """Snapshot of current resource usage."""
    timestamp: datetime = Field(default_factory=datetime.now, description="Snapshot timestamp")
    vram_total_gb: float = Field(ge=0.0, description="Total VRAM in GB")
    vram_used_gb: float = Field(ge=0.0, description="VRAM used in GB")
    vram_available_gb: float = Field(ge=0.0, description="VRAM available in GB")
    ram_total_gb: float = Field(ge=0.0, description="Total RAM in GB")
    ram_used_gb: float = Field(ge=0.0, description="RAM used in GB")
    ram_available_gb: float = Field(ge=0.0, description="RAM available in GB")
    loaded_models: list[LoadedModel] = Field(default_factory=list, description="Currently loaded models")

    @field_serializer('timestamp')
    def serialize_timestamp(self, value: datetime) -> str:
        return value.isoformat()


class LoadDecision(BaseModel):
    """Decision result for a model load request."""
    approved: bool = Field(description="Whether the load is approved")
    model_id: str = Field(description="Model identifier")
    quantisation: str = Field(description="Quantisation variant")
    models_to_evict: list[str] = Field(default_factory=list, description="Model IDs to evict")
    requires_user_approval: bool = Field(default=False, description="Whether user approval is required")
    reason: str = Field(description="Human-readable reason for decision")


from typing import Protocol, runtime_checkable


@runtime_checkable
class ApprovalCallback(Protocol):
    """Protocol for approval callback interface."""
    
    async def request_approval(
        self,
        action_description: str,
        pinned_model_to_evict: str,
        new_model_requesting: str,
        memory_impact: str,
    ) -> bool:
        """Request user approval for an action.
        
        Args:
            action_description: Description of the action requiring approval
            pinned_model_to_evict: Which pinned model would be evicted
            new_model_requesting: Which new model is requesting the space
            memory_impact: Description of memory impact
            
        Returns:
            True if approved, False otherwise
        """
        ...


class DownloadRequest(BaseModel):
    """Request to download a model."""
    model_id: str = Field(description="Model identifier")
    source: ModelSource = Field(description="Model source")
    quantisation: str | None = Field(default=None, description="Quantisation variant")
    adapter_name: str = Field(description="Which adapter will use this model")
    reason: str = Field(description="Why this model is being requested")


class DownloadResult(BaseModel):
    """Result of a model download operation."""
    success: bool = Field(description="Whether download succeeded")
    model_id: str = Field(description="Model identifier")
    quantisation: str | None = Field(default=None, description="Quantisation variant downloaded")
    size_downloaded_gb: float = Field(ge=0.0, description="Size downloaded in GB")
    duration_seconds: float = Field(ge=0.0, description="Download duration in seconds")
    error: str | None = Field(default=None, description="Error message if failed")


class ScratchpadEntry(BaseModel):
    """A single entry in a task's scratchpad."""
    entry_id: UUID = Field(default_factory=uuid4, description="Unique entry identifier")
    task_id: UUID = Field(description="Task identifier")
    worker_id: str = Field(description="Worker that created this entry")
    entry_type: ScratchpadEntryType = Field(description="Type of scratchpad entry")
    content: str = Field(description="Entry content")
    timestamp: datetime = Field(default_factory=datetime.now, description="When entry was created")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    @field_serializer('timestamp')
    def serialize_timestamp(self, value: datetime) -> str:
        return value.isoformat()


class Scratchpad(BaseModel):
    """A per-task working memory scratchpad for worker reasoning."""
    scratchpad_id: UUID = Field(default_factory=uuid4, description="Unique scratchpad identifier")
    task_id: UUID = Field(description="Task identifier")
    entries: list[ScratchpadEntry] = Field(default_factory=list, description="All entries in the scratchpad")
    created_at: datetime = Field(default_factory=datetime.now, description="When scratchpad was created")
    completed_at: datetime | None = Field(default=None, description="When scratchpad was compacted")
    summary: str | None = Field(default=None, description="Compacted summary of scratchpad")


class WorkerRating(BaseModel):
    """A performance rating for a worker on a specific task."""
    rating_id: str = Field(description="Unique rating identifier (UUID)")
    worker_id: str = Field(description="Worker being rated")
    task_id: str = Field(description="Task identifier")
    score: int = Field(ge=1, le=10, description="Performance score from 1 to 10")
    model_used: str = Field(description="Model used for this task")
    instruction_file_version: int = Field(description="Instruction file version used")
    comment: str | None = Field(default=None, description="Optional comment on the rating")
    created_at: datetime = Field(description="When the rating was created")

    @field_validator('score')
    @classmethod
    def validate_score(cls, v: int) -> int:
        """Validate that score is between 1 and 10."""
        if not 1 <= v <= 10:
            raise ValueError('Score must be between 1 and 10')
        return v


class InstructionFile(BaseModel):
    """An instruction file for a worker or orchestrator."""
    worker_id: str = Field(description="Worker or orchestrator identifier")
    version: int = Field(description="Instruction file version (starts at 1, increments on update)")
    content: str = Field(description="Full markdown instruction content")
    obsidian_path: str = Field(description="Obsidian vault path for this file")
    created_at: datetime = Field(description="When this version was created")
    updated_at: datetime = Field(description="When this version was last updated")


class InstructionChangelogEntry(BaseModel):
    """A changelog entry for instruction file updates."""
    worker_id: str = Field(description="Worker or orchestrator identifier")
    version: int = Field(description="Instruction file version this entry describes")
    trigger: str = Field(description="What caused this update")
    diff_summary: str = Field(description="LLM-generated summary of what changed")
    rating_trend: float | None = Field(default=None, description="Rating trend at time of update")
    created_at: datetime = Field(description="When this changelog entry was created")


class VersionUpdateProposal(BaseModel):
    """A proposal to update an instruction file."""
    proposal_id: str = Field(description="Unique proposal identifier (UUID)")
    worker_id: str = Field(description="Worker identifier")
    current_version: int = Field(description="Current instruction file version")
    proposed_content: str = Field(description="LLM-generated updated content")
    trigger_reason: str = Field(description="Reason for update proposal")
    rating_trend: float = Field(description="Rating trend that triggered this proposal")
    status: str = Field(description="Proposal status: pending, approved, or rejected")
    created_at: datetime = Field(description="When this proposal was created")


class OrchestratorMetrics(BaseModel):
    """Metrics for orchestrator routing decisions."""
    task_id: str = Field(description="Task identifier")
    routed_to_worker_id: str = Field(description="Worker that was selected for this task")
    routing_score: float = Field(description="Score assigned to selected worker at routing time")
    task_completed: bool = Field(description="Whether the task reached a terminal success state")
    user_rating: float | None = Field(default=None, description="Manual rating if provided (1-10), else None")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When this routing decision was made")


class Scratchpad(BaseModel):
    """A per-task working memory scratchpad for worker reasoning."""
    scratchpad_id: UUID = Field(default_factory=uuid4, description="Unique scratchpad identifier")
    task_id: UUID = Field(description="Task identifier")
    entries: list[ScratchpadEntry] = Field(default_factory=list, description="All entries in the scratchpad")
    created_at: datetime = Field(default_factory=datetime.now, description="When scratchpad was created")
    completed_at: datetime | None = Field(default=None, description="When scratchpad was compacted")
    summary: str | None = Field(default=None, description="Compacted summary of scratchpad")
    is_compacted: bool = Field(default=False, description="Whether scratchpad has been compacted")

    @field_serializer('created_at')
    def serialize_created_at(self, value: datetime) -> str:
        return value.isoformat()
    
    @field_serializer('completed_at')
    def serialize_completed_at(self, value: datetime | None) -> str | None:
        return value.isoformat() if value else None

