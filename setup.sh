#!/usr/bin/env bash
# Hermes Wakeword Pipe setup — one-command installer for the voice pipeline + Hermes plugin.
#
# Usage: bash setup.sh
#
# Installs:
#   1. Voice pipeline deps (openWakeWord, piper-tts, webrtcvad, numpy)
#   2. Plugin into ~/.hermes/plugins/hermes-wakeword-pipe/
#   3. Systemd service for auto-start on boot
#   4. Voice models (Piper en_US-lessac-medium, custom wake word)

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
HERMES_VENV="${HOME}/.hermes/hermes-agent/venv"
HERMES_PLUGINS="${HOME}/.hermes/plugins/hermes-wakeword-pipe"
VOICE_DIR="${HOME}/.hermes/voice"
PIPER_VOICES="${HOME}/.hermes/piper-voices"

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}   Hermes Wakeword Pipe Voice Pipeline Installer${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""

# ── 1. Check prerequisites ──────────────────────────
echo -e "${YELLOW}[1/5] Checking prerequisites...${NC}"

if [ ! -d "$HERMES_VENV" ]; then
    echo -e "${RED}X Hermes Agent not found at $HERMES_VENV${NC}"
    echo "  Install Hermes first: https://hermes-agent.nousresearch.com"
    exit 1
fi

if ! grep -q "API_SERVER_ENABLED=true" "${HOME}/.hermes/.env" 2>/dev/null; then
    echo -e "${YELLOW}! Hermes API server not enabled. Adding to .env...${NC}"
    echo "API_SERVER_ENABLED=true" >> "${HOME}/.hermes/.env"
    echo "API_SERVER_KEY=hermes-wakeword-pipe-local-$(openssl rand -hex 8)" >> "${HOME}/.hermes/.env"
    echo -e "${GREEN}+ API server enabled${NC}"
fi

# ── 2. Install Python deps ──────────────────────────
echo -e "${YELLOW}[2/5] Installing Python dependencies...${NC}"
"$HERMES_VENV/bin/pip" install -q openwakeword piper-tts webrtcvad numpy
echo -e "${GREEN}+ Python deps installed${NC}"

# ── 3. Copy plugin ──────────────────────────────────
echo -e "${YELLOW}[3/5] Installing Hermes plugin...${NC}"
mkdir -p "$HERMES_PLUGINS"
cp -r "$REPO_DIR/hermes-plugin/"* "$HERMES_PLUGINS/"
echo -e "${GREEN}+ Plugin installed to $HERMES_PLUGINS${NC}"

# ── 4. Copy voice pipeline ──────────────────────────
echo -e "${YELLOW}[4/5] Installing voice pipeline...${NC}"
mkdir -p "$VOICE_DIR"
cp "$REPO_DIR/hermes_voice.py" "$VOICE_DIR/"
echo -e "${GREEN}+ Pipeline installed to $VOICE_DIR${NC}"

# Download Piper voice models if not present
mkdir -p "$PIPER_VOICES"
_voice_base="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US"
for _voice in "lessac/medium/en_US-lessac-medium" "ryan/high/en_US-ryan-high" "ryan/medium/en_US-ryan-medium"; do
    _voice_name="${_voice##*/}"
    if [ ! -f "$PIPER_VOICES/${_voice_name}.onnx" ]; then
        echo -e "${YELLOW}  Downloading Piper voice (${_voice_name})...${NC}"
        curl -sL -o "$PIPER_VOICES/${_voice_name}.onnx" "$_voice_base/${_voice}.onnx"
        curl -sL -o "$PIPER_VOICES/${_voice_name}.onnx.json" "$_voice_base/${_voice}.onnx.json"
        echo -e "${GREEN}  + Voice model downloaded${NC}"
    fi
done

# ── 5. Install systemd service ──────────────────────
echo -e "${YELLOW}[5/5] Installing systemd service...${NC}"

SERVICE_CONTENT="[Unit]
Description=Hermes Wakeword Pipe Voice Pipeline
After=network-online.target sound.target
Wants=network-online.target

[Service]
Type=simple
User=${USER}
WorkingDirectory=${VOICE_DIR}
Environment=\"PATH=${HERMES_VENV}/bin:/usr/bin:/bin\"
Environment=\"ONNXRUNTIME_LOG_SEVERITY=3\"
ExecStartPre=/bin/bash -c 'amixer -c 2 set PCM 100% 2>/dev/null || true'
ExecStartPre=/bin/bash -c 'pkill -f arecord.*plughw 2>/dev/null || true'
ExecStart=${HERMES_VENV}/bin/python3 -u ${VOICE_DIR}/hermes_voice.py
ExecStop=/bin/bash -c 'pkill -f hermes_voice.py'
Restart=always
RestartSec=5
LimitNOFILE=4096

[Install]
WantedBy=multi-user.target"

if systemctl --user list-units &>/dev/null; then
    mkdir -p "${HOME}/.config/systemd/user"
    echo "$SERVICE_CONTENT" > "${HOME}/.config/systemd/user/hermes-wakeword-pipe-voice.service"
    systemctl --user daemon-reload
    echo -e "${GREEN}+ User systemd service installed${NC}"
    echo ""
    echo -e "${GREEN}============================================${NC}"
    echo -e "${GREEN}   Setup Complete!${NC}"
    echo -e "${GREEN}============================================${NC}"
    echo ""
    echo "  Start voice pipeline:"
    echo "    systemctl --user enable --now hermes-wakeword-pipe-voice"
    echo ""
    echo "  View dashboard:"
    echo "    http://localhost:9119 -> Hermes Wakeword Pipe tab"
    echo ""
    echo "  Test: say 'Hey Bob' to start talking!"
else
    echo -e "${YELLOW}! Could not install systemd service (not running under systemd?)${NC}"
    echo "  Manual start: python3 ${VOICE_DIR}/hermes_voice.py"
fi
