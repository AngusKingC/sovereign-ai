"""
Tests for audio capture module.
"""

import pytest
from unittest.mock import patch, MagicMock

from system.audio_capture import AudioConfig, AudioCapture
from core.observability import MemoryTraceEmitter
from core.exceptions import SkillExecutionError


class TestAudioConfig:
    """Tests for AudioConfig class."""

    def test_audio_config_constructs_with_correct_defaults(self):
        """AudioConfig constructs with correct defaults (sample_rate=16000, channels=1)."""
        config = AudioConfig()
        assert config.sample_rate == 16000
        assert config.channels == 1
        assert config.chunk_size == 1024
        assert config.format == 8
        assert config.record_seconds == 3.0

    def test_audio_config_record_seconds_is_3_0_by_default(self):
        """AudioConfig.record_seconds is 3.0 by default."""
        config = AudioConfig()
        assert config.record_seconds == 3.0


class TestAudioCapture:
    """Tests for AudioCapture class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.emitter = MemoryTraceEmitter()
        self.config = AudioConfig()
        self.capture = AudioCapture(config=self.config, emitter=self.emitter)

    @pytest.mark.asyncio
    async def test_is_available_returns_false_when_pyaudio_not_installed(self):
        """AudioCapture.is_available() returns False when pyaudio not installed."""
        with patch("system.audio_capture.AudioCapture._get_pa", side_effect=ImportError):
            result = await self.capture.is_available()
            assert result is False

    @pytest.mark.asyncio
    async def test_is_available_returns_true_when_pyaudio_available_and_device_found(self):
        """AudioCapture.is_available() returns True when pyaudio available and device found."""
        mock_pa = MagicMock()
        mock_pa.get_device_count.return_value = 1
        mock_pa.get_device_info_by_index.return_value = {"maxInputChannels": 1}

        with patch("system.audio_capture.AudioCapture._get_pa", return_value=mock_pa):
            result = await self.capture.is_available()
            assert result is True

    @pytest.mark.asyncio
    async def test_capture_chunk_raises_skill_execution_error_when_pyaudio_not_installed(self):
        """AudioCapture.capture_chunk() raises SkillExecutionError when pyaudio not installed."""
        with patch.object(self.capture, "_get_pa", side_effect=SkillExecutionError("audio_capture", "pyaudio not installed — run: pip install pyaudio")):
            with pytest.raises(SkillExecutionError) as exc_info:
                await self.capture.capture_chunk()
            assert "pyaudio not installed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_capture_chunk_raises_skill_execution_error_when_no_microphone_device(self):
        """AudioCapture.capture_chunk() raises SkillExecutionError when no microphone device."""
        mock_pa = MagicMock()
        mock_pa.open.side_effect = Exception("No input device found")

        with patch("system.audio_capture.AudioCapture._get_pa", return_value=mock_pa):
            with pytest.raises(SkillExecutionError) as exc_info:
                await self.capture.capture_chunk()
            assert "Failed to capture audio" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_capture_chunk_returns_bytes_when_pyaudio_succeeds(self):
        """AudioCapture.capture_chunk() returns bytes when PyAudio succeeds."""
        mock_stream = MagicMock()
        mock_stream.read.return_value = b"audio_data"
        mock_stream.stop_stream = MagicMock()
        mock_stream.close = MagicMock()

        mock_pa = MagicMock()
        mock_pa.open.return_value = mock_stream

        with patch("system.audio_capture.AudioCapture._get_pa", return_value=mock_pa):
            result = await self.capture.capture_chunk()
            assert result is not None
            assert isinstance(result, bytes)

    @pytest.mark.asyncio
    async def test_capture_chunk_emits_trace_event_with_byte_count_in_data(self):
        """AudioCapture.capture_chunk() emits trace event with byte count in data."""
        mock_stream = MagicMock()
        mock_stream.read.return_value = b"audio_data"
        mock_stream.stop_stream = MagicMock()
        mock_stream.close = MagicMock()

        mock_pa = MagicMock()
        mock_pa.open.return_value = mock_stream

        with patch("system.audio_capture.AudioCapture._get_pa", return_value=mock_pa):
            await self.capture.capture_chunk()

        events = self.emitter.get_events()
        assert len(events) == 1
        assert events[0].event_type == "operation_complete"
        assert "byte_count" in events[0].data

    def test_close_terminates_pyaudio_instance_when_initialised(self):
        """AudioCapture.close() terminates PyAudio instance when initialised."""
        mock_pa = MagicMock()
        self.capture._pa = mock_pa

        self.capture.close()

        mock_pa.terminate.assert_called_once()
        assert self.capture._pa is None

    def test_close_does_not_raise_when_pyaudio_not_initialised(self):
        """AudioCapture.close() does not raise when PyAudio not initialised."""
        self.capture._pa = None

        # Should not raise
        self.capture.close()
        assert self.capture._pa is None
