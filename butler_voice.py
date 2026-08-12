#!/usr/bin/env python3
"""Butler voice pipeline — wake word "hey_jarvis" -> STT -> Butler Hermes -> CD002 speaker.

Adapted from Hermes Wakeword Pipe v0.4.0 for N150 Butler (Ubuntu 24.04).
"""

import subprocess, sys, os, json, time, urllib.request, urllib.error, threading, tempfile, io
import numpy as np
from pathlib import Path
import wave

# ── Configuration ──────────────────────────────────────
WAKE_WORD = "hey_jarvis"
WAKE_THRESHOLD = 0.65
WAKE_COOLDOWN = 3.0
SAMPLE_RATE = 16000
CHUNK_MS = 80
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_MS / 1000)

# Butler hardware: mic=card 1 (USB FS AUDIO), speaker=card 2 (CD002 Jieli)
AUDIO_DEVICE = "plughw:1,0"
SPEAKER_DEVICE = "plughw:2,0"

VAD_AGGRESSIVENESS = 2
VAD_SILENCE_SECS = 1.2
VAD_FRAME_MS = 30
MAX_RECORD_SECS = 10

# Butler Hermes API (profile: butler)
HERMES_API_URL = "http://localhost:8643/v1/chat/completions"

def _load_api_key() -> str:
    env_path = str(Path.home() / ".hermes/profiles/butler/.env")
    try:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("API_SERVER_KEY="):
                    return line.split("=", 1)[1]
    except Exception:
        pass
    return ""

HERMES_API_KEY = _load_api_key()

# Cloud ASR (DashScope MaaS qwen3-asr-flash)
ASR_ENABLED = True
ASR_KEY = os.environ.get("HERMES_VOICE_ASR_KEY", "")
ASR_BASE = "https://ws-4jinhjc7i3rl678j.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
ASR_MODEL = "qwen3-asr-flash"
ASR_TIMEOUT = 10

# Piper TTS
PIPER_MODEL = str(Path.home() / ".hermes/piper-voices/en_US-lessac-medium.onnx")
MAX_TOKENS = 80

# ── Load dashboard config (overrides defaults) ─────────
_config_path = str(Path.home() / ".hermes" / "hermes-wakeword-pipe_config.json")
try:
    with open(_config_path) as f:
        _cfg = json.load(f)
    if _cfg.get("wake_word"):
        WAKE_WORD = _cfg["wake_word"]
    if _cfg.get("wake_threshold") is not None:
        WAKE_THRESHOLD = float(_cfg["wake_threshold"])
    if _cfg.get("tts_voice"):
        PIPER_MODEL = str(Path.home() / ".hermes/piper-voices" / f"{_cfg['tts_voice']}.onnx")
    if _cfg.get("max_tokens") is not None:
        MAX_TOKENS = int(_cfg["max_tokens"])
except Exception:
    pass  # use defaults


def log(msg: str):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

# Log what config we loaded (now that log() is defined)
log(f"Config: wake={WAKE_WORD} threshold={WAKE_THRESHOLD} tts_voice={Path(PIPER_MODEL).stem}")


def tone(freq: int, ms: int, sample_rate: int = 22050) -> np.ndarray:
    n = int(sample_rate * ms / 1000)
    t = np.linspace(0, ms / 1000, n, False)
    return (np.sin(2 * np.pi * freq * t) * 0.3 * 32767).astype(np.int16)


def chime_start() -> bytes:
    return np.concatenate([tone(880, 60), tone(0, 30), tone(1320, 120)]).tobytes()

def chime_listening() -> bytes:
    return np.concatenate([tone(1000, 120), tone(0, 60), tone(1400, 150)]).tobytes()

def chime_done() -> bytes:
    return np.concatenate([tone(1320, 180), tone(0, 60), tone(880, 200), tone(0, 60), tone(660, 300)]).tobytes()

def chime_error() -> bytes:
    return np.concatenate([tone(440, 200), tone(0, 100), tone(440, 250)]).tobytes()


def play_raw(raw_audio: bytes, sample_rate: int = 22050):
    subprocess.run(["aplay", "-q", "-D", SPEAKER_DEVICE, "-f", "S16_LE", "-r", str(sample_rate), "-c", "1"],
                   input=raw_audio, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)


