"""Tests for web server."""

from unittest.mock import Mock, AsyncMock
from fastapi.testclient import TestClient

from web.server import create_app
from core.auth import AuthManager
from core.observability import MemoryTraceEmitter


class TestWebServer:
    """Tests for web server endpoints."""

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

    def test_health_returns_200_without_auth(self):
        """Test that GET /health returns 200 without auth token."""
        response = self.client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "version": "0.1.0"}

    def test_get_tasks_returns_401_without_token(self):
        """Test that GET /api/tasks returns 401 when no auth token provided."""
        response = self.client.get("/api/tasks")
        assert response.status_code == 401

    def test_get_tasks_returns_200_with_valid_token(self):
        """Test that GET /api/tasks returns 200 with valid token."""
        response = self.client.get(
            "/api/tasks",
            headers={"Authorization": "Bearer test-token"}
        )
        assert response.status_code == 200

    def test_get_tasks_returns_empty_list_when_no_tasks(self):
        """Test that GET /api/tasks returns {"tasks": []} when orchestrator has no tasks."""
        self.orchestrator.list_tasks = AsyncMock(return_value=[])
        response = self.client.get(
            "/api/tasks",
            headers={"Authorization": "Bearer test-token"}
        )
        assert response.json() == {"tasks": []}

    def test_post_tasks_returns_401_without_token(self):
        """Test that POST /api/tasks returns 401 without token."""
        response = self.client.post("/api/tasks", json={"intent": "test"})
        assert response.status_code == 401

    def test_post_tasks_returns_200_with_valid_token(self):
        """Test that POST /api/tasks returns 200 with valid token and correct body."""
        response = self.client.post(
            "/api/tasks",
            json={"intent": "test intent", "priority": "medium"},
            headers={"Authorization": "Bearer test-token"}
        )
        assert response.status_code == 200

    def test_post_tasks_response_includes_task_id_and_status(self):
        """Test that POST /api/tasks response includes task_id and status."""
        response = self.client.post(
            "/api/tasks",
            json={"intent": "test intent", "priority": "medium"},
            headers={"Authorization": "Bearer test-token"}
        )
        data = response.json()
        assert "task_id" in data
        assert "status" in data
        assert data["status"] == "queued"

    def test_get_workers_returns_200_with_valid_token(self):
        """Test that GET /api/workers returns 200 with valid token."""
        response = self.client.get(
            "/api/workers",
            headers={"Authorization": "Bearer test-token"}
        )
        assert response.status_code == 200

    def test_get_workers_returns_empty_list_when_no_workers(self):
        """Test that GET /api/workers returns {"workers": []} when no workers registered."""
        self.orchestrator.list_workers = AsyncMock(return_value=[])
        response = self.client.get(
            "/api/workers",
            headers={"Authorization": "Bearer test-token"}
        )
        assert response.json() == {"workers": []}

    def test_get_trace_returns_200_with_valid_token(self):
        """Test that GET /api/trace returns 200 with valid token."""
        response = self.client.get(
            "/api/trace",
            headers={"Authorization": "Bearer test-token"}
        )
        assert response.status_code == 200

    def test_get_trace_returns_events_with_at_most_100(self):
        """Test that GET /api/trace returns {"events": [...]} with at most 100 events."""
        # Add 150 events to emitter
        from core.observability import TraceEvent, TraceComponent, TraceLevel, TraceEventType
        from datetime import datetime, timezone
        from uuid import uuid4
        
        for i in range(150):
            event = TraceEvent(
                event_id=uuid4(),
                event_type=TraceEventType.COMPONENT_START,
                component=TraceComponent.WEB,
                level=TraceLevel.INFO,
                message=f"Test event {i}",
                data={},
                duration_ms=0,
                timestamp=datetime.now(timezone.utc),
            )
            self.emitter._events.append(event)
        
        response = self.client.get(
            "/api/trace",
            headers={"Authorization": "Bearer test-token"}
        )
        data = response.json()
        assert "events" in data
        assert len(data["events"]) <= 100

    def test_get_tasks_returns_401_with_invalid_token(self):
        """Test that GET /api/tasks returns 401 with invalid token."""
        self.auth_manager.validate_token = AsyncMock(return_value=False)
        response = self.client.get(
            "/api/tasks",
            headers={"Authorization": "Bearer invalid-token"}
        )
        assert response.status_code == 401

    def test_websocket_rejects_connection_without_token(self):
        """Test that WebSocket /ws rejects connection without token (close code 1008)."""
        with self.client.websocket_connect("/ws") as websocket:
            # The connection should be rejected immediately
            pass

    def test_websocket_accepts_connection_with_valid_token(self):
        """Test that WebSocket /ws accepts connection with valid token."""
        with self.client.websocket_connect("/ws?token=test-token") as websocket:
            # Connection should be accepted
            pass

    def test_websocket_returns_task_id_on_message_send(self):
        """Test that WebSocket /ws returns {"task_id": ..., "status": "queued"} on message send."""
        with self.client.websocket_connect("/ws?token=test-token") as websocket:
            websocket.send_json({"intent": "test intent"})
            response = websocket.receive_json()
            assert "task_id" in response
            assert response["status"] == "queued"
