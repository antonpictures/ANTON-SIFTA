#!/usr/bin/env python3
"""swarm_perception_heartbeat.py — Alice's perception heart.

Beats continuously: captures a short slice of room audio + a screenshot,
transcribes the audio locally (whisper tiny), asks the local omni model
(lfm3-omni) for a compact perception summary, and writes a single shared
file — .sifta_state/latest_perception.json — that every cortex turn can
read. This is the "heart" that keeps the laptop aware of the room.

Usage:
  python3 System/swarm_perception_heartbeat.py            # beat forever (60s)
  python3 System/swarm_perception_heartbeat.py --once     # one beat
  python3 System/swarm_perception_heartbeat.py --interval 30 --audio-seconds 6
"""

from __future__ import annotations

import argparse
import base64
import datetime
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STATE = REPO / ".sifta_state"
LATEST = STATE / "latest_perception.json"
AMBIENT = STATE / "ambient_room_transcripts.jsonl"
ACTIVE_WINDOW = STATE / "active_window.jsonl"
AUDIO_TMP = Path("/tmp/perception_heartbeat_audio.wav")
SCREEN_TMP = Path("/tmp/perception_heartbeat_screen.png")
WHISPER_OUT = Path("/tmp")

OLLAMA = os.environ.get("SIFTA_OLLAMA_URL", "http://127.0.0.1:11434")
DEFAULT_MODEL = os.environ.get("SIFTA_PERCEPTION_MODEL", "lfm3-omni:latest")


def _log(msg: str) -> None:
    line = f"{datetime.datetime.now().isoformat()} {msg}"
    print(line, flush=True)
    try:
        STATE.mkdir(parents=True, exist_ok=True)
        (STATE / "perception_heartbeat.log").open("a").write(line + "\n")
    except Exception:
        pass


def capture_audio(seconds: int) -> bool:
    try:
        # sox: record from default input, 16kHz mono 16-bit, trim to N seconds
        subprocess.run(
            ["sox", "-d", "-r", "16000", "-c", "1", "-b", "16", str(AUDIO_TMP),
             "trim", "0", str(seconds)],
            timeout=seconds + 10, capture_output=True,
        )
        return AUDIO_TMP.exists() and AUDIO_TMP.stat().st_size > 1000
    except Exception as e:
        _log(f"audio capture failed: {e}")
        return False


def transcribe_audio() -> str:
    try:
        # openai-whisper CLI, tiny model, txt output
        subprocess.run(
            ["whisper", str(AUDIO_TMP), "--model", "tiny", "--output_format", "txt",
             "--output_dir", str(WHISPER_OUT), "--fp16", "False", "--language", "en"],
            timeout=120, capture_output=True,
        )
        txt_path = WHISPER_OUT / (AUDIO_TMP.stem + ".txt")
        if txt_path.exists():
            return txt_path.read_text(encoding="utf-8", errors="replace").strip()
    except Exception as e:
        _log(f"transcribe failed: {e}")
    return ""


def capture_screen() -> bool:
    try:
        subprocess.run(["screencapture", "-x", str(SCREEN_TMP)],
                       timeout=10, capture_output=True)
        return SCREEN_TMP.exists() and SCREEN_TMP.stat().st_size > 1000
    except Exception as e:
        _log(f"screen capture failed: {e}")
        return False


def active_window() -> dict:
    try:
        if ACTIVE_WINDOW.exists():
            lines = [l for l in ACTIVE_WINDOW.read_text().splitlines() if l.strip()]
            if lines:
                return json.loads(lines[-1])
    except Exception:
        pass
    return {}


def omni_perceive(transcript: str, window: dict, images_b64: list | None = None, vitals: dict | None = None) -> str:
    """Ask the local omni model for a compact perception summary."""
    try:
        prompt = (
            "You are the room's perception organ for Alice (the laptop organism). "
            "In one or two short sentences, summarize what is happening right now: "
            "who is present (George?, the owner — the person in the webcam is George, not Alice) "
            "and what they're doing, what is visible on the screen, "
            "what was audible, system state, and anything notable. Be concrete and brief. "
            "Images (if any): first = webcam view of the room, second = screen capture. "
            f"Audio transcript: {transcript or '(silence)'}. "
            f"Active window: {window.get('app')} — {window.get('window')}. "
            f"System vitals: {vitals or {}}."
        )
        msg = {"role": "user", "content": prompt}
        if images_b64:
            msg["images"] = images_b64
        payload = {
            "model": DEFAULT_MODEL,
            "messages": [msg],
            "stream": False,
            "options": {"temperature": 0.2, "num_predict": 120},
        }
        req = urllib.request.Request(
            f"{OLLAMA}/api/chat",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read())
        return (data.get("message", {}).get("content") or "").strip()
    except Exception as e:
        _log(f"omni perceive failed: {e}")
        # Fallback: text-only summary from transcript + window
        if transcript:
            return f"Heard: {transcript[:200]} | Window: {window.get('app')}"
        return f"Window: {window.get('app')} — {window.get('window')}"


