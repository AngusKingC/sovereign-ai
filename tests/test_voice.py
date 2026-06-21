"""
Tests for voice interface and voice daemon.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.observability import (
    MemoryTraceEmitter,
)
from core.voice_interface import VoiceConfig, VoiceCommand, VoiceInterface
from core.schemas import Task
from system.voice_daemon import VoiceDaemon


class TestVoiceConfig:
    """Tests for VoiceConfig Pydantic model."""

    def test_voice_config_constructs_with_correct_defaults(self):
        """VoiceConfig constructs with correct defaults (wake_word="jarvis", enabled=True)."""
        config = VoiceConfig()
        assert config.wake_word == "jarvis"
        assert config.enabled is True
        assert config.wake_word_sensitivity == 0.5
        assert config.stt_model == "base"
        assert config.tts_voice is None
        assert config.noise_threshold == 0.01
        assert config.silence_timeout_ms == 1500

    def test_voice_config_wake_word_sensitivity_rejects_values_outside_0_to_1(self):
        """VoiceConfig.wake_word_sensitivity rejects values outside 0.0-1.0."""
        with pytest.raises(ValueError):
            VoiceConfig(wake_word_sensitivity=1.5)

        with pytest.raises(ValueError):
            VoiceConfig(wake_word_sensitivity=-0.5)

    def test_voice_config_silence_timeout_ms_rejects_values_below_100(self):
        """VoiceConfig.silence_timeout_ms rejects values below 100."""
        with pytest.raises(ValueError):
            VoiceConfig(silence_timeout_ms=50)


class TestVoiceCommand:
    """Tests for VoiceCommand Pydantic model."""

    def test_voice_command_constructs_with_required_fields_and_correct_defaults(self):
        """VoiceCommand constructs with required fields and correct defaults."""
        command = VoiceCommand(transcript="hello world", confidence=0.9)
        assert command.transcript == "hello world"
        assert command.confidence == 0.9
        assert command.wake_word_detected is False
        assert command.command_id is not None
        assert command.detected_at is not None

    def test_voice_command_confidence_rejects_values_outside_0_to_1(self):
        """VoiceCommand.confidence rejects values outside 0.0-1.0."""
        with pytest.raises(ValueError):
            VoiceCommand(transcript="hello", confidence=1.5)

        with pytest.raises(ValueError):
            VoiceCommand(transcript="hello", confidence=-0.5)


class TestVoiceInterface:
    """Tests for VoiceInterface class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.emitter = MemoryTraceEmitter()
        self.voice = VoiceInterface(emitter=self.emitter)

    @pytest.mark.asyncio
    async def test_detect_wake_word_returns_true_when_transcript_contains_wake_word_case_insensitive(self):
        """detect_wake_word() returns True when transcript contains wake word (case-insensitive)."""
        with patch.object(self.voice, "_transcribe", return_value="Jarvis, turn on the lights"):
            result = await self.voice.detect_wake_word(b"audio")
            assert result is True

    @pytest.mark.asyncio
    async def test_detect_wake_word_returns_false_when_transcript_does_not_contain_wake_word(self):
        """detect_wake_word() returns False when transcript does not contain wake word."""
        with patch.object(self.voice, "_transcribe", return_value="turn on the lights"):
            result = await self.voice.detect_wake_word(b"audio")
            assert result is False

    @pytest.mark.asyncio
    async def test_detect_wake_word_emits_trace_event_when_wake_word_detected(self):
        """detect_wake_word() emits trace event when wake word detected."""
        with patch.object(self.voice, "_transcribe", return_value="Jarvis, turn on the lights"):
            await self.voice.detect_wake_word(b"audio")

        events = self.emitter.get_events()
        assert len(events) == 1
        assert events[0].event_type == "voice_wake_word_detected"
        assert events[0].component == "voice"
        assert events[0].level == "info"

    @pytest.mark.asyncio
    async def test_detect_wake_word_does_not_emit_trace_event_when_wake_word_not_detected(self):
        """detect_wake_word() does NOT emit trace event when wake word not detected."""
        with patch.object(self.voice, "_transcribe", return_value="turn on the lights"):
            await self.voice.detect_wake_word(b"audio")

        events = self.emitter.get_events()
        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_process_command_returns_voice_command_with_correct_transcript(self):
        """process_command() returns VoiceCommand with correct transcript."""
        with patch.object(self.voice, "_transcribe", return_value="hello world"):
            command = await self.voice.process_command(b"audio")

        assert command is not None
        assert command.transcript == "hello world"
        assert command.confidence == 1.0

    @pytest.mark.asyncio
    async def test_process_command_returns_none_when_transcript_is_empty(self):
        """process_command() returns None when transcript is empty."""
        with patch.object(self.voice, "_transcribe", return_value=""):
            command = await self.voice.process_command(b"audio")

        assert command is None

    @pytest.mark.asyncio
    async def test_process_command_emits_trace_event_with_transcript_length_not_transcript_text(self):
        """process_command() emits trace event with transcript length (not transcript text)."""
        with patch.object(self.voice, "_transcribe", return_value="hello world"):
            await self.voice.process_command(b"audio")

        events = self.emitter.get_events()
        assert len(events) == 1
        assert events[0].event_type == "voice_command_received"
        assert events[0].data["transcript_length"] == 11
        assert "transcript" not in events[0].data

    @pytest.mark.asyncio
    async def test_start_listening_sets_listening_true_and_emits_trace_event(self):
        """start_listening() sets _listening=True and emits trace event."""
        await self.voice.start_listening()

        assert self.voice._listening is True

        events = self.emitter.get_events()
        assert len(events) == 1
        assert events[0].event_type == "voice_listening_started"
        assert events[0].component == "voice"
        assert events[0].level == "info"

    @pytest.mark.asyncio
    async def test_stop_listening_sets_listening_false_and_emits_trace_event(self):
        """stop_listening() sets _listening=False and emits trace event."""
        await self.voice.start_listening()
        self.emitter.clear()

        await self.voice.stop_listening()

        assert self.voice._listening is False

        events = self.emitter.get_events()
        assert len(events) == 1
        assert events[0].event_type == "voice_listening_stopped"
        assert events[0].component == "voice"
        assert events[0].level == "info"

    @pytest.mark.asyncio
    async def test_notify_emits_trace_event_with_message_length_not_message_text(self):
        """notify() emits trace event with message length (not message text)."""
        await self.voice.notify("hello world")

        events = self.emitter.get_events()
        assert len(events) == 1
        assert events[0].event_type == "voice_notification_sent"
        assert events[0].data["message_length"] == 11
        assert "message" not in events[0].data

    @pytest.mark.asyncio
    async def test_transcribe_delegates_to_transcription_skill_when_skill_is_set(self):
        """_transcribe() delegates to transcription_skill.transcribe_bytes() when skill is set."""
        mock_skill = AsyncMock()
        mock_skill.transcribe_bytes.return_value = "hello world"
        voice = VoiceInterface(emitter=self.emitter, transcription_skill=mock_skill)

        result = await voice._transcribe(b"audio")

        assert result == "hello world"
        mock_skill.transcribe_bytes.assert_called_once_with(b"audio")

    @pytest.mark.asyncio
    async def test_transcribe_returns_empty_string_when_no_transcription_skill_injected(self):
        """_transcribe() returns "" when no transcription skill injected."""
        result = await self.voice._transcribe(b"audio")

        assert result == ""

    @pytest.mark.asyncio
    async def test_notify_calls_tts_skill_speak_when_skill_is_set(self):
        """notify() calls tts_skill.speak() when skill is set."""
        mock_skill = AsyncMock()
        voice = VoiceInterface(emitter=self.emitter, tts_skill=mock_skill)

        await voice.notify("hello world")

        mock_skill.speak.assert_called_once_with("hello world")

    @pytest.mark.asyncio
    async def test_notify_falls_back_to_print_when_no_tts_skill_injected(self):
        """notify() falls back to print when no TTS skill injected."""
        with patch("builtins.print") as mock_print:
            await self.voice.notify("hello world")

            mock_print.assert_called_once_with("[VOICE] hello world")


