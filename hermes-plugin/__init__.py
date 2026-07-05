"""PiHermes plugin for Hermes Agent — admin tools for the voice pipeline."""

import json
import subprocess
import os

PIPELINE_SCRIPT = os.path.expanduser("~/beets_voice_full.py")
LOG_PATH = "/tmp/voice_v21.log"


def _run(cmd: list[str]) -> dict:
    """Run a shell command and return stdout/stderr/exit_code."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return {"ok": r.returncode == 0, "stdout": r.stdout.strip(), "stderr": r.stderr.strip()}
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": "timeout"}
    except Exception as e:
        return {"ok": False, "stdout": "", "stderr": str(e)}


def _pipeline_running() -> bool:
    result = _run(["pgrep", "-f", "beets_voice_full.py"])
    return result["ok"] and len(result["stdout"]) > 0


def register(ctx):
    # ── Tool: pihermes_status ──
    def handle_status(params, **kwargs):
        """Check if the voice pipeline is running."""
        del kwargs
        running = _pipeline_running()

        log_tail = _run(["tail", "-3", LOG_PATH])
        recent = log_tail.get("stdout", "no log") if log_tail["ok"] else "log unavailable"

        return json.dumps({
            "success": True,
            "pipeline_running": running,
            "recent_log": recent[:300],
        })

    ctx.register_tool(
        name="pihermes_status",
        toolset="pihermes",
        schema={
            "name": "pihermes_status",
            "description": "Check whether the PiHermes voice pipeline is running on this machine.",
            "parameters": {"type": "object", "properties": {}},
        },
        handler=handle_status,
        description="Check whether the PiHermes voice pipeline is running.",
    )

    # ── Tool: pihermes_restart ──
    def handle_restart(params, **kwargs):
        """Restart the voice pipeline."""
        del kwargs

        # Kill existing
        _run(["pkill", "-f", "beets_voice_full.py"])

        import time
        time.sleep(1)

        # Start fresh
        venv_python = os.path.expanduser("~/.hermes/hermes-agent/venv/bin/python3")
        subprocess.Popen(
            [venv_python, "-u", PIPELINE_SCRIPT],
            stdout=open(LOG_PATH, "w"),
            stderr=subprocess.STDOUT,
            start_new_session=True,
            cwd=os.path.expanduser("~"),
        )

        time.sleep(3)
        running = _pipeline_running()

        return json.dumps({
            "success": running,
            "message": "Pipeline restarted" if running else "Pipeline failed to start — check logs",
        })

    ctx.register_tool(
        name="pihermes_restart",
        toolset="pihermes",
        schema={
            "name": "pihermes_restart",
            "description": "Restart the PiHermes voice pipeline service.",
            "parameters": {"type": "object", "properties": {}},
        },
        handler=handle_restart,
        description="Restart the PiHermes voice pipeline.",
    )

    # ── Hook: log pipeline tool calls ──
    def on_tool_call(tool_name, params, result):
        if tool_name.startswith("pihermes_"):
            print(f"[pihermes] tool called: {tool_name} -> {result[:100]}")

    ctx.register_hook("post_tool_call", on_tool_call)
