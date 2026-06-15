"""Tests for Screenshot Skill."""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from io import BytesIO

from skills.screenshot.skill import ScreenshotSkill
from core.observability import MemoryTraceEmitter
from core.exceptions import SkillExecutionError, ApprovalDeniedError


@pytest.mark.asyncio
class TestScreenshotSkill:
    """Tests for ScreenshotSkill."""

    async def test_capture_returns_bytes_when_pil_succeeds(self) -> None:
        """Test that capture returns bytes when PIL ImageGrab succeeds."""
        emitter = MemoryTraceEmitter()
        skill = ScreenshotSkill(emitter=emitter)

        mock_image = MagicMock()
        
        def mock_save(buffer, format):
            buffer.write(b"fake_png_data")

        mock_image.save = mock_save

        with patch("skills.screenshot.skill.ImageGrab") as mock_grab:
            mock_grab.grab.return_value = mock_image

            with patch("core.approval_gate.ApprovalGate") as mock_gate_class:
                mock_gate = AsyncMock()
                mock_gate.request_approval = AsyncMock()
                mock_gate_class.return_value = mock_gate

                result = await skill.capture()

                assert isinstance(result, bytes)
                assert len(result) > 0

    async def test_capture_requests_approval_before_capturing(self) -> None:
        """Test that capture requests approval before capturing."""
        emitter = MemoryTraceEmitter()
        skill = ScreenshotSkill(emitter=emitter)

        mock_image = MagicMock()
        mock_image.save = Mock()

        with patch("skills.screenshot.skill.ImageGrab") as mock_grab:
            mock_grab.grab.return_value = mock_image

            with patch("core.approval_gate.ApprovalGate") as mock_gate_class:
                mock_gate = AsyncMock()
                mock_gate.request_approval = AsyncMock()
                mock_gate_class.return_value = mock_gate

                await skill.capture()

                mock_gate.request_approval.assert_called_once()
                call_args = mock_gate.request_approval.call_args
                assert "Capture screenshot" in call_args[1]["action_description"]

    async def test_capture_raises_approval_denied_error_when_approval_denied(self) -> None:
        """Test that capture raises ApprovalDeniedError when approval denied."""
        emitter = MemoryTraceEmitter()
        skill = ScreenshotSkill(emitter=emitter)

        with patch("core.approval_gate.ApprovalGate") as mock_gate_class:
            mock_gate = AsyncMock()
            mock_gate.request_approval = AsyncMock(side_effect=ApprovalDeniedError("test action", "denied"))
            mock_gate_class.return_value = mock_gate

            with pytest.raises(ApprovalDeniedError):
                await skill.capture()

    async def test_capture_raises_skill_execution_error_when_display_unavailable(self) -> None:
        """Test that capture raises SkillExecutionError when display unavailable."""
        emitter = MemoryTraceEmitter()
        skill = ScreenshotSkill(emitter=emitter)

        with patch("skills.screenshot.skill.ImageGrab") as mock_grab:
            mock_grab.grab.side_effect = Exception("Display not available")

            with patch("core.approval_gate.ApprovalGate") as mock_gate_class:
                mock_gate = AsyncMock()
                mock_gate.request_approval = AsyncMock()
                mock_gate_class.return_value = mock_gate

                with pytest.raises(SkillExecutionError):
                    await skill.capture()

    async def test_save_writes_png_to_specified_path(self) -> None:
        """Test that save writes PNG to specified path and returns path."""
        emitter = MemoryTraceEmitter()
        skill = ScreenshotSkill(emitter=emitter)

        mock_image = MagicMock()
        mock_image.save = Mock()

        with patch("skills.screenshot.skill.ImageGrab") as mock_grab:
            mock_grab.grab.return_value = mock_image

            with patch("core.approval_gate.ApprovalGate") as mock_gate_class:
                mock_gate = AsyncMock()
                mock_gate.request_approval = AsyncMock()
                mock_gate_class.return_value = mock_gate

                with patch("PIL.Image") as mock_image_class:
                    mock_pil_image = MagicMock()
                    mock_pil_image.save = Mock()
                    mock_image_class.open.return_value = mock_pil_image

                    result = await skill.save("test_screenshot.png")

                    assert result == "test_screenshot.png"
                    mock_pil_image.save.assert_called_once_with("test_screenshot.png")

    async def test_save_requests_approval_before_capturing(self) -> None:
        """Test that save requests approval before capturing."""
        emitter = MemoryTraceEmitter()
        skill = ScreenshotSkill(emitter=emitter)

        mock_image = MagicMock()
        mock_image.save = Mock()

        with patch("skills.screenshot.skill.ImageGrab") as mock_grab:
            mock_grab.grab.return_value = mock_image

            with patch("core.approval_gate.ApprovalGate") as mock_gate_class:
                mock_gate = AsyncMock()
                mock_gate.request_approval = AsyncMock()
                mock_gate_class.return_value = mock_gate

                with patch("PIL.Image") as mock_image_class:
                    mock_pil_image = MagicMock()
                    mock_pil_image.save = Mock()
                    mock_image_class.open.return_value = mock_pil_image

                    await skill.save("test_screenshot.png")

                    mock_gate.request_approval.assert_called_once()

    async def test_trace_event_emitted_on_successful_capture(self) -> None:
        """Test that trace event is emitted on successful capture."""
        emitter = MemoryTraceEmitter()
        skill = ScreenshotSkill(emitter=emitter)

        mock_image = MagicMock()
        mock_image.save = Mock()

        with patch("skills.screenshot.skill.ImageGrab") as mock_grab:
            mock_grab.grab.return_value = mock_image

            with patch("core.approval_gate.ApprovalGate") as mock_gate_class:
                mock_gate = AsyncMock()
                mock_gate.request_approval = AsyncMock()
                mock_gate_class.return_value = mock_gate

                await skill.capture()

                events = emitter.get_events()
                capture_events = [e for e in events if "screenshot" in e.data.get("skill", "")]
                assert len(capture_events) > 0
                assert "captured successfully" in capture_events[0].message

    async def test_capture_region_passes_region_to_imagegrab(self) -> None:
        """Test that capture(region) passes region to ImageGrab."""
        emitter = MemoryTraceEmitter()
        skill = ScreenshotSkill(emitter=emitter)

        mock_image = MagicMock()
        mock_image.save = Mock()

        with patch("skills.screenshot.skill.ImageGrab") as mock_grab:
            mock_grab.grab.return_value = mock_image

            with patch("core.approval_gate.ApprovalGate") as mock_gate_class:
                mock_gate = AsyncMock()
                mock_gate.request_approval = AsyncMock()
                mock_gate_class.return_value = mock_gate

                region = (0, 0, 100, 100)
                await skill.capture(region)

                mock_grab.grab.assert_called_once_with(bbox=region)
