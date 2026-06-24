"""Unit tests for AutoCorrector."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from core.auto_corrector import (
    ApplyResult,
    ApplyStatus,
    AutoCorrector,
    ProposalClassification,
)
from core.observability import MemoryTraceEmitter
from core.schemas import VersionUpdateProposal


@pytest.fixture
def mock_instruction_version_manager():
    """Create a mock InstructionVersionManager."""
    ivm = MagicMock()
    ivm.approve_update = AsyncMock()
    return ivm


@pytest.fixture
def mock_approval_gate():
    """Create a mock ApprovalGate."""
    gate = MagicMock()
    gate.submit_for_approval = AsyncMock()
    return gate


@pytest.fixture
def auto_corrector(mock_instruction_version_manager, mock_approval_gate):
    """Create an AutoCorrector with mocked dependencies."""
    return AutoCorrector(
        instruction_version_manager=mock_instruction_version_manager,
        approval_gate=mock_approval_gate,
        emitter=MemoryTraceEmitter(),
    )


@pytest.fixture
def safe_proposal():
    """Create a safe proposal (instruction_tweak)."""
    return VersionUpdateProposal(
        proposal_id=str(uuid4()),
        worker_id="worker-1",
        current_version=1,
        proposed_content="# Updated instruction",
        trigger_reason="rating trend -0.8",
        rating_trend=-0.8,
        status="pending",
        created_at=datetime.now(timezone.utc),
        proposal_type="instruction_tweak",
    )


@pytest.fixture
def unsafe_proposal():
    """Create an unsafe proposal (code_change)."""
    return VersionUpdateProposal(
        proposal_id=str(uuid4()),
        worker_id="worker-1",
        current_version=1,
        proposed_content="diff --git a/core/foo.py ...",
        trigger_reason="eval score 0.3",
        rating_trend=-0.8,
        status="pending",
        created_at=datetime.now(timezone.utc),
        proposal_type="code_change",
    )


class TestAutoCorrectorClassification:
    """Tests for AutoCorrector.classify()."""

    @pytest.mark.asyncio
    async def test_classify_instruction_tweak_is_safe(
        self, auto_corrector, safe_proposal
    ):
        """Given proposal_type='instruction_tweak', classify returns SAFE."""
        result = await auto_corrector.classify(safe_proposal)
        assert result == ProposalClassification.SAFE

    @pytest.mark.asyncio
    async def test_classify_routing_weight_is_safe(self, auto_corrector):
        """Given proposal_type='routing_weight', classify returns SAFE."""
        proposal = VersionUpdateProposal(
            proposal_id=str(uuid4()),
            worker_id="worker-1",
            current_version=1,
            proposed_content="weights: {worker-1: 0.8}",
            trigger_reason="routing accuracy 0.4",
            rating_trend=-0.6,
            status="pending",
            created_at=datetime.now(timezone.utc),
            proposal_type="routing_weight",
        )
        result = await auto_corrector.classify(proposal)
        assert result == ProposalClassification.SAFE

    @pytest.mark.asyncio
    async def test_classify_code_change_is_unsafe(
        self, auto_corrector, unsafe_proposal
    ):
        """Given proposal_type='code_change', classify returns UNSAFE."""
        result = await auto_corrector.classify(unsafe_proposal)
        assert result == ProposalClassification.UNSAFE

    @pytest.mark.asyncio
    async def test_classify_model_download_is_unsafe(self, auto_corrector):
        """Given proposal_type='model_download', classify returns UNSAFE."""
        proposal = VersionUpdateProposal(
            proposal_id=str(uuid4()),
            worker_id="worker-1",
            current_version=1,
            proposed_content="download qwen2.5-coder:32b",
            trigger_reason="task complexity 0.9",
            rating_trend=-0.5,
            status="pending",
            created_at=datetime.now(timezone.utc),
            proposal_type="model_download",
        )
        result = await auto_corrector.classify(proposal)
        assert result == ProposalClassification.UNSAFE

    @pytest.mark.asyncio
    async def test_classify_unknown_type_defaults_to_unsafe(self, auto_corrector):
        """Given an unknown proposal_type, classify returns UNSAFE (defense in depth)."""
        proposal = VersionUpdateProposal(
            proposal_id=str(uuid4()),
            worker_id="worker-1",
            current_version=1,
            proposed_content="unknown operation",
            trigger_reason="unknown",
            rating_trend=-0.5,
            status="pending",
            created_at=datetime.now(timezone.utc),
            proposal_type="some_new_type",
        )
        result = await auto_corrector.classify(proposal)
        assert result == ProposalClassification.UNSAFE


class TestAutoCorrectorApplyProposal:
    """Tests for AutoCorrector.apply_proposal()."""

    @pytest.mark.asyncio
    async def test_apply_proposal_safe_calls_ivm_approve_update(
        self, auto_corrector, mock_instruction_version_manager, safe_proposal
    ):
        """Given a safe proposal, apply_proposal calls IVM.approve_update exactly once."""
        result = await auto_corrector.apply_proposal(safe_proposal)

        mock_instruction_version_manager.approve_update.assert_called_once_with(
            safe_proposal
        )
        assert result.status == ApplyStatus.APPLIED
        assert result.classification == ProposalClassification.SAFE
        assert result.applied_at is not None

    @pytest.mark.asyncio
    async def test_apply_proposal_safe_does_not_call_approval_gate(
        self, auto_corrector, mock_approval_gate, safe_proposal
    ):
        """Given a safe proposal, apply_proposal does NOT call ApprovalGate.submit_for_approval."""
        await auto_corrector.apply_proposal(safe_proposal)

        mock_approval_gate.submit_for_approval.assert_not_called()

    @pytest.mark.asyncio
    async def test_apply_proposal_unsafe_calls_approval_gate(
        self,
        auto_corrector,
        mock_approval_gate,
        mock_instruction_version_manager,
        unsafe_proposal,
    ):
        """Given an unsafe proposal, apply_proposal calls ApprovalGate.submit_for_approval."""
        result = await auto_corrector.apply_proposal(unsafe_proposal)

        mock_approval_gate.submit_for_approval.assert_called_once()
        # Verify the call passed proposal_id, description, and context
        call_kwargs = mock_approval_gate.submit_for_approval.call_args[1]
        assert call_kwargs["proposal_id"] == unsafe_proposal.proposal_id
        assert "proposal_type" in call_kwargs["context"]
        assert call_kwargs["context"]["proposal_type"] == "code_change"

        # Verify IVM.approve_update was NOT called (unsafe path)
        mock_instruction_version_manager.approve_update.assert_not_called()

        assert result.status == ApplyStatus.ESCALATED
        assert result.classification == ProposalClassification.UNSAFE
        assert result.applied_at is None

    @pytest.mark.asyncio
    async def test_apply_proposal_handles_ivm_exception(
        self, auto_corrector, mock_instruction_version_manager, safe_proposal
    ):
        """Given IVM.approve_update raises, apply_proposal returns ERROR status (AR18)."""
        mock_instruction_version_manager.approve_update.side_effect = ValueError(
            "Cannot approve proposal with status approved"
        )

        result = await auto_corrector.apply_proposal(safe_proposal)

        assert result.status == ApplyStatus.ERROR
        assert "ValueError" in result.message
        assert (
            result.classification == ProposalClassification.SAFE
        )  # was classified as safe
        assert result.applied_at is None

    @pytest.mark.asyncio
    async def test_apply_proposal_handles_approval_gate_exception(
        self, auto_corrector, mock_approval_gate, unsafe_proposal
    ):
        """Given ApprovalGate.submit_for_approval raises, apply_proposal returns ERROR (AR18)."""
        mock_approval_gate.submit_for_approval.side_effect = RuntimeError(
            "DB connection lost"
        )

        result = await auto_corrector.apply_proposal(unsafe_proposal)

        assert result.status == ApplyStatus.ERROR
        assert "RuntimeError" in result.message
        assert (
            result.classification == ProposalClassification.UNSAFE
        )  # was classified as unsafe


class TestAutoCorrectorIntegration:
    """Tests for AutoCorrector integration with existing schema defaults."""

    @pytest.mark.asyncio
    async def test_default_proposal_type_is_instruction_tweak(
        self, auto_corrector, mock_instruction_version_manager
    ):
        """Given a VersionUpdateProposal constructed without proposal_type, defaults to
        'instruction_tweak' and is auto-applied as SAFE."""
        # Construct WITHOUT proposal_type — exercises OR27 compatibility shim
        proposal = VersionUpdateProposal(
            proposal_id=str(uuid4()),
            worker_id="worker-1",
            current_version=1,
            proposed_content="# Updated",
            trigger_reason="trend -0.7",
            rating_trend=-0.7,
            status="pending",
            created_at=datetime.now(timezone.utc),
            # proposal_type intentionally omitted — default applies
        )

        result = await auto_corrector.apply_proposal(proposal)

        assert result.status == ApplyStatus.APPLIED
        assert result.classification == ProposalClassification.SAFE
        mock_instruction_version_manager.approve_update.assert_called_once_with(
            proposal
        )

    @pytest.mark.asyncio
    async def test_apply_result_model_serialization(self):
        """Given an ApplyResult, verify it serializes to dict with all fields."""
        result = ApplyResult(
            proposal_id="test-id",
            status=ApplyStatus.APPLIED,
            classification=ProposalClassification.SAFE,
            message="test message",
            applied_at=datetime.now(timezone.utc),
        )

        serialized = result.model_dump()
        assert serialized["proposal_id"] == "test-id"
        assert serialized["status"] == "applied"
        assert serialized["classification"] == "safe"
        assert serialized["message"] == "test message"
        assert serialized["applied_at"] is not None
