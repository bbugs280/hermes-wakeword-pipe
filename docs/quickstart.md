# Hermes Wakeword Pipe — Quick Start Guide

## Prerequisites

- Linux machine (or any x86/ARM Linux)
- USB microphone + speaker (or combo audio dongle)
- Hermes Agent installed
- LLM API key (any Hermes-compatible provider)
- STT API key (for cloud speech-to-text; offline whisper.cpp fallback included)
- Python 3.10+

## Install (3 commands)

```bash
# 1. Clone the repo
git clone https://github.com/bbugs280/hermes-wakeword-pipe
cd hermes-wakeword-pipe

# 2. Run the installer
bash setup.sh

# 3. Start the voice pipeline
systemctl --user enable --now hermes-wakeword-pipe-voice
```

## Verify

1. Open Hermes dashboard: `http://<host>:9119`
2. Click the **Hermes Wakeword Pipe** tab — you should see "Running" status
3. Say **"Hey Bob"** — it should beep and respond

## Configuration

The voice pipeline supports configurable STT backends. By default it uses cloud STT with local whisper.cpp fallback. To configure:

```bash
# Edit the pipeline config
nano ~/.hermes/voice/hermes_voice.py

# Key settings:
#   STT provider (cloud endpoint) — configure your preferred STT API
#   Wake word — change WAKE_WORD and update the .onnx model path
#   Voice — swap PIPER_MODEL for a different Piper voice
#   LLM model — change the model in ask_hermes()
```

## Troubleshooting

```bash
# Check pipeline status
systemctl --user status hermes-wakeword-pipe-voice

# View logs
journalctl --user -u hermes-wakeword-pipe-voice -f

# Restart
systemctl --user restart hermes-wakeword-pipe-voice

# Test mic/speaker
arecord -D plughw:2,0 -d 2 test.wav
aplay -D plughw:2,0 test.wav
```

## Architecture

```
USB Audio → openWakeWord → WebRTC VAD → Cloud STT (configurable)
→ Hermes API (localhost:8642) → Piper TTS → USB Speaker
```

Offline whisper.cpp fallback runs automatically if cloud STT is unreachable.

## Next Steps

- [Configure wake word](docs/wake-word.md) (coming soon)
- [Change voice](docs/voice.md) (coming soon)
- [Admin console](http://localhost:9119/hermes-wakeword-pipe)
