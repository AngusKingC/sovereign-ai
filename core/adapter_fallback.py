"""Adapter Fallback Chain for graceful degradation when adapters fail.

This module provides a circuit breaker pattern with fallback adapters to ensure
the system degrades gracefully rather than failing hard when the primary adapter
is unavailable (Ollama crashed, VRAM full, API timeout).
"""

import time
from typing import Any

from core.observability import (
    TraceEventType,
    TraceComponent,
    TraceLevel,
    TraceEvent,
    TraceEmitter,
    MemoryTraceEmitter,
)


class AdapterFallbackChain:
    """Circuit breaker pattern with fallback adapters for graceful degradation."""

    def __init__(
        self,
        adapters: list[tuple[Any, str]],
        resource_manager: Any = None,
        approval_gate: Any = None,
        emitter: TraceEmitter | None = None,
        failure_threshold: int = 3,
        circuit_breaker_timeout: int = 60,
    ) -> None:
        """Initialize the adapter fallback chain.

        Args:
            adapters: Ordered list of (adapter_instance, model_name) pairs. First entry is primary, subsequent entries are fallbacks. Must contain at least one entry.
            resource_manager: Injected, default None. If provided, consulted before each attempt to verify VRAM fit. If not provided, skip VRAM check.
            approval_gate: Injected, default None. If provided, used to request approval before falling back to a cloud adapter.
            emitter: Injected, default MemoryTraceEmitter()
            failure_threshold: Number of consecutive failures before circuit breaker opens for an adapter
            circuit_breaker_timeout: Seconds before a tripped circuit breaker resets and the adapter is retried
        """
        if not adapters:
            raise ValueError("adapters list must contain at least one (adapter, model_name) pair")

        self.adapters = adapters
        self.resource_manager = resource_manager
        self.approval_gate = approval_gate
        self._emitter = emitter or MemoryTraceEmitter()
        self.failure_threshold = failure_threshold
        self.circuit_breaker_timeout = circuit_breaker_timeout

        # Internal state
        self._failure_counts: dict = {}
        self._circuit_open_since: dict = {}

        # Initialize failure counts for all adapters
        for i, (adapter, model_name) in enumerate(adapters):
            self._failure_counts[i] = 0
            self._circuit_open_since[i] = None

    async def execute(self, messages: list, **kwargs) -> Any:
        """Execute messages through the fallback chain.

        Iterates through self.adapters in order:
        - Check circuit breaker — if open for this adapter and timeout has not elapsed, skip it
        - If circuit breaker timeout has elapsed, reset it
        - If resource_manager is provided, check VRAM fit for this adapter/model
        - If this is not the primary adapter and appears to be a cloud adapter, request approval
        - Attempt execution — call the adapter's execution method with messages and **kwargs
        - On success: reset failure count for this adapter to 0. Return result.
        - On failure: increment failure count. If count reaches failure_threshold, open circuit breaker. Continue to next adapter.

        If all adapters are exhausted without success: raise RuntimeError

        Args:
            messages: List of Message objects to execute
            **kwargs: Additional keyword arguments to pass to the adapter

        Returns:
            The result from the adapter

        Raises:
            RuntimeError: If all adapters in fallback chain are exhausted
        """
        for i, (adapter, model_name) in enumerate(self.adapters):
            adapter_name = self._get_adapter_name(adapter)

            # Check circuit breaker
            if self._circuit_open_since[i] is not None:
                elapsed = time.time() - self._circuit_open_since[i]
                if elapsed < self.circuit_breaker_timeout:
                    # Circuit breaker still open, skip this adapter
                    seconds_remaining = self.circuit_breaker_timeout - elapsed
                    try:
                        event = TraceEvent(
                            event_type=TraceEventType.CIRCUIT_BREAKER_OPEN,
                            component=TraceComponent.ADAPTER_FALLBACK_CHAIN,
                            level=TraceLevel.WARNING,
                            message="Circuit breaker open, skipping adapter",
                            data={
                                "adapter": adapter_name,
                                "seconds_remaining": int(seconds_remaining),
                            },
                            duration_ms=0,
                        )
                        await self._emitter.emit(event)
                    except Exception:
                        pass
                    continue
                else:
                    # Circuit breaker timeout elapsed, reset it
                    self._failure_counts[i] = 0
                    self._circuit_open_since[i] = None
                    try:
                        event = TraceEvent(
                            event_type=TraceEventType.CIRCUIT_BREAKER_RESET,
                            component=TraceComponent.ADAPTER_FALLBACK_CHAIN,
                            level=TraceLevel.INFO,
                            message="Circuit breaker reset, retrying adapter",
                            data={"adapter": adapter_name},
                            duration_ms=0,
                        )
                        await self._emitter.emit(event)
                    except Exception:
                        pass

            # Check VRAM if resource_manager is provided
            if self.resource_manager is not None:
                try:
                    can_fit, reason = await self.resource_manager.can_load(model_name, "default", None)
                    if not can_fit:
                        try:
                            event = TraceEvent(
                                event_type=TraceEventType.ADAPTER_UNAVAILABLE,
                                component=TraceComponent.ADAPTER_FALLBACK_CHAIN,
                                level=TraceLevel.WARNING,
                                message="Adapter skipped due to VRAM constraints",
                                data={
                                    "reason": "vram_insufficient",
                                    "adapter": adapter_name,
                                    "detail": reason,
                                },
                                duration_ms=0,
                            )
                            await self._emitter.emit(event)
                        except Exception:
                            pass
                        continue
                except Exception:
                    # VRAM check failed, proceed anyway
                    pass

            # Check approval for cloud adapters (non-primary)
            if i > 0 and self._is_cloud_adapter(adapter):
                if self.approval_gate is not None:
                    try:
                        approved = await self.approval_gate.request_approval(
                            action_description=f"Fall back to cloud adapter {adapter_name}",
                            cloud_adapter_to_use=adapter_name,
                        )
                        if not approved:
                            try:
                                event = TraceEvent(
                                    event_type=TraceEventType.ADAPTER_UNAVAILABLE,
                                    component=TraceComponent.ADAPTER_FALLBACK_CHAIN,
                                    level=TraceLevel.WARNING,
                                    message="Cloud adapter fallback denied by approval gate",
                                    data={"reason": "approval_denied", "adapter": adapter_name},
                                    duration_ms=0,
                                )
                                await self._emitter.emit(event)
                            except Exception:
                                pass
                            continue
                    except Exception:
                        # Approval check failed, proceed anyway
                        pass

            # Attempt execution
            try:
                # Call the adapter's generate method
                result = await adapter.generate(messages, **kwargs)

                # Success: reset failure count
                self._failure_counts[i] = 0
                self._circuit_open_since[i] = None

                return result
            except Exception as e:
                # Failure: increment failure count
                self._failure_counts[i] += 1

                # Check if circuit breaker should open
                if self._failure_counts[i] >= self.failure_threshold:
                    self._circuit_open_since[i] = time.time()

                # Determine next adapter name for trace event
                next_adapter_name = None
                if i + 1 < len(self.adapters):
                    next_adapter_name = self._get_adapter_name(self.adapters[i + 1][0])

                try:
                    event = TraceEvent(
                        event_type=TraceEventType.ADAPTER_FALLBACK,
                        component=TraceComponent.ADAPTER_FALLBACK_CHAIN,
                        level=TraceLevel.WARNING,
                        message="Adapter failed, falling back to next",
                        data={
                            "failed_adapter": adapter_name,
                            "next_adapter": next_adapter_name,
                            "reason": str(e),
                            "failure_count": self._failure_counts[i],
                        },
                        duration_ms=0,
                    )
                    await self._emitter.emit(event)
                except Exception:
                    pass

                # Continue to next adapter
                continue

        # All adapters exhausted
        raise RuntimeError("All adapters in fallback chain exhausted")

    def is_available(self, adapter_index: int = 0) -> bool:
        """Check if the adapter at the given index is available.

        Returns True if the adapter has an open circuit breaker that has not yet timed out.
        Returns False otherwise. Read-only, synchronous-safe, no trace emission.

        Args:
            adapter_index: Index of the adapter to check

        Returns:
            True if adapter is available (circuit breaker not open or timeout elapsed), False otherwise
        """
        if adapter_index < 0 or adapter_index >= len(self.adapters):
            return False

        if self._circuit_open_since[adapter_index] is None:
            return True

        elapsed = time.time() - self._circuit_open_since[adapter_index]
        return elapsed >= self.circuit_breaker_timeout

    async def reset_circuit_breaker(self, adapter_index: int) -> None:
        """Manually reset the circuit breaker for the given adapter index.

        Clears failure count. Emits TraceEventType.CIRCUIT_BREAKER_RESET.
        Useful for testing and admin tooling.

        Args:
            adapter_index: Index of the adapter to reset
        """
        if adapter_index < 0 or adapter_index >= len(self.adapters):
            return

        self._failure_counts[adapter_index] = 0
        self._circuit_open_since[adapter_index] = None

        adapter_name = self._get_adapter_name(self.adapters[adapter_index][0])

        try:
            event = TraceEvent(
                event_type=TraceEventType.CIRCUIT_BREAKER_RESET,
                component=TraceComponent.ADAPTER_FALLBACK_CHAIN,
                level=TraceLevel.INFO,
                message="Circuit breaker manually reset",
                data={"adapter": adapter_name},
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            pass

    def get_status(self) -> list[dict]:
        """Return current status of all adapters in the chain.

        Returns list of dicts with keys: index, adapter, model, failures, circuit_open, resets_in_seconds.
        Read-only.

        Returns:
            List of adapter status dicts
        """
        status = []
        for i, (adapter, model_name) in enumerate(self.adapters):
            adapter_name = self._get_adapter_name(adapter)
            circuit_open = self._circuit_open_since[i] is not None
            resets_in_seconds = None

            if circuit_open and self._circuit_open_since[i] is not None:
                elapsed = time.time() - self._circuit_open_since[i]
                resets_in_seconds = max(0, self.circuit_breaker_timeout - elapsed)

            status.append({
                "index": i,
                "adapter": adapter_name,
                "model": model_name,
                "failures": self._failure_counts[i],
                "circuit_open": circuit_open,
                "resets_in_seconds": resets_in_seconds,
            })

        return status

    def _get_adapter_name(self, adapter: Any) -> str:
        """Get the name of an adapter instance.

        Args:
            adapter: The adapter instance

        Returns:
            The adapter name (class name or string representation)
        """
        return adapter.__class__.__name__ if hasattr(adapter, "__class__") else str(adapter)

    def _is_cloud_adapter(self, adapter: Any) -> bool:
        """Check if an adapter appears to be a cloud adapter.

        Cloud adapters are identified by class name containing "Gemini", "OpenAI", "Anthropic", or "OpenRouter".

        Args:
            adapter: The adapter instance

        Returns:
            True if adapter appears to be a cloud adapter, False otherwise
        """
        adapter_name = self._get_adapter_name(adapter).lower()
        cloud_keywords = ["gemini", "openai", "anthropic", "openrouter"]
        return any(keyword in adapter_name for keyword in cloud_keywords)
