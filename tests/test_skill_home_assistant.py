"""Tests for Home Assistant Skill."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import os
import httpx

from skills.home_assistant.skill import HomeAssistantSkill
from core.approval_gate import ApprovalResponse
from core.observability import MemoryTraceEmitter
from core.exceptions import SkillExecutionError, ApprovalDeniedError


@pytest.mark.asyncio
class TestHomeAssistantSkill:
    """Tests for HomeAssistantSkill."""

    async def test_get_states_returns_list_of_entity_dicts(self) -> None:
        """Test that get_states returns list of entity dicts when HA responds."""
        # Set environment variables before creating skill
        os.environ["HA_BASE_URL"] = "http://localhost:8123"
        os.environ["HA_TOKEN"] = "test_token"

        emitter = MemoryTraceEmitter()
        skill = HomeAssistantSkill(emitter=emitter)

        mock_response = Mock()
        mock_response.json.return_value = [
            {"entity_id": "light.living_room", "state": "on"},
            {"entity_id": "switch.kitchen", "state": "off"},
        ]

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            states = await skill.get_states()

            assert len(states) == 2
            assert states[0]["entity_id"] == "light.living_room"
            assert states[1]["entity_id"] == "switch.kitchen"

        # Clean up
        del os.environ["HA_BASE_URL"]
        del os.environ["HA_TOKEN"]

    async def test_get_state_returns_correct_entity_dict(self) -> None:
        """Test that get_state returns correct entity dict for valid entity_id."""
        # Set environment variables before creating skill
        os.environ["HA_BASE_URL"] = "http://localhost:8123"
        os.environ["HA_TOKEN"] = "test_token"

        emitter = MemoryTraceEmitter()
        skill = HomeAssistantSkill(emitter=emitter)

        mock_response = Mock()
        mock_response.json.return_value = {"entity_id": "light.living_room", "state": "on"}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            state = await skill.get_state("light.living_room")

            assert state["entity_id"] == "light.living_room"
            assert state["state"] == "on"

        # Clean up
        del os.environ["HA_BASE_URL"]
        del os.environ["HA_TOKEN"]

    async def test_get_state_raises_skill_execution_error_when_entity_not_found(self) -> None:
        """Test that get_state raises SkillExecutionError when entity not found."""
        # Set environment variables before creating skill
        os.environ["HA_BASE_URL"] = "http://localhost:8123"
        os.environ["HA_TOKEN"] = "test_token"

        emitter = MemoryTraceEmitter()
        skill = HomeAssistantSkill(emitter=emitter)

        mock_response = Mock()
        mock_response.status_code = 404

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            with pytest.raises(SkillExecutionError) as exc_info:
                await skill.get_state("light.nonexistent")

            assert "not found" in str(exc_info.value).lower()

        # Clean up
        del os.environ["HA_BASE_URL"]
        del os.environ["HA_TOKEN"]

    async def test_call_service_sends_correct_post_to_ha_rest_api(self) -> None:
        """Test that call_service sends correct POST to HA REST API."""
        # Set environment variables before creating skill
        os.environ["HA_BASE_URL"] = "http://localhost:8123"
        os.environ["HA_TOKEN"] = "test_token"

        emitter = MemoryTraceEmitter()
        skill = HomeAssistantSkill(emitter=emitter)

        mock_response = Mock()
        mock_response.raise_for_status = Mock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            with patch("core.approval_gate.ApprovalGate") as mock_gate_class:
                mock_gate = AsyncMock()
                approval_response = ApprovalResponse(
                    request_id="test-request-id",
                    task_id="test-task-id",
                    approved=True,
                    approved_by="test-user",
                )
                mock_gate.request_approval = AsyncMock(return_value=approval_response)
                mock_gate_class.return_value = mock_gate

                result = await skill.call_service("light", "turn_on", "light.living_room")

                assert result is True
                mock_client.post.assert_called_once()
                call_args = mock_client.post.call_args
                assert "light" in call_args[0][0]
                assert "turn_on" in call_args[0][0]

        # Clean up
        del os.environ["HA_BASE_URL"]
        del os.environ["HA_TOKEN"]

    async def test_call_service_requests_approval_before_executing(self) -> None:
        """Test that call_service requests approval before executing."""
        # Set environment variables before creating skill
        os.environ["HA_BASE_URL"] = "http://localhost:8123"
        os.environ["HA_TOKEN"] = "test_token"

        emitter = MemoryTraceEmitter()
        skill = HomeAssistantSkill(emitter=emitter)

        mock_response = Mock()
        mock_response.raise_for_status = Mock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            with patch("core.approval_gate.ApprovalGate") as mock_gate_class:
                mock_gate = AsyncMock()
                approval_response = ApprovalResponse(
                    request_id="test-request-id",
                    task_id="test-task-id",
                    approved=True,
                    approved_by="test-user",
                )
                mock_gate.request_approval = AsyncMock(return_value=approval_response)
                mock_gate_class.return_value = mock_gate

                await skill.call_service("light", "turn_on", "light.living_room")

                mock_gate.request_approval.assert_called_once()
                call_args = mock_gate.request_approval.call_args
                request = call_args[0][0]
                assert "light.turn_on" in request.action_description

        # Clean up
        del os.environ["HA_BASE_URL"]
        del os.environ["HA_TOKEN"]

    async def test_call_service_raises_approval_denied_error_when_approval_denied(self) -> None:
        """Test that call_service raises ApprovalDeniedError when approval denied."""
        # Set environment variables before creating skill
        os.environ["HA_BASE_URL"] = "http://localhost:8123"
        os.environ["HA_TOKEN"] = "test_token"

        emitter = MemoryTraceEmitter()
        skill = HomeAssistantSkill(emitter=emitter)

        with patch("core.approval_gate.ApprovalGate") as mock_gate_class:
            mock_gate = AsyncMock()
            mock_response = ApprovalResponse(
                request_id="test-request-id",
                task_id="test-task-id",
                approved=False,
                approved_by="test-user",
                decision_reason="Test denial",
            )
            mock_gate.request_approval = AsyncMock(return_value=mock_response)
            mock_gate_class.return_value = mock_gate

            with pytest.raises(ApprovalDeniedError):
                await skill.call_service("light", "turn_on", "light.living_room")

        # Clean up
        del os.environ["HA_BASE_URL"]
        del os.environ["HA_TOKEN"]

    async def test_get_states_raises_skill_execution_error_when_ha_unreachable(self) -> None:
        """Test that get_states raises SkillExecutionError when HA unreachable."""
        # Set environment variables before creating skill
        os.environ["HA_BASE_URL"] = "http://localhost:8123"
        os.environ["HA_TOKEN"] = "test_token"

        emitter = MemoryTraceEmitter()
        skill = HomeAssistantSkill(emitter=emitter)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get.side_effect = httpx.HTTPError("Connection refused")
            mock_client_class.return_value = mock_client

            with pytest.raises(SkillExecutionError):
                await skill.get_states()

        # Clean up
        del os.environ["HA_BASE_URL"]
        del os.environ["HA_TOKEN"]

    async def test_token_read_from_env_var_never_hardcoded(self) -> None:
        """Test that token is read from env var and never hardcoded."""
        # Set environment variables before creating skill
        os.environ["HA_BASE_URL"] = "http://localhost:8123"
        os.environ["HA_TOKEN"] = "test_token_from_env"

        emitter = MemoryTraceEmitter()
        skill = HomeAssistantSkill(emitter=emitter)

        mock_response = Mock()
        mock_response.json.return_value = []

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            await skill.get_states()

            # Verify the token from env var was used in the request
            call_args = mock_client.get.call_args
            headers = call_args[1]["headers"]
            assert "Bearer test_token_from_env" in headers["Authorization"]

        # Clean up
        del os.environ["HA_BASE_URL"]
        del os.environ["HA_TOKEN"]
