"""Adapter fallback chain tests."""

import pytest
import asyncio
import time

from datetime import datetime, timezone

from core.adapter_fallback import AdapterFallbackChain
from core.observability import MemoryTraceEmitter, TraceEventType, TraceComponent
from core.schemas import Message, MessageRole


class MockAdapter:
    """Mock adapter for testing."""

    def __init__(self, name: str, should_fail: bool = False, failure_message: str = "Mock adapter failed"):
        self.name = name
        self.should_fail = should_fail
        self.failure_message = failure_message
        self.call_count = 0

    async def generate(self, messages: list, **kwargs):
        """Generate a response."""
        self.call_count += 1
        if self.should_fail:
            raise RuntimeError(self.failure_message)
        # Extract content from first message for response
        content = messages[0].content if messages else "empty"
        return f"Response from {self.name}: {content}"


class MockCloudAdapter(MockAdapter):
    """Mock cloud adapter for testing approval gating."""

    def __init__(self, name: str, should_fail: bool = False):
        # Use cloud adapter naming convention
        super().__init__(name, should_fail)
        self.__class__.__name__ = f"OpenAI{name}"  # Simulate cloud adapter name


class MockResourceManager:
    """Mock resource manager for testing VRAM checks."""

    def __init__(self, can_load_results: dict[str, tuple[bool, str]] | None = None):
        self.can_load_results = can_load_results or {}
        self.can_load_call_count = 0

    async def can_load(self, model_id: str, quantisation: str, registry):
        """Check if model can load."""
        self.can_load_call_count += 1
        return self.can_load_results.get(model_id, (True, "Fits"))


class MockApprovalGate:
    """Mock approval gate for testing."""

    def __init__(self, approved: bool = True):
        self.approved = approved
        self.request_approval_call_count = 0

    async def request_approval(self, action_description: str, **kwargs):
        """Request approval."""
        self.request_approval_call_count += 1
        return self.approved


