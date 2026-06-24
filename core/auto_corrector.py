"""
AutoCorrector — self-healing proposal application.

Single responsibility: Classify VersionUpdateProposals as safe or unsafe,
apply safe proposals directly via InstructionVersionManager.approve_update(),
escalate unsafe proposals to the existing ApprovalGate path.

Safe proposal types (auto-applied):
- 'instruction_tweak': updates to worker/orchestrator instruction markdown files.
  Reversible via InstructionVersionManager.rollback(). Non-destructive.

Unsafe proposal types (escalated to ApprovalGate):
- 'code_change': modifications to Python source files. Requires human review.
- 'model_download': network + disk operations. Requires human approval.
- Unknown types: default to unsafe (defense in depth — never auto-apply what
  we don't recognize).

The AutoCorrector is an optional dependency of InstructionVersionManager.
When auto_corrector=None (the default), IVM behavior is unchanged — every
proposal goes to the ApprovalGate. When auto_corrector is provided, IVM
delegates the apply/escalate decision to AutoCorrector.

Observability note: AutoCorrector emits trace events via _emit_trace(). For
the audit trail to persist in production, the TraceEmitter must be durable
(e.g., PostgresTraceEmitter, file-based emitter). MemoryTraceEmitter (used
in tests) is in-memory only and evaporates on restart. The future CLI-wiring
plan MUST specify a durable emitter — see S0.3 deferred risks.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING
from uuid import uuid4

from pydantic import BaseModel, Field

from core.observability import (
    MemoryTraceEmitter,
    TraceComponent,
    TraceEmitter,
    TraceEvent,
    TraceEventType,
    TraceLevel,
)
from core.schemas import VersionUpdateProposal

if TYPE_CHECKING:
    from core.approval_gate import ApprovalGate
    from core.instruction_versioning import InstructionVersionManager


class ProposalClassification(str, Enum):
    """AutoCorrector's classification of a proposal's safety."""

    SAFE = "safe"
    UNSAFE = "unsafe"


class ApplyStatus(str, Enum):
    """Outcome of AutoCorrector.apply_proposal()."""

    APPLIED = "applied"  # Safe proposal — auto-applied via IVM
    ESCALATED = "escalated"  # Unsafe proposal — sent to ApprovalGate
    ERROR = "error"  # Application failed — see message


class ApplyResult(BaseModel):
    """Result of AutoCorrector.apply_proposal()."""

    proposal_id: str = Field(description="Proposal ID that was processed")
    status: ApplyStatus = Field(description="Outcome of the apply attempt")
    classification: ProposalClassification = Field(
        description="Whether the proposal was classified as SAFE or UNSAFE"
    )
    message: str = Field(
        default="",
        description="Human-readable detail (error message on ERROR, summary otherwise)",
    )
    applied_at: datetime | None = Field(
        default=None,
        description="When the proposal was applied (set on APPLIED only)",
    )


class AutoCorrector:
    """Classifies and applies VersionUpdateProposals.

    Safe proposals are auto-applied via InstructionVersionManager.approve_update().
    Unsafe proposals are escalated to ApprovalGate via submit_for_approval().

    The safe/unsafe boundary is determined by proposal_type:
    - SAFE_TYPES: {'instruction_tweak', 'routing_weight'} — reversible, non-destructive
    - UNSAFE_TYPES: {'code_change', 'model_download'} — irreversible or destructive
    - Unknown types default to UNSAFE (defense in depth).
    """

    SAFE_TYPES: frozenset[str] = frozenset({"instruction_tweak", "routing_weight"})
    UNSAFE_TYPES: frozenset[str] = frozenset({"code_change", "model_download"})

    def __init__(
        self,
        instruction_version_manager: "InstructionVersionManager",
        approval_gate: "ApprovalGate",
        emitter: TraceEmitter | None = None,
    ) -> None:
        """Initialize AutoCorrector.

        Args:
            instruction_version_manager: IVM instance for applying safe proposals.
            approval_gate: ApprovalGate instance for escalating unsafe proposals.
            emitter: TraceEmitter for observability (defaults to MemoryTraceEmitter).
        """
        self.instruction_version_manager = instruction_version_manager
        self.approval_gate = approval_gate
        self.emitter = emitter if emitter is not None else MemoryTraceEmitter()

    async def classify(self, proposal: VersionUpdateProposal) -> ProposalClassification:
        """Classify a proposal as SAFE or UNSAFE based on its proposal_type.

        Args:
            proposal: The VersionUpdateProposal to classify.

        Returns:
            ProposalClassification.SAFE if proposal_type is in SAFE_TYPES,
            ProposalClassification.UNSAFE otherwise (including unknown types —
            defense in depth).
        """
        if proposal.proposal_type in self.SAFE_TYPES:
            return ProposalClassification.SAFE
        # Unknown types default to UNSAFE — never auto-apply what we don't recognize.
        return ProposalClassification.UNSAFE

    async def apply_proposal(self, proposal: VersionUpdateProposal) -> ApplyResult:
        """Classify and apply/escalate a proposal.

        Safe proposals: call InstructionVersionManager.approve_update(proposal).
        Unsafe proposals: call ApprovalGate.submit_for_approval(...) with the
        proposal's details. The approval_gate then handles the human-in-the-loop
        flow (existing behavior).

        Args:
            proposal: The VersionUpdateProposal to process.

        Returns:
            ApplyResult with status (APPLIED / ESCALATED / ERROR) and details.
            Callers (specifically InstructionVersionManager.check_and_trigger_update)
            MUST inspect the status: on ERROR, the caller is responsible for
            cleaning up any pending-proposal tracking state, because neither
            approve_update (safe path) nor submit_for_approval (unsafe path)
            ran to completion.
        """
        classification = await self.classify(proposal)

        if classification == ProposalClassification.SAFE:
            try:
                await self.instruction_version_manager.approve_update(proposal)
                applied_at = datetime.now(timezone.utc)

                await self._emit_trace(
                    level=TraceLevel.INFO,
                    message=f"AutoCorrector applied safe proposal {proposal.proposal_id} "
                    f"(type={proposal.proposal_type}, worker={proposal.worker_id})",
                    data={
                        "proposal_id": proposal.proposal_id,
                        "proposal_type": proposal.proposal_type,
                        "worker_id": proposal.worker_id,
                        "classification": classification.value,
                        "applied_at": applied_at.isoformat(),
                    },
                )

                return ApplyResult(
                    proposal_id=proposal.proposal_id,
                    status=ApplyStatus.APPLIED,
                    classification=classification,
                    message=f"Auto-applied {proposal.proposal_type} proposal for "
                    f"worker {proposal.worker_id}",
                    applied_at=applied_at,
                )
            except Exception as exc:
                # Per AR18: log warning with exc info, don't crash.
                # Common cause: IVM.approve_update raises ValueError if proposal
                # status is not "pending" (e.g., race condition with manual review).
                # Caller (IVM.check_and_trigger_update) MUST clear _pending_proposals
                # on this ERROR return — see S5 Edit 4.
                await self._emit_trace(
                    level=TraceLevel.WARNING,
                    message=f"AutoCorrector failed to apply proposal {proposal.proposal_id}: {exc}",
                    data={
                        "proposal_id": proposal.proposal_id,
                        "proposal_type": proposal.proposal_type,
                        "worker_id": proposal.worker_id,
                        "error": str(exc),
                    },
                )
                return ApplyResult(
                    proposal_id=proposal.proposal_id,
                    status=ApplyStatus.ERROR,
                    classification=classification,
                    message=f"IVM.approve_update raised {type(exc).__name__}: {exc}",
                )

        # Unsafe path: escalate to ApprovalGate.
        try:
            await self.approval_gate.submit_for_approval(
                proposal_id=proposal.proposal_id,
                description=(
                    f"AutoCorrector escalation: {proposal.proposal_type} proposal "
                    f"for worker {proposal.worker_id} ({proposal.trigger_reason})"
                ),
                context={
                    "proposal_id": proposal.proposal_id,
                    "worker_id": proposal.worker_id,
                    "proposal_type": proposal.proposal_type,
                    "current_version": proposal.current_version,
                    "trigger_reason": proposal.trigger_reason,
                    "rating_trend": proposal.rating_trend,
                },
            )

            await self._emit_trace(
                level=TraceLevel.INFO,
                message=f"AutoCorrector escalated unsafe proposal {proposal.proposal_id} "
                f"(type={proposal.proposal_type}, worker={proposal.worker_id})",
                data={
                    "proposal_id": proposal.proposal_id,
                    "proposal_type": proposal.proposal_type,
                    "worker_id": proposal.worker_id,
                    "classification": classification.value,
                },
            )

            return ApplyResult(
                proposal_id=proposal.proposal_id,
                status=ApplyStatus.ESCALATED,
                classification=classification,
                message=f"Escalated {proposal.proposal_type} proposal to ApprovalGate",
            )
        except Exception as exc:
            # Per AR18: log warning, don't crash.
            # Caller (IVM.check_and_trigger_update) MUST clear _pending_proposals
            # on this ERROR return — see S5 Edit 4.
            await self._emit_trace(
                level=TraceLevel.WARNING,
                message=(
                    f"AutoCorrector failed to escalate proposal {proposal.proposal_id}: {exc}"
                ),
                data={
                    "proposal_id": proposal.proposal_id,
                    "proposal_type": proposal.proposal_type,
                    "worker_id": proposal.worker_id,
                    "error": str(exc),
                },
            )
            return ApplyResult(
                proposal_id=proposal.proposal_id,
                status=ApplyStatus.ERROR,
                classification=classification,
                message=f"ApprovalGate.submit_for_approval raised {type(exc).__name__}: {exc}",
            )

    async def _emit_trace(
        self,
        level: TraceLevel,
        message: str,
        data: dict,
    ) -> None:
        """Emit a trace event for AutoCorrector operations.

        Args:
            level: Trace level (INFO for success, WARNING for failures).
            message: Human-readable trace message.
            data: Additional trace data.
        """
        try:
            await self.emitter.emit(
                TraceEvent(
                    event_id=uuid4(),
                    timestamp=datetime.now(timezone.utc),
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.ORCHESTRATOR,
                    level=level,
                    message=message,
                    data=data,
                    duration_ms=0,
                )
            )
        except Exception:
            # Per AR18: trace emission failure must not crash AutoCorrector.
            pass
