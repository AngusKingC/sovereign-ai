"""Tests for security components: AuthManager, InputSanitiser, AuthMiddleware, SecretsAudit."""

import pytest

from core.auth import AuthManager
from core.input_sanitiser import InputSanitiser
from core.observability import (
    TraceEventType,
    MemoryTraceEmitter,
)
from web.middleware.auth_middleware import AuthMiddleware, SecretsAudit


pytestmark = pytest.mark.asyncio


@pytest.mark.asyncio
class TestAuthManager:
    """Tests for AuthManager class."""

    async def test_get_or_create_token_generates_token_and_writes_to_env_when_not_present(self, tmp_path):
        """Test that get_or_create_token generates token and writes to .env when not present."""
        env_path = tmp_path / ".env"
        emitter = MemoryTraceEmitter()
        manager = AuthManager(env_path=str(env_path), emitter=emitter)

        token = await manager.get_or_create_token()

        assert token is not None
        assert len(token) > 0
        assert env_path.exists()
        content = env_path.read_text()
        assert "JARVIS_AUTH_TOKEN" in content
        assert token in content

    async def test_get_or_create_token_loads_existing_token_from_env_when_present(self, tmp_path):
        """Test that get_or_create_token loads existing token from .env when present."""
        env_path = tmp_path / ".env"
        existing_token = "existing_test_token_12345"
        env_path.write_text(f"JARVIS_AUTH_TOKEN={existing_token}")
        emitter = MemoryTraceEmitter()
        manager = AuthManager(env_path=str(env_path), emitter=emitter)

        token = await manager.get_or_create_token()

        assert token == existing_token

    async def test_get_or_create_token_emits_warning_trace_event_when_generating_new_token(self, tmp_path):
        """Test that get_or_create_token emits WARNING trace event when generating new token."""
        env_path = tmp_path / ".env"
        emitter = MemoryTraceEmitter()
        manager = AuthManager(env_path=str(env_path), emitter=emitter)

        await manager.get_or_create_token()

        events = emitter.get_events()
        assert len(events) == 1
        assert events[0].event_type == TraceEventType.AUTH_TOKEN_CREATED
        assert events[0].level == "warning"

    async def test_get_or_create_token_emits_info_trace_event_when_loading_existing_token(self, tmp_path):
        """Test that get_or_create_token emits INFO trace event when loading existing token."""
        env_path = tmp_path / ".env"
        existing_token = "existing_test_token_12345"
        env_path.write_text(f"JARVIS_AUTH_TOKEN={existing_token}")
        emitter = MemoryTraceEmitter()
        manager = AuthManager(env_path=str(env_path), emitter=emitter)

        await manager.get_or_create_token()

        events = emitter.get_events()
        assert len(events) == 1
        assert events[0].event_type == TraceEventType.AUTH_TOKEN_LOADED
        assert events[0].level == "info"

    async def test_get_or_create_token_never_includes_token_value_in_trace_event_data(self, tmp_path):
        """Test that get_or_create_token never includes token value in trace event data."""
        env_path = tmp_path / ".env"
        emitter = MemoryTraceEmitter()
        manager = AuthManager(env_path=str(env_path), emitter=emitter)

        await manager.get_or_create_token()

        events = emitter.get_events()
        assert len(events) == 1
        assert "token" not in events[0].data
        assert events[0].data.get("token_present") is True

    async def test_validate_token_returns_true_for_correct_token(self, tmp_path):
        """Test that validate_token returns True for correct token."""
        env_path = tmp_path / ".env"
        existing_token = "test_token_12345"
        env_path.write_text(f"JARVIS_AUTH_TOKEN={existing_token}")
        emitter = MemoryTraceEmitter()
        manager = AuthManager(env_path=str(env_path), emitter=emitter)

        is_valid = await manager.validate_token(existing_token)

        assert is_valid is True

    async def test_validate_token_returns_false_for_incorrect_token(self, tmp_path):
        """Test that validate_token returns False for incorrect token."""
        env_path = tmp_path / ".env"
        existing_token = "test_token_12345"
        env_path.write_text(f"JARVIS_AUTH_TOKEN={existing_token}")
        emitter = MemoryTraceEmitter()
        manager = AuthManager(env_path=str(env_path), emitter=emitter)

        is_valid = await manager.validate_token("wrong_token")

        assert is_valid is False

    async def test_validate_token_uses_timing_safe_comparison(self, tmp_path, monkeypatch):
        """Test that validate_token uses timing-safe comparison (calls secrets.compare_digest)."""
        env_path = tmp_path / ".env"
        existing_token = "test_token_12345"
        env_path.write_text(f"JARVIS_AUTH_TOKEN={existing_token}")
        emitter = MemoryTraceEmitter()
        manager = AuthManager(env_path=str(env_path), emitter=emitter)

        import secrets
        calls = []
        
        def mock_compare_digest(a, b):
            calls.append((a, b))
            return True
        
        monkeypatch.setattr(secrets, "compare_digest", mock_compare_digest)

        await manager.validate_token(existing_token)

        # Verify the mock was called with the expected arguments
        assert len(calls) == 1
        assert calls[0][0] == existing_token

    async def test_rotate_token_generates_new_token_and_invalidates_old_one(self, tmp_path):
        """Test that rotate_token generates new token and invalidates old one."""
        env_path = tmp_path / ".env"
        existing_token = "old_token_12345"
        env_path.write_text(f"JARVIS_AUTH_TOKEN={existing_token}")
        emitter = MemoryTraceEmitter()
        manager = AuthManager(env_path=str(env_path), emitter=emitter)

        new_token = await manager.rotate_token()

        assert new_token != existing_token
        # Old token should no longer be valid
        is_valid = await manager.validate_token(existing_token)
        assert is_valid is False
        # New token should be valid
        is_valid = await manager.validate_token(new_token)
        assert is_valid is True

    async def test_rotate_token_emits_warning_trace_event(self, tmp_path):
        """Test that rotate_token emits WARNING trace event."""
        env_path = tmp_path / ".env"
        existing_token = "old_token_12345"
        env_path.write_text(f"JARVIS_AUTH_TOKEN={existing_token}")
        emitter = MemoryTraceEmitter()
        manager = AuthManager(env_path=str(env_path), emitter=emitter)

        await manager.rotate_token()

        events = emitter.get_events()
        assert len(events) == 1
        assert events[0].event_type == TraceEventType.AUTH_TOKEN_ROTATED
        assert events[0].level == "warning"