class TestAdapterFallbackChain:
    """Test AdapterFallbackChain functionality."""

    @pytest.fixture
    def fallback_chain(self):
        """Create a fallback chain for testing."""
        primary = MockAdapter("primary")
        fallback = MockAdapter("fallback")
        return AdapterFallbackChain(
            adapters=[(primary, "model1"), (fallback, "model2")],
            emitter=MemoryTraceEmitter(),
        )

    @pytest.mark.asyncio
    async def test_execute_calls_primary_adapter_and_returns_result_on_success(self, fallback_chain):
        """Test execute() calls primary adapter and returns result on success."""
        messages = [Message(role=MessageRole.USER, content="test prompt", timestamp=datetime.now(timezone.utc))]
        result = await fallback_chain.execute(messages)

        assert result == "Response from primary: test prompt"
        assert fallback_chain.adapters[0][0].call_count == 1
        assert fallback_chain.adapters[1][0].call_count == 0

    @pytest.mark.asyncio
    async def test_execute_falls_back_to_second_adapter_when_primary_raises(self):
        """Test execute() falls back to second adapter when primary raises."""
        primary = MockAdapter("primary", should_fail=True)
        fallback = MockAdapter("fallback")
        chain = AdapterFallbackChain(
            adapters=[(primary, "model1"), (fallback, "model2")],
            emitter=MemoryTraceEmitter(),
        )

        messages = [Message(role=MessageRole.USER, content="test prompt", timestamp=datetime.now(timezone.utc))]
        result = await chain.execute(messages)

        assert result == "Response from fallback: test prompt"
        assert primary.call_count == 1
        assert fallback.call_count == 1

    @pytest.mark.asyncio
    async def test_execute_falls_back_through_full_chain_and_raises_runtime_error_when_all_adapters_fail(self):
        """Test execute() falls back through full chain and raises RuntimeError when all adapters fail."""
        primary = MockAdapter("primary", should_fail=True)
        fallback = MockAdapter("fallback", should_fail=True)
        chain = AdapterFallbackChain(
            adapters=[(primary, "model1"), (fallback, "model2")],
            emitter=MemoryTraceEmitter(),
        )

        messages = [Message(role=MessageRole.USER, content="test prompt", timestamp=datetime.now(timezone.utc))]
        with pytest.raises(RuntimeError, match="All adapters in fallback chain exhausted"):
            await chain.execute(messages)

        assert primary.call_count == 1
        assert fallback.call_count == 1

    @pytest.mark.asyncio
    async def test_execute_opens_circuit_breaker_after_failure_threshold_consecutive_failures(self):
        """Test execute() opens circuit breaker after failure_threshold consecutive failures."""
        primary = MockAdapter("primary", should_fail=True)
        fallback = MockAdapter("fallback")  # Does not fail
        chain = AdapterFallbackChain(
            adapters=[(primary, "model1"), (fallback, "model2")],
            emitter=MemoryTraceEmitter(),
            failure_threshold=2,
        )

        # First failure - primary fails, fallback succeeds
        messages1 = [Message(role=MessageRole.USER, content="test prompt 1", timestamp=datetime.now(timezone.utc))]
        result1 = await chain.execute(messages1)
        assert result1 == "Response from fallback: test prompt 1"

        # Second failure - primary fails, fallback succeeds
        messages2 = [Message(role=MessageRole.USER, content="test prompt 2", timestamp=datetime.now(timezone.utc))]
        result2 = await chain.execute(messages2)
        assert result2 == "Response from fallback: test prompt 2"

        # Third attempt - primary should be skipped due to circuit breaker, fallback succeeds
        messages3 = [Message(role=MessageRole.USER, content="test prompt 3", timestamp=datetime.now(timezone.utc))]
        result3 = await chain.execute(messages3)
        assert result3 == "Response from fallback: test prompt 3"

        assert primary.call_count == 2  # Only called twice, third time skipped
        assert fallback.call_count == 3  # Called all three times

    @pytest.mark.asyncio
    async def test_execute_skips_adapter_with_open_circuit_breaker(self):
        """Test execute() skips adapter with open circuit breaker."""
        primary = MockAdapter("primary", should_fail=True)
        fallback = MockAdapter("fallback")  # Does not fail
        chain = AdapterFallbackChain(
            adapters=[(primary, "model1"), (fallback, "model2")],
            emitter=MemoryTraceEmitter(),
            failure_threshold=1,
        )

        # First failure - opens circuit breaker
        messages1 = [Message(role=MessageRole.USER, content="test prompt 1", timestamp=datetime.now(timezone.utc))]
        result1 = await chain.execute(messages1)
        assert result1 == "Response from fallback: test prompt 1"

        # Second attempt - primary should be skipped
        messages2 = [Message(role=MessageRole.USER, content="test prompt 2", timestamp=datetime.now(timezone.utc))]
        result2 = await chain.execute(messages2)
        assert result2 == "Response from fallback: test prompt 2"

        assert primary.call_count == 1  # Only called once
        assert fallback.call_count == 2  # Called both times

    @pytest.mark.asyncio
    async def test_execute_resets_circuit_breaker_after_timeout_elapses_and_retries_adapter(self):
        """Test execute() resets circuit breaker after timeout elapses and retries adapter."""
        primary = MockAdapter("primary", should_fail=True)
        fallback = MockAdapter("fallback")  # Does not fail
        chain = AdapterFallbackChain(
            adapters=[(primary, "model1"), (fallback, "model2")],
            emitter=MemoryTraceEmitter(),
            failure_threshold=1,
            circuit_breaker_timeout=1,  # 1 second timeout
        )

        # First failure - opens circuit breaker
        messages1 = [Message(role=MessageRole.USER, content="test prompt 1", timestamp=datetime.now(timezone.utc))]
        result1 = await chain.execute(messages1)
        assert result1 == "Response from fallback: test prompt 1"

        # Wait for timeout
        await asyncio.sleep(1.1)

        # Circuit breaker should be reset, primary should be tried again
        messages2 = [Message(role=MessageRole.USER, content="test prompt 2", timestamp=datetime.now(timezone.utc))]
        result2 = await chain.execute(messages2)
        assert result2 == "Response from fallback: test prompt 2"

        assert primary.call_count == 2  # Called again after timeout
        assert fallback.call_count == 2  # Called both times

    @pytest.mark.asyncio
    async def test_execute_skips_adapter_when_vram_check_fails(self):
        """Test execute() skips adapter when VRAM check fails (resource_manager provided)."""
        primary = MockAdapter("primary")
        fallback = MockAdapter("fallback")
        resource_manager = MockResourceManager(can_load_results={"model1": (False, "Does not fit"), "model2": (True, "Fits")})
        chain = AdapterFallbackChain(
            adapters=[(primary, "model1"), (fallback, "model2")],
            resource_manager=resource_manager,
            emitter=MemoryTraceEmitter(),
        )

        messages = [Message(role=MessageRole.USER, content="test prompt", timestamp=datetime.now(timezone.utc))]
        result = await chain.execute(messages)

        assert result == "Response from fallback: test prompt"
        assert primary.call_count == 0  # Skipped due to VRAM check
        assert fallback.call_count == 1
        assert resource_manager.can_load_call_count >= 1

    @pytest.mark.asyncio
    async def test_execute_skips_vram_check_when_resource_manager_is_none(self):
        """Test execute() skips VRAM check when resource_manager is None."""
        primary = MockAdapter("primary")
        fallback = MockAdapter("fallback")
        chain = AdapterFallbackChain(
            adapters=[(primary, "model1"), (fallback, "model2")],
            resource_manager=None,
            emitter=MemoryTraceEmitter(),
        )

        messages = [Message(role=MessageRole.USER, content="test prompt", timestamp=datetime.now(timezone.utc))]
        result = await chain.execute(messages)

        assert result == "Response from primary: test prompt"
        assert primary.call_count == 1
        assert fallback.call_count == 0

    @pytest.mark.asyncio
    async def test_execute_requests_approval_before_cloud_adapter_fallback_when_approval_gate_provided(self):
        """Test execute() requests approval before cloud adapter fallback when approval_gate provided."""
        primary = MockAdapter("primary", should_fail=True)
        cloud_adapter = MockCloudAdapter("cloud", should_fail=False)
        approval_gate = MockApprovalGate(approved=True)
        chain = AdapterFallbackChain(
            adapters=[(primary, "model1"), (cloud_adapter, "model2")],
            approval_gate=approval_gate,
            emitter=MemoryTraceEmitter(),
        )

        messages = [Message(role=MessageRole.USER, content="test prompt", timestamp=datetime.now(timezone.utc))]
        result = await chain.execute(messages)

        assert result == "Response from cloud: test prompt"
        assert approval_gate.request_approval_call_count == 1
        assert cloud_adapter.call_count == 1

    @pytest.mark.asyncio
    async def test_execute_skips_cloud_adapter_when_approval_denied(self):
        """Test execute() skips cloud adapter when approval denied."""
        primary = MockAdapter("primary", should_fail=True)
        cloud_adapter = MockCloudAdapter("cloud", should_fail=False)
        fallback = MockAdapter("fallback")
        approval_gate = MockApprovalGate(approved=False)
        chain = AdapterFallbackChain(
            adapters=[(primary, "model1"), (cloud_adapter, "model2"), (fallback, "model3")],
            approval_gate=approval_gate,
            emitter=MemoryTraceEmitter(),
        )

        messages = [Message(role=MessageRole.USER, content="test prompt", timestamp=datetime.now(timezone.utc))]
        result = await chain.execute(messages)

        assert result == "Response from fallback: test prompt"
        assert approval_gate.request_approval_call_count == 1
        assert cloud_adapter.call_count == 0  # Skipped due to approval denial
        assert fallback.call_count == 1

    def test_is_available_returns_correct_status_for_open_and_closed_circuit_breakers(self):
        """Test is_available() returns correct status for open and closed circuit breakers."""
        primary = MockAdapter("primary", should_fail=True)
        fallback = MockAdapter("fallback")
        chain = AdapterFallbackChain(
            adapters=[(primary, "model1"), (fallback, "model2")],
            emitter=MemoryTraceEmitter(),
            failure_threshold=1,
        )

        # Initially, all adapters are available
        assert chain.is_available(0) is True
        assert chain.is_available(1) is True

        # Manually open circuit breaker for primary
        chain._failure_counts[0] = 1
        chain._circuit_open_since[0] = 1.0  # Set to a past timestamp

        # Circuit breaker is open but timeout has elapsed
        assert chain.is_available(0) is True

        # Set circuit breaker to recent timestamp
        chain._circuit_open_since[0] = time.time()

        # Circuit breaker is open and timeout has not elapsed
        assert chain.is_available(0) is False

    def test_get_status_returns_correct_status_list_for_all_adapters(self):
        """Test get_status() returns correct status list for all adapters."""
        primary = MockAdapter("primary")
        fallback = MockAdapter("fallback")
        chain = AdapterFallbackChain(
            adapters=[(primary, "model1"), (fallback, "model2")],
            emitter=MemoryTraceEmitter(),
        )

        status = chain.get_status()

        assert len(status) == 2
        assert status[0]["index"] == 0
        assert status[0]["adapter"] == "MockAdapter"
        assert status[0]["model"] == "model1"
        assert status[0]["failures"] == 0
        assert status[0]["circuit_open"] is False
        assert status[0]["resets_in_seconds"] is None

        assert status[1]["index"] == 1
        assert status[1]["adapter"] == "MockAdapter"
        assert status[1]["model"] == "model2"
        assert status[1]["failures"] == 0
        assert status[1]["circuit_open"] is False
        assert status[1]["resets_in_seconds"] is None

    @pytest.mark.asyncio
    async def test_reset_circuit_breaker_clears_failure_count_and_emits_reset_trace_event(self):
        """Test reset_circuit_breaker() clears failure count and emits reset trace event."""
        primary = MockAdapter("primary", should_fail=True)
        fallback = MockAdapter("fallback")
        chain = AdapterFallbackChain(
            adapters=[(primary, "model1"), (fallback, "model2")],
            emitter=MemoryTraceEmitter(),
            failure_threshold=1,
        )

        # Open circuit breaker
        chain._failure_counts[0] = 1
        chain._circuit_open_since[0] = time.time()

        # Reset circuit breaker
        await chain.reset_circuit_breaker(0)

        assert chain._failure_counts[0] == 0
        assert chain._circuit_open_since[0] is None

        # Check trace event was emitted
        events = chain._emitter.get_events()
        reset_events = [e for e in events if e.event_type == TraceEventType.CIRCUIT_BREAKER_RESET]
        assert len(reset_events) > 0

    @pytest.mark.asyncio
    async def test_trace_event_emitted_on_fallback_with_correct_failed_adapter_name(self):
        """Test trace event emitted on fallback with correct failed adapter name."""
        primary = MockAdapter("primary", should_fail=True, failure_message="Primary failed")
        fallback = MockAdapter("fallback")
        chain = AdapterFallbackChain(
            adapters=[(primary, "model1"), (fallback, "model2")],
            emitter=MemoryTraceEmitter(),
        )

        messages = [Message(role=MessageRole.USER, content="test prompt", timestamp=datetime.now(timezone.utc))]
        await chain.execute(messages)

        events = chain._emitter.get_events()
        fallback_events = [e for e in events if e.event_type == TraceEventType.ADAPTER_FALLBACK]
        assert len(fallback_events) > 0

        fallback_event = fallback_events[0]
        assert fallback_event.data["failed_adapter"] == "MockAdapter"
        assert fallback_event.data["next_adapter"] == "MockAdapter"
        assert "Primary failed" in fallback_event.data["reason"]
