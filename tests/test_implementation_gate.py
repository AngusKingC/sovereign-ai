"""
Tests for ImplementationGate (Plan 88).
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.approval_gate import ApprovalActionType, ApprovalGate
from core.implementation_gate import ImplementationGate
from core.pemads_judge import JudgeVerdict


@pytest.fixture
def mock_approval_gate():
    """Mock ApprovalGate."""
    gate = AsyncMock(spec=ApprovalGate)
    return gate


@pytest.fixture
def implementation_gate(mock_approval_gate):
    """ImplementationGate fixture."""
    return ImplementationGate(
        approval_gate=mock_approval_gate,
        emitter=None,
        auto_approve_threshold=90.0,
        human_approval_threshold=75.0,
        approval_ttl_seconds=300,
    )


@pytest.fixture
def mock_task():
    """Mock task."""
    task = MagicMock()
    task.task_id = "task-123"
    task.session_id = "session-456"
    return task


@pytest.mark.asyncio
async def test_gate_auto_approve_high_quality(implementation_gate, mock_task):
    """Test that high quality (>= 90%) results in auto-approval."""
    verdict = JudgeVerdict(
        debate_id="debate-123",
        winning_expert_id="expert_a",
        winning_quality_pct=95.0,
        threshold=85.0,
        passed=True,
        all_scores={"expert_a": 95.0},
        feedback="Excellent solution",
        judged_at=datetime.now(timezone.utc),
        winning_solution_code="def foo(): return 1",
    )

    decision = await implementation_gate.check(verdict, mock_task)

    assert decision.approved is True
    assert decision.requires_human_approval is False
    assert decision.pending is False
    assert decision.approved_by == "auto"
    assert ">= auto-approve threshold" in decision.reason


@pytest.mark.asyncio
async def test_gate_human_approval_medium_quality(
    implementation_gate, mock_approval_gate, mock_task
):
    """Test that medium quality (75-90%) requires human approval."""
    verdict = JudgeVerdict(
        debate_id="debate-123",
        winning_expert_id="expert_a",
        winning_quality_pct=80.0,
        threshold=85.0,
        passed=True,
        all_scores={"expert_a": 80.0},
        feedback="Good solution",
        judged_at=datetime.now(timezone.utc),
        winning_solution_code="def foo(): return 1",
    )

    # Mock approval request response
    mock_approval_gate.request_approval.return_value = MagicMock(approved=False)

    decision = await implementation_gate.check(verdict, mock_task)

    assert decision.approved is False
    assert decision.requires_human_approval is True
    assert decision.pending is True  # Rev2 H6 fix
    assert decision.approved_by == "pending"
    assert "Human approval submitted" in decision.reason

    # Verify approval request was created
    mock_approval_gate.request_approval.assert_called_once()
    call_args = mock_approval_gate.request_approval.call_args
    approval_request = call_args[0][0]
    assert approval_request.risk_level == "medium"
    assert approval_request.action_type == ApprovalActionType.SYSTEM_CONFIG


@pytest.mark.asyncio
async def test_gate_reject_below_threshold(implementation_gate, mock_task):
    """Test that quality below task threshold is rejected."""
    verdict = JudgeVerdict(
        debate_id="debate-123",
        winning_expert_id="expert_a",
        winning_quality_pct=70.0,
        threshold=85.0,
        passed=False,  # Below threshold
        all_scores={"expert_a": 70.0},
        feedback="Poor solution",
        judged_at=datetime.now(timezone.utc),
        winning_solution_code="def foo(): return 1",
    )

    decision = await implementation_gate.check(verdict, mock_task)

    assert decision.approved is False
    assert decision.requires_human_approval is False
    assert decision.pending is False
    assert decision.approved_by == "auto"
    assert "below threshold" in decision.reason


@pytest.mark.asyncio
async def test_gate_reject_below_human_threshold(implementation_gate, mock_task):
    """Test that quality below human approval threshold (75%) is rejected even if passed task threshold."""
    verdict = JudgeVerdict(
        debate_id="debate-123",
        winning_expert_id="expert_a",
        winning_quality_pct=70.0,
        threshold=65.0,  # Below human threshold but above task threshold
        passed=True,
        all_scores={"expert_a": 70.0},
        feedback="Mediocre solution",
        judged_at=datetime.now(timezone.utc),
        winning_solution_code="def foo(): return 1",
    )

    decision = await implementation_gate.check(verdict, mock_task)

    assert decision.approved is False
    assert decision.requires_human_approval is False
    assert decision.pending is False
    assert decision.approved_by == "auto"
    assert "below human approval threshold" in decision.reason


@pytest.mark.asyncio
async def test_gate_approval_request_created(
    implementation_gate, mock_approval_gate, mock_task
):
    """Test that approval request is created with correct parameters."""
    verdict = JudgeVerdict(
        debate_id="debate-123",
        winning_expert_id="expert_a",
        winning_quality_pct=80.0,
        threshold=85.0,
        passed=True,
        all_scores={"expert_a": 80.0},
        feedback="Good solution",
        judged_at=datetime.now(timezone.utc),
        winning_solution_code="def foo(): return 1",
    )

    mock_approval_gate.request_approval.return_value = MagicMock(approved=False)

    await implementation_gate.check(verdict, mock_task)

    # Verify approval request structure
    call_args = mock_approval_gate.request_approval.call_args
    approval_request = call_args[0][0]

    assert approval_request.request_id == "pemads-gate-debate-123"
    assert approval_request.task_id == "task-123"
    assert approval_request.session_id == "session-456"
    assert (
        approval_request.action_description
        == "PEMADS implementation gate for debate debate-123"
    )
    assert approval_request.action_parameters == {
        "debate_id": "debate-123",
        "winning_expert": "expert_a",
        "quality_pct": 80.0,
    }
    assert approval_request.risk_level == "medium"
    assert approval_request.reason_for_approval == "Good solution"

    # Verify expires_at is approximately 300 seconds in the future
    now = datetime.now(timezone.utc)
    expires_at = approval_request.expires_at
    time_diff = (expires_at - now).total_seconds()
    assert 295 <= time_diff <= 305  # Allow 5 second tolerance
