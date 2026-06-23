"""
Multi-Worker Dispatcher.

Single responsibility: Dispatch the same task to multiple workers concurrently
or sequentially, collect all responses, and allow user to select the best.
"""

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from pydantic import BaseModel, Field

from core.observability import (
    TraceComponent,
    TraceEventType,
    TraceLevel,
    TraceEvent,
    TraceEmitter,
    MemoryTraceEmitter,
)

if TYPE_CHECKING:
    from core.orchestrator import Orchestrator
    from core.resource_budget import ResourceBudget
    from core.rating_system import RatingSystem
    from core.resource_manager import ResourceManager


class WorkerResponse(BaseModel):
    """Response from a single worker in multi-worker mode."""
    
    worker_id: str
    response: str | None = None
    error: str | None = None
    duration_ms: float
    succeeded: bool


class MultiWorkerResult(BaseModel):
    """Result of a multi-worker dispatch operation."""
    
    result_id: str = Field(default_factory=lambda: str(uuid4()))
    task: str
    mode: str
    responses: list[WorkerResponse]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    winner_worker_id: str | None = None


class MultiWorkerDispatcher:
    """Dispatches tasks to multiple workers and collects responses."""
    
    def __init__(
        self,
        orchestrator: "Orchestrator",
        resource_budget: "ResourceBudget",
        rating_system: "RatingSystem",
        resource_manager: "ResourceManager | None" = None,
        emitter: TraceEmitter | None = None,
        max_workers: int = 3,
    ) -> None:
        """Initialize the multi-worker dispatcher.
        
        Args:
            orchestrator: Orchestrator for routing decisions
            resource_budget: ResourceBudget for checking worker resource requirements
            rating_system: RatingSystem for recording user selections
            resource_manager: Optional ResourceManager for model VRAM management
            emitter: TraceEmitter for observability
            max_workers: Maximum number of workers to dispatch to
        """
        self.orchestrator = orchestrator
        self.resource_budget = resource_budget
        self.rating_system = rating_system
        self.resource_manager = resource_manager
        self.max_workers = max_workers
        self._emitter = emitter if emitter is not None else MemoryTraceEmitter()
        
        # In-memory storage for results
        self._results: dict[str, MultiWorkerResult] = {}
    
    async def dispatch(
        self,
        task: str,
        worker_ids: list[str] | None = None,
        mode: str = "sequential"
    ) -> MultiWorkerResult:
        """Dispatch task to multiple workers and collect responses.
        
        Args:
            task: The task string to dispatch
            worker_ids: Optional list of specific worker IDs to use. If None,
                queries orchestrator for top candidates.
            mode: Dispatch mode - "parallel" or "sequential"
            
        Returns:
            MultiWorkerResult with all worker responses
            
        Raises:
            ValueError: If mode is not "parallel" or "sequential"
            RuntimeError: If no workers pass resource budget check
        """
        if mode not in ("parallel", "sequential"):
            raise ValueError(f"Invalid mode: {mode}. Must be 'parallel' or 'sequential'")
        
        start_time = datetime.now(timezone.utc)
        
        # Get worker IDs
        if worker_ids is None:
            worker_ids = await self.orchestrator.get_top_candidates(task, self.max_workers)
        
        # Filter workers by resource budget
        eligible_workers: list[str] = []
        for worker_id in worker_ids:
            worker = self.orchestrator.workers.get(worker_id)
            if worker is None:
                continue
            
            try:
                budget_ok = await self.resource_budget.check_all_budgets(worker_id)
                if budget_ok:
                    eligible_workers.append(worker_id)
            except Exception:
                # Budget check failure - skip this worker
                continue
        
        if not eligible_workers:
            raise RuntimeError("No workers within resource budget")
        
        # Emit dispatch started event
        await self._emitter.emit(TraceEvent(
            event_type=TraceEventType.MULTI_WORKER_DISPATCH_STARTED,
            component=TraceComponent.MULTI_WORKER,
            message="Multi-worker dispatch started",
            level=TraceLevel.INFO,
            data={
                "task": task,
                "mode": mode,
                "worker_count": len(eligible_workers),
            },
            duration_ms=0,
        ))
        
        # Release orchestrator model from VRAM before dispatching workers
        if self.resource_manager is not None:
            try:
                if self.orchestrator.fallback_chain is not None:
                    await self.resource_manager.release_model(self.orchestrator.fallback_chain)
                await self._emitter.emit(TraceEvent(
                    event_type=TraceEventType.MULTI_WORKER_ORCHESTRATOR_MODEL_RELEASED,
                    component=TraceComponent.MULTI_WORKER,
                    message="Orchestrator model released from VRAM",
                    level=TraceLevel.INFO,
                    data={},
                    duration_ms=0,
                ))
            except Exception:
                # Release failure must not abort dispatch
                pass
        
        # Dispatch based on mode
        responses: list[WorkerResponse] = []
        
        if mode == "parallel":
            responses = await self._dispatch_parallel(task, eligible_workers)
        else:
            responses = await self._dispatch_sequential(task, eligible_workers)
        
        # Calculate total duration
        total_duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        
        # Count successes and failures
        success_count = sum(1 for r in responses if r.succeeded)
        fail_count = len(responses) - success_count
        
        # Create result
        result = MultiWorkerResult(
            task=task,
            mode=mode,
            responses=responses,
        )
        
        # Store result
        self._results[result.result_id] = result
        
        # Emit dispatch completed event
        await self._emitter.emit(TraceEvent(
            event_type=TraceEventType.MULTI_WORKER_DISPATCH_COMPLETED,
            component=TraceComponent.MULTI_WORKER,
            message="Multi-worker dispatch completed",
            level=TraceLevel.INFO,
            data={
                "success_count": success_count,
                "fail_count": fail_count,
                "total_duration_ms": total_duration_ms,
                "mode": mode,
            },
            duration_ms=total_duration_ms,
        ))
        
        return result
    
    async def _dispatch_parallel(self, task: str, worker_ids: list[str]) -> list[WorkerResponse]:
        """Dispatch task to all workers concurrently.
        
        Args:
            task: The task string
            worker_ids: List of worker IDs to dispatch to
            
        Returns:
            List of WorkerResponse objects
        """
        async def dispatch_single(worker_id: str) -> WorkerResponse:
            """Dispatch to a single worker."""
            worker = self.orchestrator.workers.get(worker_id)
            if worker is None:
                return WorkerResponse(
                    worker_id=worker_id,
                    error="Worker not found",
                    duration_ms=0,
                    succeeded=False,
                )
            
            start_time = datetime.now(timezone.utc)
            try:
                output = await worker.execute(task)
                duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
                # Handle both WorkerOutput (production) and str (test mocks)
                if isinstance(output, str):
                    response_content = output
                else:
                    response_content = output.content
                return WorkerResponse(
                    worker_id=worker_id,
                    response=response_content,
                    duration_ms=duration_ms,
                    succeeded=True,
                )
            except Exception as e:
                duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
                await self._emitter.emit(TraceEvent(
                    event_type=TraceEventType.MULTI_WORKER_WORKER_FAILED,
                    component=TraceComponent.MULTI_WORKER,
                    message=f"Worker {worker_id} failed",
                    level=TraceLevel.ERROR,
                    data={
                        "worker_id": worker_id,
                        "error": str(e),
                    },
                    duration_ms=duration_ms,
                ))
                return WorkerResponse(
                    worker_id=worker_id,
                    error=str(e),
                    duration_ms=duration_ms,
                    succeeded=False,
                )
        
        # Dispatch all workers concurrently
        results = await asyncio.gather(
            *[dispatch_single(wid) for wid in worker_ids],
            return_exceptions=True,
        )
        
        # Handle exceptions from gather
        responses: list[WorkerResponse] = []
        for result in results:
            if isinstance(result, Exception):
                responses.append(WorkerResponse(
                    worker_id="unknown",
                    error=str(result),
                    duration_ms=0,
                    succeeded=False,
                ))
            else:
                assert isinstance(result, WorkerResponse)
                responses.append(result)
        
        return responses
    
    async def _dispatch_sequential(self, task: str, worker_ids: list[str]) -> list[WorkerResponse]:
        """Dispatch task to workers one at a time.
        
        Args:
            task: The task string
            worker_ids: List of worker IDs to dispatch to
            
        Returns:
            List of WorkerResponse objects
        """
        responses: list[WorkerResponse] = []
        
        for worker_id in worker_ids:
            worker = self.orchestrator.workers.get(worker_id)
            if worker is None:
                responses.append(WorkerResponse(
                    worker_id=worker_id,
                    error="Worker not found",
                    duration_ms=0,
                    succeeded=False,
                ))
                continue
            
            # Ensure model is loaded before worker runs
            if self.resource_manager is not None:
                try:
                    await self.resource_manager.ensure_model(worker.adapter)
                    await self._emitter.emit(TraceEvent(
                        event_type=TraceEventType.MULTI_WORKER_WORKER_MODEL_ENSURED,
                        component=TraceComponent.MULTI_WORKER,
                        message=f"Worker {worker_id} model ensured",
                        level=TraceLevel.INFO,
                        data={"worker_id": worker_id},
                        duration_ms=0,
                    ))
                except Exception:
                    # Ensure failure must not abort dispatch
                    pass
            
            start_time = datetime.now(timezone.utc)
            try:
                output = await worker.execute(task)
                duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
                # Handle both WorkerOutput (production) and str (test mocks)
                if isinstance(output, str):
                    response_content = output
                else:
                    response_content = output.content
                responses.append(WorkerResponse(
                    worker_id=worker_id,
                    response=response_content,
                    duration_ms=duration_ms,
                    succeeded=True,
                ))
            except Exception as e:
                duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
                await self._emitter.emit(TraceEvent(
                    event_type=TraceEventType.MULTI_WORKER_WORKER_FAILED,
                    component=TraceComponent.MULTI_WORKER,
                    message=f"Worker {worker_id} failed",
                    level=TraceLevel.ERROR,
                    data={
                        "worker_id": worker_id,
                        "error": str(e),
                    },
                    duration_ms=duration_ms,
                ))
                responses.append(WorkerResponse(
                    worker_id=worker_id,
                    error=str(e),
                    duration_ms=duration_ms,
                    succeeded=False,
                ))
            
            # Release model after worker completes
            if self.resource_manager is not None:
                try:
                    await self.resource_manager.release_model(worker.adapter)
                    await self._emitter.emit(TraceEvent(
                        event_type=TraceEventType.MULTI_WORKER_WORKER_MODEL_RELEASED,
                        component=TraceComponent.MULTI_WORKER,
                        message=f"Worker {worker_id} model released",
                        level=TraceLevel.INFO,
                        data={"worker_id": worker_id},
                        duration_ms=0,
                    ))
                except Exception:
                    # Release failure must not abort dispatch
                    pass
        
        return responses
    
    async def select_winner(self, result_id: str, winner_worker_id: str) -> None:
        """Select the winning worker for a multi-worker result.
        
        Args:
            result_id: The result ID to select winner for
            winner_worker_id: The worker ID that won
            
        Raises:
            KeyError: If result_id is not found
        """
        if result_id not in self._results:
            raise KeyError(f"Result not found: {result_id}")
        
        result = self._results[result_id]
        
        # Record rating for winner
        await self.rating_system.record_rating(winner_worker_id, 1.0)
        
        # Record slightly lower rating for non-winners that succeeded
        for response in result.responses:
            if response.succeeded and response.worker_id != winner_worker_id:
                await self.rating_system.record_rating(response.worker_id, 0.9)
        
        # Set winner
        result.winner_worker_id = winner_worker_id
        
        # Emit winner selected event
        await self._emitter.emit(TraceEvent(
            event_type=TraceEventType.MULTI_WORKER_WINNER_SELECTED,
            component=TraceComponent.MULTI_WORKER,
            message="Winner selected",
            level=TraceLevel.INFO,
            data={
                "result_id": result_id,
                "winner_worker_id": winner_worker_id,
            },
            duration_ms=0,
        ))
    
    async def get_result(self, result_id: str) -> MultiWorkerResult | None:
        """Retrieve a stored multi-worker result.
        
        Args:
            result_id: The result ID to retrieve
            
        Returns:
            MultiWorkerResult if found, None otherwise
        """
        return self._results.get(result_id)
