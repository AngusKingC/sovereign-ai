"""
Audio Capture - PyAudio-based microphone capture.

Single responsibility: Isolate all PyAudio interaction behind a clean interface.
This is the only file in the project that imports pyaudio.
"""

import time

from pydantic import BaseModel, Field

from core.observability import (
    TraceComponent,
    TraceEventType,
    TraceLevel,
    TraceEvent,
    TraceEmitter,
    MemoryTraceEmitter,
)
from core.exceptions import SkillExecutionError


class AudioConfig(BaseModel):
    """Configuration for audio capture."""
    sample_rate: int = 16000
    channels: int = 1
    chunk_size: int = 1024
    format: int = 8  # pyaudio.paInt16 = 8
    record_seconds: float = 3.0


class AudioCapture:
    """Audio capture using PyAudio."""

    def __init__(
        self,
        config: AudioConfig | None = None,
        emitter: TraceEmitter | None = None,
    ):
        """Initialize the audio capture."""
        self._config = config or AudioConfig()
        self._emitter = emitter or MemoryTraceEmitter()
        self._pa = None  # PyAudio instance — lazy init

    def _get_pa(self):
        """
        Lazy-initialise PyAudio instance on first call.

        Returns:
            PyAudio instance

        Raises:
            SkillExecutionError: If pyaudio not installed
        """
        if self._pa is None:
            try:
                import pyaudio
                self._pa = pyaudio.PyAudio()
            except ImportError:
                raise SkillExecutionError(
                    "audio_capture",
                    "pyaudio not installed — run: pip install pyaudio"
                )
        return self._pa

    async def capture_chunk(self) -> bytes:
        """
        Open a PyAudio stream, record audio, close stream.

        Returns:
            Raw PCM bytes

        Raises:
            SkillExecutionError: If PyAudio unavailable or device not found
        """
        start_time = time.time()

        try:
            pa = self._get_pa()

            stream = pa.open(
                format=self._config.format,
                channels=self._config.channels,
                rate=self._config.sample_rate,
                input=True,
                frames_per_buffer=self._config.chunk_size,
            )

            frames = []
            for _ in range(int(self._config.sample_rate / self._config.chunk_size * self._config.record_seconds)):
                frames.append(stream.read(self._config.chunk_size))

            stream.stop_stream()
            stream.close()

            audio_bytes = b"".join(frames)
            duration_ms = int((time.time() - start_time) * 1000)

            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.VOICE,
                    level=TraceLevel.INFO,
                    message="Audio capture completed",
                    data={
                        "byte_count": len(audio_bytes),
                        "duration_ms": duration_ms,
                    },
                    duration_ms=duration_ms,
                )
                await self._emitter.emit(event)
            except Exception:
                pass

            return audio_bytes

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)

            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.VOICE,
                    level=TraceLevel.ERROR,
                    message="Audio capture failed",
                    data={
                        "error": str(e),
                    },
                    duration_ms=duration_ms,
                )
                await self._emitter.emit(event)
            except Exception:
                pass

            raise SkillExecutionError("audio_capture", f"Failed to capture audio: {str(e)}")

    async def is_available(self) -> bool:
        """
        Check if PyAudio is installed and a microphone device is available.

        Returns:
            True if PyAudio is installed and device found, False otherwise
        """
        try:
            pa = self._get_pa()
            device_count = pa.get_device_count()

            if device_count == 0:
                return False

            # Check if any input device is available
            for i in range(device_count):
                device_info = pa.get_device_info_by_index(i)
                if device_info.get("maxInputChannels", 0) > 0:
                    return True

            return False

        except Exception:
            return False

    def close(self) -> None:
        """Terminate PyAudio instance if initialised."""
        if self._pa is not None:
            try:
                self._pa.terminate()
            except Exception:
                pass
            self._pa = None
