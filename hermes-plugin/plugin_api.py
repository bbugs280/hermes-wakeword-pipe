"""PiHermes plugin API — FastAPI routes for the dashboard."""

from fastapi import APIRouter, HTTPException
import subprocess
import os
import json
from pathlib import Path

router = APIRouter()
PIPELINE_SCRIPT = str(Path.home() / "beets_voice_full.py")
LOG_PATH = "/tmp/voice_v21.log"
CONFIG_PATH = str(Path.home() / ".hermes" / "pihermes_config.json")


def _run(cmd: list[str], timeout: int = 10) -> tuple[bool, str, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", "timeout"
    except Exception as e:
        return False, "", str(e)


def _pipeline_running() -> bool:
    """Check if pipeline is running (via pgrep, not just systemd)."""
    ok, stdout, _ = _run(["pgrep", "-f", "beets_voice_full.py"])
    return ok and len(stdout) > 0


def _load_config() -> dict:
    """Load PiHermes config from disk."""
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "tts_voice": "en_US-lessac-medium",
            "wake_word": "hey_bob",
            "wake_threshold": 0.65,
            "stt_provider": "cloud",
            "stt_endpoint": "",
            "max_tokens": 80,
        }


def _save_config(config: dict):
    """Save PiHermes config to disk."""
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


@router.get("/status")
async def get_status():
    """Check if voice pipeline is running and return recent log."""
    running = _pipeline_running()

    log_ok, log_out, _ = _run(["tail", "-5", LOG_PATH])
    recent_log = log_out if log_ok else "log unavailable"

    # Get uptime if running
    uptime = ""
    if running:
        ok, pid, _ = _run(["pgrep", "-f", "beets_voice_full.py"])
        if ok:
            ok2, etime, _ = _run(["ps", "-o", "etime=", "-p", pid.split("\n")[0]])
            uptime = etime if ok2 else ""

    return {
        "pipeline_running": running,
        "uptime": uptime,
        "recent_log": recent_log,
    }


@router.post("/restart")
async def restart_pipeline():
    """Restart the voice pipeline."""
    # Kill existing process
    _run(["pkill", "-f", "beets_voice_full.py"])

    # Start fresh
    import time
    time.sleep(1)

    # Start in background
    subprocess.Popen(
        [os.path.expanduser("~/.hermes/hermes-agent/venv/bin/python3"),
         "-u", PIPELINE_SCRIPT],
        stdout=open(LOG_PATH, "w"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
        cwd=str(Path.home()),
    )

    time.sleep(3)
    running = _pipeline_running()

    return {
        "success": running,
        "message": "Pipeline restarted" if running else "Pipeline failed to start - check logs",
    }


@router.get("/config")
async def get_config():
    """Get current PiHermes configuration."""
    return _load_config()


@router.post("/config")
async def update_config(
    tts_voice: str | None = None,
    wake_word: str | None = None,
    wake_threshold: float | None = None,
    stt_provider: str | None = None,
    stt_endpoint: str | None = None,
    max_tokens: int | None = None,
):
    """Update PiHermes configuration. Requires pipeline restart to apply."""
    config = _load_config()

    changes = {}

    if tts_voice is not None:
        config["tts_voice"] = tts_voice
        changes["tts_voice"] = tts_voice

    if wake_word is not None:
        config["wake_word"] = wake_word
        changes["wake_word"] = wake_word

    if wake_threshold is not None:
        config["wake_threshold"] = wake_threshold
        changes["wake_threshold"] = wake_threshold

    if stt_provider is not None:
        config["stt_provider"] = stt_provider
        changes["stt_provider"] = stt_provider

    if stt_endpoint is not None:
        config["stt_endpoint"] = stt_endpoint
        changes["stt_endpoint"] = stt_endpoint

    if max_tokens is not None:
        config["max_tokens"] = max_tokens
        changes["max_tokens"] = max_tokens

    _save_config(config)

    # Also update the running pipeline script
    _apply_config_to_script(config)

    return {
        "success": True,
        "changes": changes,
        "note": "Restart pipeline for changes to take effect",
    }


def _apply_config_to_script(config: dict):
    """Write config values into the pipeline script."""
    # This updates the key values in beets_voice_full.py
    script_path = PIPELINE_SCRIPT
    if not os.path.exists(script_path):
        return

    with open(script_path) as f:
        content = f.read()

    # Update known config values via sed-like replacement
    import re

    # max_tokens
    content = re.sub(
        r'"max_tokens": \d+',
        f'"max_tokens": {config["max_tokens"]}',
        content,
    )

    # WAKE_THRESHOLD
    content = re.sub(
        r"WAKE_THRESHOLD = [\d.]+",
        f"WAKE_THRESHOLD = {config['wake_threshold']}",
        content,
    )

    # WAKE_WORD
    content = re.sub(
        r'WAKE_WORD = "[^"]*"',
        f'WAKE_WORD = "{config["wake_word"]}"',
        content,
    )

    with open(script_path, "w") as f:
        f.write(content)


@router.get("/voices")
async def list_voices():
    """List available Piper TTS voices."""
    voices_dir = Path.home() / ".hermes" / "piper-voices"
    voices = []
    if voices_dir.exists():
        for f in sorted(voices_dir.glob("*.onnx")):
            name = f.stem  # e.g. "en_US-lessac-medium"
            voices.append({"id": name, "name": name})
    return {"voices": voices}


@router.get("/audio-devices")
async def list_audio_devices():
    """List available audio capture devices."""
    ok, stdout, _ = _run(["arecord", "-l"])
    devices = []
    if ok:
        for line in stdout.split("\n"):
            if "card" in line and "device" in line:
                devices.append(line.strip())
    return {"devices": devices if devices else ["No devices found — run arecord -l"]}
