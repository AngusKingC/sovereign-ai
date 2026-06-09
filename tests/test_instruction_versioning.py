"""Tests for InstructionVersionManager."""

import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock

from core.instruction_versioning import InstructionVersionManager
from core.worker_factory import DynamicWorkerProfile
from core.schemas import InstructionFile, VersionUpdateProposal, WorkerRating
from core.observability import MemoryTraceEmitter, TraceEventType, TraceComponent
from core.worker_base import LLMResponse


class TestInstructionVersionManager:
    """Tests for InstructionVersionManager class."""
    
    @pytest.fixture
    def mock_instruction_generator(self):
        """Create a mock InstructionGenerator."""
        generator = Mock()
        generator.get_instruction_file = AsyncMock()
        generator.update_instruction_file = AsyncMock()
        return generator
    
    @pytest.fixture
    def mock_rating_system(self):
        """Create a mock RatingSystem."""
        rating_system = Mock()
        rating_system.get_trend = AsyncMock()
        rating_system.get_ratings = AsyncMock()
        return rating_system
    
    @pytest.fixture
    def mock_approval_gate(self):
        """Create a mock ApprovalGate."""
        gate = Mock()
        gate.submit_for_approval = AsyncMock()
        return gate
    
    @pytest.fixture
    def mock_memory_router(self):
        """Create a mock MemoryRouter."""
        router = Mock()
        router.write = AsyncMock()
        router.fetch = AsyncMock()
        return router
    
    @pytest.fixture
    def emitter(self):
        """Create a MemoryTraceEmitter for testing."""
        return MemoryTraceEmitter()
    
    @pytest.fixture
    def version_manager(self, mock_instruction_generator, mock_rating_system, mock_approval_gate, mock_memory_router, emitter):
        """Create an InstructionVersionManager instance with mocked dependencies."""
        return InstructionVersionManager(
            instruction_generator=mock_instruction_generator,
            rating_system=mock_rating_system,
            approval_gate=mock_approval_gate,
            memory_router=mock_memory_router,
            emitter=emitter,
            trend_threshold=-0.5,
            min_ratings=5
        )
    
    @pytest.fixture
    def sample_profile(self):
        """Create a sample DynamicWorkerProfile for testing."""
        return DynamicWorkerProfile(
            worker_id="test-worker",
            worker_type="specialist",
            name="Test Worker",
            description="A test worker",
            purpose="Testing versioning",
            capabilities=["test_capability"],
            preferred_models=["qwen2.5-coder:7b"],
            performance_score=0.8
        )
    
    @pytest.fixture
    def sample_instruction_file(self):
        """Create a sample InstructionFile for testing."""
        return InstructionFile(
            worker_id="test-worker",
            version=1,
            content="# Test Worker Instruction",
            obsidian_path="workers/test-worker_INSTRUCTION.md",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
    
    @pytest.mark.asyncio
    async def test_check_and_trigger_update_returns_none_when_trend_is_above_threshold(
        self, version_manager, mock_rating_system, sample_profile
    ):
        """Test that check_and_trigger_update returns None when trend is above threshold."""
        mock_rating_system.get_trend.return_value = 0.3  # Above -0.5 threshold
        
        result = await version_manager.check_and_trigger_update(sample_profile)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_check_and_trigger_update_returns_none_when_insufficient_ratings(
        self, version_manager, mock_rating_system, mock_instruction_generator, sample_profile, sample_instruction_file
    ):
        """Test that check_and_trigger_update returns None when insufficient ratings."""
        mock_rating_system.get_trend.return_value = -0.8  # Below threshold
        mock_rating_system.get_ratings.return_value = [WorkerRating(
            rating_id="rating-1",
            worker_id="test-worker",
            task_id="task-1",
            score=5,
            model_used="qwen2.5-coder:7b",
            instruction_file_version=1,
            created_at=datetime.now()
        )]  # Only 1 rating, below min_ratings=5
        mock_instruction_generator.get_instruction_file.return_value = sample_instruction_file
        
        result = await version_manager.check_and_trigger_update(sample_profile)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_check_and_trigger_update_returns_version_update_proposal_when_trend_below_threshold(
        self, version_manager, mock_rating_system, mock_instruction_generator, sample_profile, sample_instruction_file
    ):
        """Test that check_and_trigger_update returns VersionUpdateProposal when trend below threshold."""
        mock_rating_system.get_trend.return_value = -0.8  # Below -0.5 threshold
        mock_rating_system.get_ratings.return_value = [
            WorkerRating(
                rating_id=f"rating-{i}",
                worker_id="test-worker",
                task_id=f"task-{i}",
                score=5,
                model_used="qwen2.5-coder:7b",
                instruction_file_version=1,
                created_at=datetime.now()
            )
            for i in range(10)
        ]  # 10 ratings, above min_ratings=5
        mock_instruction_generator.get_instruction_file.return_value = sample_instruction_file
        mock_instruction_generator.update_instruction_file.return_value = InstructionFile(
            worker_id="test-worker",
            version=2,
            content="# Updated Instruction",
            obsidian_path="workers/test-worker_INSTRUCTION.md",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        result = await version_manager.check_and_trigger_update(sample_profile)
        
        assert isinstance(result, VersionUpdateProposal)
        assert result.worker_id == "test-worker"
        assert result.status == "pending"
        assert result.rating_trend == -0.8
    
    @pytest.mark.asyncio
    async def test_check_and_trigger_update_submits_proposal_to_approval_gate(
        self, version_manager, mock_rating_system, mock_instruction_generator, mock_approval_gate, sample_profile, sample_instruction_file
    ):
        """Test that check_and_trigger_update submits proposal to ApprovalGate."""
        mock_rating_system.get_trend.return_value = -0.8
        mock_rating_system.get_ratings.return_value = [
            WorkerRating(
                rating_id=f"rating-{i}",
                worker_id="test-worker",
                task_id=f"task-{i}",
                score=5,
                model_used="qwen2.5-coder:7b",
                instruction_file_version=1,
                created_at=datetime.now()
            )
            for i in range(10)
        ]
        mock_instruction_generator.get_instruction_file.return_value = sample_instruction_file
        mock_instruction_generator.update_instruction_file.return_value = InstructionFile(
            worker_id="test-worker",
            version=2,
            content="# Updated Instruction",
            obsidian_path="workers/test-worker_INSTRUCTION.md",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        await version_manager.check_and_trigger_update(sample_profile)
        
        assert mock_approval_gate.submit_for_approval.call_count >= 1
        call_args = mock_approval_gate.submit_for_approval.call_args
        assert call_args[1]["description"] is not None
        assert call_args[1]["context"]["worker_id"] == "test-worker"
    
    @pytest.mark.asyncio
    async def test_check_and_trigger_update_returns_none_when_trend_is_none(
        self, version_manager, mock_rating_system, sample_profile
    ):
        """Test that check_and_trigger_update returns None when trend is None."""
        mock_rating_system.get_trend.return_value = None
        
        result = await version_manager.check_and_trigger_update(sample_profile)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_approve_update_applies_update_and_returns_new_instruction_file(
        self, version_manager, mock_instruction_generator, sample_instruction_file
    ):
        """Test that approve_update applies update and returns new InstructionFile."""
        proposal = VersionUpdateProposal(
            proposal_id="proposal-1",
            worker_id="test-worker",
            current_version=1,
            proposed_content="# Updated Instruction",
            trigger_reason="rating trend -0.8",
            rating_trend=-0.8,
            status="pending",
            created_at=datetime.now()
        )
        
        mock_instruction_generator.get_instruction_file.return_value = sample_instruction_file
        
        result = await version_manager.approve_update(proposal)
        
        assert isinstance(result, InstructionFile)
        assert result.worker_id == "test-worker"
        assert result.version == 2
        assert result.content == "# Updated Instruction"
    
    @pytest.mark.asyncio
    async def test_approve_update_sets_proposal_status_to_approved(
        self, version_manager, mock_instruction_generator, sample_instruction_file, mock_memory_router
    ):
        """Test that approve_update sets proposal status to approved."""
        proposal = VersionUpdateProposal(
            proposal_id="proposal-1",
            worker_id="test-worker",
            current_version=1,
            proposed_content="# Updated Instruction",
            trigger_reason="rating trend -0.8",
            rating_trend=-0.8,
            status="pending",
            created_at=datetime.now()
        )
        
        mock_instruction_generator.get_instruction_file.return_value = sample_instruction_file
        
        await version_manager.approve_update(proposal)
        
        # Verify proposal status was updated
        assert mock_memory_router.write.call_count >= 2
        status_call = [call for call in mock_memory_router.write.call_args_list 
                      if call[0][0].get("type") == "version_update_proposal"]
        assert len(status_call) >= 1
        assert status_call[-1][0][0]["status"] == "approved"
    
    @pytest.mark.asyncio
    async def test_approve_update_raises_if_proposal_status_is_not_pending(
        self, version_manager
    ):
        """Test that approve_update raises if proposal status is not pending."""
        proposal = VersionUpdateProposal(
            proposal_id="proposal-1",
            worker_id="test-worker",
            current_version=1,
            proposed_content="# Updated Instruction",
            trigger_reason="rating trend -0.8",
            rating_trend=-0.8,
            status="approved",  # Not pending
            created_at=datetime.now()
        )
        
        with pytest.raises(ValueError, match="Cannot approve proposal with status approved"):
            await version_manager.approve_update(proposal)
    
    @pytest.mark.asyncio
    async def test_rollback_restores_target_version_as_new_version(
        self, version_manager, mock_instruction_generator, sample_instruction_file
    ):
        """Test that rollback restores target version as new version."""
        mock_instruction_generator.get_instruction_file.return_value = sample_instruction_file
        mock_instruction_generator.get_instruction_file.return_value.version = 3
        
        # Mock version history
        version_manager.get_version_history = AsyncMock(return_value=[
            InstructionFile(
                worker_id="test-worker",
                version=1,
                content="# Version 1",
                obsidian_path="workers/test-worker_INSTRUCTION.md",
                created_at=datetime.now(),
                updated_at=datetime.now()
            ),
            InstructionFile(
                worker_id="test-worker",
                version=2,
                content="# Version 2",
                obsidian_path="workers/test-worker_INSTRUCTION.md",
                created_at=datetime.now(),
                updated_at=datetime.now()
            ),
            sample_instruction_file
        ])
        
        result = await version_manager.rollback("test-worker", 2)
        
        assert isinstance(result, InstructionFile)
        assert result.worker_id == "test-worker"
        assert result.version == 4  # New version (3 + 1)
        assert result.content == "# Version 2"  # Content from version 2
    
    @pytest.mark.asyncio
    async def test_rollback_uses_trigger_rollback_to_v_target_version(
        self, version_manager, mock_instruction_generator, sample_instruction_file, mock_memory_router
    ):
        """Test that rollback uses trigger 'rollback to v{target_version}'."""
        mock_instruction_generator.get_instruction_file.return_value = sample_instruction_file
        mock_instruction_generator.get_instruction_file.return_value.version = 3
        
        version_manager.get_version_history = AsyncMock(return_value=[
            InstructionFile(
                worker_id="test-worker",
                version=1,
                content="# Version 1",
                obsidian_path="workers/test-worker_INSTRUCTION.md",
                created_at=datetime.now(),
                updated_at=datetime.now()
            ),
            sample_instruction_file
        ])
        
        await version_manager.rollback("test-worker", 1)
        
        # Verify changelog entry was created with correct trigger
        changelog_call = [call for call in mock_memory_router.write.call_args_list 
                         if call[0][0].get("type") == "instruction_changelog"]
        assert len(changelog_call) >= 1
        assert changelog_call[-1][0][0]["trigger"] == "rollback to v1"
    
    @pytest.mark.asyncio
    async def test_rollback_raises_if_target_version_does_not_exist(
        self, version_manager, mock_instruction_generator, sample_instruction_file
    ):
        """Test that rollback raises if target version does not exist."""
        mock_instruction_generator.get_instruction_file.return_value = sample_instruction_file
        
        version_manager.get_version_history = AsyncMock(return_value=[
            sample_instruction_file
        ])
        
        with pytest.raises(ValueError, match="Version 5 not found"):
            await version_manager.rollback("test-worker", 5)
    
    @pytest.mark.asyncio
    async def test_get_version_history_returns_all_versions_oldest_first(
        self, version_manager, mock_memory_router
    ):
        """Test that get_version_history returns all versions oldest first."""
        mock_memory_router.fetch.return_value = [
            {
                "content": {
                    "worker_id": "test-worker",
                    "version": 3,
                    "content": "# Version 3",
                    "obsidian_path": "workers/test-worker_INSTRUCTION.md",
                    "created_at": datetime(2026, 6, 9, 12, 0, 0).isoformat(),
                    "updated_at": datetime(2026, 6, 9, 12, 0, 0).isoformat()
                }
            },
            {
                "content": {
                    "worker_id": "test-worker",
                    "version": 1,
                    "content": "# Version 1",
                    "obsidian_path": "workers/test-worker_INSTRUCTION.md",
                    "created_at": datetime(2026, 6, 9, 10, 0, 0).isoformat(),
                    "updated_at": datetime(2026, 6, 9, 10, 0, 0).isoformat()
                }
            },
            {
                "content": {
                    "worker_id": "test-worker",
                    "version": 2,
                    "content": "# Version 2",
                    "obsidian_path": "workers/test-worker_INSTRUCTION.md",
                    "created_at": datetime(2026, 6, 9, 11, 0, 0).isoformat(),
                    "updated_at": datetime(2026, 6, 9, 11, 0, 0).isoformat()
                }
            }
        ]
        
        history = await version_manager.get_version_history("test-worker")
        
        assert len(history) == 3
        assert history[0].version == 1
        assert history[1].version == 2
        assert history[2].version == 3
    
    @pytest.mark.asyncio
    async def test_trace_event_emitted_for_update_proposed(
        self, version_manager, mock_rating_system, mock_instruction_generator, mock_approval_gate, emitter, sample_profile, sample_instruction_file
    ):
        """Test that trace event is emitted for update_proposed."""
        mock_rating_system.get_trend.return_value = -0.8
        mock_rating_system.get_ratings.return_value = [
            WorkerRating(
                rating_id=f"rating-{i}",
                worker_id="test-worker",
                task_id=f"task-{i}",
                score=5,
                model_used="qwen2.5-coder:7b",
                instruction_file_version=1,
                created_at=datetime.now()
            )
            for i in range(10)
        ]
        mock_instruction_generator.get_instruction_file.return_value = sample_instruction_file
        mock_instruction_generator.update_instruction_file.return_value = InstructionFile(
            worker_id="test-worker",
            version=2,
            content="# Updated Instruction",
            obsidian_path="workers/test-worker_INSTRUCTION.md",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        await version_manager.check_and_trigger_update(sample_profile)
        
        events = emitter.get_events()
        assert len(events) > 0
        assert any(
            event.event_type == TraceEventType.OPERATION_COMPLETE and
            event.component == TraceComponent.SYSTEM and
            "Instruction update proposed" in event.message
            for event in events
        )
    
    @pytest.mark.asyncio
    async def test_trace_event_emitted_for_update_approved(
        self, version_manager, mock_instruction_generator, emitter, sample_instruction_file
    ):
        """Test that trace event is emitted for update_approved."""
        proposal = VersionUpdateProposal(
            proposal_id="proposal-1",
            worker_id="test-worker",
            current_version=1,
            proposed_content="# Updated Instruction",
            trigger_reason="rating trend -0.8",
            rating_trend=-0.8,
            status="pending",
            created_at=datetime.now()
        )
        
        mock_instruction_generator.get_instruction_file.return_value = sample_instruction_file
        
        await version_manager.approve_update(proposal)
        
        events = emitter.get_events()
        assert len(events) > 0
        assert any(
            event.event_type == TraceEventType.OPERATION_COMPLETE and
            event.component == TraceComponent.SYSTEM and
            "Instruction update approved" in event.message
            for event in events
        )
    
    @pytest.mark.asyncio
    async def test_trace_event_emitted_for_version_rolled_back(
        self, version_manager, mock_instruction_generator, emitter, sample_instruction_file
    ):
        """Test that trace event is emitted for version_rolled_back."""
        mock_instruction_generator.get_instruction_file.return_value = sample_instruction_file
        mock_instruction_generator.get_instruction_file.return_value.version = 3
        
        version_manager.get_version_history = AsyncMock(return_value=[
            InstructionFile(
                worker_id="test-worker",
                version=1,
                content="# Version 1",
                obsidian_path="workers/test-worker_INSTRUCTION.md",
                created_at=datetime.now(),
                updated_at=datetime.now()
            ),
            sample_instruction_file
        ])
        
        await version_manager.rollback("test-worker", 1)
        
        events = emitter.get_events()
        assert len(events) > 0
        assert any(
            event.event_type == TraceEventType.OPERATION_COMPLETE and
            event.component == TraceComponent.SYSTEM and
            "rolled back" in event.message
            for event in events
        )