@pytest.mark.asyncio
class TestInputSanitiser:
    """Tests for InputSanitiser class."""

    async def test_sanitise_returns_text_unchanged_when_no_blocked_patterns_present(self):
        """Test that sanitise returns text unchanged when no blocked patterns present."""
        emitter = MemoryTraceEmitter()
        sanitiser = InputSanitiser(emitter=emitter)

        text = "This is clean text with no injection patterns"
        result = await sanitiser.sanitise(text)

        assert result == text
        events = emitter.get_events()
        assert len(events) == 0

    async def test_sanitise_replaces_triple_backtick_with_blocked(self):
        """Test that sanitise replaces triple backtick with [BLOCKED]."""
        emitter = MemoryTraceEmitter()
        sanitiser = InputSanitiser(emitter=emitter)

        text = "Some text ``` with code blocks"
        result = await sanitiser.sanitise(text)

        assert "[BLOCKED]" in result
        assert chr(96) + chr(96) + chr(96) not in result

    async def test_sanitise_replaces_ignore_previous_instructions_with_blocked(self):
        """Test that sanitise replaces IGNORE PREVIOUS INSTRUCTIONS with [BLOCKED]."""
        emitter = MemoryTraceEmitter()
        sanitiser = InputSanitiser(emitter=emitter)

        text = "Some text IGNORE PREVIOUS INSTRUCTIONS with injection"
        result = await sanitiser.sanitise(text)

        assert "[BLOCKED]" in result
        assert "IGNORE PREVIOUS INSTRUCTIONS" not in result

    async def test_sanitise_emits_warning_trace_event_when_pattern_found(self):
        """Test that sanitise emits WARNING trace event when pattern found."""
        emitter = MemoryTraceEmitter()
        sanitiser = InputSanitiser(emitter=emitter)

        text = "Some text IGNORE PREVIOUS INSTRUCTIONS with injection"
        await sanitiser.sanitise(text)

        events = emitter.get_events()
        assert len(events) == 1
        assert events[0].event_type == TraceEventType.INPUT_SANITISED
        assert events[0].level == "warning"

    async def test_sanitise_includes_matched_patterns_in_trace_event_data(self):
        """Test that sanitise includes matched patterns in trace event data."""
        emitter = MemoryTraceEmitter()
        sanitiser = InputSanitiser(emitter=emitter)

        text = "Some text IGNORE PREVIOUS INSTRUCTIONS with injection"
        await sanitiser.sanitise(text)

        events = emitter.get_events()
        assert len(events) == 1
        assert "matched_patterns" in events[0].data
        assert len(events[0].data["matched_patterns"]) > 0

    async def test_is_clean_returns_true_when_no_blocked_patterns(self):
        """Test that is_clean returns True when no blocked patterns."""
        emitter = MemoryTraceEmitter()
        sanitiser = InputSanitiser(emitter=emitter)

        text = "This is clean text with no injection patterns"
        result = await sanitiser.is_clean(text)

        assert result is True

    async def test_is_clean_returns_false_when_blocked_pattern_present(self):
        """Test that is_clean returns False when blocked pattern present."""
        emitter = MemoryTraceEmitter()
        sanitiser = InputSanitiser(emitter=emitter)

        text = "Some text IGNORE PREVIOUS INSTRUCTIONS with injection"
        result = await sanitiser.is_clean(text)

        assert result is False