class TestVoiceDaemon:
    """Tests for VoiceDaemon class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.emitter = MemoryTraceEmitter()
        self.voice = VoiceInterface(emitter=self.emitter)
        self.orchestrator = AsyncMock()
        self.approval_gate = MagicMock()
        self.daemon = VoiceDaemon(
            voice_interface=self.voice,
            orchestrator=self.orchestrator,
            approval_gate=self.approval_gate,
            emitter=self.emitter,
        )

    @pytest.mark.asyncio
    async def test_start_calls_voice_interface_start_listening_and_sets_running_true(self):
        """start() calls voice_interface.start_listening() and sets _running=True."""
        await self.daemon.start()

        assert self.daemon._running is True
        assert self.voice._listening is True

    @pytest.mark.asyncio
    async def test_stop_calls_voice_interface_stop_listening_and_sets_running_false(self):
        """stop() calls voice_interface.stop_listening() and sets _running=False."""
        await self.daemon.start()
        await self.daemon.stop()

        assert self.daemon._running is False
        assert self.voice._listening is False

    @pytest.mark.asyncio
    async def test_run_once_submits_command_to_orchestrator_when_wake_word_detected(self):
        """run_once() submits command to orchestrator when wake word detected."""
        with patch.object(self.voice, "_transcribe", return_value="Jarvis, turn on the lights"):
            command = await self.daemon.run_once(b"audio")

        assert command is not None
        self.orchestrator.submit_task.assert_called_once()
        submitted_task = self.orchestrator.submit_task.call_args[0][0]
        assert submitted_task.intent == "Jarvis, turn on the lights"

    @pytest.mark.asyncio
    async def test_run_once_returns_none_when_wake_word_not_detected(self):
        """run_once() returns None when wake word not detected."""
        with patch.object(self.voice, "_transcribe", return_value="turn on the lights"):
            command = await self.daemon.run_once(b"audio")

        assert command is None
        self.orchestrator.submit_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_submit_command_creates_task_from_command_transcript_and_submits_to_orchestrator(self):
        """_submit_command() creates Task from command transcript and submits to orchestrator."""
        command = VoiceCommand(transcript="hello world", confidence=1.0)

        await self.daemon._submit_command(command)

        self.orchestrator.submit_task.assert_called_once()
        submitted_task = self.orchestrator.submit_task.call_args[0][0]
        assert isinstance(submitted_task, Task)
        assert submitted_task.intent == "hello world"

    @pytest.mark.asyncio
    async def test_get_audio_chunk_delegates_to_audio_capture_when_set(self):
        """VoiceDaemon._get_audio_chunk() delegates to audio_capture.capture_chunk() when set."""
        mock_capture = AsyncMock()
        mock_capture.capture_chunk.return_value = b"audio_data"
        daemon = VoiceDaemon(
            voice_interface=self.voice,
            orchestrator=self.orchestrator,
            approval_gate=self.approval_gate,
            audio_capture=mock_capture,
            emitter=self.emitter,
        )

        result = await daemon._get_audio_chunk()

        assert result == b"audio_data"
        mock_capture.capture_chunk.assert_called_once()
