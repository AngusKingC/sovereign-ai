"""Tests for EmailGateway."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from gateways.email.gateway import EmailGateway


@pytest.fixture
def email_gateway():
    """Create EmailGateway instance with mocked SMTP."""
    gateway = EmailGateway(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="test@example.com",
        smtp_password="password",  # pragma: allowlist secret
        from_addr="test@example.com",
        to_addrs=["recipient@example.com"],
    )
    return gateway


def test_send_approval_request(email_gateway):
    """Test sending an approval request email."""
    with patch.object(email_gateway, "_send_smtp") as mock_send:
        import asyncio

        result = asyncio.run(
            email_gateway.send_approval_request(
                request_id="test-123",
                description="Test approval request",
                risk_level="medium",
                expires_at="2024-01-01T00:00:00Z",
            )
        )

        assert result is True
        mock_send.assert_called_once()


def test_send_notification(email_gateway):
    """Test sending a general notification email."""
    from core.notification import Notification, NotificationType

    notification = Notification(
        type=NotificationType.INFO,
        title="Test Notification",
        source="test",
        message="Test message body",
    )

    with patch.object(email_gateway, "_send_smtp") as mock_send:
        import asyncio

        result = asyncio.run(email_gateway.send_notification(notification))

        assert result is True
        mock_send.assert_called_once()


def test_smtp_failure_handled(email_gateway):
    """Test that SMTP failures are handled gracefully."""
    with patch.object(email_gateway, "_send_smtp", side_effect=Exception("SMTP error")):
        import asyncio

        result = asyncio.run(
            email_gateway.send_approval_request(
                request_id="test-123",
                description="Test approval request",
                risk_level="medium",
                expires_at="2024-01-01T00:00:00Z",
            )
        )

        assert result is False
