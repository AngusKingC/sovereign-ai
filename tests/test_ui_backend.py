from fastapi.testclient import TestClient

from core.auth import AuthManager
from core.observability import MemoryTraceEmitter

# Import from web/server instead of deleted backend/main
from web.server import create_app

# Create test app
auth_manager = AuthManager()
emitter = MemoryTraceEmitter()
app = create_app(orchestrator=None, auth_manager=auth_manager, emitter=emitter)

client = TestClient(app)


def get_test_token():
    """Generate a valid test token synchronously."""
    import asyncio

    return asyncio.run(auth_manager.get_or_create_token())


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_status_unauthorized():
    response = client.get("/api/status")
    assert response.status_code == 401


def test_status_authorized():
    token = get_test_token()
    response = client.get("/api/status", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert "phase" in data
    assert "uptime" in data


def test_subagents_authorized():
    token = get_test_token()
    response = client.get(
        "/api/subagents", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "subagents" in data
    assert isinstance(data["subagents"], list)


def test_get_costs_summary():
    token = get_test_token()
    res = client.get("/api/costs/summary", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert "daily_spend" in data
    assert "daily_cap" in data


def test_get_costs_daily():
    token = get_test_token()
    res = client.get("/api/costs/daily", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert "total_usd" in res.json()


def test_get_circuit_breaker_status():
    token = get_test_token()
    res = client.get(
        "/api/circuit-breaker/status", headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert "workers" in data
    assert "degraded_ratio" in data


def test_post_circuit_breaker_reset():
    token = get_test_token()
    res = client.post(
        "/api/circuit-breaker/reset",
        json={"worker_id": "test_worker"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    # Stub returns "not_implemented" per Rev5 L-B fix
    assert res.json()["status"] == "not_implemented"


def test_get_approvals_pending():
    token = get_test_token()
    res = client.get(
        "/api/approvals/pending", headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_post_approvals_respond():
    token = get_test_token()
    res = client.post(
        "/api/approvals/test-id/respond",
        json={"approved": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code in (200, 404)  # 404 if no pending approval exists


def test_get_memory_slots():
    token = get_test_token()
    res = client.get("/api/memory/slots", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_get_skills():
    token = get_test_token()
    res = client.get("/api/skills", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    if data:
        assert "name" in data[0]
        assert "tier" in data[0]


def test_get_system_stats():
    token = get_test_token()
    res = client.get("/api/system", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert "cpu_percent" in data
    assert "memory_percent" in data
