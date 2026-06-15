"""
Transcription Skill - audio transcription using Whisper via faster-whisper.

Single responsibility: Transcribe audio files to text using local Whisper model.
"""

import os
import tempfile
from typing import Any

from core.observability import (
    TraceComponent,
    TraceEventType,
    TraceLevel,
    TraceEvent,
    TraceEmitter,
    MemoryTraceEmitter,
)
from core.exceptions import SkillExecutionError


class TranscriptionSkill:
    """Skill for audio transcription."""

    def __init__(self, emitter: TraceEmitter | None = None) -> None:
        """Initialize the transcription skill."""
        self._emitter = emitter or MemoryTraceEmitter()
        self._model_name = os.getenv("WHISPER_MODEL", "base")
        self._model = None  # Lazy loading

    def _load_model(self) -> Any:
        """Load Whisper model lazily on first use."""
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
                self._model = WhisperModel(self._model_name, device="cpu", compute_type="int8")
            except ImportError:
                raise SkillExecutionError(
                    "transcription",
                    "faster-whisper not installed. Install with: pip install faster-whisper"
                )
        return self._model

    async def transcribe(self, audio_path: str, language: str | None = None) -> str:
        """
        Transcribe audio file to text.

        Args:
            audio_path: Path to audio file
            language: Language code (e.g., "en", "es"). If not specified, auto-detect

        Returns:
            Transcribed text

        Raises:
            SkillExecutionError: If transcription fails or model not available
        """
        model = self._load_model()

        try:
            segments, info = model.transcribe(audio_path, language=language)
            text = " ".join(segment.text for segment in segments)

            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.INFO,
                    message="Audio transcription completed",
                    data={
                        "skill": "transcription",
                        "language": info.language if info else language,
                        "duration": info.duration if info else 0,
                    },
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception:
                pass

            return text

        except Exception as e:
            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.ERROR,
                    message="Audio transcription failed",
                    data={
                        "skill": "transcription",
                        "audio_path": audio_path,
                        "error": str(e),
                    },
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception:
                pass
            raise SkillExecutionError("transcription", f"Failed to transcribe: {str(e)}")

    async def transcribe_bytes(self, audio_bytes: bytes, language: str | None = None) -> str:
        """
        Transcribe audio bytes to text.

        Args:
            audio_bytes: Audio data as bytes
            language: Language code (e.g., "en", "es"). If not specified, auto-detect

        Returns:
            Transcribed text

        Raises:
            SkillExecutionError: If transcription fails or model not available
        """
        # Write bytes to temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_path = temp_file.name
            temp_file.write(audio_bytes)

        try:
            # Transcribe from temp file
            text = await self.transcribe(temp_path, language)
            return text
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_path)
            except Exception:
                pass
