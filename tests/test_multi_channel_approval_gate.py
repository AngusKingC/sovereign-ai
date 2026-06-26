"""Tests for MultiChannelApprovalGate."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.approval_gate import ApprovalGate, ApprovalRequest, ApprovalResponse
from core.multi_channel_approval_gate import MultiChannelApprovalGate
from gateways.email.gateway import EmailGateway
from gateways.telegram.gateway import TelegramGateway


@pytest.fixture
def mock_approval_gate():
    """Mock ApprovalGate."""
    gate = MagicMock(spec=ApprovalGate)
    gate.request_approval = AsyncMock(
        return_value=ApprovalResponse(
            request_id="test-id",
            task_id="task-123",
            approved=True,
            approved_by="test",
        )
    )
    gate.respond = AsyncMock(
        return_value=ApprovalResponse(
            request_id="test-id",
            task_id="task-123",
            approved=True,
            approved_by="test",
        )
    )
    return gate


@pytest.fixture
def mock_telegram_gateway():
    """Mock TelegramGateway."""
    gateway = MagicMock(spec=TelegramGateway)
    gateway.send_notification = AsyncMock()
    gateway.poll_updates = AsyncMock(return_value=[])
    gateway.extract_commands = AsyncMock(return_value=[])
    return gateway


@pytest.fixture
def mock_email_gateway():
    """Mock EmailGateway."""
    gateway = MagicMock(spec=EmailGateway)
    gateway.send_approval_request = AsyncMock(return_value=True)
    return gateway


@pytest.fixture
def sample_approval_request():
    """Sample ApprovalRequest."""
    from core.approval_gate import ApprovalActionType

    return ApprovalRequest(
        request_id="test-123",
        task_id="task-123",
        session_id="session-1",
        action_type=ApprovalActionType.FILE_WRITE,
        action_description="Test action",
        action_parameters={},
        risk_level="medium",
        reason_for_approval="Test reason",
        expires_at=datetime.now(timezone.utc),
    )


def test_request_approval_fans_out_to_telegram(
    mock_approval_gate, mock_telegram_gateway, sample_approval_request
):
    """Test that approval requests are sent to Telegram when configured."""
    gate = MultiChannelApprovalGate(
        approval_gate=mock_approval_gate,
        telegram_gateway=mock_telegram_gateway,
    )

    import asyncio

    asyncio.run(gate.request_approval(sample_approval_request))

    # Verify primary gate was called
    mock_approval_gate.request_approval.assert_called_once()

    # Verify Telegram was notified
    mock_telegram_gateway.send_notification.assert_called_once()


def test_request_approval_fans_out_to_email(
    mock_approval_gate, mock_email_gateway, sample_approval_request
):
    """Test that approval requests are sent to Email when configured."""
    gate = MultiChannelApprovalGate(
        approval_gate=mock_approval_gate,
        email_gateway=mock_email_gateway,
    )

    import asyncio

    asyncio.run(gate.request_approval(sample_approval_request))

    # Verify primary gate was called
    mock_approval_gate.request_approval.assert_called_once()

    # Verify Email was notified
    mock_email_gateway.send_approval_request.assert_called_once()


def test_request_approval_web_only_no_gateways(
    mock_approval_gate, sample_approval_request
):
    """Test that approval requests work with only the primary gate."""
    gate = MultiChannelApprovalGate(
        approval_gate=mock_approval_gate,
    )

    import asyncio

    asyncio.run(gate.request_approval(sample_approval_request))

    # Verify primary gate was called
    mock_approval_gate.request_approval.assert_called_once()


def test_respond_from_telegram_channel(mock_approval_gate, mock_telegram_gateway):
    """Test responding to an approval from Telegram channel."""
    gate = MultiChannelApprovalGate(
        approval_gate=mock_approval_gate,
        telegram_gateway=mock_telegram_gateway,
    )

    import asyncio

    asyncio.run(
        gate.respond(
            request_id="test-id",
            approved=True,
            responder="telegram",
            channel="telegram",
        )
    )

    # Verify primary gate was called
    mock_approval_gate.respond.assert_called_once_with(
        "test-id", True, "telegram", always_approve=False
    )


def test_respond_from_web_channel(mock_approval_gate):
    """Test responding to an approval from Web channel."""
    gate = MultiChannelApprovalGate(
        approval_gate=mock_approval_gate,
    )

    import asyncio

    asyncio.run(
        gate.respond(
            request_id="test-id",
            approved=True,
            responder="web",
        )
    )

    # Verify primary gate was called
    mock_approval_gate.respond.assert_called_once_with(
        "test-id", True, "web", always_approve=False
    )


def test_poll_telegram_responses_approve(mock_approval_gate, mock_telegram_gateway):
    """Test polling Telegram for APPROVE commands."""

    async def mock_extract(updates):
        return ["APPROVE test-123"]

    mock_telegram_gateway.extract_commands = mock_extract

    gate = MultiChannelApprovalGate(
        approval_gate=mock_approval_gate,
        telegram_gateway=mock_telegram_gateway,
    )

    import asyncio

    asyncio.run(gate.poll_telegram_responses())

    # Verify respond was called with approved=True
    mock_approval_gate.respond.assert_called_once_with(
        "test-123", True, "telegram", always_approve=False
    )


def test_poll_telegram_responses_deny(mock_approval_gate, mock_telegram_gateway):
    """Test polling Telegram for DENY commands."""

    async def mock_extract(updates):
        return ["DENY test-123"]

    mock_telegram_gateway.extract_commands = mock_extract

    gate = MultiChannelApprovalGate(
        approval_gate=mock_approval_gate,
        telegram_gateway=mock_telegram_gateway,
    )

    import asyncio

    asyncio.run(gate.poll_telegram_responses())

    # Verify respond was called with approved=False
    mock_approval_gate.respond.assert_called_once_with(
        "test-123", False, "telegram", always_approve=False
    )


def test_poll_telegram_responses_invalid_command(
    mock_approval_gate, mock_telegram_gateway
):
    """Test that invalid commands are ignored."""

    async def mock_extract(updates):
        return ["INVALID test-123"]

    mock_telegram_gateway.extract_commands = mock_extract

    gate = MultiChannelApprovalGate(
        approval_gate=mock_approval_gate,
        telegram_gateway=mock_telegram_gateway,
    )

    import asyncio

    asyncio.run(gate.poll_telegram_responses())

    # Verify respond was NOT called
    mock_approval_gate.respond.assert_not_called()
