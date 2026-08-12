# Hermes Wakeword Pipe — Voice Pipeline Plugin for Hermes Agent

A **Hermes Agent plugin** that adds an always-listening voice interface to any Hermes installation. Wake word detection → speech-to-text → Hermes LLM → text-to-speech, all managed through a dashboard admin console.

## 🎤 What It Does

```
"Hey Bob" → openWakeWord (custom wake word model) → WebRTC VAD
→ cloud STT (~1s) → Hermes API → Piper TTS → speaker
~10s total cycle from wake to response
```

## ⚡ Quick Install

```bash
git clone https://github.com/bbugs280/hermes-wakeword-pipe
cd hermes-wakeword-pipe
bash setup.sh
```

This installs:
- Voice pipeline (`hermes_voice.py`) + systemd service
- Hermes dashboard plugin (admin console)
- openWakeWord + custom wake word model
- Piper TTS + voice models
- WebRTC VAD for smart silence detection

## 📦 What's Inside

```
hermes-wakeword-pipe/
├── hermes_voice.py        ← Voice pipeline (wake → STT → Hermes → TTS)
├── setup.sh                    ← One-command installer
├── hermes-plugin/              ← Hermes Agent plugin
│   ├── plugin.yaml
│   ├── __init__.py             ← Tools: hermes-wakeword-pipe_status, hermes-wakeword-pipe_restart
│   ├── dashboard/
│   │   ├── manifest.json
│   │   ├── dist/index.js       ← Admin console tab
│   │   ├── dist/style.css
│   │   └── plugin_api.py       ← FastAPI backend routes
│   └── plugin_api.py
├── docs/
│   ├── quickstart.md
│   ├── admin-console-spec.md
│   └── changes/
```

## 🔧 Requirements

- Linux machine (or any Linux with USB audio)
- USB microphone + speaker (or combo dongle)
- Hermes Agent installed
- LLM API key (any Hermes-supported provider)
- STT provider API key (cloud STT via configurable endpoint; offline whisper.cpp fallback included)
- Python 3.10+

## 🏗️ Architecture

```
USB Audio Dongle          Linux machine
┌──────────────┐         ┌──────────────────────────┐
│ arecord (mic)│  PCM    │ openWakeWord (onnx)      │
│      ↕       │←───────→│  → Wake word detection   │
│ aplay (spkr) │         │       ↓                  │
└──────────────┘         │ WebRTC VAD (silence)     │
                         │       ↓                  │
                         │ Cloud STT (configurable) │
                         │  + whisper.cpp fallback  │
                         │       ↓                  │
                         │ Hermes API (localhost)    │
                         │       ↓                  │
                         │ Piper TTS → speaker      │
                         └──────────────────────────┘
```

## 🌐 Community

- **Hermes Agent:** [github.com/NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)
- **Hermes Wakeword Pipe discussions:** [GitHub Discussions](https://github.com/bbugs280/hermes-wakeword-pipe/discussions)

## 📄 License

Apache 2.0 — see [LICENSE](LICENSE)
