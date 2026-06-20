"""
Screenshot Skill - captures screen content using Pillow ImageGrab.

Single responsibility: Capture screen content as PNG bytes or save to file.
"""

from io import BytesIO
from datetime import datetime, timedelta
from uuid import uuid4

from PIL import ImageGrab

from core.approval_gate import ApprovalRequest, ApprovalActionType
from core.observability import (
    TraceComponent,
    TraceEventType,
    TraceLevel,
    TraceEvent,
    TraceEmitter,
    MemoryTraceEmitter,
)
from core.exceptions import SkillExecutionError, ApprovalDeniedError


class ScreenshotSkill:
    """Skill for capturing screenshots."""

    def __init__(self, emitter: TraceEmitter | None = None) -> None:
        """Initialize the screenshot skill."""
        self._emitter = emitter or MemoryTraceEmitter()

    async def capture(self, region: tuple | None = None) -> bytes:
        """
        Capture screen content as PNG bytes.

        Args:
            region: Optional tuple (left, top, right, bottom) for region capture

        Returns:
            PNG bytes

        Raises:
            SkillExecutionError: If display not available or capture fails
            ApprovalDeniedError: If approval is denied
        """
        from core.approval_gate import ApprovalGate

        # Request approval before capturing
        approval_gate = ApprovalGate(emitter=self._emitter)
        action_description = "Capture screenshot"
        try:
            request = ApprovalRequest(
                request_id=str(uuid4()),
                task_id=str(uuid4()),
                session_id="default",
                action_type=ApprovalActionType.FILE_WRITE,
                action_description=action_description,
                action_parameters={"region": region},
                risk_level="low",
                reason_for_approval="Screenshot capture requires approval per policy",
                expires_at=datetime.utcnow() + timedelta(seconds=300),
            )
            response = await approval_gate.request_approval(request)
            if not response.approved:
                raise ApprovalDeniedError(action_description)
        except ApprovalDeniedError:
            raise

        try:
            # Capture screenshot
            if region:
                screenshot = ImageGrab.grab(bbox=region)
            else:
                screenshot = ImageGrab.grab()

            # Convert to PNG bytes
            buffer = BytesIO()
            screenshot.save(buffer, format="PNG")
            buffer.seek(0)
            png_bytes = buffer.getvalue()

            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.INFO,
                    message="Screenshot captured successfully",
                    data={
                        "skill": "screenshot",
                        "region": region,
                        "size_bytes": len(png_bytes),
                    },
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception:
                # Trace emission failure - non-critical, continue
                pass

            return png_bytes

        except Exception as e:
            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.ERROR,
                    message="Screenshot capture failed",
                    data={
                        "skill": "screenshot",
                        "region": region,
                        "error": str(e),
                    },
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception:
                # Trace emission failure - non-critical, continue
                pass
            raise SkillExecutionError("screenshot", f"Failed to capture screenshot: {str(e)}")

    async def save(self, path: str, region: tuple | None = None) -> str:
        """
        Capture screenshot and save to file.

        Args:
            path: File path to save screenshot
            region: Optional tuple (left, top, right, bottom) for region capture

        Returns:
            Path where screenshot was saved

        Raises:
            SkillExecutionError: If display not available or save fails
            ApprovalDeniedError: If approval is denied
        """
        # Capture screenshot
        png_bytes = await self.capture(region)

        try:
            # Save to file
            from PIL import Image

            image = Image.open(BytesIO(png_bytes))
            image.save(path)

            return path

        except Exception as e:
            raise SkillExecutionError("screenshot", f"Failed to save screenshot: {str(e)}")
