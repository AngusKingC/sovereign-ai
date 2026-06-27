"""Tests for fallback chain endpoints (Plan 92)."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from core.auth import AuthManager
from core.observability import MemoryTraceEmitter


@pytest.fixture
def mock_orchestrator():
    """Mock orchestrator with fallback_chain."""
    orchestrator = Mock()
    orchestrator.fallback_chain = []
    return orchestrator


@pytest.fixture
def client(mock_orchestrator):
    """Test client with mocked orchestrator and auth."""
    from web.server import create_app

    auth_manager = Mock(spec=AuthManager)
    auth_manager.validate_token = AsyncMock(return_value=True)
    emitter = MemoryTraceEmitter()

    app = create_app(mock_orchestrator, auth_manager, emitter)
    return TestClient(app)


def test_get_fallback_chain_empty(client, mock_orchestrator):
    """Test get fallback chain returns empty list when not configured."""
    response = client.get(
        "/api/adapters/fallback", headers={"Authorization": "Bearer test-token"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["chain"] == []


def test_get_fallback_chain_with_adapters(client, mock_orchestrator):
    """Test get fallback chain returns configured adapters."""
    mock_adapter1 = Mock()
    mock_adapter1.model_name = "ollama"
    mock_adapter2 = Mock()
    mock_adapter2.model_name = "openai"
    mock_orchestrator.fallback_chain = [mock_adapter1, mock_adapter2]

    response = client.get(
        "/api/adapters/fallback", headers={"Authorization": "Bearer test-token"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["chain"] == ["ollama", "openai"]


def test_set_fallback_chain(client, mock_orchestrator):
    """Test set fallback chain resolves adapter names."""
    with patch("cli.adapter_factory.create_adapter") as mock_create:
        mock_adapter = Mock()
        mock_adapter.model_name = "ollama"
        mock_create.return_value = mock_adapter

        response = client.put(
            "/api/adapters/fallback",
            json={"chain": ["ollama", "openai"]},
            headers={"Authorization": "Bearer test-token"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["chain"] == ["ollama", "openai"]
        assert data["resolved_count"] == 2
        assert mock_orchestrator.fallback_chain is not None


def test_set_fallback_chain_invalid_adapter(client, mock_orchestrator):
    """Test set fallback chain returns 400 for invalid adapter."""
    with patch("cli.adapter_factory.create_adapter") as mock_create:
        mock_create.side_effect = Exception("Unknown adapter")

        response = client.put(
            "/api/adapters/fallback",
            json={"chain": ["invalid-adapter"]},
            headers={"Authorization": "Bearer test-token"},
        )
        assert response.status_code == 400
        assert "Failed to create adapter" in response.json()["detail"]


def test_get_available_adapters(client):
    """Test get available adapters returns list of adapter types."""
    with patch("cli.adapter_factory.ADAPTER_TYPES", ["ollama", "openai", "anthropic"]):
        response = client.get(
            "/api/adapters/available", headers={"Authorization": "Bearer test-token"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "adapters" in data
        assert len(data["adapters"]) > 0
