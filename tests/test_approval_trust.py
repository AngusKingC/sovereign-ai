"""Approval trust registry tests."""

import pytest

from core.approval_trust import ApprovalTrustRegistry, TrustLevel
from core.observability import MemoryTraceEmitter, TraceEventType, TraceComponent
from core.exceptions import ApprovalDeniedError


pytestmark = pytest.mark.asyncio


class MockMemoryRouter:
    """Mock memory router for testing."""

    def __init__(self):
        self.storage = {}

    async def scoped_read(self, scope: str, key: str):
        """Read from scoped storage."""
        return self.storage.get(f"{scope}:{key}")

    async def scoped_write(self, scope: str, key: str, data):
        """Write to scoped storage."""
        self.storage[f"{scope}:{key}"] = data


class TestApprovalTrustRegistry:
    """Test ApprovalTrustRegistry functionality."""

    @pytest.fixture
    def memory_router(self):
        """Create a mock memory router."""
        return MockMemoryRouter()

    @pytest.fixture
    def emitter(self):
        """Create a memory trace emitter."""
        return MemoryTraceEmitter()

    @pytest.fixture
    def registry(self, memory_router, emitter):
        """Create an approval trust registry."""
        return ApprovalTrustRegistry(memory_router=memory_router, emitter=emitter)

    async def test_get_trust_level_returns_always_ask_for_unknown_command(self, registry):
        """Test get_trust_level() returns ALWAYS_ASK for unknown command."""
        trust_level = await registry.get_trust_level("unknown command")
        assert trust_level == TrustLevel.ALWAYS_ASK

    async def test_get_trust_level_returns_session_trust_after_set_trust_session_scope(self, registry):
        """Test get_trust_level() returns SESSION_TRUST after set_trust(scope="session")."""
        await registry.set_trust("test command", TrustLevel.SESSION_TRUST, scope="session")
        trust_level = await registry.get_trust_level("test command")
        assert trust_level == TrustLevel.SESSION_TRUST

    async def test_get_trust_level_returns_permanent_trust_after_set_trust_permanent_scope(self, registry):
        """Test get_trust_level() returns PERMANENT_TRUST after set_trust(scope="permanent")."""
        await registry.set_trust("test command", TrustLevel.PERMANENT_TRUST, scope="permanent")
        trust_level = await registry.get_trust_level("test command")
        assert trust_level == TrustLevel.PERMANENT_TRUST

    async def test_set_trust_persists_to_memory_router_for_permanent_scope(self, registry, memory_router):
        """Test set_trust() persists to MemoryRouter for PERMANENT scope."""
        await registry.set_trust("test command", TrustLevel.PERMANENT_TRUST, scope="permanent")
        # Check that it was persisted
        stored_data = await memory_router.scoped_read("approval_trust", "test command")
        assert stored_data is not None
        assert stored_data["level"] == TrustLevel.PERMANENT_TRUST

    async def test_set_trust_does_not_persist_to_memory_router_for_session_scope(self, registry, memory_router):
        """Test set_trust() does NOT persist to MemoryRouter for SESSION scope."""
        await registry.set_trust("test command", TrustLevel.SESSION_TRUST, scope="session")
        # Check that it was NOT persisted
        stored_data = await memory_router.scoped_read("approval_trust", "test command")
        assert stored_data is None

    async def test_revoke_trust_removes_from_session_dict(self, registry):
        """Test revoke_trust() removes from session dict."""
        await registry.set_trust("test command", TrustLevel.SESSION_TRUST, scope="session")
        await registry.revoke_trust("test command")
        trust_level = await registry.get_trust_level("test command")
        assert trust_level == TrustLevel.ALWAYS_ASK

    async def test_revoke_trust_calls_memory_router_delete_for_permanent_trust(self, registry, memory_router):
        """Test revoke_trust() calls MemoryRouter delete for PERMANENT trust."""
        await registry.set_trust("test command", TrustLevel.PERMANENT_TRUST, scope="permanent")
        await registry.revoke_trust("test command")
        # Check that it was deleted from memory router
        stored_data = await memory_router.scoped_read("approval_trust", "test command")
        assert stored_data is None

    async def test_is_trusted_returns_true_for_session_trust(self, registry):
        """Test is_trusted() returns True for SESSION_TRUST."""
        await registry.set_trust("test command", TrustLevel.SESSION_TRUST, scope="session")
        is_trusted = await registry.is_trusted("test command")
        assert is_trusted is True

    async def test_is_trusted_returns_true_for_permanent_trust(self, registry):
        """Test is_trusted() returns True for PERMANENT_TRUST."""
        await registry.set_trust("test command", TrustLevel.PERMANENT_TRUST, scope="permanent")
        is_trusted = await registry.is_trusted("test command")
        assert is_trusted is True

    async def test_is_trusted_returns_false_for_always_ask(self, registry):
        """Test is_trusted() returns False for ALWAYS_ASK."""
        is_trusted = await registry.is_trusted("unknown command")
        assert is_trusted is False

    async def test_is_trusted_raises_approval_denied_error_for_never_allow_pattern(self, registry):
        """Test is_trusted() raises ApprovalDeniedError for NEVER_ALLOW pattern (e.g. rm -rf /)."""
        with pytest.raises(ApprovalDeniedError):
            await registry.is_trusted("rm -rf /")

    async def test_get_trust_level_raises_approval_denied_error_for_blocked_pattern(self, registry):
        """Test get_trust_level() raises ApprovalDeniedError for a blocked pattern."""
        with pytest.raises(ApprovalDeniedError):
            await registry.get_trust_level("rm -rf /")

    async def test_trace_event_emitted_on_set_trust(self, registry, emitter):
        """Test trace event emitted on set_trust()."""
        await registry.set_trust("test command", TrustLevel.SESSION_TRUST, scope="session")
        events = emitter.get_events()
        trust_granted_events = [e for e in events if e.event_type == TraceEventType.TRUST_GRANTED]
        assert len(trust_granted_events) > 0
        assert trust_granted_events[0].data["command"] == "test command"
        assert trust_granted_events[0].data["level"] == TrustLevel.SESSION_TRUST

    async def test_trace_event_emitted_on_revoke_trust(self, registry, emitter):
        """Test trace event emitted on revoke_trust()."""
        await registry.set_trust("test command", TrustLevel.SESSION_TRUST, scope="session")
        await registry.revoke_trust("test command")
        events = emitter.get_events()
        trust_revoked_events = [e for e in events if e.event_type == TraceEventType.TRUST_REVOKED]
        assert len(trust_revoked_events) > 0
        assert trust_revoked_events[0].data["command"] == "test command"

    async def test_trace_event_emitted_on_never_allow_block(self, registry, emitter):
        """Test trace event emitted when command matches NEVER_ALLOW pattern."""
        with pytest.raises(ApprovalDeniedError):
            await registry.get_trust_level("rm -rf /")
        events = emitter.get_events()
        trust_blocked_events = [e for e in events if e.event_type == TraceEventType.TRUST_BLOCKED]
        assert len(trust_blocked_events) > 0
        assert trust_blocked_events[0].data["command"] == "rm -rf /"
        assert "rm -rf /" in trust_blocked_events[0].data["pattern"]
