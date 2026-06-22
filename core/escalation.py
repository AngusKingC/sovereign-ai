"""
Escalation engine for determining when to escalate tasks to cloud models.

Single responsibility: Evaluate worker output and decide whether to escalate
to cloud models based on confidence, errors, or denial flags.
"""

import time
from typing import TYPE_CHECKING
from uuid import uuid4
from datetime import datetime, timezone

from core.schemas import Task, WorkerOutput, EscalationDecision
from core.observability import (
    TraceComponent,
    TraceLevel,
    TraceEventType,
    MemoryTraceEmitter,
)

if TYPE_CHECKING:
    from core.approval_gate import ApprovalGate
    from core.memory_router import MemoryRouter
    from core.observability import TraceEmitter


class EscalationEngine:
    """Engine for evaluating escalation decisions and managing approval workflow."""

    def __init__(
        self,
        approval_gate: "ApprovalGate",
        memory_router: "MemoryRouter",
        emitter: "TraceEmitter | None" = None,
    ):
        self._approval_gate = approval_gate
        self._memory_router = memory_router
        self._emitter = emitter or MemoryTraceEmitter()

    async def evaluate(
        self,
        task: Task,
        worker_output: WorkerOutput,
        available_models: list[str],
    ) -> EscalationDecision:
        """
        Evaluate whether to escalate based on worker output.

        Escalation triggers when any of these conditions are true:
        - worker_output.confidence < 0.5
        - worker_output.metadata.get("denied") is True
        - worker_output.metadata.get("error") is True

        Args:
            task: The task being processed
            worker_output: Output from the local worker
            available_models: List of available model names for escalation

        Returns:
            EscalationDecision with should_escalate set appropriately
        """
        from core.observability import TraceEvent

        reasons = []
        should_escalate = False

        # Check escalation triggers
        if worker_output.confidence < 0.5:
            reasons.append(f"Low confidence: {worker_output.confidence}")
            should_escalate = True

        if worker_output.metadata.get("denied") is True:
            reasons.append("Worker denied request")
            should_escalate = True

        if worker_output.metadata.get("error") is True:
            reasons.append("Worker encountered error")
            should_escalate = True

        if not should_escalate:
            # No escalation needed
            decision = EscalationDecision(
                task_id=task.task_id,
                should_escalate=False,
                reasons=[],
                suggested_model="",
                estimated_cost=0.0,
                tier="local",
            )
        else:
            # Escalation triggered
            suggested_model = available_models[0] if available_models else ""
            decision = EscalationDecision(
                task_id=task.task_id,
                should_escalate=True,
                reasons=reasons,
                suggested_model=suggested_model,
                estimated_cost=0.0,
                tier="cloud",
            )

        # Emit trace event
        start_time = time.perf_counter()
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        event = TraceEvent(
            event_type=TraceEventType.OPERATION_COMPLETE,
            component=TraceComponent.ORCHESTRATOR,
            level=TraceLevel.INFO,
            message=f"Escalation evaluated: {should_escalate}",
            data={
                "task_id": str(task.task_id),
                "should_escalate": should_escalate,
                "reasons": reasons,
            },
            duration_ms=duration_ms,
        )
        await self._emitter.emit(event)

        return decision

    async def request_approval(self, task: Task, decision: EscalationDecision) -> bool:
        """
        Request user approval for escalation via ApprovalGate.

        Args:
            task: The task being escalated
            decision: The escalation decision to approve

        Returns:
            True if approved, False if denied
        """
        from core.observability import TraceEvent
        from core.approval_gate import ApprovalRequest
        from datetime import timedelta

        approval_request = ApprovalRequest(
            request_id=str(uuid4()),
            task_id=str(task.task_id),
            session_id=str(uuid4()),
            action_type="cloud_escalation",
            action_description=f"Escalate task {task.task_id} to {decision.tier} model {decision.suggested_model}",
            action_parameters={"tier": decision.tier, "to_model": decision.suggested_model},
            risk_level="high",
            reason_for_approval="; ".join(decision.reasons),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )

        approval_response = await self._approval_gate.request_approval(approval_request)

        # Record denial on decision if denied
        if not approval_response.approved:
            decision.metadata["approval_denied"] = True

        # Emit trace event
        start_time = time.perf_counter()
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        event = TraceEvent(
            event_type=TraceEventType.OPERATION_COMPLETE if approval_response.approved else TraceEventType.OPERATION_ERROR,
            component=TraceComponent.ORCHESTRATOR,
            level=TraceLevel.INFO if approval_response.approved else TraceLevel.WARNING,
            message=f"Escalation {'approved' if approval_response.approved else 'denied'}",
            data={
                "task_id": str(task.task_id),
                "approved": approval_response.approved,
                "decision_reason": approval_response.decision_reason,
            },
            duration_ms=duration_ms,
        )
        await self._emitter.emit(event)

        return approval_response.approved

    async def execute_escalation(self, task: Task, decision: EscalationDecision) -> WorkerOutput:
        """
        Execute escalation after approval is granted.

        This is a stub - actual cloud dispatch is Phase 7.
        Writes the escalation decision to memory via ScopedMemoryRouter with "global" scope.

        Args:
            task: The task being escalated
            decision: The approved escalation decision

        Returns:
            WorkerOutput signalling escalation approval pending actual dispatch
        """
        from core.observability import TraceEvent
        from core.memory_router import ScopedMemoryRouter

        # Create scoped router for global scope
        scoped_router = ScopedMemoryRouter(self._memory_router, "global", emitter=self._emitter)

        # Write escalation decision to memory
        decision_dict = {
            "task_id": str(decision.task_id),
            "should_escalate": decision.should_escalate,
            "reasons": decision.reasons,
            "suggested_model": decision.suggested_model,
            "tier": decision.tier,
            "to_model": decision.to_model,
        }
        await scoped_router.write(decision_dict)

        # Emit trace event
        start_time = time.perf_counter()
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        event = TraceEvent(
            event_type=TraceEventType.OPERATION_COMPLETE,
            component=TraceComponent.ORCHESTRATOR,
            level=TraceLevel.INFO,
            message="Escalation executed",
            data={
                "task_id": str(task.task_id),
                "to_model": decision.suggested_model,
            },
            duration_ms=duration_ms,
        )
        await self._emitter.emit(event)

        # Return stub WorkerOutput
        return WorkerOutput(
            worker_id="cloud",
            task_id=task.task_id,
            content="Escalation approved — awaiting cloud execution",
            confidence=0.0,
            model_used=decision.suggested_model,
            metadata={"escalated": True, "to_model": decision.suggested_model},
        )
