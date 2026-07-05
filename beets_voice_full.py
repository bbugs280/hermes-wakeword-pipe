#!/usr/bin/env python3
"""PiHermes voice pipeline — v21: Production voice assistant for Raspberry Pi.

Full pipeline: openWakeWord -> WebRTC VAD -> cloud STT (configurable)
-> Hermes API -> Piper TTS -> speaker

Features: custom wake word, 5-chime audio UX, language guard,
streaming TTS with pre-render, WebRTC VAD, cloud+whisper fallback STT.
"""

import subprocess, sys, os, json, time, urllib.request, urllib.error, threading, tempfile, io
import numpy as np
from pathlib import Path
import wave

# ── Configuration ──────────────────────────────────────
WAKE_WORD = "hey_bob"
WAKE_THRESHOLD = 0.65
WAKE_COOLDOWN = 3.0
SAMPLE_RATE = 16000
CHUNK_MS = 80
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_MS / 1000)

AUDIO_DEVICE = "plughw:2,0"
SPEAKER_DEVICE = "plughw:3,0"

SILENCE_THRESHOLD = 40
SILENCE_DURATION = 1.5
MAX_RECORD_SECS = 10
MIN_RECORD_SECS = 0.5

HERMES_API_URL = "http://localhost:8642/v1/chat/completions"

def _load_api_key() -> str:
    env_path = str(Path.home() / ".hermes/.env")
    try:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("API_SERVER_KEY="):
                    return line.split("=", 1)[1]
    except Exception:
        pass
    return ""

HERMES_API_KEY=_load_api_key()
# Cloud ASR (DashScope MaaS qwen3-asr-flash)
ASR_ENABLED = True
ASR_KEY = "***REMOVED***"
ASR_BASE = "https://ws-4jinhjc7i3rl678j.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
ASR_MODEL = "qwen3-asr-flash"
ASR_TIMEOUT = 10

# VAD (WebRTC — lightweight, no GPU needed)
VAD_AGGRESSIVENESS = 2   # 0=least, 3=most aggressive
VAD_SILENCE_SECS = 1.2    # stop after this many seconds of silence
VAD_FRAME_MS = 30

# whisper.cpp
WHISPER_CLI = str(Path.home() / "whisper-bin-ubuntu-arm64/whisper-cli")
WHISPER_MODEL = str(Path.home() / "ggml-tiny.en.bin")
WHISPER_LIB = str(Path.home() / "whisper-bin-ubuntu-arm64")
PIPER_MODEL = str(Path.home() / ".hermes/piper-voices/en_US-lessac-medium.onnx")


def log(msg: str):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


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
    """Record speech using WebRTC VAD — stops when user stops talking."""
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
        log("\u26a0 No speech detected by VAD")
        return None

    duration = len(frames) * VAD_FRAME_MS / 1000
    log(f"\U0001f3a4 Recorded {duration:.1f}s")
    return b"".join(frames)


def transcribe(pcm_data: bytes) -> str | None:
    """Transcribe via cloud ASR (qwen3-asr-flash) with whisper fallback."""
    import wave, base64

    # Convert PCM to WAV in memory
    audio = np.frombuffer(pcm_data, dtype=np.int16)
    audio = np.clip(audio * 3, -32768, 32767).astype(np.int16)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio.tobytes())
    wav_bytes = buf.getvalue()

    # Try cloud ASR first
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
            log(f"Cloud empty ({ms:.0f}ms), falling back to whisper")
        except Exception as e:
            log(f"Cloud STT failed ({e}), falling back to whisper")

    # Whisper fallback
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav_path = f.name
    with open(wav_path, "wb") as f:
        f.write(wav_bytes)

    try:
        t0 = time.time()
        env = os.environ.copy()
        env["LD_LIBRARY_PATH"] = WHISPER_LIB
        result = subprocess.run(
            [WHISPER_CLI, "-m", WHISPER_MODEL, "-f", wav_path,
             "--no-timestamps", "-l", "en", "-t", "2"],
            capture_output=True, text=True, timeout=30, env=env)
        ms = (time.time() - t0) * 1000
        text = result.stdout.strip()
        if text:
            log(f'STT (whisper, {ms:.0f}ms): "{text}"')
            return text
        log(f"Whisper empty ({ms:.0f}ms)")
        return None
    except subprocess.TimeoutExpired:
        log("STT timed out")
        return None
    finally:
        Path(wav_path).unlink(missing_ok=True)



