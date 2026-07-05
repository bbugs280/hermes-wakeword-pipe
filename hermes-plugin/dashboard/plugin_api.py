"""PiHermes plugin API — FastAPI routes for the dashboard."""

from fastapi import APIRouter, Request
import subprocess
import os
import json
import time
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
    ok, stdout, _ = _run(["pgrep", "-f", "beets_voice_full.py"])
    return ok and len(stdout) > 0


def _load_config() -> dict:
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "tts_voice": "en_US-lessac-medium",
            "wake_word": "hey_bob",
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
    log_ok, log_out, _ = _run(["tail", "-5", LOG_PATH])
    recent_log = log_out if log_ok else "log unavailable"

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
async def restart_pipeline(request: Request):
    # Kill existing
    _run(["pkill", "-f", "beets_voice_full.py"])
    time.sleep(1)

    # Start fresh
    venv_python = os.path.expanduser("~/.hermes/hermes-agent/venv/bin/python3")
    try:
        subprocess.Popen(
            [venv_python, "-u", PIPELINE_SCRIPT],
            stdout=open(LOG_PATH, "w"),
            stderr=subprocess.STDOUT,
            start_new_session=True,
            cwd=str(Path.home()),
        )
    except Exception as e:
        return {"success": False, "message": f"Start failed: {e}"}

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
    _apply_config_to_script(config)

    return {
        "success": True,
        "changes": changes,
        "note": "Restart pipeline for changes to take effect",
    }


def _apply_config_to_script(config: dict):
    script_path = PIPELINE_SCRIPT
    if not os.path.exists(script_path):
        return
    import re
    with open(script_path) as f:
        content = f.read()
    content = re.sub(r'"max_tokens": \d+', f'"max_tokens": {config["max_tokens"]}', content)
    content = re.sub(r'WAKE_THRESHOLD = [\d.]+', f'WAKE_THRESHOLD = {config["wake_threshold"]}', content)
    content = re.sub(r'WAKE_WORD = "[^"]*"', f'WAKE_WORD = "{config["wake_word"]}"', content)
    with open(script_path, "w") as f:
        f.write(content)


@router.get("/voices")
async def list_voices(request: Request):
    voices_dir = Path.home() / ".hermes" / "piper-voices"
    voices = []
    if voices_dir.exists():
        for f in sorted(voices_dir.glob("*.onnx")):
            name = f.stem
            voices.append({"id": name, "name": name})
    return {"voices": voices}
