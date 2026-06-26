"""Tests for API stub endpoints created in Plan 90."""

from unittest.mock import AsyncMock, Mock

from fastapi.testclient import TestClient

from core.auth import AuthManager
from core.observability import MemoryTraceEmitter
from web.server import create_app


class TestApiStubs:
    """Tests for API stub endpoints."""

    def setup_method(self):
        """Set up test fixtures."""
        # Mock orchestrator
        self.orchestrator = Mock()
        self.orchestrator.list_tasks = AsyncMock(return_value=[])
        self.orchestrator.list_workers = AsyncMock(return_value=[])
        self.orchestrator.submit_task = AsyncMock(return_value="test-task-id")

        # Mock auth manager
        self.auth_manager = Mock(spec=AuthManager)
        self.auth_manager.validate_token = AsyncMock(return_value=True)

        # Mock emitter
        self.emitter = MemoryTraceEmitter()

        # Create app
        self.app = create_app(self.orchestrator, self.auth_manager, self.emitter)
        self.client = TestClient(self.app)

    def test_list_models_stub(self):
        """Test /api/models returns empty list (stub)."""
        res = self.client.get(
            "/api/models", headers={"Authorization": "Bearer test-token"}
        )
        assert res.status_code == 200
        assert res.json() == []

    def test_get_model_stub_404(self):
        """Test /api/models/{id} returns 404 (stub)."""
        res = self.client.get(
            "/api/models/nonexistent", headers={"Authorization": "Bearer test-token"}
        )
        assert res.status_code == 404
        assert "not found" in res.json()["detail"].lower()

    def test_search_models_stub(self):
        """Test /api/models/search returns empty list (stub)."""
        res = self.client.get(
            "/api/models/search?query=test",
            headers={"Authorization": "Bearer test-token"},
        )
        assert res.status_code == 200
        assert res.json() == []

    def test_create_worker_stub_501(self):
        """Test /api/workers/create returns 501 (stub)."""
        res = self.client.post(
            "/api/workers/create?description=test",
            headers={"Authorization": "Bearer test-token"},
        )
        assert res.status_code == 501
        assert "not yet implemented" in res.json()["detail"].lower()

    def test_update_worker_stub_501(self):
        """Test /api/workers/{id} PUT returns 501 (stub)."""
        res = self.client.put(
            "/api/workers/test-id",
            json={},
            headers={"Authorization": "Bearer test-token"},
        )
        assert res.status_code == 501
        assert "not yet implemented" in res.json()["detail"].lower()

    def test_delete_worker_stub_501(self):
        """Test /api/workers/{id} DELETE returns 501 (stub)."""
        res = self.client.delete(
            "/api/workers/test-id", headers={"Authorization": "Bearer test-token"}
        )
        assert res.status_code == 501
        assert "not yet implemented" in res.json()["detail"].lower()
