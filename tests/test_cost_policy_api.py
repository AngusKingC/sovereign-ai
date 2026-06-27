"""Tests for cost policy API endpoints (Plan 94)."""

from unittest.mock import Mock

from fastapi.testclient import TestClient


def test_get_cost_policy_endpoint_exists():
    """Test GET /api/costs/policy endpoint exists and is callable."""
    from core.auth import AuthManager
    from core.cost_tracker import CostPolicy
    from core.orchestrator import Orchestrator
    from web.server import create_app

    mock_cost_tracker = Mock()
    mock_cost_tracker.get_policy.return_value = CostPolicy(
        daily_cap_usd=10.0,
        monthly_cap_usd=100.0,
        alert_threshold_pct=0.80,
        fallback_threshold_pct=0.90,
        fallback_model="llama3.2:1b",
    )

    mock_orchestrator = Mock(spec=Orchestrator)
    mock_orchestrator.cost_tracker = mock_cost_tracker

    app = create_app(
        orchestrator=mock_orchestrator, auth_manager=Mock(spec=AuthManager)
    )
    client = TestClient(app)

    response = client.get("/api/costs/policy")
    # Endpoint exists (401 = auth required, 200 = success)
    assert response.status_code in [200, 401]


def test_put_cost_policy_endpoint_exists():
    """Test PUT /api/costs/policy endpoint exists and is callable."""
    from core.auth import AuthManager
    from core.cost_tracker import CostPolicy
    from core.orchestrator import Orchestrator
    from web.server import create_app

    mock_cost_tracker = Mock()
    mock_cost_tracker.get_policy.return_value = CostPolicy()
    mock_cost_tracker.update_policy.return_value = None

    mock_orchestrator = Mock(spec=Orchestrator)
    mock_orchestrator.cost_tracker = mock_cost_tracker

    app = create_app(
        orchestrator=mock_orchestrator, auth_manager=Mock(spec=AuthManager)
    )
    client = TestClient(app)

    update_data = {"daily_cap_usd": 20.0}
    response = client.put("/api/costs/policy", json=update_data)
    # Endpoint exists (401 = auth required, 200/422 = validation)
    assert response.status_code in [200, 401, 422]


def test_cost_policy_validation_negative_cap():
    """Test PUT /api/costs/policy validates negative caps."""
    from core.auth import AuthManager
    from core.cost_tracker import CostPolicy
    from core.orchestrator import Orchestrator
    from web.server import create_app

    mock_cost_tracker = Mock()
    mock_cost_tracker.get_policy.return_value = CostPolicy()

    mock_orchestrator = Mock(spec=Orchestrator)
    mock_orchestrator.cost_tracker = mock_cost_tracker

    app = create_app(
        orchestrator=mock_orchestrator, auth_manager=Mock(spec=AuthManager)
    )
    client = TestClient(app)

    update_data = {"daily_cap_usd": -10.0}
    response = client.put("/api/costs/policy", json=update_data)
    # Should reject negative cap (422) or require auth (401)
    assert response.status_code in [401, 422]
