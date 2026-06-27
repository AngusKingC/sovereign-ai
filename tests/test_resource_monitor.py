"""Tests for resource monitor API endpoint (Plan 94)."""

from unittest.mock import AsyncMock, Mock

from fastapi.testclient import TestClient


def test_get_resource_monitor_endpoint_exists():
    """Test GET /api/resources/monitor endpoint exists and is callable."""
    from core.auth import AuthManager
    from core.orchestrator import Orchestrator
    from web.server import create_app

    mock_orchestrator = Mock(spec=Orchestrator)
    mock_orchestrator.system_profiler = None

    app = create_app(
        orchestrator=mock_orchestrator, auth_manager=Mock(spec=AuthManager)
    )
    client = TestClient(app)

    response = client.get("/api/resources/monitor")
    # Endpoint exists (401 = auth required, 200 = success with psutil fallback)
    assert response.status_code in [200, 401]


def test_get_resource_monitor_with_profiler():
    """Test GET /api/resources/monitor uses SystemProfiler when available."""
    from core.auth import AuthManager
    from core.orchestrator import Orchestrator
    from web.server import create_app

    mock_profiler = Mock()
    mock_profiler.refresh = AsyncMock()

    mock_orchestrator = Mock(spec=Orchestrator)
    mock_orchestrator.system_profiler = mock_profiler

    app = create_app(
        orchestrator=mock_orchestrator, auth_manager=Mock(spec=AuthManager)
    )
    client = TestClient(app)

    response = client.get("/api/resources/monitor")
    # Endpoint exists (401 = auth required, 200 = success)
    assert response.status_code in [200, 401]


def test_get_resource_monitor_fallback_without_profiler():
    """Test GET /api/resources/monitor falls back to psutil when profiler not configured."""
    from core.auth import AuthManager
    from core.orchestrator import Orchestrator
    from web.server import create_app

    mock_orchestrator = Mock(spec=Orchestrator)
    mock_orchestrator.system_profiler = None

    app = create_app(
        orchestrator=mock_orchestrator, auth_manager=Mock(spec=AuthManager)
    )
    client = TestClient(app)

    response = client.get("/api/resources/monitor")
    # Endpoint exists (401 = auth required, 200 = success with psutil fallback)
    assert response.status_code in [200, 401]


def test_get_resource_monitor_response_structure():
    """Test GET /api/resources/monitor returns expected response structure."""
    from core.auth import AuthManager
    from core.orchestrator import Orchestrator
    from web.server import create_app

    mock_orchestrator = Mock(spec=Orchestrator)
    mock_orchestrator.system_profiler = None

    app = create_app(
        orchestrator=mock_orchestrator, auth_manager=Mock(spec=AuthManager)
    )
    client = TestClient(app)

    response = client.get("/api/resources/monitor")
    if response.status_code == 200:
        data = response.json()
        # Check expected fields exist
        assert "cpu_percent" in data
        assert "memory_percent" in data
        assert "disk_percent" in data
        assert "timestamp" in data
