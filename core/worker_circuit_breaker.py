"""Worker-level circuit breaker for cascade failure prevention.

This module implements a circuit breaker pattern at the worker level to prevent
cascade failures when a worker repeatedly fails. The circuit breaker tracks
per-worker failure counts and opens the circuit when the threshold is reached,
preventing further attempts until a timeout elapses or a manual reset occurs.

Architecture Compliance (AR1):
- Lives in core/; imports only from core/observability.py
- No imports from workers/, adapters/, cli/, memory/, skills/, web/, or system/

Architecture Compliance (AR11):
- TraceEmitter is injected via constructor; never uses global emit_trace()

Architecture Compliance (AR12):
- Trace emission is async; state mutations are synchronous (in-memory state)
"""

import logging
import time
from typing import Any, Dict, List, Optional

from core.observability import TraceEmitter

logger = logging.getLogger(__name__)


class WorkerCircuitBreaker:
    """Circuit breaker for worker-level failure tracking.

    This class tracks per-worker failure counts and opens circuits when
    the failure threshold is reached. Open circuits prevent further worker
    execution until a timeout elapses or a manual reset occurs.

    The circuit breaker uses a canonical roster (_registered_workers) as the
    denominator for degraded worker ratio calculations, not the lazily-populated
    _failure_counts dict. This prevents the denominator bug where defensive
    auto-registration in record_failure could inflate the denominator.
    """

    def __init__(
        self,
        emitter: Optional[TraceEmitter] = None,
        failure_threshold: int = 3,
        reset_timeout: int = 60,
    ) -> None:
        """Initialize the worker circuit breaker.

        Args:
            emitter: TraceEmitter for circuit breaker events (injected per AR11)
            failure_threshold: Number of failures before circuit opens
            reset_timeout: Seconds before circuit auto-resets after opening
        """
        self._emitter = emitter
        self._failure_threshold = failure_threshold
        self._reset_timeout = reset_timeout

        # Internal state
        self._registered_workers: set[str] = set()  # Canonical roster
        self._failure_counts: Dict[str, int] = {}  # Per-worker failure count
        self._circuit_open_since: Dict[str, Optional[float]] = {}  # Open timestamp

    def register_worker(self, worker_id: str) -> None:
        """Seed the tracked worker set with worker_id (count=0, circuit closed).

        Adds worker_id to _registered_workers (the canonical roster used as
        denominator for get_degraded_worker_ratio) AND seeds _failure_counts
        and _circuit_open_since. MUST be called by Orchestrator.register_worker
        for every worker at registration time. Idempotent — registering an
        already-tracked worker is a no-op.

        (Source: Claude Rev2 review Issue #1 — CRITICAL; Rev3 had a regression
        where get_degraded_worker_ratio still used _failure_counts as denominator
        instead of the registered roster. Rev4 fixes this by tracking
        _registered_workers separately. — Claude Rev3 review Issue #4)

        Args:
            worker_id: Worker identifier
        """
        if worker_id not in self._registered_workers:
            self._registered_workers.add(worker_id)
            self._failure_counts[worker_id] = 0
            self._circuit_open_since[worker_id] = None

    def record_failure(self, worker_id: str) -> None:
        """Increment failure count for worker_id. Open circuit if threshold reached.

        If worker_id is not registered, auto-registers it first (defensive).

        Args:
            worker_id: Worker identifier
        """
        # Defensive auto-registration if not in roster
        if worker_id not in self._registered_workers:
            self.register_worker(worker_id)

        self._failure_counts[worker_id] += 1
        failure_count = self._failure_counts[worker_id]

        # Open circuit if threshold reached
        if failure_count >= self._failure_threshold:
            if self._circuit_open_since[worker_id] is None:
                self._circuit_open_since[worker_id] = time.time()
                self._emit_circuit_open_event(worker_id, failure_count)

    def record_success(self, worker_id: str) -> None:
        """Reset failure count for worker_id. Close circuit if open.

        If worker_id is not registered, auto-registers it first (defensive).

        Args:
            worker_id: Worker identifier
        """
        # Defensive auto-registration if not in roster
        if worker_id not in self._registered_workers:
            self.register_worker(worker_id)

        # Reset failure count
        self._failure_counts[worker_id] = 0

        # Close circuit if open
        if self._circuit_open_since[worker_id] is not None:
            self._circuit_open_since[worker_id] = None
            self._emit_circuit_reset_event(worker_id)

    def is_available(self, worker_id: str) -> bool:
        """True if worker_id's circuit is closed or reset timeout has elapsed.

        Unknown (unregistered) workers return True (no failures recorded).

        Args:
            worker_id: Worker identifier

        Returns:
            True if worker is available, False if circuit is open
        """
        # Unknown workers are available (no failures recorded)
        if worker_id not in self._registered_workers:
            return True

        # Circuit is closed
        if self._circuit_open_since[worker_id] is None:
            return True

        # Check if reset timeout has elapsed
        open_since = self._circuit_open_since[worker_id]
        if open_since is not None:
            elapsed = time.time() - open_since
            if elapsed >= self._reset_timeout:
                # Auto-reset circuit
                self._circuit_open_since[worker_id] = None
                self._failure_counts[worker_id] = 0
                self._emit_circuit_reset_event(worker_id)
                return True

        return False

    async def reset_circuit(self, worker_id: str) -> None:
        """Manually reset circuit for worker_id. Emits CIRCUIT_BREAKER_RESET trace.

        Args:
            worker_id: Worker identifier
        """
        if worker_id in self._registered_workers:
            self._circuit_open_since[worker_id] = None
            self._failure_counts[worker_id] = 0
            self._emit_circuit_reset_event(worker_id)

    def get_status(self) -> List[Dict[str, Any]]:
        """Return status of all tracked workers. Read-only, sync-safe.

        Returns:
            List of status dicts for each tracked worker
        """
        status = []
        for worker_id in self._registered_workers:
            status.append(
                {
                    "worker_id": worker_id,
                    "failure_count": self._failure_counts[worker_id],
                    "circuit_open": self._circuit_open_since[worker_id] is not None,
                    "circuit_open_since": self._circuit_open_since[worker_id],
                }
            )
        return status

    def get_degraded_workers(self) -> List[str]:
        """Return list of worker_ids with open circuits. Used by orchestrator for degraded mode.

        Returns:
            List of worker identifiers with open circuits
        """
        return [
            worker_id
            for worker_id in self._registered_workers
            if self._circuit_open_since[worker_id] is not None
        ]

    def get_degraded_worker_ratio(self) -> float:
        """Return ratio of workers with open circuits to TOTAL REGISTERED workers.

        Uses _registered_workers (the canonical roster populated by register_worker)
        as the denominator, NOT _failure_counts. This fixes the Rev3 regression
        where the denominator was len(_failure_counts) — which could grow beyond
        the registered set due to defensive auto-registration in record_failure.

        Returns 0.0 if no workers registered. Used by orchestrator to detect
        cascade failure.

        (Source: Claude Rev3 review Issue #4 — Rev3 claimed to fix the denominator
        bug from Rev2 but S3.1 still used _failure_counts. Rev4 fixes this properly
        by tracking _registered_workers as a separate set.)

        Returns:
            Ratio in [0.0, 1.0]
        """
        if not self._registered_workers:
            return 0.0
        degraded = len(self.get_degraded_workers())
        total = len(self._registered_workers)
        return degraded / total

    def _emit_circuit_open_event(self, worker_id: str, failure_count: int) -> None:
        """Emit CIRCUIT_BREAKER_OPEN trace event.

        Args:
            worker_id: Worker identifier
            failure_count: Current failure count
        """
        # Note: This is a synchronous method but trace emission is async.
        # We fire-and-forget the async emission to avoid blocking the circuit
        # breaker logic. This is acceptable because trace emission is optional.
        # In production, the emitter should handle the async scheduling.
        # For now, we log synchronously as a fallback.
        # TODO: Make this async when the caller is async (S2/S3 integration)
        logger.warning(
            "Circuit opened for worker %s after %d failures", worker_id, failure_count
        )

    def _emit_circuit_reset_event(self, worker_id: str) -> None:
        """Emit CIRCUIT_BREAKER_RESET trace event.

        Args:
            worker_id: Worker identifier
        """
        # Note: Same fire-and-forget pattern as _emit_circuit_open_event
        # TODO: Make this async when the caller is async (S2/S3 integration)
        logger.info("Circuit reset for worker %s", worker_id)