def record_until_silence(proc_stdout) -> bytes | None:
    import webrtcvad
    vad = webrtcvad.Vad(VAD_AGGRESSIVENESS)

    frames = []
    silence_frames = 0
    speech_detected = False
    max_frames = int(MAX_RECORD_SECS * 1000 / VAD_FRAME_MS)
    frame_bytes = int(SAMPLE_RATE * VAD_FRAME_MS / 1000) * 2

    for i in range(max_frames):
        raw = proc_stdout.read(frame_bytes)
        if not raw or len(raw) < frame_bytes:
            break
        frames.append(raw)

        is_speech = vad.is_speech(raw, SAMPLE_RATE)

        if is_speech:
            speech_detected = True
            silence_frames = 0
        elif speech_detected:
            silence_frames += 1

        silence_secs = silence_frames * VAD_FRAME_MS / 1000
        if speech_detected and silence_secs >= VAD_SILENCE_SECS:
            break

    if not speech_detected:
        log("No speech detected by VAD")
        return None

    duration = len(frames) * VAD_FRAME_MS / 1000
    log(f"Recorded {duration:.1f}s")
    return b"".join(frames)


def transcribe(pcm_data: bytes) -> str | None:
    import base64

    audio = np.frombuffer(pcm_data, dtype=np.int16)
    audio = np.clip(audio * 3, -32768, 32767).astype(np.int16)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio.tobytes())
    wav_bytes = buf.getvalue()

    if ASR_ENABLED:
        try:
            t0 = time.time()
            audio_b64 = base64.b64encode(wav_bytes).decode()
            data_url = f"data:audio/wav;base64,{audio_b64}"

            payload = json.dumps({
                "model": ASR_MODEL,
                "messages": [{
                    "role": "user",
                    "content": [{
                        "type": "input_audio",
                        "input_audio": {"data": data_url}
                    }]
                }]
            }).encode()

            req = urllib.request.Request(f"{ASR_BASE}/chat/completions", data=payload)
            req.add_header("Content-Type", "application/json")
            req.add_header("Authorization", f"Bearer {ASR_KEY}")

            resp = urllib.request.urlopen(req, timeout=ASR_TIMEOUT)
            ms = (time.time() - t0) * 1000
            result = json.loads(resp.read())
            text = result["choices"][0]["message"]["content"].strip()

            if text:
                log(f'STT (cloud, {ms:.0f}ms): "{text}"')
                return text
            log(f"Cloud empty ({ms:.0f}ms)")
            return None
        except Exception as e:
            log(f"Cloud STT failed: {e}")
            return None

    return None


def is_non_english(text: str) -> bool:
    for ch in text:
        cp = ord(ch)
        if (0x4E00 <= cp <= 0x9FFF or 0x3040 <= cp <= 0x30FF or 
            0xAC00 <= cp <= 0xD7AF or 0x3000 <= cp <= 0x303F):
            return True
    return False


def ask_hermes(text: str) -> str:
    payload = json.dumps({
        "model": "hermes-agent",
        "messages": [
            {"role": "user", "content": text},
        ],
        "max_tokens": 80, "temperature": 0.7,
    }).encode()
    req = urllib.request.Request(HERMES_API_URL, data=payload)
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {HERMES_API_KEY}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())["choices"][0]["message"]["content"]
    except Exception as e:
        log(f"API error: {e}")
        return "Sorry, I'm having trouble reaching the assistant. Please try again."


