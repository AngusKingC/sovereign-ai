"""
Layer 1 Orchestrator.

Single responsibility: Analytical coordination layer that routes tasks to workers
without holding opinions or writing beliefs. Pure analysis and dispatch.
"""

import time
from typing import TYPE_CHECKING

from core.schemas import Task, WorkerOutput, TaskStatus, WorkerStatus, OrchestratorMetrics, StrategicContext, EscalationDecision, EscalationTier
from core.approval_gate import ApprovalActionType
from core.observability import (
    TraceComponent,
    TraceEventType,
    TraceLevel,
    TraceEvent,
    TraceEmitter,
    MemoryTraceEmitter,
)

if TYPE_CHECKING:
    from core.memory_router import MemoryRouter
    from core.worker_base import WorkerBase
    from core.task_state_machine import TaskStateMachine
    from core.scratchpad import ScratchpadManager
    from core.orchestrator_improvement import OrchestratorImprovementLoop
    from core.approval_gate import ApprovalGate, ApprovalRequest
    from core.escalation import EscalationEngine
    from core.adapter_fallback import AdapterFallbackChain


class Orchestrator:
    """Analytical coordination layer that routes tasks to workers."""

    def __init__(
        self,
        memory_router: "MemoryRouter",
        improvement_loop: "OrchestratorImprovementLoop | None" = None,
        cloud_fallback_model: str = "gpt-4o",
        approval_gate: "ApprovalGate | None" = None,
        escalation_engine: "EscalationEngine | None" = None,
        fallback_chain: "AdapterFallbackChain | None" = None,
        a2a_router: "A2ARouter | None" = None,
        emitter: TraceEmitter | None = None,
    ) -> None:
        """Initialize the orchestrator with dependencies."""
        self.memory_router = memory_router
        self.improvement_loop = improvement_loop
        self.cloud_fallback_model = cloud_fallback_model
        self.approval_gate = approval_gate
        self.escalation_engine = escalation_engine
        self.fallback_chain = fallback_chain
        self._a2a_router = a2a_router
        self.workers: dict[str, "WorkerBase"] = {}
        self.pending_approval_queue: list[Task] = []
        self._emitter = emitter or MemoryTraceEmitter()
        
        # Import TaskStateMachine lazily to avoid circular imports
        from core.task_state_machine import TaskStateMachine
        self.state_machine = TaskStateMachine(memory_router)
        
        # Import ScratchpadManager lazily to avoid circular imports
        from core.scratchpad import ScratchpadManager
        self.scratchpad_manager = ScratchpadManager(memory_router)

    def register_worker(self, worker_id: str, worker: "WorkerBase") -> None:
        """Register a worker with the orchestrator."""
        self.workers[worker_id] = worker
        
        # Inject fallback chain into worker if available
        if self.fallback_chain is not None and hasattr(worker, "fallback_chain"):
            worker.fallback_chain = self.fallback_chain
        
        # Emit worker registration event (wrapped to avoid crashing main path)
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            # Safely extract profile data if available
            worker_type = getattr(worker.profile, "worker_type", "unknown") if hasattr(worker, "profile") else "unknown"
            capabilities = getattr(worker.profile, "capabilities", []) if hasattr(worker, "profile") else []
            
            loop.create_task(self._emitter.emit(TraceEvent(
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
            )))
        except Exception:
            pass  # Trace failure should not crash main path

    async def get_top_candidates(self, task: str, n: int) -> list[str]:
        """Returns IDs of the top n registered workers ordered by routing score for this task.
        
        Args:
            task: The task string to score workers against
            n: Maximum number of worker IDs to return
            
        Returns:
            List of worker IDs ordered by routing score (highest first)
        """
        from core.schemas import Task, TaskPriority, WorkerStatus
        from datetime import datetime
        from uuid import uuid4
        
        # Create a minimal task object for scoring
        # Use a simple complexity score of 0.5 for all tasks when called with a string
        task_obj = Task(
            task_id=uuid4(),
            intent=task,
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            created_at=datetime.utcnow(),
        )
        
        # Score each worker using the existing algorithm
        scored_workers = []
        intent_words = set(word.lower() for word in task.lower().split())
        
        for worker_id, worker in self.workers.items():
            # Skip workers that are not ACTIVE (if they have a status attribute)
            if hasattr(worker.profile, 'status'):
                if worker.profile.status != WorkerStatus.ACTIVE:
                    continue
            
            score = 0
            
            # +2 points for complexity match (within 0.1 tolerance)
            if abs(task_obj.complexity_score - worker.profile.preferred_complexity) < 0.1:
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
        scored_workers.sort(key=lambda x: (-x[0], list(self.workers.keys()).index(x[1])))
        
        # Return top n worker IDs
        return [worker_id for _, worker_id in scored_workers[:n]]

    async def process_task(self, task: Task, worker_id: str) -> WorkerOutput:
        """
        Process a task by routing it to the specified worker.
        
        This is a minimal implementation for testing.
        """
        if worker_id not in self.workers:
            from core.exceptions import WorkerNotFoundError
            raise WorkerNotFoundError(worker_id)

        worker = self.workers[worker_id]
        
        # Transition to EXECUTING before worker execution
        try:
            task = await self.state_machine.transition(
                task, TaskStatus.EXECUTING, reason="Worker execution starting", actor="orchestrator"
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
            output = await worker.run(task)
            
            # Escalation check if escalation_engine is configured
            if self.escalation_engine:
                try:
                    decision = await self.escalation_engine.evaluate(task, output, [self.cloud_fallback_model])
                    if decision.should_escalate:
                        # Request approval for escalation
                        if self.approval_gate:
                            approved = await self.escalation_engine.request_approval(task, decision)
                            if approved:
                                # Execute escalation
                                output = await self.escalation_engine.execute_escalation(task, decision)
                            else:
                                # Escalation denied
                                output.metadata["escalation_denied"] = True
                                output.metadata["denied_reason"] = "User denied escalation"
                        else:
                            # No approval gate - escalate automatically
                            output = await self.escalation_engine.execute_escalation(task, decision)
                except Exception:
                    # Escalation error should not crash task processing
                    pass
            
            # Transition to VALIDATING after worker execution
            task = await self.state_machine.transition(
                task, TaskStatus.VALIDATING, reason="Worker execution complete, validating output", actor="orchestrator"
            )
            
            # Simple validation - if output has content, transition to COMPLETE
            if output.content:
                task = await self.state_machine.transition(
                    task, TaskStatus.COMPLETE, reason="Validation passed", actor="orchestrator"
                )
                # Compact scratchpad when task transitions to COMPLETE
                try:
                    await self.scratchpad_manager.compact(task.task_id)
                except Exception:
                    # Silently fail if scratchpad compaction fails
                    pass
                # Mark task as completed in orchestrator metrics
                if self.improvement_loop:
                    try:
                        await self.improvement_loop.mark_task_completed(str(task.task_id))
                    except Exception:
                        pass  # Metrics update failure should not crash task completion
            else:
                task = await self.state_machine.transition(
                    task, TaskStatus.FAILED, reason="Validation failed: empty output", actor="orchestrator"
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
                except Exception:
                    pass
            
            return output
        except Exception as e:
            # On any failure, transition to FAILED if possible
            if self.state_machine.can_transition(task, TaskStatus.FAILED):
                task = await self.state_machine.transition(
                    task, TaskStatus.FAILED, reason=f"Worker execution failed: {str(e)}", actor="orchestrator"
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
                except Exception:
                    pass
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
                task, TaskStatus.RECEIVED, reason="Task received by orchestrator", actor="orchestrator"
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
        except Exception:
            pass

        # Transition to PLANNED before routing
        try:
            task = await self.state_machine.transition(
                task, TaskStatus.PLANNED, reason="Planning worker selection", actor="orchestrator"
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
            if hasattr(worker.profile, 'status'):
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
                    user_rating=None
                )
                try:
                    await self.improvement_loop.record_routing_decision(metrics)
                except Exception:
                    pass  # Metrics recording failure should not crash routing
            
            try:
                event = TraceEvent(
                    event_type=TraceEventType.ORCHESTRATOR_ROUTING_COMPLETE,
                    component=TraceComponent.ORCHESTRATOR,
                    message="Worker selected (only one registered)",
                    level=TraceLevel.INFO,
                    data={
                        "selected_worker": worker_id,
                        "scoring_breakdown": [{"worker_id": worker_id, "score": 1, "reason": "only worker"}],
                    },
                    duration_ms=duration_ms,
                )
                await self._emitter.emit(event)
            except Exception:
                pass
            
            # Update StrategicContext after successful routing decision
            try:
                current_context = await self.memory_router.get_global_context(caller_id="orchestrator")
                if current_context is None:
                    current_context = StrategicContext()
                
                # Update recent task summary
                current_context.recent_task_summary = f"Task {task.task_id}: {task.intent} routed to {worker_id}"
                
                # Update active workers list
                current_context.active_workers = list(self.workers.keys())
                
                # Update timestamp
                from datetime import datetime
                current_context.updated_at = datetime.utcnow()
                
                await self.memory_router.set_global_context(current_context, caller_id="orchestrator")
            except Exception:
                pass  # Context update failure should not crash routing
            
            return await self.process_task(task, worker_id)

        # Score each worker
        scored_workers = []
        intent_words = set(word.lower() for word in task.intent.lower().split())
        scoring_breakdown = []
        
        for worker_id, worker in self.workers.items():
            # Skip workers that are not ACTIVE (if they have a status attribute)
            if hasattr(worker.profile, 'status'):
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
            scoring_breakdown.append({
                "worker_id": worker_id,
                "score": score,
                "reasons": reasons,
            })
        
        # Sort by score descending, then by registration order (maintained by dict iteration order)
        scored_workers.sort(key=lambda x: (-x[0], list(self.workers.keys()).index(x[1])))
        
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
                user_rating=None
            )
            try:
                await self.improvement_loop.record_routing_decision(metrics)
            except Exception:
                pass  # Metrics recording failure should not crash routing
        
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
        except Exception:
            pass
        
        # Update StrategicContext after successful routing decision
        try:
            current_context = await self.memory_router.get_global_context(caller_id="orchestrator")
            if current_context is None:
                current_context = StrategicContext()
            
            # Update recent task summary
            current_context.recent_task_summary = f"Task {task.task_id}: {task.intent} routed to {selected_worker_id}"
            
            # Update active workers list
            current_context.active_workers = list(self.workers.keys())
            
            # Update timestamp
            from datetime import datetime
            current_context.updated_at = datetime.utcnow()
            
            await self.memory_router.set_global_context(current_context, caller_id="orchestrator")
        except Exception:
            pass  # Context update failure should not crash routing
        
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

    async def process_pending_approval(self, task_id: str, approved: bool) -> Task | None:
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
            worker_type = getattr(worker.profile, "worker_type", "unknown") if hasattr(worker, "profile") else "unknown"
            capabilities = getattr(worker.profile, "capabilities", []) if hasattr(worker, "profile") else []
            
            loop.create_task(self._emitter.emit(TraceEvent(
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
            )))
        except Exception:
            pass  # Trace failure should not crash main path

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
