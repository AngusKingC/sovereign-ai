"""
Voice Daemon - background daemon that runs the voice loop and submits commands to the orchestrator.

Single responsibility: Manage the voice interface lifecycle and submit voice commands to the orchestrator.
This module defines the voice daemon that will be wired to real microphone capture in Prompt 33.5.
"""

import asyncio

from core.observability import (
    TraceComponent,
    TraceEventType,
    TraceLevel,
    TraceEvent,
    TraceEmitter,
    MemoryTraceEmitter,
)
from core.voice_interface import VoiceInterface, VoiceCommand
from core.schemas import Task


class VoiceDaemon:
    """Background daemon that runs the voice loop and submits commands to the orchestrator."""

    def __init__(
        self,
        voice_interface: VoiceInterface,
        orchestrator,
        approval_gate,
        audio_capture=None,   # AudioCapture | None
        emitter: TraceEmitter | None = None,
    ):
        """Initialize the voice daemon."""
        self._voice = voice_interface
        self._orchestrator = orchestrator
        self._approval_gate = approval_gate
        self._audio_capture = audio_capture
        self._emitter = emitter or MemoryTraceEmitter()
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the voice daemon."""
        await self._voice.start_listening()
        self._running = True
        self._task = asyncio.create_task(self._loop())

        try:
            event = TraceEvent(
                event_type=TraceEventType.COMPONENT_START,
                component=TraceComponent.VOICE,
                level=TraceLevel.INFO,
                message="Voice daemon started",
                data={},
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            pass

    async def stop(self) -> None:
        """Stop the voice daemon."""
        self._running = False

        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        await self._voice.stop_listening()

        try:
            event = TraceEvent(
                event_type=TraceEventType.COMPONENT_STOP,
                component=TraceComponent.VOICE,
                level=TraceLevel.INFO,
                message="Voice daemon stopped",
                data={},
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            pass

    async def _loop(self) -> None:
        """Main voice loop - continuously listen for wake word and process commands."""
        while self._running:
            try:
                chunk = await self._get_audio_chunk()

                if await self._voice.detect_wake_word(chunk):
                    await self._voice.notify("Listening...")
                    command_chunk = await self._get_audio_chunk()
                    command = await self._voice.process_command(command_chunk)

                    if command is not None:
                        await self._submit_command(command)

                await asyncio.sleep(0.1)

            except asyncio.CancelledError:
                break
            except Exception:
                pass

    async def _get_audio_chunk(self) -> bytes:
        """
        Capture audio chunk using AudioCapture.

        Returns:
            Audio data as bytes (empty bytes if no AudioCapture injected)
        """
        if self._audio_capture is not None:
            return await self._audio_capture.capture_chunk()
        return b""  # Preserves stub behaviour

    async def _submit_command(self, command: VoiceCommand) -> None:
        """
        Submit a voice command to the orchestrator.

        Args:
            command: Voice command to submit
        """
        try:
            # Create a Task from the command transcript as intent
            task = Task(
                task_id=command.command_id,
                intent=command.transcript,
                complexity_score=0.5,
                priority="normal",
                status="received",
                current_state="received",
                created_at=command.detected_at,
            )

            # Submit to orchestrator
            await self._orchestrator.submit_task(task)

            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.VOICE,
                    level=TraceLevel.INFO,
                    message="Voice command submitted to orchestrator",
                    data={
                        "command_id": str(command.command_id),
                        "task_id": str(task.task_id),
                    },
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception:
                pass

        except Exception:
            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.VOICE,
                    level=TraceLevel.ERROR,
                    message="Failed to submit voice command to orchestrator",
                    data={
                        "command_id": str(command.command_id),
                    },
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception:
                pass

    async def run_once(self, audio_bytes: bytes) -> VoiceCommand | None:
        """
        Process a single audio chunk — for testing and one-shot use.

        Args:
            audio_bytes: Audio data as bytes

        Returns:
            VoiceCommand if wake word detected and command processed, None otherwise
        """
        if await self._voice.detect_wake_word(audio_bytes):
            await self._voice.notify("Listening...")
            command = await self._voice.process_command(audio_bytes)

            if command is not None:
                await self._submit_command(command)
                return command

        return None
