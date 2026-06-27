"""Tests for worker API endpoints (Plan 93)."""

from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient

from core.schemas import WorkerStatus
from core.worker_factory import DynamicWorkerProfile
from web.server import create_app


@pytest.fixture
def mock_orchestrator():
    """Mock orchestrator with worker factory."""
    orchestrator = Mock()

    # Mock worker factory
    worker_factory = Mock()
    worker_factory.create_worker = AsyncMock(return_value=Mock())
    worker_factory.list_workers = AsyncMock(return_value=[])
    worker_factory.deregister_worker = AsyncMock()
    worker_factory.persistence = Mock()
    worker_factory.persistence.save = AsyncMock()

    orchestrator.worker_factory = worker_factory
    orchestrator.workers = {}

    return orchestrator


@pytest.fixture
def mock_auth_manager():
    """Mock auth manager."""
    auth_manager = Mock()
    auth_manager.validate_token = AsyncMock(return_value=True)
    return auth_manager


@pytest.fixture
def client(mock_orchestrator, mock_auth_manager):
    """Test client with mocked dependencies."""
    app = create_app(orchestrator=mock_orchestrator, auth_manager=mock_auth_manager)
    return TestClient(app)


@pytest.fixture
def sample_worker_profile():
    """Sample worker profile for testing."""
    return DynamicWorkerProfile(
        worker_id="test_worker",
        worker_type="code_worker",
        name="Test Worker",
        description="A test worker for code review",
        purpose="Code review and analysis",
        capabilities=["code", "review", "analysis"],
        complexity_min=0.3,
        complexity_max=0.8,
        preferred_complexity=0.5,
        depth_preference=0.6,
        speculation_tolerance=0.4,
        source_skepticism=0.5,
        verbosity=0.7,
        standing_instructions=["Be thorough", "Check security"],
        preferred_model="gpt-4",
        preferred_models=["gpt-4", "gpt-3.5-turbo"],
        escalation_threshold=0.8,
        tasks_completed=10,
        avg_confidence=0.85,
        performance_score=0.9,
        active_tasks=2,
        status=WorkerStatus.ACTIVE,
    )


def test_create_worker_from_description(
    client, mock_orchestrator, sample_worker_profile
):
    """Test creating a worker from natural language description."""
    # Mock the worker creation
    mock_worker = Mock()
    mock_worker.profile = sample_worker_profile
    mock_orchestrator.worker_factory.create_worker.return_value = mock_worker

    response = client.post(
        "/api/workers/create",
        json={
            "description": "Create a Python code review worker",
            "task_intent": "code review",
        },
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["worker_id"] == "test_worker"
    assert data["name"] == "Test Worker"
    assert data["worker_type"] == "code_worker"
    assert data["capabilities"] == ["code", "review", "analysis"]

    # Verify factory was called
    mock_orchestrator.worker_factory.create_worker.assert_called_once()


def test_list_workers(client, mock_orchestrator, sample_worker_profile):
    """Test listing all registered workers."""
    # Mock the worker list
    mock_orchestrator.worker_factory.list_workers.return_value = [sample_worker_profile]

    response = client.get(
        "/api/workers", headers={"Authorization": "Bearer test-token"}
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["worker_id"] == "test_worker"
    assert data[0]["name"] == "Test Worker"

    # Verify factory was called
    mock_orchestrator.worker_factory.list_workers.assert_called_once()


def test_get_worker_by_id(client, mock_orchestrator, sample_worker_profile):
    """Test getting a specific worker by ID."""
    # Mock the worker list
    mock_orchestrator.worker_factory.list_workers.return_value = [sample_worker_profile]

    response = client.get(
        "/api/workers/test_worker", headers={"Authorization": "Bearer test-token"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["worker_id"] == "test_worker"
    assert data["name"] == "Test Worker"


def test_get_worker_404_for_nonexistent(client, mock_orchestrator):
    """Test getting a worker that doesn't exist returns 404."""
    # Mock empty worker list
    mock_orchestrator.worker_factory.list_workers.return_value = []

    response = client.get(
        "/api/workers/nonexistent_worker",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_update_worker_config(client, mock_orchestrator, sample_worker_profile):
    """Test updating worker configuration."""
    # Mock the worker list
    mock_orchestrator.worker_factory.list_workers.return_value = [sample_worker_profile]

    response = client.put(
        "/api/workers/test_worker",
        json={"verbosity": 0.9, "preferred_model": "gpt-4-turbo"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["worker_id"] == "test_worker"
    # Note: The update modifies the profile in place, so we check the response


def test_delete_worker(client, mock_orchestrator, sample_worker_profile):
    """Test deleting/deregistering a worker."""
    # Mock the worker list
    mock_orchestrator.worker_factory.list_workers.return_value = [sample_worker_profile]
    mock_orchestrator.worker_factory.deregister_worker.return_value = None

    response = client.delete(
        "/api/workers/test_worker", headers={"Authorization": "Bearer test-token"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "deleted"
    assert data["worker_id"] == "test_worker"

    # Verify deregister was called
    mock_orchestrator.worker_factory.deregister_worker.assert_called_once_with(
        "test_worker"
    )
