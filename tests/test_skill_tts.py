"""Tests for TTS Skill."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import os

from skills.tts.skill import TTSSkill
from core.observability import MemoryTraceEmitter
from core.exceptions import SkillExecutionError


@pytest.mark.asyncio
class TestTTSSkill:
    """Tests for TTSSkill."""

    async def test_synthesise_calls_piper_subprocess_with_correct_arguments(self) -> None:
        """Test that synthesise calls Piper subprocess with correct arguments."""
        emitter = MemoryTraceEmitter()
        skill = TTSSkill(emitter=emitter)

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b"fake_wav_data", b"")

        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = mock_process

            await skill.synthesise("Hello world")

            mock_popen.assert_called_once()
            call_args = mock_popen.call_args[0][0]
            assert "piper" in call_args
            assert "--model" in call_args

    async def test_synthesise_returns_bytes_from_piper_stdout(self) -> None:
        """Test that synthesise returns bytes from Piper stdout."""
        emitter = MemoryTraceEmitter()
        skill = TTSSkill(emitter=emitter)

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b"fake_wav_data", b"")

        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = mock_process

            result = await skill.synthesise("Hello world")

            assert isinstance(result, bytes)
            assert result == b"fake_wav_data"

    async def test_speak_calls_synthesise_then_plays_audio(self) -> None:
        """Test that speak calls synthesise then plays audio."""
        emitter = MemoryTraceEmitter()
        skill = TTSSkill(emitter=emitter)

        with patch("skills.tts.skill.TTSSkill.synthesise") as mock_synthesise:
            mock_synthesise.return_value = b"fake_wav_data"

            with patch("platform.system") as mock_platform:
                mock_platform.return_value = "Windows"

                with patch("winsound.PlaySound") as mock_play:
                    with patch("tempfile.NamedTemporaryFile") as mock_temp:
                        mock_temp_file = MagicMock()
                        mock_temp_file.name = "temp.wav"
                        mock_temp.__enter__ = Mock(return_value=mock_temp_file)
                        mock_temp.__exit__ = Mock(return_value=False)
                        mock_temp.return_value = mock_temp

                        with patch("os.unlink") as mock_unlink:
                            await skill.speak("Hello world")

                            mock_synthesise.assert_called_once_with("Hello world", None)

    async def test_speak_with_explicit_voice_overrides_default(self) -> None:
        """Test that speak with explicit voice overrides default."""
        emitter = MemoryTraceEmitter()
        skill = TTSSkill(emitter=emitter)

        with patch("skills.tts.skill.TTSSkill.synthesise") as mock_synthesise:
            mock_synthesise.return_value = b"fake_wav_data"

            with patch("platform.system") as mock_platform:
                mock_platform.return_value = "Windows"

                with patch("winsound.PlaySound"):
                    with patch("tempfile.NamedTemporaryFile") as mock_temp:
                        mock_temp_file = MagicMock()
                        mock_temp_file.name = "temp.wav"
                        mock_temp.__enter__ = Mock(return_value=mock_temp_file)
                        mock_temp.__exit__ = Mock(return_value=False)
                        mock_temp.return_value = mock_temp

                        with patch("os.unlink"):
                            await skill.speak("Hello world", voice="custom_voice")

                            mock_synthesise.assert_called_once_with("Hello world", "custom_voice")

    async def test_synthesise_raises_skill_execution_error_when_piper_binary_not_found(self) -> None:
        """Test that synthesise raises SkillExecutionError when Piper binary not found."""
        emitter = MemoryTraceEmitter()
        skill = TTSSkill(emitter=emitter)

        with patch("subprocess.Popen") as mock_popen:
            mock_popen.side_effect = FileNotFoundError("piper not found")

            with pytest.raises(SkillExecutionError) as exc_info:
                await skill.synthesise("Hello world")

            assert "not found" in str(exc_info.value).lower()

    async def test_voice_read_from_piper_voice_env_var_when_not_specified(self) -> None:
        """Test that voice is read from PIPER_VOICE env var when not specified."""
        os.environ["PIPER_VOICE"] = "test_voice"

        emitter = MemoryTraceEmitter()
        skill = TTSSkill(emitter=emitter)

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b"fake_wav_data", b"")

        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = mock_process

            await skill.synthesise("Hello world")

            call_args = mock_popen.call_args[0][0]
            assert "test_voice" in call_args

        # Clean up
        del os.environ["PIPER_VOICE"]

    async def test_trace_event_emitted_on_speak_with_text_length_in_data(self) -> None:
        """Test that trace event is emitted on speak with text length in data."""
        emitter = MemoryTraceEmitter()
        skill = TTSSkill(emitter=emitter)

        with patch("skills.tts.skill.TTSSkill.synthesise") as mock_synthesise:
            mock_synthesise.return_value = b"fake_wav_data"

            with patch("platform.system") as mock_platform:
                mock_platform.return_value = "Windows"

                with patch("winsound.PlaySound"):
                    with patch("tempfile.NamedTemporaryFile") as mock_temp:
                        mock_temp_file = MagicMock()
                        mock_temp_file.name = "temp.wav"
                        mock_temp.__enter__ = Mock(return_value=mock_temp_file)
                        mock_temp.__exit__ = Mock(return_value=False)
                        mock_temp.return_value = mock_temp

                        with patch("os.unlink"):
                            await skill.speak("Hello world")

                            events = emitter.get_events()
                            tts_events = [e for e in events if "tts" in e.data.get("skill", "")]
                            assert len(tts_events) > 0
                            assert tts_events[0].data.get("text_length") == len("Hello world")

    async def test_synthesise_with_empty_text_raises_value_error(self) -> None:
        """Test that synthesise with empty text raises ValueError."""
        emitter = MemoryTraceEmitter()
        skill = TTSSkill(emitter=emitter)

        with pytest.raises(ValueError):
            await skill.synthesise("")
