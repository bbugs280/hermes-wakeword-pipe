"""PiHermes plugin API — FastAPI routes for the dashboard."""

from fastapi import APIRouter
import subprocess

router = APIRouter()
SERVICE_NAME = "pihermes-voice"
LOG_PATH = "/tmp/voice_v21.log"


def _run(cmd: list[str], timeout: int = 10) -> tuple[bool, str, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", "timeout"
    except Exception as e:
        return False, "", str(e)


@router.get("/status")
async def get_status():
    """Check if voice pipeline is running and return recent log."""
    ok, stdout, stderr = _run(["systemctl", "is-active", SERVICE_NAME])
    running = ok and stdout == "active"

    log_ok, log_out, _ = _run(["tail", "-5", LOG_PATH])
    recent_log = log_out if log_ok else "log unavailable"

    return {
        "pipeline_running": running,
        "service": SERVICE_NAME,
        "recent_log": recent_log,
    }


@router.post("/restart")
async def restart_pipeline():
    """Restart the voice pipeline service."""
    ok, stdout, stderr = _run(["systemctl", "restart", SERVICE_NAME])
    return {
        "success": ok,
        "message": "Pipeline restarted" if ok else stderr,
    }


@router.post("/config")
async def update_config(wake_word: str | None = None, voice: str | None = None):
    """Update pipeline config (wake word, voice, etc). Stub for now."""
    changes = {}
    if wake_word:
        changes["wake_word"] = wake_word
    if voice:
        changes["voice"] = voice
    return {"success": True, "changes": changes, "note": "Config updates require pipeline restart"}
