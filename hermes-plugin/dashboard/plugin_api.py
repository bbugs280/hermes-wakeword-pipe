"""Hermes Wakeword Pipe plugin API — FastAPI routes for the dashboard."""

from fastapi import APIRouter, Request
import subprocess
import os
import json
import time
from pathlib import Path

router = APIRouter()
CONFIG_PATH = str(Path.home() / ".hermes" / "hermes-wakeword-pipe_config.json")


def _run(cmd: list[str], timeout: int = 10) -> tuple[bool, str, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", "timeout"
    except Exception as e:
        return False, "", str(e)


def _pipeline_running() -> bool:
    ok, stdout, _ = _run(["systemctl", "--user", "is-active", "butler-voice"])
    return ok and "active" in stdout


def _load_config() -> dict:
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "tts_voice": "en_US-lessac-medium",
            "wake_word": "hey_jarvis",
            "wake_threshold": 0.65,
            "stt_provider": "cloud",
            "stt_endpoint": "https://dashscope.aliyuncs.com/api/v1/services/audio/asr/paraformer-realtime-v2",
            "stt_model": "paraformer-realtime-v2",
            "max_tokens": 80,
        }


def _save_config(config: dict):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


@router.get("/status")
async def get_status(request: Request):
    running = _pipeline_running()
    log_ok, log_out, _ = _run(["journalctl", "--user", "-u", "butler-voice", "--no-pager", "-n", "10", "-o", "cat"])
    recent_log = log_out if log_ok else "log unavailable"

    uptime = ""
    if running:
        ok, pid, _ = _run(["pgrep", "-f", "hermes_voice.py"])
        if ok:
            ok2, etime, _ = _run(["ps", "-o", "etime=", "-p", pid.split("\n")[0]])
            uptime = etime if ok2 else ""

    return {
        "pipeline_running": running,
        "uptime": uptime,
        "recent_log": recent_log,
    }


@router.post("/restart")
async def restart_pipeline(request: Request):
    # Restart via systemd — the single source of truth for pipeline lifecycle
    ok, stdout, stderr = _run(["systemctl", "--user", "restart", "butler-voice"])
    if not ok:
        return {"success": False, "message": f"systemctl restart failed: {stderr}"}

    time.sleep(4)
    running = _pipeline_running()

    return {
        "success": running,
        "message": "Pipeline restarted" if running else "Pipeline may still be starting — check in a few seconds",
    }


@router.get("/config")
async def get_config(request: Request):
    return _load_config()


@router.post("/config")
async def update_config(
    request: Request,
    tts_voice: str | None = None,
    wake_word: str | None = None,
    wake_threshold: float | None = None,
    stt_provider: str | None = None,
    stt_endpoint: str | None = None,
    stt_model: str | None = None,
    max_tokens: int | None = None,
):
    config = _load_config()
    changes = {}

    for key, val in [
        ("tts_voice", tts_voice), ("wake_word", wake_word),
        ("wake_threshold", wake_threshold), ("stt_provider", stt_provider),
        ("stt_endpoint", stt_endpoint), ("stt_model", stt_model),
        ("max_tokens", max_tokens),
    ]:
        if val is not None:
            config[key] = val
            changes[key] = val

    _save_config(config)

    return {
        "success": True,
        "changes": changes,
        "note": "Restart pipeline for changes to take effect",
    }


@router.get("/voices")
async def list_voices(request: Request):
    voices_dir = Path.home() / ".hermes" / "piper-voices"
    voices = []
    if voices_dir.exists():
        for f in sorted(voices_dir.glob("*.onnx")):
            name = f.stem
            voices.append({"id": name, "name": name})
    return {"voices": voices}
