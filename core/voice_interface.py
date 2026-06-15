"""
Voice Interface - wake word detection, STT, and TTS output.

Single responsibility: Provide voice input/output capabilities for the Jarvis framework.
This module defines the voice interface layer that will be wired to real audio capture
and Whisper STT in Prompt 33.5.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from core.observability import (
    TraceComponent,
    TraceEventType,
    TraceLevel,
    TraceEvent,
    TraceEmitter,
    MemoryTraceEmitter,
)


class VoiceConfig(BaseModel):
    """Configuration for voice interface."""
    wake_word: str = "jarvis"
    wake_word_sensitivity: float = Field(default=0.5, ge=0.0, le=1.0)
    stt_model: str = "base"
    tts_voice: str | None = None
    noise_threshold: float = Field(default=0.01, ge=0.0)
    silence_timeout_ms: int = Field(default=1500, ge=100)
    enabled: bool = True


class VoiceCommand(BaseModel):
    """A voice command transcribed from audio."""
    command_id: UUID = Field(default_factory=uuid4)
    transcript: str
    confidence: float = Field(ge=0.0, le=1.0)
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    wake_word_detected: bool = False


class VoiceInterface:
    """Voice interface for wake word detection, STT, and TTS output."""

    def __init__(
        self,
        config: VoiceConfig | None = None,
        emitter: TraceEmitter | None = None,
    ):
        """Initialize the voice interface."""
        self._config = config or VoiceConfig()
        self._emitter = emitter or MemoryTraceEmitter()
        self._listening = False

    async def detect_wake_word(self, audio_bytes: bytes) -> bool:
        """
        Check if audio contains the configured wake word.

        Args:
            audio_bytes: Audio data as bytes

        Returns:
            True if wake word detected, False otherwise
        """
        # Stub implementation: transcribe and check for wake word
        transcript = await self._transcribe_stub(audio_bytes)
        detected = self._config.wake_word.lower() in transcript.lower()

        if detected:
            try:
                event = TraceEvent(
                    event_type=TraceEventType.VOICE_WAKE_WORD_DETECTED,
                    component=TraceComponent.VOICE,
                    level=TraceLevel.INFO,
                    message=f"Wake word '{self._config.wake_word}' detected",
                    data={"wake_word": self._config.wake_word},
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception:
                pass

        return detected

    async def _transcribe_stub(self, audio_bytes: bytes) -> str:
        """
        Stub for STT — delegates to TranscriptionSkill in Prompt 33.5.

        Args:
            audio_bytes: Audio data as bytes

        Returns:
            Transcribed text (empty string in this stub)
        """
        # Real implementation wired in Prompt 33.5
        return ""

    async def process_command(self, audio_bytes: bytes) -> VoiceCommand | None:
        """
        Transcribe audio and create a voice command.

        Args:
            audio_bytes: Audio data as bytes

        Returns:
            VoiceCommand if transcript is valid, None otherwise
        """
        transcript = await self._transcribe_stub(audio_bytes)

        if not transcript or len(transcript) < self._config.noise_threshold:
            return None

        command = VoiceCommand(
            transcript=transcript,
            confidence=1.0,  # Stub confidence
            wake_word_detected=False,
        )

        try:
            event = TraceEvent(
                event_type=TraceEventType.VOICE_COMMAND_RECEIVED,
                component=TraceComponent.VOICE,
                level=TraceLevel.INFO,
                message="Voice command received",
                data={
                    "command_id": str(command.command_id),
                    "transcript_length": len(transcript),
                    "confidence": command.confidence,
                },
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            pass

        return command

    async def start_listening(self) -> None:
        """Start listening for voice input."""
        self._listening = True

        try:
            event = TraceEvent(
                event_type=TraceEventType.VOICE_LISTENING_STARTED,
                component=TraceComponent.VOICE,
                level=TraceLevel.INFO,
                message="Voice listening started",
                data={},
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            pass

    async def stop_listening(self) -> None:
        """Stop listening for voice input."""
        self._listening = False

        try:
            event = TraceEvent(
                event_type=TraceEventType.VOICE_LISTENING_STOPPED,
                component=TraceComponent.VOICE,
                level=TraceLevel.INFO,
                message="Voice listening stopped",
                data={},
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            pass

    async def notify(self, message: str) -> None:
        """
        Stub for TTS output notification — real TTS wired in Prompt 33.5.

        Args:
            message: Message to speak
        """
        try:
            event = TraceEvent(
                event_type=TraceEventType.VOICE_NOTIFICATION_SENT,
                component=TraceComponent.VOICE,
                level=TraceLevel.INFO,
                message="Voice notification sent",
                data={"message_length": len(message)},
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            pass
