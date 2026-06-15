"""Tests for Transcription Skill."""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import os

from skills.transcription.skill import TranscriptionSkill
from core.observability import MemoryTraceEmitter
from core.exceptions import SkillExecutionError


@pytest.mark.asyncio
class TestTranscriptionSkill:
    """Tests for TranscriptionSkill."""

    async def test_transcribe_calls_faster_whisper_with_correct_model(self) -> None:
        """Test that transcribe calls faster-whisper with correct model and returns text."""
        emitter = MemoryTraceEmitter()
        skill = TranscriptionSkill(emitter=emitter)

        mock_model = MagicMock()
        mock_segments = [MagicMock(text="Hello world")]
        mock_info = MagicMock(language="en", duration=1.5)
        mock_model.transcribe.return_value = (mock_segments, mock_info)

        with patch("faster_whisper.WhisperModel") as mock_whisper:
            mock_whisper.return_value = mock_model

            result = await skill.transcribe("test_audio.wav")

            assert result == "Hello world"
            mock_whisper.assert_called_once_with("base", device="cpu", compute_type="int8")

    async def test_transcribe_passes_language_parameter_when_specified(self) -> None:
        """Test that transcribe passes language parameter when specified."""
        emitter = MemoryTraceEmitter()
        skill = TranscriptionSkill(emitter=emitter)

        mock_model = MagicMock()
        mock_segments = [MagicMock(text="Hola mundo")]
        mock_info = MagicMock(language="es", duration=1.5)
        mock_model.transcribe.return_value = (mock_segments, mock_info)

        with patch("faster_whisper.WhisperModel") as mock_whisper:
            mock_whisper.return_value = mock_model

            await skill.transcribe("test_audio.wav", language="es")

            mock_model.transcribe.assert_called_once_with("test_audio.wav", language="es")

    async def test_transcribe_uses_default_language_when_not_specified(self) -> None:
        """Test that transcribe uses default language when not specified."""
        emitter = MemoryTraceEmitter()
        skill = TranscriptionSkill(emitter=emitter)

        mock_model = MagicMock()
        mock_segments = [MagicMock(text="Hello world")]
        mock_info = MagicMock(language="en", duration=1.5)
        mock_model.transcribe.return_value = (mock_segments, mock_info)

        with patch("faster_whisper.WhisperModel") as mock_whisper:
            mock_whisper.return_value = mock_model

            await skill.transcribe("test_audio.wav")

            mock_model.transcribe.assert_called_once_with("test_audio.wav", language=None)

    async def test_transcribe_bytes_writes_temp_file_transcribes_deletes(self) -> None:
        """Test that transcribe_bytes writes temp file, transcribes, deletes temp file."""
        emitter = MemoryTraceEmitter()
        skill = TranscriptionSkill(emitter=emitter)

        mock_model = MagicMock()
        mock_segments = [MagicMock(text="Hello world")]
        mock_info = MagicMock(language="en", duration=1.5)
        mock_model.transcribe.return_value = (mock_segments, mock_info)

        with patch("faster_whisper.WhisperModel") as mock_whisper:
            mock_whisper.return_value = mock_model

            with patch("tempfile.NamedTemporaryFile") as mock_temp:
                mock_temp_file = MagicMock()
                mock_temp_file.name = "temp_audio.wav"
                mock_temp.__enter__ = Mock(return_value=mock_temp_file)
                mock_temp.__exit__ = Mock(return_value=False)
                mock_temp.return_value = mock_temp

                with patch("os.unlink") as mock_unlink:
                    result = await skill.transcribe_bytes(b"fake_audio_data")

                    assert result == "Hello world"
                    mock_temp_file.write.assert_called_once()
                    mock_unlink.assert_called_once()

    async def test_transcribe_raises_skill_execution_error_when_faster_whisper_not_installed(self) -> None:
        """Test that transcribe raises SkillExecutionError when faster-whisper not installed."""
        emitter = MemoryTraceEmitter()
        skill = TranscriptionSkill(emitter=emitter)

        with patch("faster_whisper.WhisperModel") as mock_whisper:
            mock_whisper.side_effect = ImportError("faster-whisper not installed")

            with pytest.raises(SkillExecutionError) as exc_info:
                await skill.transcribe("test_audio.wav")

            assert "not installed" in str(exc_info.value).lower()

    async def test_model_name_read_from_whisper_model_env_var(self) -> None:
        """Test that model name is read from WHISPER_MODEL env var."""
        os.environ["WHISPER_MODEL"] = "large"

        emitter = MemoryTraceEmitter()
        skill = TranscriptionSkill(emitter=emitter)

        mock_model = MagicMock()
        mock_segments = [MagicMock(text="Hello world")]
        mock_info = MagicMock(language="en", duration=1.5)
        mock_model.transcribe.return_value = (mock_segments, mock_info)

        with patch("faster_whisper.WhisperModel") as mock_whisper:
            mock_whisper.return_value = mock_model

            await skill.transcribe("test_audio.wav")

            mock_whisper.assert_called_once_with("large", device="cpu", compute_type="int8")

        # Clean up
        del os.environ["WHISPER_MODEL"]

    async def test_trace_event_emitted_on_transcription_with_language_in_data(self) -> None:
        """Test that trace event is emitted on transcription with language in data."""
        emitter = MemoryTraceEmitter()
        skill = TranscriptionSkill(emitter=emitter)

        mock_model = MagicMock()
        mock_segments = [MagicMock(text="Hello world")]
        mock_info = MagicMock(language="en", duration=1.5)
        mock_model.transcribe.return_value = (mock_segments, mock_info)

        with patch("faster_whisper.WhisperModel") as mock_whisper:
            mock_whisper.return_value = mock_model

            await skill.transcribe("test_audio.wav")

            events = emitter.get_events()
            transcription_events = [e for e in events if "transcription" in e.data.get("skill", "")]
            assert len(transcription_events) > 0
            assert transcription_events[0].data.get("language") == "en"

    async def test_model_loaded_lazily_not_instantiated_at_construction(self) -> None:
        """Test that model is loaded lazily, not instantiated at construction time."""
        emitter = MemoryTraceEmitter()
        
        with patch("faster_whisper.WhisperModel") as mock_whisper:
            # Create skill - should not load model yet
            skill = TranscriptionSkill(emitter=emitter)
            mock_whisper.assert_not_called()

            # Call transcribe - should load model now
            mock_model = MagicMock()
            mock_segments = [MagicMock(text="Hello world")]
            mock_info = MagicMock(language="en", duration=1.5)
            mock_model.transcribe.return_value = (mock_segments, mock_info)
            mock_whisper.return_value = mock_model

            await skill.transcribe("test_audio.wav")

            # Model should be loaded now
            mock_whisper.assert_called_once()
