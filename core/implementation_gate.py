"""
PEMADS Phase 3: Implementation Gate

Gates implementation of a debated solution based on:
1. Quality threshold (from JudgeVerdict.passed)
2. Risk assessment (unsafe implementations require approval)
3. Approval gate integration (for high-risk implementations)

If gate passes → solution is implemented.
If gate fails → solution is rejected, task may be retried or escalated.
If gate requires approval → ApprovalGate.request_approval is called.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from core.approval_gate import ApprovalActionType, ApprovalGate, ApprovalRequest
from core.pemads_judge import JudgeVerdict

logger = logging.getLogger(__name__)


@dataclass
class GateDecision:
    """Result of implementation gate check."""

    debate_id: str
    approved: bool
    requires_human_approval: bool
    reason: str
    approved_by: str  # "auto", "pending", or human responder
    decided_at: datetime
    pending: bool = (
        False  # Rev2 H6 fix — True when request is submitted but not yet responded to
    )


class ImplementationGate:
    """Gates PEMADS solution implementation."""

    # Risk thresholds for auto-approval vs human approval
    AUTO_APPROVE_THRESHOLD = 90.0  # >= 90% quality → auto-approve
    HUMAN_APPROVAL_THRESHOLD = 75.0  # 75-90% → human approval required
    # Below 75% → auto-reject

    # Rev2 L3 fix — thresholds are configurable via constructor
    def __init__(
        self,
        approval_gate: ApprovalGate,
        emitter: Optional[Any] = None,
        auto_approve_threshold: float = 90.0,
        human_approval_threshold: float = 75.0,
        approval_ttl_seconds: int = 300,
    ) -> None:
        self._approval_gate = approval_gate
        self._emitter = emitter
        self._auto_approve_threshold = auto_approve_threshold
        self._human_approval_threshold = human_approval_threshold
        self._approval_ttl_seconds = approval_ttl_seconds

    async def check(self, verdict: JudgeVerdict, task: Any) -> GateDecision:
        """Check if a solution should be implemented.

        Decision tree:
        1. If verdict.passed is False → reject (quality below threshold)
        2. If quality >= AUTO_APPROVE_THRESHOLD → auto-approve
        3. If quality >= HUMAN_APPROVAL_THRESHOLD → submit for approval, return pending
        4. Below HUMAN_APPROVAL_THRESHOLD → reject (even if passed threshold)

        Rev2 H6 fix — medium-quality tier returns pending=True instead of treating
        the initial request_approval response as final. The orchestrator holds the
        task in AWAITING_APPROVAL state and resumes when respond() is called.
        """
        from datetime import timedelta

        now = datetime.now(timezone.utc)

        # Case 1: Quality below task threshold
        if not verdict.passed:
            return GateDecision(
                debate_id=verdict.debate_id,
                approved=False,
                requires_human_approval=False,
                pending=False,
                reason=f"Quality {verdict.winning_quality_pct:.1f}% below threshold {verdict.threshold:.1f}%",
                approved_by="auto",
                decided_at=now,
            )

        # Case 2: High quality → auto-approve
        if verdict.winning_quality_pct >= self._auto_approve_threshold:
            return GateDecision(
                debate_id=verdict.debate_id,
                approved=True,
                requires_human_approval=False,
                pending=False,
                reason=f"Quality {verdict.winning_quality_pct:.1f}% >= auto-approve threshold {self._auto_approve_threshold}%",
                approved_by="auto",
                decided_at=now,
            )

        # Case 3: Medium quality → human approval required
        if verdict.winning_quality_pct >= self._human_approval_threshold:
            # Rev2 H5 fix — use timedelta, not now.replace(second=now.second + 300)
            # datetime.replace(second=...) only accepts 0-59; adding 300 raises ValueError.
            expires_at = now + timedelta(seconds=self._approval_ttl_seconds)

            approval_request = ApprovalRequest(
                request_id=f"pemads-gate-{verdict.debate_id}",
                task_id=getattr(task, "task_id", ""),
                session_id=getattr(task, "session_id", ""),
                action_type=ApprovalActionType.SYSTEM_CONFIG,
                action_description=f"PEMADS implementation gate for debate {verdict.debate_id}",
                action_parameters={
                    "debate_id": verdict.debate_id,
                    "winning_expert": verdict.winning_expert_id,
                    "quality_pct": verdict.winning_quality_pct,
                },
                risk_level="medium",
                reason_for_approval=verdict.feedback,
                created_at=now,
                expires_at=expires_at,
            )

            # Submit for approval — returns immediately with pending status
            await self._approval_gate.request_approval(approval_request)

            # Rev2 H6 fix — don't treat initial pending response as denial.
            # request_approval returns approved=False while pending. The orchestrator
            # should hold the task in AWAITING_APPROVAL and resume when respond() is called.
            return GateDecision(
                debate_id=verdict.debate_id,
                approved=False,  # Not yet approved — will be updated when respond() is called
                requires_human_approval=True,
                pending=True,  # Rev2 H6 fix — mark as pending, not denied
                reason=f"Human approval submitted (expires {expires_at.isoformat()}). Awaiting response.",
                approved_by="pending",
                decided_at=now,
            )

        # Case 4: Below human approval threshold → reject
        return GateDecision(
            debate_id=verdict.debate_id,
            approved=False,
            requires_human_approval=False,
            pending=False,
            reason=f"Quality {verdict.winning_quality_pct:.1f}% below human approval threshold {self._human_approval_threshold}%",
            approved_by="auto",
            decided_at=now,
        )
