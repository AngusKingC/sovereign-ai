"""HTTP client skill tests."""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from skills.http_client.skill import HttpClientSkill
from core.approval_gate import ApprovalGate
from core.observability import MemoryTraceEmitter, TraceEventType, TraceComponent


pytestmark = pytest.mark.asyncio


class TestHttpClientSkill:
    """Test HttpClientSkill functionality."""

    @pytest.fixture
    def http_client_skill(self):
        """Create an HTTP client skill for testing."""
        return HttpClientSkill(
            emitter=MemoryTraceEmitter(),
            approval_gate=None,
            timeout=30,
        )

    async def test_get_returns_correct_response_dict_no_approval(self, http_client_skill):
        """Test get() returns correct response dict, no approval required."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "response body"
        mock_response.headers = {"content-type": "application/json"}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("skills.http_client.skill.httpx.AsyncClient", return_value=mock_client):
            result = await http_client_skill.get("http://example.com")

        assert result["status_code"] == 200
        assert result["body"] == "response body"
        assert result["headers"]["content-type"] == "application/json"

    async def test_post_requires_approval_gate_returns_response(self):
        """Test post() requires approval gate, returns response."""
        mock_approval_gate = Mock(spec=ApprovalGate)
        mock_approval_gate.request_approval = AsyncMock(return_value=True)

        http_client_skill = HttpClientSkill(
            emitter=MemoryTraceEmitter(),
            approval_gate=mock_approval_gate,
            timeout=30,
        )

        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.text = "created"
        mock_response.headers = {}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("skills.http_client.skill.httpx.AsyncClient", return_value=mock_client):
            result = await http_client_skill.post("http://example.com", body={"key": "value"})

        assert result["status_code"] == 201
        assert result["body"] == "created"
        mock_approval_gate.request_approval.assert_called_once()

    async def test_post_denied_by_approval_gate_no_http_call(self):
        """Test post() denied by approval gate — no HTTP call made."""
        mock_approval_gate = Mock(spec=ApprovalGate)
        mock_approval_gate.request_approval = AsyncMock(return_value=False)

        http_client_skill = HttpClientSkill(
            emitter=MemoryTraceEmitter(),
            approval_gate=mock_approval_gate,
            timeout=30,
        )

        result = await http_client_skill.post("http://example.com", body={"key": "value"})

        assert result["status_code"] == 403
        assert "denied" in result["body"].lower()

    async def test_put_requires_approval(self):
        """Test put() requires approval."""
        mock_approval_gate = Mock(spec=ApprovalGate)
        mock_approval_gate.request_approval = AsyncMock(return_value=True)

        http_client_skill = HttpClientSkill(
            emitter=MemoryTraceEmitter(),
            approval_gate=mock_approval_gate,
            timeout=30,
        )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "updated"
        mock_response.headers = {}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.put = AsyncMock(return_value=mock_response)

        with patch("skills.http_client.skill.httpx.AsyncClient", return_value=mock_client):
            result = await http_client_skill.put("http://example.com", body={"key": "value"})

        assert result["status_code"] == 200
        mock_approval_gate.request_approval.assert_called_once()

    async def test_delete_requires_approval(self):
        """Test delete() requires approval."""
        mock_approval_gate = Mock(spec=ApprovalGate)
        mock_approval_gate.request_approval = AsyncMock(return_value=True)

        http_client_skill = HttpClientSkill(
            emitter=MemoryTraceEmitter(),
            approval_gate=mock_approval_gate,
            timeout=30,
        )

        mock_response = Mock()
        mock_response.status_code = 204
        mock_response.text = ""
        mock_response.headers = {}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.delete = AsyncMock(return_value=mock_response)

        with patch("skills.http_client.skill.httpx.AsyncClient", return_value=mock_client):
            result = await http_client_skill.delete("http://example.com")

        assert result["status_code"] == 204
        mock_approval_gate.request_approval.assert_called_once()

    async def test_get_with_params_and_headers_passed_correctly(self, http_client_skill):
        """Test get() with params and headers passed correctly to client."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "response"
        mock_response.headers = {}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("skills.http_client.skill.httpx.AsyncClient", return_value=mock_client):
            await http_client_skill.get(
                "http://example.com",
                params={"key": "value"},
                headers={"Authorization": "Bearer token"},
            )

        mock_client.get.assert_called_once()
        call_kwargs = mock_client.get.call_args[1]
        assert call_kwargs["params"] == {"key": "value"}
        assert call_kwargs["headers"] == {"Authorization": "Bearer token"}

    async def test_trace_event_emitted_with_method_and_url(self, http_client_skill):
        """Test trace event emitted with method and URL — verify enum values, confirm body not logged."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "response body"
        mock_response.headers = {}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("skills.http_client.skill.httpx.AsyncClient", return_value=mock_client):
            await http_client_skill.get("http://example.com")

        events = http_client_skill._emitter.get_events()
        assert len(events) > 0
        assert any(event.event_type == TraceEventType.HTTP_REQUEST for event in events)
        assert any(event.component == TraceComponent.HTTP_CLIENT_SKILL for event in events)

        # Verify body is not logged in trace data
        for event in events:
            if event.event_type == TraceEventType.HTTP_REQUEST:
                assert "body" not in event.data
                assert event.data.get("method") == "GET"
                assert event.data.get("url") == "http://example.com"

    async def test_http_error_status_code_handled(self, http_client_skill):
        """Test HTTP error status code (4xx/5xx) handled — returns dict with status_code, does not raise."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "not found"
        mock_response.headers = {}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("skills.http_client.skill.httpx.AsyncClient", return_value=mock_client):
            result = await http_client_skill.get("http://example.com")

        assert result["status_code"] == 404
        assert result["body"] == "not found"