def append_ambient(transcript: str, ts: float) -> None:
    if not transcript:
        return
    try:
        STATE.mkdir(parents=True, exist_ok=True)
        import hashlib
        row = {
            "ts": ts,
            "source": "perception_heartbeat",
            "source_ts": ts,
            "truth_label": "AMBIENT_ROOM_TRANSCRIPT_V1",
            "text": transcript,
            "text_preview": transcript[:200],
            "text_sha256": hashlib.sha256(transcript.encode()).hexdigest(),
            "stt_confidence": 0.0,
            "word_count": len(transcript.split()),
            "raw_audio_stored": False,
            "raw_text_stored": True,
            "retention_rule": "Full transcript text is retained.",
            "writer": "swarm_perception_heartbeat",
        }
        with AMBIENT.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception as e:
        _log(f"ambient append failed: {e}")


def capture_system_vitals() -> dict:
    """Compact system vitals for the heart — load, memory, battery."""
    try:
        import psutil
        load = os.getloadavg() if hasattr(os, "getloadavg") else (0.0, 0.0, 0.0)
        ncpu = psutil.cpu_count() or 1
        mem = psutil.virtual_memory()
        bat = psutil.sensors_battery()
        return {
            "load1": round(load[0], 2),
            "load5": round(load[1], 2),
            "load15": round(load[2], 2),
            "ncpu": ncpu,
            "cpu_pct": round(psutil.cpu_percent(interval=0.2), 1),
            "mem_used_pct": round(mem.percent, 1),
            "mem_used_gb": round(mem.used / (1024**3), 2),
            "mem_total_gb": round(mem.total / (1024**3), 2),
            "battery_pct": (round(bat.percent, 1) if bat else None),
            "power": ("AC" if (bat is None or bat.power_plugged) else "battery"),
        }
    except Exception as e:
        _log(f"system vitals failed: {e}")
        return {}


def capture_webcam_frame() -> bool:
    """Capture a still from the MacBook Pro camera (sees George)."""
    out = Path("/tmp/perception_heartbeat_cam.png")
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-f", "avfoundation", "-video_size", "640x480",
             "-framerate", "30", "-i", "0:none",
             "-frames:v", "1", "-q:v", "2", "-update", "1", str(out)],
            timeout=15, capture_output=True,
        )
        return out.exists() and out.stat().st_size > 1000
    except Exception as e:
        _log(f"webcam capture failed: {e}")
        return False


def capture_video_frame() -> bool:
    """Capture a short screen video and extract a mid-frame for omni vision."""
    clip = Path("/tmp/perception_heartbeat_clip.mov")
    try:
        subprocess.run(["screencapture", "-v", "-V3", str(clip)],
                       timeout=12, capture_output=True)
        if not clip.exists() or clip.stat().st_size < 10000:
            return False
        subprocess.run(
            ["ffmpeg", "-y", "-ss", "1.5", "-i", str(clip), "-frames:v", "1",
             "-q:v", "2", str(SCREEN_TMP)],
            timeout=20, capture_output=True,
        )
        return SCREEN_TMP.exists() and SCREEN_TMP.stat().st_size > 1000
    except Exception as e:
        _log(f"video frame capture failed: {e}")
        return False


def beat() -> dict:
    ts = time.time()
    iso = datetime.datetime.fromtimestamp(ts).isoformat()
    _log("beat start")

    audio_ok = capture_audio(8)
    transcript = transcribe_audio() if audio_ok else ""
    _log(f"transcript: {transcript[:120]!r}")

    video_ok = capture_video_frame()
    screen_ok = False
    if not video_ok:
        screen_ok = capture_screen()
    cam_ok = capture_webcam_frame()

    image_b64_list = []
    if cam_ok:
        try:
            image_b64_list.append(base64.b64encode(Path("/tmp/perception_heartbeat_cam.png").read_bytes()).decode())
        except Exception:
            pass
    img_path = None
    if video_ok or screen_ok:
        try:
            image_b64_list.append(base64.b64encode(SCREEN_TMP.read_bytes()).decode())
            img_path = str(SCREEN_TMP)
        except Exception:
            pass

    vitals = capture_system_vitals()
    window = active_window()
    summary = omni_perceive(transcript, window, image_b64_list, vitals)
    _log(f"perception: {summary[:200]!r}")

    perception = {
        "ts": ts,
        "iso": iso,
        "audio_seconds": 8,
        "audio_transcript": transcript,
        "perception_summary": summary,
        "active_window": {
            "app": window.get("app"),
            "window": window.get("window"),
            "ts": window.get("ts"),
        },
        "system_vitals": vitals,
        "screenshot_path": img_path,
        "webcam_path": ("/tmp/perception_heartbeat_cam.png" if cam_ok else None),
        "model": DEFAULT_MODEL,
        "writer": "swarm_perception_heartbeat",
    }
    try:
        STATE.mkdir(parents=True, exist_ok=True)
        LATEST.write_text(json.dumps(perception, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        _log(f"write latest_perception failed: {e}")

    append_ambient(transcript, ts)
    _log("beat done")
    return perception


def main() -> int:
    ap = argparse.ArgumentParser(description="Alice perception heartbeat")
    ap.add_argument("--once", action="store_true", help="single beat then exit")
    ap.add_argument("--interval", type=int, default=60, help="seconds between beats")
    ap.add_argument("--audio-seconds", type=int, default=8)
    args = ap.parse_args()

    STATE.mkdir(parents=True, exist_ok=True)
    _log(f"heartbeat started (interval={args.interval}s, audio={args.audio_seconds}s, model={DEFAULT_MODEL})")

    while True:
        try:
            beat()
        except Exception as e:
            _log(f"beat crashed: {e}")
        if args.once:
            break
        time.sleep(args.interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())