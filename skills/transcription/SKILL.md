# Transcription Skill

## Description
Audio transcription using Whisper via faster-whisper library. Transcribes audio files or bytes to text.

## Parameters
- audio_path (str, required): Path to audio file (for transcribe method)
- audio_bytes (bytes, required): Audio data as bytes (for transcribe_bytes method)
- language (str, optional): Language code (e.g., "en", "es"). If not specified, auto-detect

## Output
- transcribe(): Returns transcribed text
- transcribe_bytes(): Returns transcribed text

## Dependencies
- faster-whisper>=0.10.0
- Environment variable: WHISPER_MODEL (default "base")

## Hardware
CPU-based transcription. No GPU required but recommended for faster processing.

## Tags
transcription, audio, whisper, speech-to-text
