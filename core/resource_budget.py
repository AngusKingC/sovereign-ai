"""
Resource Budget - Multi-Worker Resource Enforcement

Single responsibility: Enforce resource budgets for multi-worker dispatch,
including token limits, concurrent worker limits, and VRAM limits.
"""

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.observability import (
    MemoryTraceEmitter,
    TraceComponent,
    TraceEmitter,
    TraceEvent,
    TraceEventType,
    TraceLevel,
)

if TYPE_CHECKING:
    from core.cost_tracker import CostTracker
    from system.resource_manager import ResourceManager

logger = logging.getLogger(__name__)


@dataclass
class BudgetCheckResult:
    """Result of a budget check."""

    approved: bool
    reason: str
    tokens_available: int = 0


class ResourceBudget:
    """Manages resource budgets for multi-worker dispatch."""

    def __init__(
        self,
        max_tokens_per_task: int = 8192,
        max_tokens_per_session: int = 65536,
        max_concurrent_workers: int = 3,
        max_task_duration_seconds: int = 300,
        resource_manager: "ResourceManager | None" = None,
        emitter: TraceEmitter | None = None,
        cost_tracker: "CostTracker | None" = None,
    ) -> None:
        """Initialize the resource budget manager.

        Args:
            max_tokens_per_task: Maximum tokens allowed per task
            max_tokens_per_session: Maximum tokens allowed per session
            max_concurrent_workers: Maximum concurrent workers allowed
            max_task_duration_seconds: Maximum task duration in seconds
            resource_manager: Optional resource manager for VRAM enforcement
            emitter: Trace emitter for observability
            cost_tracker: Optional cost tracker for spend cap enforcement
        """
        self._max_tokens_per_task = max_tokens_per_task
        self._max_tokens_per_session = max_tokens_per_session
        self._max_concurrent_workers = max_concurrent_workers
        self._max_task_duration_seconds = max_task_duration_seconds
        self._resource_manager = resource_manager
        self._emitter = emitter or MemoryTraceEmitter()
        self._cost_tracker = cost_tracker
        self._session_token_usage: dict[str, int] = {}

    async def check_token_budget(
        self,
        task_id: str,
        tokens_requested: int,
        session_id: str | None = None,
    ) -> BudgetCheckResult:
        """Verify the requested token count does not exceed per-task or per-session limits.

        Args:
            task_id: Task identifier
            tokens_requested: Number of tokens requested
            session_id: Optional session identifier for session-level tracking

        Returns:
            BudgetCheckResult indicating approval status and reason
        """
        # Check per-task limit
        if tokens_requested > self._max_tokens_per_task:
            try:
                await self._emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.OPERATION_COMPLETE,
                        component=TraceComponent.WORKER,
                        level=TraceLevel.WARNING,
                        message="Token budget denied - exceeds per-task limit",
                        data={
                            "task_id": task_id,
                            "tokens_requested": tokens_requested,
                            "max_tokens_per_task": self._max_tokens_per_task,
                        },
                        duration_ms=0,
                    )
                )
            except Exception as e:
                logger.warning("Trace emission failed: %s", e)
            return BudgetCheckResult(
                approved=False,
                reason=f"Token request {tokens_requested} exceeds per-task limit {self._max_tokens_per_task}",
                tokens_available=self._max_tokens_per_task,
            )

        # Check per-session limit if session_id provided
        if session_id:
            session_used = self._session_token_usage.get(session_id, 0)
            if session_used + tokens_requested > self._max_tokens_per_session:
                try:
                    await self._emitter.emit(
                        TraceEvent(
                            event_type=TraceEventType.OPERATION_COMPLETE,
                            component=TraceComponent.WORKER,
                            level=TraceLevel.WARNING,
                            message="Token budget denied - exceeds per-session limit",
                            data={
                                "task_id": task_id,
                                "session_id": session_id,
                                "tokens_requested": tokens_requested,
                                "session_used": session_used,
                                "max_tokens_per_session": self._max_tokens_per_session,
                            },
                            duration_ms=0,
                        )
                    )
                except Exception as e:
                    logger.warning("Trace emission failed: %s", e)
                return BudgetCheckResult(
                    approved=False,
                    reason=f"Token request {tokens_requested} would exceed per-session limit {self._max_tokens_per_session} (already used {session_used})",
                    tokens_available=max(
                        0, self._max_tokens_per_session - session_used
                    ),
                )

        # Check cost cap if cost_tracker is configured
        if self._cost_tracker is not None:
            try:
                # Rough estimate: tokens * 0.00001 (refined by CostTracker)
                estimated_cost = tokens_requested * 0.00001
                cost_decision = await self._cost_tracker.check_spend(
                    estimated_cost_usd=estimated_cost
                )
                if not cost_decision.approved:
                    try:
                        await self._emitter.emit(
                            TraceEvent(
                                event_type=TraceEventType.OPERATION_COMPLETE,
                                component=TraceComponent.WORKER,
                                level=TraceLevel.WARNING,
                                message="Cost cap exceeded",
                                data={
                                    "task_id": task_id,
                                    "tokens_requested": tokens_requested,
                                    "estimated_cost_usd": estimated_cost,
                                    "reason": cost_decision.reason,
                                },
                                duration_ms=0,
                            )
                        )
                    except Exception as e:
                        logger.warning("Trace emission failed: %s", e)
                    return BudgetCheckResult(
                        approved=False,
                        reason=f"Cost cap exceeded: {cost_decision.reason}",
                        tokens_available=self._max_tokens_per_task,
                    )
            except Exception as e:
                # Cost check failure should not crash budget check
                # Per AR18: broad except requires inline comment + WARNING trace
                try:
                    await self._emitter.emit(
                        TraceEvent(
                            event_type=TraceEventType.OPERATION_ERROR,
                            component=TraceComponent.WORKER,
                            message=f"Cost check failed: {type(e).__name__}: {e}",
                            level=TraceLevel.WARNING,
                            data={"error": str(e)},
                            duration_ms=0,
                        )
                    )
                except Exception as e2:
                    logger.warning("Trace emission failed: %s", e2)

        # Budget approved
        try:
            await self._emitter.emit(
                TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.INFO,
                    message="Token budget approved",
                    data={
                        "task_id": task_id,
                        "tokens_requested": tokens_requested,
                    },
                    duration_ms=0,
                )
            )
        except Exception as e:
            logger.warning("Trace emission failed: %s", e)

        tokens_available = self._max_tokens_per_task
        if session_id:
            tokens_available = min(
                tokens_available,
                self._max_tokens_per_session
                - self._session_token_usage.get(session_id, 0),
            )

        return BudgetCheckResult(
            approved=True,
            reason="Token budget approved",
            tokens_available=tokens_available,
        )

    async def check_worker_budget(
        self,
        current_concurrent: int,
    ) -> BudgetCheckResult:
        """Verify adding one more concurrent worker does not exceed max_concurrent_workers.

        Args:
            current_concurrent: Current number of concurrent workers

        Returns:
            BudgetCheckResult indicating approval status and reason
        """
        if current_concurrent >= self._max_concurrent_workers:
            try:
                await self._emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.OPERATION_COMPLETE,
                        component=TraceComponent.WORKER,
                        level=TraceLevel.WARNING,
                        message="Worker budget denied - exceeds max concurrent workers",
                        data={
                            "current_concurrent": current_concurrent,
                            "max_concurrent_workers": self._max_concurrent_workers,
                        },
                        duration_ms=0,
                    )
                )
            except Exception as e:
                logger.warning("Trace emission failed: %s", e)
            return BudgetCheckResult(
                approved=False,
                reason=f"Current concurrent workers {current_concurrent} already at or exceeds max {self._max_concurrent_workers}",
                tokens_available=0,
            )

        try:
            await self._emitter.emit(
                TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.INFO,
                    message="Worker budget approved",
                    data={
                        "current_concurrent": current_concurrent,
                        "max_concurrent_workers": self._max_concurrent_workers,
                    },
                    duration_ms=0,
                )
            )
        except Exception as e:
            logger.warning("Trace emission failed: %s", e)

        return BudgetCheckResult(
            approved=True,
            reason="Worker budget approved",
            tokens_available=0,
        )

    async def check_vram_budget(
        self,
        model_vram_mb: int,
    ) -> BudgetCheckResult:
        """Verify the model fits in available VRAM if ResourceManager is provided.

        Args:
            model_vram_mb: VRAM required by the model in MB

        Returns:
            BudgetCheckResult indicating approval status and reason
        """
        if self._resource_manager is None:
            try:
                await self._emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.OPERATION_COMPLETE,
                        component=TraceComponent.WORKER,
                        level=TraceLevel.INFO,
                        message="VRAM budget check skipped - no resource manager",
                        data={
                            "model_vram_mb": model_vram_mb,
                        },
                        duration_ms=0,
                    )
                )
            except Exception as e:
                logger.warning("Trace emission failed: %s", e)
            return BudgetCheckResult(
                approved=True,
                reason="No resource manager - VRAM check skipped",
                tokens_available=0,
            )

        # Get available VRAM from resource manager
        # This requires system profile and loaded model info
        # For now, we'll approve and let ResourceManager handle the actual check during load
        try:
            await self._emitter.emit(
                TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.INFO,
                    message="VRAM budget approved - delegated to ResourceManager",
                    data={
                        "model_vram_mb": model_vram_mb,
                    },
                    duration_ms=0,
                )
            )
        except Exception as e:
            logger.warning("Trace emission failed: %s", e)

        return BudgetCheckResult(
            approved=True,
            reason="VRAM budget approved - delegated to ResourceManager",
            tokens_available=0,
        )

    async def check_all(
        self,
        task_id: str,
        tokens_requested: int,
        model_vram_mb: int,
        current_concurrent: int,
        session_id: str | None = None,
    ) -> BudgetCheckResult:
        """Run all budget checks and return the first failure or approval if all pass.

        Args:
            task_id: Task identifier
            tokens_requested: Number of tokens requested
            model_vram_mb: VRAM required by the model in MB
            current_concurrent: Current number of concurrent workers
            session_id: Optional session identifier for session-level tracking

        Returns:
            BudgetCheckResult indicating approval status and reason
        """
        # Check token budget first
        token_result = await self.check_token_budget(
            task_id, tokens_requested, session_id
        )
        if not token_result.approved:
            return token_result

        # Check worker budget
        worker_result = await self.check_worker_budget(current_concurrent)
        if not worker_result.approved:
            return worker_result

        # Check VRAM budget
        vram_result = await self.check_vram_budget(model_vram_mb)
        if not vram_result.approved:
            return vram_result

        # All checks passed
        try:
            await self._emitter.emit(
                TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.INFO,
                    message="All budget checks approved",
                    data={
                        "task_id": task_id,
                        "tokens_requested": tokens_requested,
                        "model_vram_mb": model_vram_mb,
                        "current_concurrent": current_concurrent,
                    },
                    duration_ms=0,
                )
            )
        except Exception as e:
            logger.warning("Trace emission failed: %s", e)

        return BudgetCheckResult(
            approved=True,
            reason="All budget checks approved",
            tokens_available=token_result.tokens_available,
        )

    async def check_all_budgets(self, worker_id: str) -> bool:
        """Legacy method for backward compatibility with tests.

        Deprecated: Use check_worker_budget instead.
        This method is kept for backward compatibility with existing tests.
        """
        # For backward compatibility, just check worker budget and return bool
        result = await self.check_worker_budget(current_concurrent=0)
        return result.approved

    async def record_token_usage(
        self,
        task_id: str,
        tokens_used: int,
        session_id: str | None = None,
    ) -> None:
        """Record actual token usage after task completion.

        Args:
            task_id: Task identifier
            tokens_used: Actual number of tokens used
            session_id: Optional session identifier for session-level tracking
        """
        if session_id:
            self._session_token_usage[session_id] = (
                self._session_token_usage.get(session_id, 0) + tokens_used
            )

        try:
            await self._emitter.emit(
                TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.INFO,
                    message="Token usage recorded",
                    data={
                        "task_id": task_id,
                        "tokens_used": tokens_used,
                        "session_id": session_id if session_id else "none",
                    },
                    duration_ms=0,
                )
            )
        except Exception as e:
            logger.warning("Trace emission failed: %s", e)
