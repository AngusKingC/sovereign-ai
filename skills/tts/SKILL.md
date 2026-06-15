# TTS Skill

## Description
Text-to-speech synthesis using Piper TTS subprocess. Converts text to WAV audio bytes or plays audio directly.

## Parameters
- text (str, required): Text to synthesise
- voice (str, optional): Voice model to use. Overrides default from PIPER_VOICE env var

## Output
- synthesise(): Returns WAV audio bytes
- speak(): Returns None (plays audio directly)

## Dependencies
- Piper TTS binary (from https://github.com/rhasspy/piper)
- Environment variables: PIPER_BIN (path to Piper binary, defaults to "piper"), PIPER_VOICE (default voice model)

## Hardware
No special hardware requirements. CPU-based synthesis.

## Tags
tts, text-to-speech, audio, synthesis
