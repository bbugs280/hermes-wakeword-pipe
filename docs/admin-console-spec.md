# PiHermes Admin Console — Specification v0.1

## Overview

The PiHermes admin console is a **dashboard plugin** for Hermes Agent. It appears as a "PiHermes" tab in the Hermes web dashboard (http://<pi>:9119) and provides configuration and monitoring for the voice pipeline.

## Architecture

```
Browser (Hermes Dashboard)          Raspberry Pi 5
┌──────────────────────────┐       ┌─────────────────────────┐
│ PiHermes tab (React)     │──REST─│ plugin_api.py (FastAPI)  │
│  → status card           │       │  → /api/plugins/pihermes/│
│  → voice config          │       │     status, restart,     │
│  → wake word picker      │       │     config, audio-test   │
│  → log viewer            │       │       ↓                  │
└──────────────────────────┘       │ systemctl pihermes-voice │
                                   │ beets_voice_full.py      │
                                   └─────────────────────────┘
```

## Pages / Sections

### 1. Status Dashboard

Shows pipeline health at a glance.

```
┌─ Pipeline Status ──────────────────────┐
│ Status: 🟢 Running (uptime: 2h 14m)    │
│ [Restart] [Stop]                       │
│                                         │
│ Last interaction: 3 min ago             │
│ Query: "what's the weather"             │
│ Response: "It's sunny, 28°C in HK"      │
│ Cycle time: 11.2s                       │
└─────────────────────────────────────────┘
```

**API endpoint:** `GET /api/plugins/pihermes/status`
**Response:** `{ pipeline_running, uptime, last_query, last_response, cycle_time_ms }`

### 2. Voice Configuration

Control how the assistant sounds.

```
┌─ Voice ────────────────────────────────┐
│ TTS Voice:  [lessac (female) ▾]        │
│             [ryan (male)               │
│              alba (female)             │
│              aru (male)]               │
│                                         │
│ Speaking speed: [━━━━●━━━] 1.0x        │
│                                         │
│ Response length:                        │
│   ○ Short (1 sentence)                 │
│   ● Normal (2-3 sentences)             │
│   ○ Detailed                           │
└─────────────────────────────────────────┘
```

**API:** `GET /api/plugins/pihermes/config` → `{ voice, speed, brevity }`
**API:** `POST /api/plugins/pihermes/config` → update settings

### 3. Wake Word Configuration

Pick or customize the activation phrase.

```
┌─ Wake Word ────────────────────────────┐
│ Preset:  [Hey Bob     ▾]               │
│          [Hey Hermes                    │
│           Hey Jarvis                    │
│           Custom...]                    │
│                                         │
│ Threshold: [━━━━●━━━━━━━] 0.65         │
│ (higher = fewer false triggers)         │
│                                         │
│ [Test Wake Word] — flash indicator      │
└─────────────────────────────────────────┘
```

**API:** `GET /api/plugins/pihermes/config` → `{ wake_word, wake_threshold }`

### 4. LLM Configuration

The AI brain behind the voice.

```
┌─ AI Model ─────────────────────────────┐
│ Provider:  [DeepSeek     ▾]            │
│            [OpenAI                       │
│             Anthropic                    │
│             Ollama (local)]              │
│                                         │
│ Model:     [deepseek-v4-flash ▾]       │
│                                         │
│ API Key:   [••••••••••••••] [Test]     │
│                                         │
│ System prompt:                          │
│ ┌─────────────────────────────────────┐ │
│ │ You are a voice assistant. Be...    │ │
│ │                                     │ │
│ └─────────────────────────────────────┘ │
│ [Save] [Reset to Default]               │
└─────────────────────────────────────────┘
```

**API:** `POST /api/plugins/pihermes/config` → update model/provider/key/prompt

### 5. Audio Hardware

Test and configure microphone and speaker.

```
┌─ Audio ────────────────────────────────┐
│ Microphone: [plughw:2,0 ▾]             │
│ Speaker:    [plughw:2,0 ▾]             │
│                                         │
│ Mic gain:   [━━━━━━●━━━] 80%           │
│ Volume:     [━━━━━━━●━━] 90%           │
│                                         │
│ [🎤 Test Mic]  [🔊 Test Speaker]        │
│                                         │
│ VAD sensitivity:                        │
│   ○ Low (0)  ● Normal (2)  ○ High (3)  │
└─────────────────────────────────────────┘
```

**API:** `POST /api/plugins/pihermes/audio-test` → `{ test_type: "mic"|"speaker", result }`

### 6. Logs

Live pipeline output.

```
┌─ Logs ─────────────────────────────────┐
│ [🔄 Live] [⚠ Errors] [⬇ Download]      │
│                                         │
│ ┌─────────────────────────────────────┐ │
│ │ [17:05:01] 🔔 Wake word! (0.82)    │ │
│ │ [17:05:01] 🎤 Listening...         │ │
│ │ [17:05:04] 🎤 Recorded 2.8s        │ │
│ │ [17:05:05] ☁️ STT (cloud, 987ms)   │ │
│ │ [17:05:05] 🤔 Asking: "weather?"   │ │
│ │ [17:05:07] 🤖 Response (2147ms)    │ │
│ │ [17:05:07] 🔊 Speaking (84 chars)  │ │
│ └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

**API:** `GET /api/plugins/pihermes/logs?lines=50&filter=all|errors`

## Data Flow

```
User clicks "Restart"
  → POST /api/plugins/pihermes/restart
  → plugin_api.py: subprocess.run(["systemctl", "restart", "pihermes-voice"])
  → JSON response: { success: true }
  → Dashboard updates status badge

User changes voice
  → POST /api/plugins/pihermes/config { voice: "ryan-high" }
  → plugin_api.py: write config → restart pipeline
  → JSON response: { success: true, changes: { voice: "ryan-high" } }
  → Dashboard shows confirmation + new voice in status
```

## Acceptance Criteria

### Status Dashboard
- [x] Shows pipeline running/stopped/error
- [x] Restart button works (systemctl restart)
- [ ] Shows uptime
- [ ] Shows last interaction details

### Voice Config
- [ ] Voice dropdown (lessac, ryan, alba, aru)
- [ ] Speed slider
- [ ] Response brevity toggle
- [ ] Changes persist after restart

### Wake Word
- [ ] Preset picker (Hey Bob, Hey Hermes, Hey Jarvis)
- [ ] Threshold slider
- [ ] Test button triggers visual feedback

### LLM Config
- [ ] Provider dropdown
- [ ] Model picker (per provider)
- [ ] API key input (masked) + test button
- [ ] System prompt editor
- [ ] Save + reset to default

### Audio Hardware
- [ ] Device dropdowns (populated from arecord/aplay)
- [ ] Gain + volume sliders
- [ ] Mic test (record → playback)
- [ ] Speaker test (play tone)
- [ ] VAD sensitivity selector

### Logs
- [x] Live log tail (implemented)
- [ ] Filter: all / errors only
- [ ] Download button

### Service Control
- [x] Restart pipeline
- [ ] Stop pipeline
- [ ] Start on boot toggle
- [ ] Update pipeline (git pull)

## Current State vs Spec

| Section | Implemented | Missing |
|---------|------------|---------|
| Pipeline status | ✅ Running/stopped badge | Uptime, last interaction |
| Restart button | ✅ | Stop, start-on-boot |
| Log viewer | ✅ Live tail | Filter, download |
| Voice config | ❌ | Everything |
| Wake word | ❌ | Everything |
| LLM config | ❌ | Everything |
| Audio hardware | ❌ | Everything |

## Next Build Priority

1. Voice config (TTS voice picker + speed) — highest user-facing impact
2. LLM config (provider + model + API key) — essential for any user
3. Wake word config (presets + threshold)
4. Audio hardware (device picker + test buttons)
5. Full status (uptime, last interaction, cycle time)
