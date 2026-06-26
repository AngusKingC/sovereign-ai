import os

import pytest
from fastapi.testclient import TestClient

# Set env var before importing app
os.environ["SOVEREIGN_DEV_TOKEN"] = "dev-token-sovereign-ai-ui"

# Import the app from backend directory
import sys  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from main import app  # noqa: E402

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_status_unauthorized():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        client.get("/api/status")
    assert exc.value.status_code == 401


def test_status_authorized():
    response = client.get(
        "/api/status", headers={"Authorization": "Bearer dev-token-sovereign-ai-ui"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "sessionId" in data
    assert "phase" in data
    assert "uptime" in data


def test_login():
    response = client.post("/api/auth/login")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "sovereign_token" in response.cookies


def test_memory_slots_authorized():
    response = client.get(
        "/api/memory/slots",
        headers={"Authorization": "Bearer dev-token-sovereign-ai-ui"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 512


def test_subagents_authorized():
    response = client.get(
        "/api/subagents", headers={"Authorization": "Bearer dev-token-sovereign-ai-ui"}
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0
