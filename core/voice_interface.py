"""
Voice Interface - wake word detection, STT, and TTS output.

Single responsibility: Provide voice input/output capabilities for the Jarvis framework.
This module defines the voice interface layer that will be wired to real audio capture
and Whisper STT in Prompt 33.5.
"""

from datetime import datetime, timezone
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
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    wake_word_detected: bool = False


class VoiceInterface:
    """Voice interface for wake word detection, STT, and TTS output."""

    def __init__(
        self,
        config: VoiceConfig | None = None,
        emitter: TraceEmitter | None = None,
        transcription_skill=None,   # TranscriptionSkill | None
        tts_skill=None,             # TTSSkill | None
    ):
        """Initialize the voice interface."""
        self._config = config or VoiceConfig()
        self._emitter = emitter or MemoryTraceEmitter()
        self._listening = False
        self._transcription_skill = transcription_skill
        self._tts_skill = tts_skill

    async def detect_wake_word(self, audio_bytes: bytes) -> bool:
        """
        Check if audio contains the configured wake word.

        Args:
            audio_bytes: Audio data as bytes

        Returns:
            True if wake word detected, False otherwise
        """
        # Transcribe and check for wake word
        transcript = await self._transcribe(audio_bytes)
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

    async def _transcribe(self, audio_bytes: bytes) -> str:
        """
        Transcribe audio bytes to text using TranscriptionSkill.

        Args:
            audio_bytes: Audio data as bytes

        Returns:
            Transcribed text (empty string if no skill injected)
        """
        if self._transcription_skill is not None:
            return await self._transcription_skill.transcribe_bytes(audio_bytes)
        return ""  # Preserves stub behaviour for tests that don't inject the skill

    async def process_command(self, audio_bytes: bytes) -> VoiceCommand | None:
        """
        Transcribe audio and create a voice command.

        Args:
            audio_bytes: Audio data as bytes

        Returns:
            VoiceCommand if transcript is valid, None otherwise
        """
        transcript = await self._transcribe(audio_bytes)

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
        Speak a message using TTS or fall back to console output.

        Args:
            message: Message to speak
        """
        if self._tts_skill is not None:
            await self._tts_skill.speak(message)
        else:
            print(f"[VOICE] {message}")

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
