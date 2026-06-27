"""
Layer 1 Orchestrator.

Single responsibility: Analytical coordination layer that routes tasks to workers
without holding opinions or writing beliefs. Pure analysis and dispatch.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from core.input_sanitiser import InputSanitiser
from core.observability import (
    MemoryTraceEmitter,
    TraceComponent,
    TraceEmitter,
    TraceEvent,
    TraceEventType,
    TraceLevel,
)
from core.schemas import StrategicContext, Task, TaskStatus, WorkerOutput, WorkerStatus

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.a2a_protocol import A2ARequest, A2AResponse, A2ARouter
    from core.adapter_fallback import AdapterFallbackChain
    from core.approval_gate import ApprovalGate
    from core.cost_tracker import CostTracker
    from core.escalation import EscalationEngine
    from core.evaluator import OutputEvaluator
    from core.expert_panel_manager import ExpertPanelManager
    from core.implementation_gate import ImplementationGate
    from core.memory_router import MemoryRouter
    from core.model_tier_router import ModelTierRouter
    from core.multi_channel_approval_gate import MultiChannelApprovalGate
    from core.orchestrator_improvement import OrchestratorImprovementLoop
    from core.pemads_judge import PEMADSJudge
    from core.resource_manager import ResourceManager
    from core.trace_optimiser import TraceOptimiser
    from core.vram_manager import VRAMManager
    from core.worker_base import WorkerBase
    from core.worker_circuit_breaker import WorkerCircuitBreaker
    from core.worker_factory import WorkerFactory
    from memory.debate_pool import DebatePool
    from orchestrator.improvement_loop import ImprovementLoopOrchestrator
    from system.model_acquisition import ModelAcquisition
    from system.model_registry import ModelRegistry


class Orchestrator:
    """Analytical coordination layer that routes tasks to workers."""

    def __init__(
        self,
        memory_router: "MemoryRouter",
        improvement_loop: "OrchestratorImprovementLoop | None" = None,
        improvement_loop_orchestrator: "ImprovementLoopOrchestrator | None" = None,
        cloud_fallback_model: str = "gpt-4o",
        approval_gate: "ApprovalGate | None" = None,
        multi_channel_approval_gate: "MultiChannelApprovalGate | None" = None,
        escalation_engine: "EscalationEngine | None" = None,
        fallback_chain: "AdapterFallbackChain | None" = None,
        a2a_router: "A2ARouter | None" = None,
        input_sanitiser: InputSanitiser | None = None,
        output_evaluator: "OutputEvaluator | None" = None,
        emitter: TraceEmitter | None = None,
        cost_tracker: "CostTracker | None" = None,
        worker_circuit_breaker: "WorkerCircuitBreaker | None" = None,
        degraded_mode_threshold: float = 0.5,
        model_tier_router: "ModelTierRouter | None" = None,
        expert_panel_manager: "ExpertPanelManager | None" = None,
        vram_manager: "VRAMManager | None" = None,
        debate_pool: "DebatePool | None" = None,
        pemads_judge: "PEMADSJudge | None" = None,
        implementation_gate: "ImplementationGate | None" = None,
        model_registry: "ModelRegistry | None" = None,
        resource_manager: "ResourceManager | None" = None,
        model_acquisition: "ModelAcquisition | None" = None,
        worker_factory: "WorkerFactory | None" = None,
    ) -> None:
        """Initialize the orchestrator with dependencies.

        Args:
            memory_router: MemoryRouter for memory operations
            improvement_loop: OrchestratorImprovementLoop for improvement decisions (deprecated, use improvement_loop_orchestrator)
            improvement_loop_orchestrator: ImprovementLoopOrchestrator wire module for improvement tasks
            cloud_fallback_model: Fallback model for cloud operations
            approval_gate: ApprovalGate for approval requests
            escalation_engine: EscalationEngine for escalation logic
            fallback_chain: AdapterFallbackChain for adapter fallback
            a2a_router: A2ARouter for agent-to-agent routing
            input_sanitiser: InputSanitiser for input validation
            output_evaluator: OutputEvaluator for output evaluation
            emitter: TraceEmitter for observability
            cost_tracker: CostTracker for spend cap enforcement
        """
        self.memory_router = memory_router
        self.improvement_loop = (
            improvement_loop  # Deprecated: use improvement_loop_orchestrator
        )
        self.improvement_loop_orchestrator = improvement_loop_orchestrator
        self.cloud_fallback_model = cloud_fallback_model
        self.approval_gate = approval_gate
        self.multi_channel_approval_gate = multi_channel_approval_gate
        self.escalation_engine = escalation_engine
        self.fallback_chain = fallback_chain
        self._a2a_router = a2a_router
        self.output_evaluator = output_evaluator
        self.trace_optimiser: "TraceOptimiser | None" = None
        self.workers: dict[str, "WorkerBase"] = {}
        self.pending_approval_queue: list[Task] = []
        self._emitter = emitter or MemoryTraceEmitter()
        self._input_sanitiser = input_sanitiser or InputSanitiser(emitter=emitter)
        self._cost_tracker = cost_tracker
        self.worker_circuit_breaker = worker_circuit_breaker
        self.degraded_mode_threshold = degraded_mode_threshold
        self.model_tier_router = model_tier_router
        self.expert_panel_manager = expert_panel_manager
        self.vram_manager = vram_manager
        self.debate_pool = debate_pool
        self.pemads_judge = pemads_judge
        self.implementation_gate = implementation_gate
        self.model_registry = model_registry
        self.resource_manager = resource_manager
        self.model_acquisition = model_acquisition
        self.worker_factory = worker_factory
        # Issue #2 fix: type annotation matches runtime tuple storage.
        # Each entry is (task, worker_id, queued_at) for timeout tracking (Issue #5).
        self._queued_tasks: list[tuple[Task, str, datetime]] = []

        # Import TaskStateMachine lazily to avoid circular imports
        from core.task_state_machine import TaskStateMachine

        self.state_machine = TaskStateMachine(memory_router)

        # Import ScratchpadManager lazily to avoid circular imports
        from core.scratchpad import ScratchpadManager

        self.scratchpad_manager = ScratchpadManager(memory_router)

    async def _execute_task(self, task: Task, worker_id: str) -> WorkerOutput:
        """Execute a task via the assigned worker. Called by process_task (normal
        path) and _maybe_resume_queued_tasks (resume path).

        This method contains the worker.run + record_success/record_failure logic.
        It does NOT call _maybe_resume_queued_tasks (no recursion). It does NOT
        check is_degraded() (caller is responsible for that check).

        (Source: Claude Rev3 review Issue #2 — Rev3's _maybe_resume_queued_tasks
        called process_task, which called _maybe_resume_queued_tasks at its start,
        creating unbounded recursion. Rev4 breaks the cycle by extracting this
        helper.)

        Args:
            task: The task to execute
            worker_id: The worker to route to

        Returns:
            WorkerOutput from the worker
        """
        worker = self.workers[worker_id]

        # Transition to EXECUTING.
        # Resume path arrives with task in QUEUED state (Rev5 Issue #1 fix —
        # _maybe_resume_queued_tasks no longer pre-transitions).
        # Direct process_task path may arrive in any pre-EXECUTING state
        # (e.g., RECEIVED, PLANNED). Guard handles both.
        if task.current_state != TaskStatus.EXECUTING:
            task = await self.state_machine.transition(
                task,
                TaskStatus.EXECUTING,
                reason="Worker execution starting",
                actor="orchestrator",
            )

        try:
            output = await worker.run(task)
            if self.worker_circuit_breaker is not None:
                self.worker_circuit_breaker.record_success(worker_id)
            return output
        except Exception:
            if self.worker_circuit_breaker is not None:
                self.worker_circuit_breaker.record_failure(worker_id)
            raise

    def is_degraded(self) -> bool:
        """True if degraded worker ratio exceeds threshold.

        Returns False if worker_circuit_breaker is None (no circuit breaker configured).

        Returns:
            True if system is in degraded mode, False otherwise
        """
        if self.worker_circuit_breaker is None:
            return False
        ratio = self.worker_circuit_breaker.get_degraded_worker_ratio()
        return ratio >= self.degraded_mode_threshold

    async def _maybe_resume_queued_tasks(self) -> None:
        """Opportunistically drain the task queue when system exits degraded mode.

        Called at process_task entry (when a new task arrives). If the system is
        no longer degraded, resume up to N queued tasks (N = number of available
        workers). Each resumed task is executed via _execute_task (not process_task)
        to avoid recursion (Issue #2 fix).

        Rev5 Issue #1 fix: Does NOT pre-transition tasks to EXECUTING. Tasks are
        transitioned from QUEUED to EXECUTING inside _execute_task, which handles
        both direct and resume paths uniformly.
        """
        if not self._queued_tasks or self.is_degraded():
            return

        # Determine how many tasks to resume (limit to available workers)
        available_workers = len(self.workers)
        tasks_to_resume = min(len(self._queued_tasks), available_workers)

        # Resume tasks in FIFO order
        for _ in range(tasks_to_resume):
            if not self._queued_tasks:
                break
            task, worker_id, _ = self._queued_tasks.pop(0)
            try:
                # Use _execute_task, not process_task, to avoid recursion (Issue #2 fix)
                await self._execute_task(task, worker_id)
                logger.info(
                    "Resumed queued task %s for worker %s", task.task_id, worker_id
                )
            except Exception:
                # If resume fails, re-queue the task for next attempt
                self._queued_tasks.append((task, worker_id, datetime.now(timezone.utc)))
                logger.warning(
                    "Failed to resume queued task %s, re-queued", task.task_id
                )

    def register_worker(self, worker_id: str, worker: "WorkerBase") -> None:
        """Register a worker with the orchestrator."""
        self.workers[worker_id] = worker

        # Inject fallback chain into worker if available
        if self.fallback_chain is not None and hasattr(worker, "fallback_chain"):
            worker.fallback_chain = self.fallback_chain

        # NEW: register with circuit breaker so denominator is the full roster
        if self.worker_circuit_breaker is not None:
            self.worker_circuit_breaker.register_worker(worker_id)

        # Emit worker registration event (wrapped to avoid crashing main path)
        try:
            import asyncio

            loop = asyncio.get_event_loop()
            # Safely extract profile data if available
            worker_type = (
                getattr(worker.profile, "worker_type", "unknown")
                if hasattr(worker, "profile")
                else "unknown"
            )
            capabilities = (
                getattr(worker.profile, "capabilities", [])
                if hasattr(worker, "profile")
                else []
            )

            loop.create_task(
                self._emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.ORCHESTRATOR_WORKER_REGISTERED,
                        component=TraceComponent.ORCHESTRATOR,
                        message="Worker registered",
                        level=TraceLevel.INFO,
                        data={
                            "worker_id": worker_id,
                            "worker_type": worker_type,
                            "capabilities": capabilities,
                        },
                        duration_ms=0,
                    )
                )
            )
        except Exception as e:
            # Cleanup path — trace failure should not crash main path
            # Per Rule 17: broad except requires inline comment + WARNING trace
            try:
                import asyncio

                loop = asyncio.get_event_loop()
                loop.create_task(
                    self._emitter.emit(
                        TraceEvent(
                            event_type=TraceEventType.OPERATION_ERROR,
                            component=TraceComponent.ORCHESTRATOR,
                            level=TraceLevel.WARNING,
                            message=f"Worker registration trace failed: {type(e).__name__}: {e}",
                            data={
                                "exception_type": type(e).__name__,
                                "exception_message": str(e),
                            },
                            duration_ms=0,
                        )
                    )
                )
            except Exception as e2:
                logger.warning(
                    "Trace emission failed: %s", e2
                )  # Avoid infinite recursion if trace emit fails

    async def get_top_candidates(self, task: str, n: int) -> list[str]:
        """Returns IDs of the top n registered workers ordered by routing score for this task.

        Args:
            task: The task string to score workers against
            n: Maximum number of worker IDs to return

        Returns:
            List of worker IDs ordered by routing score (highest first)
        """
        from uuid import uuid4

        from core.schemas import Task, TaskPriority, WorkerStatus

        # Create a minimal task object for scoring
        # Use a simple complexity score of 0.5 for all tasks when called with a string
        task_obj = Task(
            task_id=uuid4(),
            intent=task,
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            created_at=datetime.now(timezone.utc),
        )

        # Score each worker using the existing algorithm
        scored_workers = []
        intent_words = set(word.lower() for word in task.lower().split())

        for worker_id, worker in self.workers.items():
            # Skip workers that are not ACTIVE (if they have a status attribute)
            if hasattr(worker.profile, "status"):
                if worker.profile.status != WorkerStatus.ACTIVE:
                    continue

            score = 0

            # +2 points for complexity match (within 0.1 tolerance)
            if (
                abs(task_obj.complexity_score - worker.profile.preferred_complexity)
                < 0.1
            ):
                score += 2

            # +1 point for each matching capability keyword
            capabilities_lower = [cap.lower() for cap in worker.profile.capabilities]
            for word in intent_words:
                for capability in capabilities_lower:
                    if word in capability or capability in word:
                        score += 1
                        break  # Count each word only once per worker

            scored_workers.append((score, worker_id))

        # Sort by score descending, then by registration order
        scored_workers.sort(
            key=lambda x: (-x[0], list(self.workers.keys()).index(x[1]))
        )

        # Return top n worker IDs
        return [worker_id for _, worker_id in scored_workers[:n]]

    async def process_task(self, task: Task, worker_id: str) -> WorkerOutput:
        """
        Process a task by routing it to the specified worker.

        This is a minimal implementation for testing.
        """
        # Opportunistically drain the queue if system has exited degraded mode
        await self._maybe_resume_queued_tasks()

        if worker_id not in self.workers:
            from core.exceptions import WorkerNotFoundError

            raise WorkerNotFoundError(worker_id)

        worker = self.workers[worker_id]

        # Check worker circuit breaker before execution
        if self.worker_circuit_breaker is not None:
            if not self.worker_circuit_breaker.is_available(worker_id):
                # Worker circuit is open. If system is in degraded mode, queue the task.
                if self.is_degraded():
                    # Transition to QUEUED and add to queue
                    task = await self.state_machine.transition(
                        task,
                        TaskStatus.QUEUED,
                        reason=f"Worker {worker_id} circuit open, system degraded",
                        actor="orchestrator",
                    )
                    self._queued_tasks.append(
                        (task, worker_id, datetime.now(timezone.utc))
                    )
                    logger.warning(
                        "Worker %s circuit open, system degraded — task queued",
                        worker_id,
                    )
                    # Return a placeholder output indicating task is queued
                    return WorkerOutput(
                        task_id=task.task_id,
                        worker_id=worker_id,
                        content="",
                        confidence=0.0,
                        model_used="none",
                        metadata={
                            "queued": True,
                            "reason": "Worker circuit open, system degraded",
                        },
                    )

        # Check spend cap before execution if cost_tracker is configured
        if self._cost_tracker is not None:
            try:
                # Rough estimate: cost_per_token * max_tokens (default 4096)
                max_tokens = getattr(worker, "max_tokens", 4096)
                cost_per_token = getattr(worker, "cost_per_token", 0.00001)
                estimated_cost = cost_per_token * max_tokens
                cost_decision = await self._cost_tracker.check_spend(
                    estimated_cost_usd=estimated_cost
                )
                if not cost_decision.approved:
                    # Per AR20: spend cap exceeded — fail task gracefully
                    return WorkerOutput(
                        task_id=task.task_id,
                        worker_id=worker_id,
                        content="",
                        confidence=0.0,
                        model_used="none",
                        metadata={
                            "error": f"Cost cap exceeded: {cost_decision.reason}"
                        },
                    )
                # Plan 79: Model routing (merged cost fallback + pre-execution routing)
                # Rev2 Issues #1 + #2: single route() call, single ModelChoice, stored in task.metadata
                if self.model_tier_router is not None:
                    # Single routing decision — uses cost_decision if available (cost-cap aware)
                    model_choice = self.model_tier_router.route(
                        task,
                        cost_decision=(
                            cost_decision if self._cost_tracker is not None else None
                        ),
                    )
                    # Store routing decision in task.metadata so Plan 81 can read it
                    # without re-routing (Rev2 Issue #1 fix)
                    if not hasattr(task, "metadata") or task.metadata is None:  # type: ignore[attr-defined]
                        task.metadata = {}  # type: ignore[attr-defined]
                    task.metadata["model_choice"] = {  # type: ignore[attr-defined]
                        "model_name": model_choice.model_name,
                        "complexity": model_choice.complexity.value,
                        "reason": model_choice.reason,
                        "downgraded": model_choice.downgraded,
                    }
                    # Log routing decision (single log entry per task — Rev2 Issue #2 fix)
                    if model_choice.downgraded:
                        logger.warning(
                            f"Cost fallback triggered for task {task.task_id}: routing to "
                            f"{model_choice.model_name} (downgraded from higher tier, "
                            f"reason: {model_choice.reason})"
                        )
                    else:
                        logger.info(
                            f"Task {task.task_id} routed to {model_choice.model_name} "
                            f"(tier: {model_choice.complexity.value})"
                        )
                    # Emit trace event ONLY for cost fallback (downgraded=True).
                    # Rev3 Issue #1 fix: non-downgraded routing uses logger.info only —
                    # emitting OPERATION_ERROR for normal routing pollutes error traces
                    # at PEMADS Phase 2 debate scale (multiple turns per debate).
                    # COST_FALLBACK_TRIGGERED is the correct event type for downgraded routing.
                    if model_choice.downgraded:
                        try:
                            await self._emitter.emit(
                                TraceEvent(
                                    event_type=TraceEventType.COST_FALLBACK_TRIGGERED,
                                    component=TraceComponent.ORCHESTRATOR,
                                    level=TraceLevel.WARNING,
                                    message=f"Task routed to {model_choice.model_name} due to cost fallback",
                                    data={
                                        "task_id": task.task_id,
                                        "model": model_choice.model_name,
                                        "complexity": model_choice.complexity.value,
                                        "downgraded": model_choice.downgraded,
                                        "reason": model_choice.reason,
                                    },
                                    duration_ms=0,
                                )
                            )
                        except Exception as e:
                            # AR18: trace emission failure should not crash task processing
                            logger.warning("Trace emission failed: %s", e)
                else:
                    # No router configured — backward compatible (legacy behavior)
                    # Still log cost fallback if it was triggered, just can't route
                    if (
                        self._cost_tracker is not None
                        and cost_decision is not None
                        and cost_decision.fallback_model is not None
                    ):
                        logger.warning(
                            f"Cost fallback triggered but no model_tier_router configured: "
                            f"fallback_model={cost_decision.fallback_model}"
                        )
            except Exception as e:
                # Cost check failure should not crash task processing
                # Per AR18: broad except requires inline comment + WARNING trace
                await self._emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.ORCHESTRATOR,
                        message=f"Cost check failed: {type(e).__name__}: {e}",
                        level=TraceLevel.WARNING,
                        data={"error": str(e)},
                        duration_ms=0,
                    )
                )

        # Check if task should be debated (PEMADS Phase 2)
        if self.expert_panel_manager and await self.expert_panel_manager.should_debate(
            task
        ):
            logger.info(f"Task {task.task_id} flagged for PEMADS debate")
            debate_id = await self.expert_panel_manager.run_debate(task)

            # PEMADS Phase 3: Judge the debate
            if self.pemads_judge:
                from core.task_classifier import TaskClassifier

                classifier = TaskClassifier()
                classification = classifier.classify(task.intent)
                verdict = await self.pemads_judge.judge_debate(
                    debate_id, classification.task_type
                )

                if self.implementation_gate:
                    gate_decision = await self.implementation_gate.check(verdict, task)

                    # Rev2 H6 fix — handle pending state (medium-quality awaiting human approval)
                    if gate_decision.pending:
                        logger.info(
                            f"PEMADS gate pending for task {task.task_id}: {gate_decision.reason}"
                        )
                        # Hold task in AWAITING_APPROVAL state. The task will be resumed
                        # when ApprovalGate.respond() is called (via Web UI, Telegram, or Email).
                        task.metadata = task.metadata or {}
                        task.metadata["pemads_pending"] = {
                            "debate_id": debate_id,
                            "verdict": verdict.__dict__,
                            "gate_decision": gate_decision.__dict__,
                        }
                        # Transition to AWAITING_APPROVAL — orchestrator's pending_approval_queue
                        # handles resumption when respond() is called
                        return WorkerOutput(
                            task_id=task.task_id,
                            worker_id=worker_id,
                            content="",
                            confidence=0.0,
                            model_used="none",
                            metadata={
                                "pending": True,
                                "reason": gate_decision.reason,
                                "debate_id": debate_id,
                            },
                        )

                    elif not gate_decision.approved:
                        logger.info(
                            f"PEMADS gate rejected task {task.task_id}: {gate_decision.reason}"
                        )
                        task.metadata = task.metadata or {}
                        task.metadata["pemads_rejection"] = gate_decision.reason
                        return WorkerOutput(
                            task_id=task.task_id,
                            worker_id=worker_id,
                            content="",
                            confidence=0.0,
                            model_used="none",
                            metadata={
                                "error": gate_decision.reason,
                                "debate_id": debate_id,
                            },
                        )

                    else:
                        logger.info(f"PEMADS gate approved task {task.task_id}")
                        # Rev2 H8 fix — route the winning solution to implementation instead
                        # of re-executing the original task intent. The entire PEMADS chain
                        # (debate + judge + gate) is useless if we discard the winning solution.
                        task.metadata = task.metadata or {}
                        task.metadata["pemads_verdict"] = {
                            "debate_id": verdict.debate_id,
                            "winning_expert": verdict.winning_expert_id,
                            "quality_pct": verdict.winning_quality_pct,
                            "threshold": verdict.threshold,
                        }
                        # If the winning solution is code, execute it directly instead of
                        # re-running the original task through a worker.
                        if verdict.winning_solution_code:
                            task.metadata["pemads_winning_solution"] = (
                                verdict.winning_solution_code
                            )
                            # Route to implementation executor (sandbox) rather than worker dispatch
                            # This ensures the debated solution is what actually gets implemented
                            # TODO: wire to SandboxExecutor in Plan 90+ when sandbox is integrated
                            # For now, log that we have a winning solution
                            logger.info(
                                f"Task {task.task_id} has winning solution from {verdict.winning_expert_id}"
                            )

        # Proceed with normal execution after gate approval
        # (If winning_solution_code is set, a future plan will route it to sandbox)

        # Transition to EXECUTING before worker execution
        try:
            task = await self.state_machine.transition(
                task,
                TaskStatus.EXECUTING,
                reason="Worker execution starting",
                actor="orchestrator",
            )
            # Create scratchpad when task transitions to EXECUTING
            await self.scratchpad_manager.create(task.task_id)
        except Exception as e:
            # If transition fails, we cannot transition to FAILED from current state
            # Just return error output without state transition
            return WorkerOutput(
                task_id=task.task_id,
                worker_id=worker_id,
                content="",
                confidence=0.0,
                model_used="none",
                metadata={"error": str(e)},
            )

        try:
            # Replace: output = await worker.run(task)
            # With:
            output = await self._execute_task(task, worker_id)

            # Evaluate output quality if evaluator is available
            if self.output_evaluator:
                try:
                    evaluation = await self.output_evaluator.evaluate_output(  # noqa: F841 - stored for future use by improvement loop
                        task_id=str(task.task_id),
                        worker_id=worker_id,
                        task_description=task.intent,
                        worker_output=output.content,
                    )
                    # Store evaluation in metrics
                    # The evaluation result feeds into the improvement loop
                except Exception as inner_e:
                    # Don't crash the request if evaluation fails
                    await self._emitter.emit(
                        TraceEvent(
                            event_type=TraceEventType.OPERATION_ERROR,
                            component=TraceComponent.ORCHESTRATOR,
                            message="Output evaluation failed",
                            level=TraceLevel.WARNING,
                            data={"error": str(inner_e)},
                            duration_ms=0,
                        )
                    )

            # Escalation check if escalation_engine is configured
            if self.escalation_engine:
                try:
                    decision = await self.escalation_engine.evaluate(
                        task, output, [self.cloud_fallback_model]
                    )
                    if decision.should_escalate:
                        # Request approval for escalation
                        if self.multi_channel_approval_gate:
                            from core.approval_gate import (
                                ApprovalActionType,
                                ApprovalRequest,
                            )

                            session_id = (
                                str((task.metadata or {}).get("session_id", "default"))
                                if task.metadata
                                else "default"
                            )
                            request = ApprovalRequest(
                                request_id=f"escal-{task.task_id}",
                                task_id=str(task.task_id),
                                session_id=session_id,
                                action_type=ApprovalActionType.CLOUD_ESCALATION,
                                action_description=f"Escalation for task {task.task_id}: {', '.join(decision.reasons)}",
                                action_parameters={},
                                risk_level="medium",
                                reason_for_approval=", ".join(decision.reasons),
                                expires_at=datetime.now(timezone.utc)
                                + timedelta(seconds=300),
                            )
                            response = (
                                await self.multi_channel_approval_gate.request_approval(
                                    request
                                )
                            )
                            approved = response.approved
                        elif self.approval_gate:
                            approved = await self.escalation_engine.request_approval(
                                task, decision
                            )
                        else:
                            # No approval gate - escalate automatically
                            approved = True

                        if approved:
                            # Execute escalation
                            output = await self.escalation_engine.execute_escalation(
                                task, decision
                            )
                        else:
                            # Escalation denied
                            output.metadata["escalation_denied"] = True
                            output.metadata["denied_reason"] = "User denied escalation"
                except Exception:
                    # Escalation error should not crash task processing
                    pass

            # Transition to VALIDATING after worker execution
            task = await self.state_machine.transition(
                task,
                TaskStatus.VALIDATING,
                reason="Worker execution complete, validating output",
                actor="orchestrator",
            )

            # Simple validation - if output has content, transition to COMPLETE
            if output.content:
                task = await self.state_machine.transition(
                    task,
                    TaskStatus.COMPLETE,
                    reason="Validation passed",
                    actor="orchestrator",
                )
                # Record cost after task completion if cost_tracker is configured
                if self._cost_tracker is not None and hasattr(worker, "cost_per_token"):
                    try:
                        await self._cost_tracker.record_usage(
                            model=getattr(worker, "model_name", "unknown"),
                            tokens_in=getattr(output, "tokens_used", 0),
                            tokens_out=getattr(output, "tokens_used", 0),
                            cost_usd=getattr(output, "estimated_cost", 0.0),
                            task_id=str(task.task_id),
                        )
                    except Exception as e:
                        # Cost recording failure should not crash task completion
                        # Per AR18: broad except requires inline comment + WARNING trace
                        await self._emitter.emit(
                            TraceEvent(
                                event_type=TraceEventType.OPERATION_ERROR,
                                component=TraceComponent.ORCHESTRATOR,
                                message=f"Cost recording failed: {type(e).__name__}: {e}",
                                level=TraceLevel.WARNING,
                                data={"error": str(e)},
                                duration_ms=0,
                            )
                        )
                # Compact scratchpad when task transitions to COMPLETE
                try:
                    await self.scratchpad_manager.compact(task.task_id)
                except Exception:
                    # Silently fail if scratchpad compaction fails
                    pass

                # Improvement loop integration -- fire-and-forget via wire module
                if self.improvement_loop_orchestrator is not None:
                    try:
                        # Route through wire module for full error handling
                        improvement_task = asyncio.create_task(
                            self.improvement_loop_orchestrator.process_improvement_task(
                                task_id=str(task.task_id)
                            )
                        )
                        # Suppress "Task exception was never retrieved" warning
                        improvement_task.add_done_callback(
                            lambda t: t.exception() if t.exception() else None
                        )
                    except Exception:
                        # Per AR18: improvement loop failure should not crash task processing
                        pass

                # Mark task as completed in orchestrator metrics
                if self.improvement_loop:
                    try:
                        await self.improvement_loop.mark_task_completed(
                            str(task.task_id)
                        )
                    except Exception as e:
                        # Cleanup path — metrics update failure should not crash task completion
                        # Per Rule 17: broad except requires inline comment + WARNING trace
                        await self._emitter.emit(
                            TraceEvent(
                                event_type=TraceEventType.OPERATION_ERROR,
                                component=TraceComponent.ORCHESTRATOR,
                                level=TraceLevel.WARNING,
                                message=f"Metrics update failed: {type(e).__name__}: {e}",
                                data={
                                    "exception_type": type(e).__name__,
                                    "exception_message": str(e),
                                },
                                duration_ms=0,
                            )
                        )
            else:
                task = await self.state_machine.transition(
                    task,
                    TaskStatus.FAILED,
                    reason="Validation failed: empty output",
                    actor="orchestrator",
                )
                # Preserve scratchpad on FAILED - log task_id for debugging
                try:
                    event = TraceEvent(
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.ORCHESTRATOR,
                        message="Task failed, scratchpad preserved for debugging",
                        level=TraceLevel.INFO,
                        data={"task_id": str(task.task_id)},
                        duration_ms=0,
                    )
                    await self._emitter.emit(event)
                except Exception as e:
                    # Cleanup path — trace emit failure should not crash task processing
                    # Per Rule 17: broad except requires inline comment + WARNING trace
                    await self._emitter.emit(
                        TraceEvent(
                            event_type=TraceEventType.OPERATION_ERROR,
                            component=TraceComponent.ORCHESTRATOR,
                            level=TraceLevel.WARNING,
                            message=f"Trace emit failed: {type(e).__name__}: {e}",
                            data={
                                "exception_type": type(e).__name__,
                                "exception_message": str(e),
                            },
                            duration_ms=0,
                        )
                    )

            return output
        except Exception as e:
            # On any failure, transition to FAILED if possible
            if self.state_machine.can_transition(task, TaskStatus.FAILED):
                task = await self.state_machine.transition(
                    task,
                    TaskStatus.FAILED,
                    reason=f"Worker execution failed: {str(e)}",
                    actor="orchestrator",
                )
                # Preserve scratchpad on FAILED - log task_id for debugging
                try:
                    event = TraceEvent(
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.ORCHESTRATOR,
                        message="Task failed, scratchpad preserved for debugging",
                        level=TraceLevel.INFO,
                        data={"task_id": str(task.task_id)},
                        duration_ms=0,
                    )
                    await self._emitter.emit(event)
                except Exception as e:
                    # Cleanup path — trace emit failure should not crash task processing
                    # Per Rule 17: broad except requires inline comment + WARNING trace
                    await self._emitter.emit(
                        TraceEvent(
                            event_type=TraceEventType.OPERATION_ERROR,
                            component=TraceComponent.ORCHESTRATOR,
                            level=TraceLevel.WARNING,
                            message=f"Trace emit failed: {type(e).__name__}: {e}",
                            data={
                                "exception_type": type(e).__name__,
                                "exception_message": str(e),
                            },
                            duration_ms=0,
                        )
                    )
            raise

    async def route_task(self, task: Task) -> WorkerOutput:
        """
        Route a task to an appropriate worker based on task characteristics.

        Uses scoring algorithm:
        - +2 points if task.complexity_score matches worker.profile.preferred_complexity (within 0.1)
        - +1 point for each word in task.intent that appears in worker.profile.capabilities (case-insensitive)
        - Selects worker with highest score
        - On tie, selects worker registered first
        """
        start_time = time.perf_counter()

        if not self.workers:
            from core.exceptions import WorkerNotFoundError

            raise WorkerNotFoundError("any", "No workers registered")

        # Transition to RECEIVED on task receipt
        try:
            task = await self.state_machine.transition(
                task,
                TaskStatus.RECEIVED,
                reason="Task received by orchestrator",
                actor="orchestrator",
            )
        except Exception as e:
            # If transition fails, return error output
            return WorkerOutput(
                task_id=task.task_id,
                worker_id="none",
                content="",
                confidence=0.0,
                model_used="none",
                metadata={"error": str(e)},
            )

        # Emit trace event for routing start
        try:
            event = TraceEvent(
                event_type=TraceEventType.ORCHESTRATOR_ROUTING_START,
                component=TraceComponent.ORCHESTRATOR,
                message="Orchestrator routing started",
                level=TraceLevel.INFO,
                data={
                    "task_id": str(task.task_id),
                    "task_intent": task.intent,
                    "task_complexity": task.complexity_score,
                    "worker_count": len(self.workers),
                },
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception as e:
            # Cleanup path — trace emit failure should not crash routing
            # Per Rule 17: broad except requires inline comment + WARNING trace
            await self._emitter.emit(
                TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.ORCHESTRATOR,
                    level=TraceLevel.WARNING,
                    message=f"Trace emit failed: {type(e).__name__}: {e}",
                    data={
                        "exception_type": type(e).__name__,
                        "exception_message": str(e),
                    },
                    duration_ms=0,
                )
            )

        # Transition to PLANNED before routing
        try:
            task = await self.state_machine.transition(
                task,
                TaskStatus.PLANNED,
                reason="Planning worker selection",
                actor="orchestrator",
            )
        except Exception as e:
            # If transition fails, return error output
            return WorkerOutput(
                task_id=task.task_id,
                worker_id="none",
                content="",
                confidence=0.0,
                model_used="none",
                metadata={"error": str(e)},
            )

        # If only one worker, use it directly
        if len(self.workers) == 1:
            worker_id = next(iter(self.workers.keys()))
            worker = self.workers[worker_id]

            # Skip workers that are not ACTIVE (if they have a status attribute)
            if hasattr(worker.profile, "status"):
                if worker.profile.status != WorkerStatus.ACTIVE:
                    from core.exceptions import WorkerNotFoundError

                    raise WorkerNotFoundError(worker_id, "No workers registered")

            duration_ms = int((time.perf_counter() - start_time) * 1000)

            # Emit routing metrics if improvement loop is available
            if self.improvement_loop:
                from core.schemas import OrchestratorMetrics

                metrics = OrchestratorMetrics(
                    task_id=str(task.task_id),
                    routed_to_worker_id=worker_id,
                    routing_score=1.0,
                    task_completed=False,  # Will be updated later
                    user_rating=None,
                )
                try:
                    await self.improvement_loop.record_routing_decision(metrics)
                except Exception as e:
                    # Cleanup path — metrics recording failure should not crash routing
                    # Per Rule 17: broad except requires inline comment + WARNING trace
                    await self._emitter.emit(
                        TraceEvent(
                            event_type=TraceEventType.OPERATION_ERROR,
                            component=TraceComponent.ORCHESTRATOR,
                            level=TraceLevel.WARNING,
                            message=f"Metrics recording failed: {type(e).__name__}: {e}",
                            data={
                                "exception_type": type(e).__name__,
                                "exception_message": str(e),
                            },
                            duration_ms=0,
                        )
                    )

            try:
                event = TraceEvent(
                    event_type=TraceEventType.ORCHESTRATOR_ROUTING_COMPLETE,
                    component=TraceComponent.ORCHESTRATOR,
                    message="Worker selected (only one registered)",
                    level=TraceLevel.INFO,
                    data={
                        "selected_worker": worker_id,
                        "scoring_breakdown": [
                            {
                                "worker_id": worker_id,
                                "score": 1,
                                "reason": "only worker",
                            }
                        ],
                    },
                    duration_ms=duration_ms,
                )
                await self._emitter.emit(event)
            except Exception as e:
                # Cleanup path — trace emit failure should not crash routing
                # Per Rule 17: broad except requires inline comment + WARNING trace
                await self._emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.ORCHESTRATOR,
                        level=TraceLevel.WARNING,
                        message=f"Trace emit failed: {type(e).__name__}: {e}",
                        data={
                            "exception_type": type(e).__name__,
                            "exception_message": str(e),
                        },
                        duration_ms=0,
                    )
                )

            # Update StrategicContext after successful routing decision
            try:
                current_context = await self.memory_router.get_global_context(
                    caller_id="orchestrator"
                )
                if current_context is None:
                    from datetime import datetime, timezone

                    current_context = StrategicContext(
                        last_updated=datetime.now(timezone.utc)
                    )

                # Update active goals with recent task
                current_context.active_goals.append(
                    f"Task {task.task_id}: {task.intent} routed to {worker_id}"
                )

                # Update pending tasks with active workers
                current_context.pending_tasks = list(self.workers.keys())

                # Update timestamp
                from datetime import datetime, timezone

                current_context.last_updated = datetime.now(timezone.utc)

                await self.memory_router.set_global_context(
                    current_context, caller_id="orchestrator"
                )
            except Exception as e:
                # Cleanup path — context update failure should not crash routing
                # Per Rule 17: broad except requires inline comment + WARNING trace
                await self._emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.ORCHESTRATOR,
                        level=TraceLevel.WARNING,
                        message=f"Context update failed: {type(e).__name__}: {e}",
                        data={
                            "exception_type": type(e).__name__,
                            "exception_message": str(e),
                        },
                        duration_ms=0,
                    )
                )

            return await self.process_task(task, worker_id)

        # Score each worker
        scored_workers = []
        intent_words = set(word.lower() for word in task.intent.lower().split())
        scoring_breakdown = []

        for worker_id, worker in self.workers.items():
            # Skip workers that are not ACTIVE (if they have a status attribute)
            if hasattr(worker.profile, "status"):
                if worker.profile.status != WorkerStatus.ACTIVE:
                    continue

            score = 0
            reasons = []

            # +2 points for complexity match (within 0.1 tolerance)
            if abs(task.complexity_score - worker.profile.preferred_complexity) < 0.1:
                score += 2
                reasons.append("complexity_match")

            # +1 point for each matching capability keyword
            capabilities_lower = [cap.lower() for cap in worker.profile.capabilities]
            for word in intent_words:
                for capability in capabilities_lower:
                    if word in capability or capability in word:
                        score += 1
                        reasons.append(f"capability_match:{word}")
                        break  # Count each word only once per worker

            scored_workers.append((score, worker_id, worker))
            scoring_breakdown.append(
                {
                    "worker_id": worker_id,
                    "score": score,
                    "reasons": reasons,
                }
            )

        # Sort by score descending, then by registration order (maintained by dict iteration order)
        scored_workers.sort(
            key=lambda x: (-x[0], list(self.workers.keys()).index(x[1]))
        )

        # Select highest-scoring worker
        selected_worker_id = scored_workers[0][1]

        duration_ms = int((time.perf_counter() - start_time) * 1000)

        # Emit routing metrics if improvement loop is available
        if self.improvement_loop:
            from core.schemas import OrchestratorMetrics

            metrics = OrchestratorMetrics(
                task_id=str(task.task_id),
                routed_to_worker_id=selected_worker_id,
                routing_score=scored_workers[0][0],
                task_completed=False,  # Will be updated later
                user_rating=None,
            )
            try:
                await self.improvement_loop.record_routing_decision(metrics)
            except Exception as e:
                # Cleanup path — metrics recording failure should not crash routing
                # Per Rule 17: broad except requires inline comment + WARNING trace
                await self._emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.ORCHESTRATOR,
                        level=TraceLevel.WARNING,
                        message=f"Metrics recording failed: {type(e).__name__}: {e}",
                        data={
                            "exception_type": type(e).__name__,
                            "exception_message": str(e),
                        },
                        duration_ms=0,
                    )
                )

        try:
            event = TraceEvent(
                event_type=TraceEventType.ORCHESTRATOR_ROUTING_COMPLETE,
                component=TraceComponent.ORCHESTRATOR,
                message="Worker selected via routing",
                level=TraceLevel.INFO,
                data={
                    "selected_worker": selected_worker_id,
                    "scoring_breakdown": scoring_breakdown,
                },
                duration_ms=duration_ms,
            )
            await self._emitter.emit(event)
        except Exception as e:
            # Cleanup path — trace emit failure should not crash routing
            # Per Rule 17: broad except requires inline comment + WARNING trace
            await self._emitter.emit(
                TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.ORCHESTRATOR,
                    level=TraceLevel.WARNING,
                    message=f"Trace emit failed: {type(e).__name__}: {e}",
                    data={
                        "exception_type": type(e).__name__,
                        "exception_message": str(e),
                    },
                    duration_ms=0,
                )
            )

        # Update StrategicContext after successful routing decision
        try:
            current_context = await self.memory_router.get_global_context(
                caller_id="orchestrator"
            )
            if current_context is None:
                from datetime import datetime, timezone

                current_context = StrategicContext(
                    last_updated=datetime.now(timezone.utc)
                )

            # Update active goals with recent task
            current_context.active_goals.append(
                f"Task {task.task_id}: {task.intent} routed to {selected_worker_id}"
            )

            # Update pending tasks with active workers
            current_context.pending_tasks = list(self.workers.keys())

            # Update timestamp
            from datetime import datetime, timezone

            current_context.last_updated = datetime.now(timezone.utc)

            await self.memory_router.set_global_context(
                current_context, caller_id="orchestrator"
            )
        except Exception as e:
            # Cleanup path — context update failure should not crash routing
            # Per Rule 17: broad except requires inline comment + WARNING trace
            await self._emitter.emit(
                TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.ORCHESTRATOR,
                    level=TraceLevel.WARNING,
                    message=f"Context update failed: {type(e).__name__}: {e}",
                    data={
                        "exception_type": type(e).__name__,
                        "exception_message": str(e),
                    },
                    duration_ms=0,
                )
            )

        return await self.process_task(task, selected_worker_id)

    async def cancel_task(self, task: Task, reason: str = "Cancelled by user") -> Task:
        """
        Cancel a task by transitioning it to CANCELLED state.

        Args:
            task: The task to cancel
            reason: Reason for cancellation

        Returns:
            The updated task in CANCELLED state
        """
        task = await self.state_machine.transition(
            task, TaskStatus.CANCELLED, reason=reason, actor="user"
        )

        # Delete scratchpad when task is cancelled
        try:
            await self.scratchpad_manager.delete(task.task_id)
        except Exception:
            # Silently fail if scratchpad deletion fails
            pass

        return task

    async def process_pending_approval(
        self, task_id: str, approved: bool
    ) -> WorkerOutput | Task | None:
        """
        Process a task that was awaiting approval.

        Args:
            task_id: The task identifier
            approved: Whether approval was granted

        Returns:
            The updated task if found, None otherwise
        """
        # Find task in pending queue
        task = None
        for i, pending_task in enumerate(self.pending_approval_queue):
            if str(pending_task.task_id) == task_id:
                task = self.pending_approval_queue.pop(i)
                break

        if not task:
            return None

        if approved:
            # Transition back to EXECUTING
            task = await self.state_machine.transition(
                task, TaskStatus.EXECUTING, reason="Approval granted", actor="user"
            )
            # Re-route the task
            return await self.route_task(task)
        else:
            # Transition to CANCELLED
            task = await self.state_machine.transition(
                task, TaskStatus.CANCELLED, reason="Approval denied", actor="user"
            )
            return task

    def deregister_worker(self, worker_id: str) -> None:
        """
        Remove a worker from the orchestrator registry.

        Args:
            worker_id: The worker ID to deregister

        Raises:
            WorkerNotFoundError: If worker_id is not found in registry
        """
        from core.exceptions import WorkerNotFoundError

        if worker_id not in self.workers:
            raise WorkerNotFoundError(worker_id)

        worker = self.workers[worker_id]
        del self.workers[worker_id]

        # Emit worker deregistration event (wrapped to avoid crashing main path)
        try:
            import asyncio

            loop = asyncio.get_event_loop()
            # Safely extract profile data if available
            worker_type = (
                getattr(worker.profile, "worker_type", "unknown")
                if hasattr(worker, "profile")
                else "unknown"
            )
            capabilities = (
                getattr(worker.profile, "capabilities", [])
                if hasattr(worker, "profile")
                else []
            )

            loop.create_task(
                self._emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.ORCHESTRATOR_WORKER_DEREGISTERED,
                        component=TraceComponent.ORCHESTRATOR,
                        message="Worker deregistered",
                        level=TraceLevel.INFO,
                        data={
                            "worker_id": worker_id,
                            "worker_type": worker_type,
                            "capabilities": capabilities,
                        },
                        duration_ms=0,
                    )
                )
            )
        except Exception as e:
            # Cleanup path — trace failure should not crash main path
            # Per Rule 17: broad except requires inline comment + WARNING trace
            try:
                import asyncio

                loop = asyncio.get_event_loop()
                loop.create_task(
                    self._emitter.emit(
                        TraceEvent(
                            event_type=TraceEventType.OPERATION_ERROR,
                            component=TraceComponent.ORCHESTRATOR,
                            level=TraceLevel.WARNING,
                            message=f"Worker deregistration trace failed: {type(e).__name__}: {e}",
                            data={
                                "exception_type": type(e).__name__,
                                "exception_message": str(e),
                            },
                            duration_ms=0,
                        )
                    )
                )
            except Exception as e2:
                logger.warning(
                    "Trace emission failed: %s", e2
                )  # Avoid infinite recursion if trace emit fails

    async def submit_subtask(self, request: "A2ARequest") -> "A2AResponse":
        """
        Submit an A2A sub-task request for routing.

        Args:
            request: The A2A request to submit

        Returns:
            A2AResponse with the result

        Raises:
            RuntimeError: If A2A router is not configured
        """
        if self._a2a_router is None:
            raise RuntimeError("A2A router not configured")

        return await self._a2a_router.submit(request)

    async def submit_task(self, intent: str, priority: str = "normal") -> Task:
        """
        Submit a task to the orchestrator for routing.

        Args:
            intent: The task intent/description
            priority: Task priority ("normal", "high", or "critical")

        Returns:
            The created Task object

        Raises:
            ValueError: If priority is not a valid TaskPriority value
        """
        from uuid import uuid4

        from core.schemas import TaskPriority

        # Validate and convert priority string to enum
        try:
            priority_enum = TaskPriority(priority.lower())
        except ValueError:
            raise ValueError(
                f"Invalid priority: {priority}. Must be one of: normal, high, critical"
            )

        # Sanitise external input before it enters LLM context (Rule 14)
        # Defense-in-depth: callers may also sanitise at boundary, but the sink
        # must sanitise too in case a future caller forgets.
        if self._input_sanitiser:
            intent = await self._input_sanitiser.sanitise(intent, source="submit_task")

        # Construct Task
        task = Task(
            task_id=uuid4(),
            intent=intent,
            complexity_score=0.5,  # Default complexity
            priority=priority_enum,
            created_at=datetime.now(timezone.utc),
        )

        # Route the task
        await self.route_task(task)

        return task

    async def list_tasks(self) -> list[Task]:
        """
        Return list of tasks in the orchestrator.

        Returns:
            List of Task objects (empty if no task tracking exists)
        """
        # Check if orchestrator has _active_tasks attribute
        if hasattr(self, "_active_tasks"):
            return self._active_tasks
        return []

    async def list_workers(self) -> list[dict]:
        """
        Return list of registered workers with their profile metadata.

        Returns:
            List of dicts, one per registered worker, with keys:
            worker_id, worker_type, capabilities, preferred_model,
            preferred_complexity, tasks_completed, avg_confidence.
            Workers without a profile return a minimal dict with just worker_id.
        """
        result: list[dict[str, Any]] = []
        for worker_id, worker in self.workers.items():
            profile = getattr(worker, "profile", None)
            if profile is None:
                result.append({"worker_id": worker_id})
                continue
            result.append(
                {
                    "worker_id": worker_id,
                    "worker_type": getattr(profile, "worker_type", "unknown"),
                    "capabilities": getattr(profile, "capabilities", []),
                    "preferred_model": getattr(profile, "preferred_model", None),
                    "preferred_complexity": getattr(
                        profile, "preferred_complexity", 0.5
                    ),
                    "tasks_completed": getattr(profile, "tasks_completed", 0),
                    "avg_confidence": getattr(profile, "avg_confidence", 0.0),
                }
            )
        return result

    async def get_task(self, task_id: str) -> Task | None:
        """Return single task by ID."""
        # Check if orchestrator has _active_tasks attribute
        if hasattr(self, "_active_tasks"):
            for task in self._active_tasks:
                if task.task_id == task_id:
                    return task
        return None

    async def list_workers_with_status(self) -> list[dict]:
        """Return workers enriched with circuit breaker status."""
        # Get basic worker list
        workers = await self.list_workers()
        # TODO: enrich with circuit breaker status when worker_circuit_breaker is integrated
        # For now, return basic list
        return workers

    async def get_session_timeline(self, session_id: str) -> list[dict]:
        """Return phase timeline for a session."""
        # TODO: implement when session tracking is complete
        return []