def speak(text: str):
    clean = text.replace("*", "").replace("`", "").replace("#", "").replace("\n", ". ").strip()
    if not clean:
        return
    log(f"Speaking ({len(clean)} chars)")

    piper = subprocess.Popen(
        [sys.executable, "-m", "piper", "--model", PIPER_MODEL, "--output-raw"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def feed():
        piper.stdin.write(clean.encode())
        piper.stdin.close()
    threading.Thread(target=feed, daemon=True).start()

    audio_chunks = []
    while True:
        chunk = piper.stdout.read(65536)
        if not chunk:
            break
        audio_chunks.append(chunk)
    piper.wait()

    if not audio_chunks:
        return

    full_audio = b"".join(audio_chunks)
    duration = len(full_audio) / 2 / 22050
    log(f"  Rendered {duration:.1f}s audio, playing...")

    subprocess.run(
        ["aplay", "-q", "-D", SPEAKER_DEVICE, "-f", "S16_LE", "-r", "22050", "-c", "1"],
        input=full_audio, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        timeout=30)
    log("  Done playing")


def main():
    START_CHIME = chime_start()
    LISTENING_CHIME = chime_listening()
    DONE_CHIME = chime_done()
    ERROR_CHIME = chime_error()
    THINKING_CHIME = np.concatenate([
        tone(600, 100), tone(0, 80), tone(800, 100), tone(0, 80), tone(600, 150)]).tobytes()

    log("=" * 55)
    log("Butler Voice Pipeline — Jarvis")
    log(f"  Wake: '{WAKE_WORD}' | STT: cloud qwen3-asr-flash | TTS: Piper lessac")
    log(f"  Hermes: {HERMES_API_URL} (butler profile)")
    log(f"  Mic: {AUDIO_DEVICE} | Speaker: {SPEAKER_DEVICE}")
    log("=" * 55)

    # Kill stale arecord processes
    os.system(f"pkill -f 'arecord.*{AUDIO_DEVICE}' 2>/dev/null || true")
    time.sleep(0.3)

    # Test Hermes API
    log("Testing Hermes API...")
    test_resp = ask_hermes("Say 'I am online' and nothing else.")
    log(f"API: {test_resp[:60]}")

    speak("Jarvis online.")

    # Load wake word model
    log("Loading wake word model...")
    from openwakeword.model import Model
    model = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
    log(f"Ready. Say '{WAKE_WORD}' to talk to me.")

    arecord_cmd = ["arecord", "-q", "-D", AUDIO_DEVICE, "-f", "S16_LE", "-r", str(SAMPLE_RATE), "-c", "1"]

    def start_mic():
        time.sleep(0.1)
        return subprocess.Popen(arecord_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    mic_proc = start_mic()
    cooldown_until = 0
    restart_count = 0

    try:
        while True:
            raw = mic_proc.stdout.read(CHUNK_SIZE * 2)
            if len(raw) < CHUNK_SIZE * 2:
                ret = mic_proc.poll()
                if ret is not None:
                    err = mic_proc.stderr.read().decode(errors="ignore").strip()
                    if err:
                        log(f"Mic error: {err}")
                restart_count += 1
                if restart_count % 10 == 0:
                    log(f"Mic restarted {restart_count} times — check USB device")
                mic_proc.terminate(); mic_proc.wait()
                mic_proc = start_mic()
                continue

            audio = np.frombuffer(raw, dtype=np.int16)
            prediction = model.predict(audio)
            score = prediction.get("hey_jarvis", 0)

            if score > WAKE_THRESHOLD and time.time() > cooldown_until:
                t_cycle = time.time()
                log(f"Wake word! (score: {score:.3f})")
                threading.Thread(target=play_raw, args=(START_CHIME,), daemon=True).start()

                mic_proc.terminate(); mic_proc.wait()

                speech_proc = subprocess.Popen(
                    ["arecord", "-q", "-D", AUDIO_DEVICE, "-f", "S16_LE", "-r", str(SAMPLE_RATE), "-c", "1"],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                threading.Thread(target=play_raw, args=(LISTENING_CHIME,), daemon=True).start()

                speech = record_until_silence(speech_proc.stdout)
                speech_proc.terminate(); speech_proc.wait()
                mic_proc = start_mic()

                if not speech:
                    log("No speech detected.")
                    threading.Thread(target=play_raw, args=(ERROR_CHIME,), daemon=True).start()
                    continue

                threading.Thread(target=play_raw, args=(THINKING_CHIME,), daemon=True).start()
                log("Processing speech...")

                text = transcribe(speech)
                if not text or text.strip() in ("", ".", "(silence)", "[ Silence ]"):
                    log("Nothing transcribed.")
                    threading.Thread(target=play_raw, args=(ERROR_CHIME,), daemon=True).start()
                    continue

                query_text = text[:100] if len(text) > 100 else text
                if len(text) > 100:
                    log(f'Truncated query from {len(text)} to {len(query_text)} chars')

                if is_non_english(text):
                    log(f"Non-English detected, skipping: {text}")
                    speak("Sorry, I only speak English right now.")
                    threading.Thread(target=play_raw, args=(DONE_CHIME,), daemon=True).start()
                    cooldown_until = time.time() + WAKE_COOLDOWN
                    continue

                log(f'Asking Jarvis: "{query_text}"...')
                t_api = time.time()

                progress_done = threading.Event()
                def show_progress():
                    for _ in range(10):
                        if progress_done.is_set():
                            break
                        time.sleep(0.8)
                        if not progress_done.is_set():
                            sys.stdout.write(".")
                            sys.stdout.flush()
                threading.Thread(target=show_progress, daemon=True).start()

                response = ask_hermes(query_text)
                progress_done.set()
                sys.stdout.write("\n"); sys.stdout.flush()
                api_ms = (time.time() - t_api) * 1000
                log(f"Response ({api_ms:.0f}ms): {response}")

                speak(response)
                threading.Thread(target=play_raw, args=(DONE_CHIME,), daemon=True).start()

                total_s = time.time() - t_cycle
                log(f"Total cycle: {total_s:.1f}s")

                cooldown_until = time.time() + WAKE_COOLDOWN
                log("Ready for next wake word...")

    except KeyboardInterrupt:
        log("Shutting down...")
    finally:
        mic_proc.terminate(); mic_proc.wait()
        log("Goodbye!")


if __name__ == "__main__":
    main()
