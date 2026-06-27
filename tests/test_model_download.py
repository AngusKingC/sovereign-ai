"""Tests for model download endpoints (Plan 92)."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient

from core.auth import AuthManager
from core.observability import MemoryTraceEmitter
from core.schemas import DownloadStatus
from system.model_acquisition import ModelAcquisition


@pytest.fixture
def mock_orchestrator():
    """Mock orchestrator with required dependencies."""
    orchestrator = Mock()
    orchestrator.model_registry = Mock()
    orchestrator.model_acquisition = Mock(spec=ModelAcquisition)
    orchestrator.approval_gate = Mock()
    orchestrator.resource_manager = Mock()
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


def test_download_model_already_downloaded(client, mock_orchestrator):
    """Test download endpoint when model is already downloaded."""
    mock_entry = Mock()
    mock_entry.download_status = DownloadStatus.DOWNLOADED
    mock_orchestrator.model_registry.get = AsyncMock(return_value=mock_entry)

    response = client.post(
        "/api/models/download?model_id=test-model",
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "already_downloaded"
    assert data["model_id"] == "test-model"


def test_download_model_initiates_download(client, mock_orchestrator):
    """Test download endpoint initiates download and returns download_id."""
    mock_entry = Mock()
    mock_entry.download_status = DownloadStatus.NOT_DOWNLOADED
    mock_entry.quantisation_variants = []
    mock_orchestrator.model_registry.get = AsyncMock(return_value=mock_entry)
    mock_orchestrator.model_acquisition.request_download = AsyncMock(
        return_value=Mock(success=True)
    )
    mock_orchestrator.model_acquisition._in_flight_downloads = {}

    mock_approval_response = Mock()
    mock_approval_response.approved = True
    mock_orchestrator.approval_gate.request_approval = AsyncMock(
        return_value=mock_approval_response
    )

    response = client.post(
        "/api/models/download?model_id=test-model&quantisation=q4_0",
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "download_id" in data
    assert data["status"] == "initiated"
    # Verify download_id format (dl- followed by 8 hex chars)
    assert data["download_id"].startswith("dl-")
    assert len(data["download_id"]) == 11  # "dl-" + 8 chars


def test_download_model_requires_approval(client, mock_orchestrator):
    """Test download endpoint requires approval for large downloads."""
    mock_entry = Mock()
    mock_entry.download_status = DownloadStatus.NOT_DOWNLOADED
    mock_entry.quantisation_variants = [Mock(size_bytes=2_000_000_000)]  # 2GB
    mock_orchestrator.model_registry.get = AsyncMock(return_value=mock_entry)

    mock_approval_response = Mock()
    mock_approval_response.approved = False
    mock_orchestrator.approval_gate.request_approval = AsyncMock(
        return_value=mock_approval_response
    )

    response = client.post(
        "/api/models/download?model_id=test-model",
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "approval_required"
    assert "request_id" in data


def test_get_download_status(client, mock_orchestrator):
    """Test get download status endpoint."""
    mock_status = {
        "download_id": "dl-abc123",
        "model_id": "test-model",
        "status": "downloading",
        "progress_pct": 45.0,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "error": None,
    }
    mock_orchestrator.model_acquisition.get_download_status = AsyncMock(
        return_value=mock_status
    )

    response = client.get(
        "/api/models/download/dl-abc123/status",
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["download_id"] == "dl-abc123"
    assert data["status"] == "downloading"
    assert data["progress_pct"] == 45.0


def test_get_download_status_not_found(client, mock_orchestrator):
    """Test get download status returns 404 for unknown download_id."""
    mock_orchestrator.model_acquisition.get_download_status = AsyncMock(
        return_value=None
    )

    response = client.get(
        "/api/models/download/unknown-id/status",
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 404