def is_non_english(text: str) -> bool:
    """Detect CJK characters in STT output."""
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
            {"role": "system", "content": (
                "You are Bob, a voice assistant. Answer in ONE short sentence only. "
                "Under 20 words. No lists, no markdown, no emoji. "
                "Do NOT use tools — answer from your knowledge immediately."
            )},
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
    """Stream TTS v4 — render all audio first, then play continuously.
    No mid-speech gaps. Trade: ~2s startup delay for smooth playback."""
    clean = text.replace("*", "").replace("`", "").replace("#", "").replace("\n", ". ").strip()
    if not clean: return
    log(f"🔊 Speaking ({len(clean)} chars)")

    # Render ALL audio first (Piper is slow — 500-5000ms to render)
    piper = subprocess.Popen(
        [sys.executable, "-m", "piper", "--model", PIPER_MODEL, "--output-raw"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def feed():
        piper.stdin.write(clean.encode())
        piper.stdin.close()
    threading.Thread(target=feed, daemon=True).start()

    # Collect ALL audio into buffer
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

    # Play continuously — no gaps because audio is pre-rendered
    aplay = subprocess.run(
        ["aplay", "-q", "-D", SPEAKER_DEVICE, "-f", "S16_LE", "-r", "22050", "-c", "1"],
        input=full_audio, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        timeout=30)
    
    log(f"  Done playing")

def main():
    START_CHIME = chime_start()
    LISTENING_CHIME = chime_listening()
    DONE_CHIME = chime_done()
    ERROR_CHIME = chime_error()
    THINKING_CHIME = np.concatenate([
        tone(600, 100), tone(0, 80), tone(800, 100), tone(0, 80), tone(600, 150)]).tobytes()

    log("=" * 55)
    log("PiHermes Voice v21 — Production")
    log(f"  Wake: '{WAKE_WORD}' | STT: cloud qwen3-asr-flash | TTS: Piper lessac (female) | VAD: WebRTC")
    log(f"  max_tokens: 80 | threshold: {WAKE_THRESHOLD} | cooldown: {WAKE_COOLDOWN}s")
    log(f"  Mic: {AUDIO_DEVICE} | Speaker: {SPEAKER_DEVICE}")
    log("=" * 55)

    os.system("pkill -f 'arecord.*plughw:2' 2>/dev/null || true")
    time.sleep(0.3)

    log("Testing Hermes API...")
    test_resp = ask_hermes("Say 'I am online' and nothing else.")
    log(f"API: {test_resp[:60]}")

    speak("Bob ready.")

    log("Loading wake word model...")
    from openwakeword.model import Model
    model = Model(wakeword_models=["/home/beets3d/.hermes/hermes-agent/venv/lib/python3.11/site-packages/openwakeword/resources/models/hey_bob_v0.1.onnx"], inference_framework="onnx")
    log(f"✅ Ready. Say '{WAKE_WORD}' to talk to me.")

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
                    if err: log(f"Mic error: {err}")
                restart_count += 1
                if restart_count % 10 == 0:
                    log(f"Mic restarted {restart_count} times — check USB device")
                mic_proc.terminate(); mic_proc.wait()
                mic_proc = start_mic()
                continue

            audio = np.frombuffer(raw, dtype=np.int16)
            prediction = model.predict(audio)
            score = prediction.get("hey_bob_v0.1", 0)

            if score > WAKE_THRESHOLD and time.time() > cooldown_until:
                t_cycle = time.time()
                log(f"🔔 Wake word! (score: {score:.3f})")
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

                # Truncate long queries — they trigger deep tool calls
                query_text = text[:100] if len(text) > 100 else text
                if len(text) > 100:
                    log(f'Truncated query from {len(text)}→{len(query_text)} chars')
                # Language guard: non-English STT → skip
                if is_non_english(text):
                    log(f"Non-English detected, skipping: {text}")
                    speak("Sorry, I only speak English right now.")
                    threading.Thread(target=play_raw, args=(DONE_CHIME,), daemon=True).start()
                    cooldown_until = time.time() + WAKE_COOLDOWN
                    continue

                log(f'🤔 Asking Bob: "{query_text}"...')
                t_api = time.time()
                # Progress dots while waiting for API (feels faster)
                progress_done = threading.Event()
                def show_progress():
                    for _ in range(10):
                        if progress_done.is_set():
                            break
                        time.sleep(0.8)
                        if not progress_done.is_set():
                            sys.stdout.write(".")
                            sys.stdout.flush()
                progress_thread = threading.Thread(target=show_progress, daemon=True)
                progress_thread.start()
                response = ask_hermes(query_text)
                progress_done.set()
                sys.stdout.write("\n")
                sys.stdout.flush()
                api_ms = (time.time() - t_api) * 1000
                log(f"🤖 Response ({api_ms:.0f}ms): {response}")

                speak(response)
                threading.Thread(target=play_raw, args=(DONE_CHIME,), daemon=True).start()

                total_s = time.time() - t_cycle
                log(f"⏱️  Total cycle: {total_s:.1f}s")

                cooldown_until = time.time() + WAKE_COOLDOWN
                log("Ready for next wake word...")

    except KeyboardInterrupt:
        log("\nShutting down...")
    finally:
        mic_proc.terminate(); mic_proc.wait()
        log("Goodbye!")


if __name__ == "__main__":
    main()