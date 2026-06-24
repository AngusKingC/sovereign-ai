"""
Cost Tracker - Central cost aggregation and spend cap enforcement.

Single responsibility: Track token usage costs across all workers,
enforce daily/monthly $ caps, and emit cost traces.

This is the ONLY module that should be consulted before executing a task
to verify spend is within caps. See AR20.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from core.observability import (
    MemoryTraceEmitter,
    TraceComponent,
    TraceEmitter,
    TraceEvent,
    TraceEventType,
    TraceLevel,
)

logger = logging.getLogger(__name__)


@dataclass
class CostPolicy:
    """Configuration for CostTracker."""

    daily_cap_usd: float = 10.0
    monthly_cap_usd: float = 100.0
    alert_threshold_pct: float = 0.80  # alert at 80% of cap
    fallback_threshold_pct: float = 0.90  # fallback to cheaper model at 90%
    fallback_model: str | None = None  # if set, route here when fallback triggered
    enable_traces: bool = True


@dataclass
class CostRecord:
    """A single cost record (one task execution)."""

    timestamp: datetime
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    task_id: str


@dataclass
class CostDecision:
    """Result of a spend cap check."""

    approved: bool
    reason: str
    current_daily_spend: float = 0.0
    current_monthly_spend: float = 0.0
    cap_usd: float = 0.0
    pct_of_cap: float = 0.0
    fallback_model: str | None = None


class CostTracker:
    """Tracks token usage costs and enforces spend caps."""

    def __init__(
        self,
        policy: CostPolicy | None = None,
        emitter: TraceEmitter | None = None,
    ) -> None:
        self._policy = policy or CostPolicy()
        self._emitter = emitter or MemoryTraceEmitter()
        self._records: list[CostRecord] = []
        self._daily_spend: dict[str, float] = {}  # date_str -> usd
        self._monthly_spend: dict[str, float] = {}  # month_str -> usd
        self._model_spend: dict[str, float] = {}  # model -> usd (all-time)
        self._lock = asyncio.Lock()

    async def check_spend(self, estimated_cost_usd: float = 0.0) -> CostDecision:
        """Check if a new task would exceed caps. Call BEFORE executing.

        Args:
            estimated_cost_usd: Estimated cost for the upcoming task

        Returns:
            CostDecision with approval status and reason
        """
        async with self._lock:
            now = datetime.now(timezone.utc)
            daily_key = now.strftime("%Y-%m-%d")
            monthly_key = now.strftime("%Y-%m")

            current_daily = self._daily_spend.get(daily_key, 0.0)
            current_monthly = self._monthly_spend.get(monthly_key, 0.0)

            # Check daily cap
            projected_daily = current_daily + estimated_cost_usd
            if projected_daily > self._policy.daily_cap_usd:
                return CostDecision(
                    approved=False,
                    reason="daily_cap_exceeded",
                    current_daily_spend=current_daily,
                    current_monthly_spend=current_monthly,
                    cap_usd=self._policy.daily_cap_usd,
                    pct_of_cap=projected_daily / self._policy.daily_cap_usd,
                )

            # Check monthly cap
            projected_monthly = current_monthly + estimated_cost_usd
            if projected_monthly > self._policy.monthly_cap_usd:
                return CostDecision(
                    approved=False,
                    reason="monthly_cap_exceeded",
                    current_daily_spend=current_daily,
                    current_monthly_spend=current_monthly,
                    cap_usd=self._policy.monthly_cap_usd,
                    pct_of_cap=projected_monthly / self._policy.monthly_cap_usd,
                )

            # Check fallback threshold
            pct_of_daily_cap = projected_daily / self._policy.daily_cap_usd
            if pct_of_daily_cap >= self._policy.fallback_threshold_pct:
                return CostDecision(
                    approved=True,
                    reason="fallback_threshold_reached",
                    current_daily_spend=current_daily,
                    current_monthly_spend=current_monthly,
                    cap_usd=self._policy.daily_cap_usd,
                    pct_of_cap=pct_of_daily_cap,
                    fallback_model=self._policy.fallback_model,
                )

            return CostDecision(
                approved=True,
                reason="within_caps",
                current_daily_spend=current_daily,
                current_monthly_spend=current_monthly,
                cap_usd=self._policy.daily_cap_usd,
                pct_of_cap=pct_of_daily_cap,
            )

    async def record_usage(
        self,
        model: str,
        tokens_in: int,
        tokens_out: int,
        cost_usd: float,
        task_id: str,
    ) -> None:
        """Record actual usage after task completion. Call AFTER executing.

        Args:
            model: Model name used
            tokens_in: Input tokens
            tokens_out: Output tokens
            cost_usd: Actual cost in USD
            task_id: Task identifier
        """
        async with self._lock:
            now = datetime.now(timezone.utc)
            daily_key = now.strftime("%Y-%m-%d")
            monthly_key = now.strftime("%Y-%m")

            record = CostRecord(
                timestamp=now,
                model=model,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=cost_usd,
                task_id=task_id,
            )

            self._records.append(record)

            # Update spend tracking
            self._daily_spend[daily_key] = (
                self._daily_spend.get(daily_key, 0.0) + cost_usd
            )
            self._monthly_spend[monthly_key] = (
                self._monthly_spend.get(monthly_key, 0.0) + cost_usd
            )
            self._model_spend[model] = self._model_spend.get(model, 0.0) + cost_usd

            # Emit cost trace
            if self._policy.enable_traces:
                await self._emit_cost_trace(record)

            # Check alert threshold
            if self._is_alert_threshold():
                await self._emit_alert(daily_key)

            # Check fallback threshold
            if self._is_fallback_threshold():
                await self._emit_fallback_triggered(daily_key)

    def get_daily_spend(self, date: datetime | None = None) -> float:
        """Get total spend for a given day (default: today).

        Args:
            date: Date to check (defaults to today)

        Returns:
            Total spend in USD for the day
        """
        if date is None:
            date = datetime.now(timezone.utc)
        key = date.strftime("%Y-%m-%d")
        return self._daily_spend.get(key, 0.0)

    def get_monthly_spend(self, date: datetime | None = None) -> float:
        """Get total spend for a given month (default: current month).

        Args:
            date: Date within the month to check (defaults to now)

        Returns:
            Total spend in USD for the month
        """
        if date is None:
            date = datetime.now(timezone.utc)
        key = date.strftime("%Y-%m")
        return self._monthly_spend.get(key, 0.0)

    def get_model_spend(self, model: str) -> float:
        """Get total all-time spend for a model.

        Args:
            model: Model name

        Returns:
            Total spend in USD for the model
        """
        return self._model_spend.get(model, 0.0)

    def get_spend_summary(self) -> dict[str, Any]:
        """Get summary dict with daily, monthly, per-model breakdowns.

        Returns:
            Dictionary with spend breakdowns
        """
        now = datetime.now(timezone.utc)
        return {
            "daily_spend": self.get_daily_spend(now),
            "monthly_spend": self.get_monthly_spend(now),
            "daily_cap_usd": self._policy.daily_cap_usd,
            "monthly_cap_usd": self._policy.monthly_cap_usd,
            "model_spend": self._model_spend.copy(),
            "total_records": len(self._records),
        }

    async def _emit_cost_trace(self, record: CostRecord) -> None:
        """Emit COST_RECORDED trace event.

        Args:
            record: Cost record to emit
        """
        try:
            event = TraceEvent(
                event_type=TraceEventType.COST_RECORDED,
                component=TraceComponent.ORCHESTRATOR,
                message=f"Cost recorded: ${record.cost_usd:.4f} for {record.model}",
                level=TraceLevel.INFO,
                data={
                    "model": record.model,
                    "tokens_in": record.tokens_in,
                    "tokens_out": record.tokens_out,
                    "cost_usd": record.cost_usd,
                    "task_id": record.task_id,
                    "cumulative_daily": self._daily_spend.get(
                        record.timestamp.strftime("%Y-%m-%d"), 0.0
                    ),
                    "cumulative_monthly": self._monthly_spend.get(
                        record.timestamp.strftime("%Y-%m"), 0.0
                    ),
                },
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception as e:
            # Per AR18: broad except requires inline comment + WARNING trace
            logger.warning(
                "Failed to emit cost trace: %s: %s",
                type(e).__name__,
                e,
            )

    async def _emit_alert(self, daily_key: str) -> None:
        """Emit COST_ALERT trace event.

        Args:
            daily_key: Daily spend key
        """
        try:
            event = TraceEvent(
                event_type=TraceEventType.COST_ALERT,
                component=TraceComponent.ORCHESTRATOR,
                message=f"Cost alert: daily spend at {self._policy.alert_threshold_pct:.0%} of cap",
                level=TraceLevel.WARNING,
                data={
                    "daily_spend": self._daily_spend.get(daily_key, 0.0),
                    "daily_cap_usd": self._policy.daily_cap_usd,
                    "alert_threshold_pct": self._policy.alert_threshold_pct,
                },
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception as e:
            # Per AR18: broad except requires inline comment + WARNING trace
            logger.warning(
                "Failed to emit cost alert: %s: %s",
                type(e).__name__,
                e,
            )

    async def _emit_fallback_triggered(self, daily_key: str) -> None:
        """Emit COST_FALLBACK_TRIGGERED trace event.

        Args:
            daily_key: Daily spend key
        """
        try:
            event = TraceEvent(
                event_type=TraceEventType.COST_FALLBACK_TRIGGERED,
                component=TraceComponent.ORCHESTRATOR,
                message=f"Cost fallback triggered: daily spend at {self._policy.fallback_threshold_pct:.0%} of cap",
                level=TraceLevel.WARNING,
                data={
                    "daily_spend": self._daily_spend.get(daily_key, 0.0),
                    "daily_cap_usd": self._policy.daily_cap_usd,
                    "fallback_threshold_pct": self._policy.fallback_threshold_pct,
                    "fallback_model": self._policy.fallback_model,
                },
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception as e:
            # Per AR18: broad except requires inline comment + WARNING trace
            logger.warning(
                "Failed to emit fallback triggered trace: %s: %s",
                type(e).__name__,
                e,
            )

    def _is_alert_threshold(self) -> bool:
        """True if daily spend >= alert_threshold_pct * daily_cap.

        Returns:
            Whether alert threshold is crossed
        """
        now = datetime.now(timezone.utc)
        daily_key = now.strftime("%Y-%m-%d")
        current_daily = self._daily_spend.get(daily_key, 0.0)
        return current_daily >= (
            self._policy.alert_threshold_pct * self._policy.daily_cap_usd
        )

    def _is_fallback_threshold(self) -> bool:
        """True if daily spend >= fallback_threshold_pct * daily_cap.

        Returns:
            Whether fallback threshold is crossed
        """
        now = datetime.now(timezone.utc)
        daily_key = now.strftime("%Y-%m-%d")
        current_daily = self._daily_spend.get(daily_key, 0.0)
        return current_daily >= (
            self._policy.fallback_threshold_pct * self._policy.daily_cap_usd
        )
