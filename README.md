# PiHermes — AI Voice Kit for Raspberry Pi

**"Your Pi. Your AI. Our shell. Plug in and talk."**

PiHermes turns any Raspberry Pi 5 into a voice-controlled AI assistant. It uses [Hermes Agent](https://github.com/NousResearch/hermes-agent) by Nous Research as the brain, with a self-contained voice pipeline (wake word → speech-to-text → AI → text-to-speech) that runs entirely on-device.

## 🎤 What It Does

```
"Hey Bob" → openWakeWord (custom wake word model) → WebRTC VAD
→ cloud STT (~1s) → Hermes API → Piper TTS → speaker
~10s total cycle from wake to response
```

## 🛒 Kit vs DIY

| | DIY (Free) | Kit |
|---|---|---|
| Voice pipeline | ✅ Open source | ✅ Pre-installed |
| Enclosure STL | ✅ Download & print | ✅ Premium Beets3D print |
| SD Card | ❌ Flash yourself | ✅ Pre-flashed 32GB |
| USB Mic/Speaker | ❌ Source yourself | ✅ Tested bundle |
| Power Supply | ❌ Source yourself | ✅ USB-C power adapter included |
| Admin Console | ✅ Hermes plugin | ✅ Pre-configured |

**Kit includes:** 3D-printed enclosure + pre-flashed SD card + USB mic/speaker + USB-C power supply + setup script. You bring your own Pi 5. Everything else to run the voice assistant is in the box.

## ⚡ Quick Install (DIY)

```bash
git clone https://github.com/bbugs280/pihermes
cd pihermes
bash setup.sh
```

This installs:
- Voice pipeline (`beets_voice_full.py`) + systemd service
- Hermes dashboard plugin (admin console)
- openWakeWord + custom wake word model
- Piper TTS + voice models
- WebRTC VAD for smart silence detection

## 📦 What's Inside

```
pihermes/
├── beets_voice_full.py        ← Voice pipeline (wake → STT → Hermes → TTS)
├── setup.sh                    ← One-command installer
├── hermes-plugin/              ← Hermes Agent plugin
│   ├── plugin.yaml
│   ├── __init__.py             ← Tools: pihermes_status, pihermes_restart
│   ├── dashboard/
│   │   ├── manifest.json
│   │   ├── dist/index.js       ← Admin console tab
│   │   ├── dist/style.css
│   │   └── plugin_api.py       ← FastAPI backend routes
│   └── plugin_api.py
├── enclosure/                  ← Kit components & 3D-printable STL files
│   └── README.md
├── docs/
│   └── quickstart.md
└── scripts/
    └── flash-sd.sh              ← SD card image builder
```

## 🔧 Requirements

- Raspberry Pi 5 (or Pi 4 with USB audio dongle)
- USB microphone + speaker (or combo dongle)
- Hermes Agent installed
- LLM API key (any Hermes-supported provider)
- STT provider API key (cloud STT via configurable endpoint; offline whisper.cpp fallback included)
- Python 3.10+

## 🏗️ Architecture

```
USB Audio Dongle          Raspberry Pi 5
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

## 🎯 Kit Enclosure

The PiHermes enclosure is more than a 3D-printed shell. Each kit includes:

- **Premium Beets3D enclosure** — 3D-printed in sandstone or SLA resin
- **USB-C power supply** — powers your Pi 5, no separate adapter needed
- **USB mic/speaker combo** — tested and matched to the enclosure acoustics
- **Pre-flashed SD card** — plug in and talk, zero setup
- **Internal cable management** — clean routing for power and audio

Design goals: the enclosure doubles as an acoustic chamber for the speaker, includes ventilation for Pi 5 thermals, and optionally supports a GPIO LED ring for visual status feedback.

## 🌐 Community

- **Hermes Agent:** [github.com/NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)
- **PiHermes discussions:** [GitHub Discussions](https://github.com/bbugs280/pihermes/discussions)

## 📄 License

Apache 2.0 — see [LICENSE](LICENSE)
