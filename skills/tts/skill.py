"""
TTS Skill - text-to-speech synthesis using Piper TTS.

Single responsibility: Convert text to speech using Piper TTS subprocess.
"""

import os
import subprocess
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


class TTSSkill:
    """Skill for text-to-speech synthesis."""

    def __init__(self, emitter: TraceEmitter | None = None) -> None:
        """Initialize the TTS skill."""
        self._emitter = emitter or MemoryTraceEmitter()
        self._piper_bin = os.getenv("PIPER_BIN", "piper")
        self._default_voice = os.getenv("PIPER_VOICE")

    async def synthesise(self, text: str, voice: str | None = None) -> bytes:
        """
        Synthesise text to WAV bytes using Piper TTS.

        Args:
            text: Text to synthesise
            voice: Voice model to use (overrides default from env var)

        Returns:
            WAV audio bytes

        Raises:
            ValueError: If text is empty
            SkillExecutionError: If Piper binary not found or synthesis fails
        """
        if not text or not isinstance(text, str):
            raise ValueError("Text must be a non-empty string")

        # Use provided voice or default from env var
        selected_voice = voice or self._default_voice

        try:
            # Build Piper command
            cmd = [self._piper_bin, "--model", selected_voice if selected_voice else "en_US-lessac-medium"]
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = process.communicate(input=text.encode())

            if process.returncode != 0:
                raise SkillExecutionError(
                    "tts",
                    f"Piper synthesis failed: {stderr.decode()}"
                )

            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.INFO,
                    message="TTS synthesis completed",
                    data={
                        "skill": "tts",
                        "text_length": len(text),
                        "voice": selected_voice,
                    },
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception:
                # Trace emission failure - non-critical, continue
                pass

            return stdout

        except FileNotFoundError:
            raise SkillExecutionError(
                "tts",
                "Piper binary not found. Install Piper TTS from https://github.com/rhasspy/piper"
            )
        except Exception as e:
            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.ERROR,
                    message="TTS synthesis failed",
                    data={
                        "skill": "tts",
                        "text_length": len(text),
                        "error": str(e),
                    },
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception:
                # Trace emission failure - non-critical, continue
                pass
            raise SkillExecutionError("tts", f"Failed to synthesise: {str(e)}")

    async def speak(self, text: str, voice: str | None = None) -> None:
        """
        Synthesise and play audio.

        Args:
            text: Text to speak
            voice: Voice model to use (overrides default from env var)

        Raises:
            ValueError: If text is empty
            SkillExecutionError: If synthesis or playback fails
        """
        # Synthesise audio
        wav_bytes = await self.synthesise(text, voice)

        try:
            # Play audio using platform-specific player
            import platform
            system = platform.system()

            if system == "Windows":
                # Use Windows Media Player
                import winsound
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    f.write(wav_bytes)
                    temp_path = f.name
                winsound.PlaySound(temp_path, winsound.SND_FILENAME)
                os.unlink(temp_path)
            elif system == "Darwin":  # macOS
                subprocess.run(["afplay", "-"], input=wav_bytes)
            else:  # Linux
                subprocess.run(["aplay", "-"], input=wav_bytes)

            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.INFO,
                    message="TTS playback completed",
                    data={
                        "skill": "tts",
                        "text_length": len(text),
                    },
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception:
                # Trace emission failure - non-critical, continue
                pass

        except Exception as e:
            raise SkillExecutionError("tts", f"Failed to play audio: {str(e)}")