@pytest.mark.asyncio
class TestAuthMiddleware:
    """Tests for AuthMiddleware class."""

    async def test_dispatch_returns_401_when_authorization_header_missing(self, tmp_path):
        """Test that dispatch returns 401 when Authorization header missing."""
        env_path = tmp_path / ".env"
        existing_token = "test_token_12345"
        env_path.write_text(f"JARVIS_AUTH_TOKEN={existing_token}")
        emitter = MemoryTraceEmitter()
        auth_manager = AuthManager(env_path=str(env_path), emitter=emitter)

        from starlette.requests import Request
        from starlette.applications import Starlette

        app = Starlette()
        middleware = AuthMiddleware(app, auth_manager)

        # Create mock request without Authorization header
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/test",
            "headers": [],
            "query_string": b"",
        }
        request = Request(scope)

        response = await middleware.dispatch(request, lambda req: None)

        assert response.status_code == 401

    async def test_dispatch_returns_401_when_token_invalid(self, tmp_path):
        """Test that dispatch returns 401 when token invalid."""
        env_path = tmp_path / ".env"
        existing_token = "test_token_12345"
        env_path.write_text(f"JARVIS_AUTH_TOKEN={existing_token}")
        emitter = MemoryTraceEmitter()
        auth_manager = AuthManager(env_path=str(env_path), emitter=emitter)

        from starlette.requests import Request
        from starlette.applications import Starlette

        app = Starlette()
        middleware = AuthMiddleware(app, auth_manager)

        # Create mock request with invalid token
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/test",
            "headers": [(b"authorization", b"Bearer wrong_token")],
            "query_string": b"",
        }
        request = Request(scope)

        response = await middleware.dispatch(request, lambda req: None)

        assert response.status_code == 401

    async def test_dispatch_calls_call_next_when_token_valid(self, tmp_path):
        """Test that dispatch calls call_next when token valid."""
        env_path = tmp_path / ".env"
        existing_token = "test_token_12345"
        env_path.write_text(f"JARVIS_AUTH_TOKEN={existing_token}")
        emitter = MemoryTraceEmitter()
        auth_manager = AuthManager(env_path=str(env_path), emitter=emitter)

        from starlette.requests import Request
        from starlette.applications import Starlette
        from starlette.responses import Response

        app = Starlette()
        middleware = AuthMiddleware(app, auth_manager)

        # Create mock request with valid token
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/test",
            "headers": [(b"authorization", f"Bearer {existing_token}".encode())],
            "query_string": b"",
        }
        request = Request(scope)

        call_next_called = False

        async def mock_call_next(req):
            nonlocal call_next_called
            call_next_called = True
            return Response()

        await middleware.dispatch(request, mock_call_next)

        assert call_next_called is True

    async def test_health_path_exempt_from_auth_returns_200_without_token(self, tmp_path):
        """Test that /health path exempt from auth returns 200 without token."""
        env_path = tmp_path / ".env"
        existing_token = "test_token_12345"
        env_path.write_text(f"JARVIS_AUTH_TOKEN={existing_token}")
        emitter = MemoryTraceEmitter()
        auth_manager = AuthManager(env_path=str(env_path), emitter=emitter)

        from starlette.requests import Request
        from starlette.applications import Starlette
        from starlette.responses import Response

        app = Starlette()
        middleware = AuthMiddleware(app, auth_manager)

        # Create mock request to /health without token
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/health",
            "headers": [],
            "query_string": b"",
        }
        request = Request(scope)

        call_next_called = False

        async def mock_call_next(req):
            nonlocal call_next_called
            call_next_called = True
            return Response()

        await middleware.dispatch(request, mock_call_next)

        assert call_next_called is True


@pytest.mark.asyncio
class TestSecretsAudit:
    """Tests for SecretsAudit class."""

    async def test_audit_returns_empty_list_when_config_has_no_secret_keys(self, tmp_path):
        """Test that audit returns empty list when config has no secret keys."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("normal_setting: value\nanother_setting: value2")
        emitter = MemoryTraceEmitter()
        audit = SecretsAudit(config_path=str(config_path), emitter=emitter)

        result = await audit.audit()

        assert result == []

    async def test_audit_returns_offending_key_names_when_secrets_found_in_config(self, tmp_path):
        """Test that audit returns offending key names when secrets found in config."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("normal_key: value\napi_key: secret123\nanother_key: value2")
        emitter = MemoryTraceEmitter()
        audit = SecretsAudit(config_path=str(config_path), emitter=emitter)

        result = await audit.audit()

        assert len(result) > 0
        assert "api_key" in result

    async def test_audit_emits_warning_trace_event_for_each_secret_found(self, tmp_path):
        """Test that audit emits WARNING trace event for each secret found."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("normal_key: value\napi_key: secret123\nanother_key: value2")
        emitter = MemoryTraceEmitter()
        audit = SecretsAudit(config_path=str(config_path), emitter=emitter)

        await audit.audit()

        events = emitter.get_events()
        assert len(events) > 0
        assert events[0].event_type == TraceEventType.SECRETS_AUDIT_WARNING
        assert events[0].level == "warning"

    async def test_audit_returns_empty_list_when_config_file_not_found(self, tmp_path):
        """Test that audit returns empty list when config file not found."""
        config_path = tmp_path / "nonexistent.yaml"
        emitter = MemoryTraceEmitter()
        audit = SecretsAudit(config_path=str(config_path), emitter=emitter)

        result = await audit.audit()

        assert result == []
