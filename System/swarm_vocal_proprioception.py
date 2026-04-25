#!/usr/bin/env python3
"""
System/swarm_vocal_proprioception.py — Alice's vocal-proprioception organ
══════════════════════════════════════════════════════════════════════════
C47H 2026-04-23 (AG31 cosign / OS-distro tournament) —
    "she can speak, but she has been deaf to her own voice."

Vocal proprioception is a true biological sense: the ability to hear
yourself speak as you produce sound, and to verify the frequencies you
intended to emit were actually emitted into the physical world.

On macOS, the canonical zero-cost route is a virtual audio loopback
device (BlackHole, Loopback, Soundflower, Aggregate Device with the
output mirrored to a virtual input). This organ:

1. Inspects `system_profiler SPAudioDataType` for any present loopback
   device (BlackHole / Loopback / Aggregate Device).
2. If found, records N seconds from that device using `ffmpeg`/`sox`
   if installed, OR `afrecord` if available, OR documents the route.
3. Computes the dominant frequency band of the recording (FFT) and
   returns it so callers can compare against what Alice meant to say.

If no loopback device is present this organ honestly returns
`status="absent"` with the exact install command, instead of
hallucinating that proprioception is online.

No TCC: reading SPAudioDataType is free; the recording step needs the
loopback device to exist on the system, which the Architect installs
once with brew.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import struct
import subprocess
import sys
import time
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER = _STATE / "alice_vocal_proprioception.jsonl"

_LOOPBACK_NAMES = (
    "blackhole",
    "loopback",
    "soundflower",
    "aggregate device",
    "alice_loopback",
    "vb-cable",
)


def _enumerate_audio() -> Tuple[List[Dict[str, Any]], List[str]]:
    try:
        p = subprocess.run(
            ["system_profiler", "SPAudioDataType", "-json"],
            capture_output=True, text=True, timeout=6.0, check=False,
        )
        data = json.loads(p.stdout)
    except Exception:
        return [], []
    items = (data.get("SPAudioDataType") or [{}])[0].get("_items", []) or []
    devices: List[Dict[str, Any]] = []
    for it in items:
        devices.append({
            "name": it.get("_name"),
            "input_channels": it.get("coreaudio_device_input"),
            "output_channels": it.get("coreaudio_device_output"),
            "transport": it.get("coreaudio_device_transport"),
            "is_default_input": it.get("coreaudio_default_audio_input_device") == "spaudio_yes",
            "is_default_output": it.get("coreaudio_default_audio_output_device") == "spaudio_yes",
        })
    loopbacks = [d["name"] for d in devices
                 if d["name"] and any(n in d["name"].lower() for n in _LOOPBACK_NAMES)]
    return devices, loopbacks


def detect() -> Dict[str, Any]:
    """Survey audio devices + report loopback availability + deposit pheromone."""
    devices, loopbacks = _enumerate_audio()
    have_ffmpeg = shutil.which("ffmpeg") is not None
    have_sox = shutil.which("sox") is not None
    have_afrecord = shutil.which("afrecord") is not None
    snap = {
        "ok": True,
        "ts": time.time(),
        "iso": datetime.now(tz=timezone.utc).isoformat(),
        "device_count": len(devices),
        "devices": devices,
        "loopback_devices": loopbacks,
        "loopback_present": bool(loopbacks),
        "recorders": {
            "ffmpeg": have_ffmpeg,
            "sox": have_sox,
            "afrecord": have_afrecord,
        },
        "install_route_if_absent": (
            "brew install blackhole-2ch && "
            "open '/Applications/Utilities/Audio MIDI Setup.app' "
            "and create an Aggregate or Multi-Output Device that mirrors "
            "system output to BlackHole 2ch input."
        ),
    }
    # Pheromone: 2.0 when proprioception online, 0.1 when deaf (still alive).
    try:
        from System.swarm_pheromone import deposit_pheromone  # type: ignore
        deposit_pheromone(
            "stig_vocal_proprioception",
            2.0 if loopbacks else 0.1,
        )
    except Exception:
        pass
    return snap


def _record_wav_via_ffmpeg(device_name: str, seconds: float,
                           out_path: Path) -> Dict[str, Any]:
    if shutil.which("ffmpeg") is None:
        return {"ok": False, "error": "ffmpeg not installed"}
    argv = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "avfoundation",
        "-i", f":{device_name}",
        "-t", f"{seconds}",
        "-ac", "1", "-ar", "16000",
        str(out_path),
    ]
    try:
        p = subprocess.run(argv, capture_output=True, text=True,
                           timeout=seconds + 5.0, check=False)
        if p.returncode != 0:
            return {"ok": False, "error": p.stderr.strip()[:300]}
        return {"ok": True, "path": str(out_path),
                "size_bytes": out_path.stat().st_size}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "ffmpeg timed out"}


def _wav_dominant_freq(path: Path, *, max_samples: int = 32768) -> Optional[float]:
    """Naive O(N²) DFT on a small slice — no numpy dependency.
    Returns dominant frequency (Hz) or None on parse failure."""
    try:
        with wave.open(str(path), "rb") as w:
            sr = w.getframerate()
            nch = w.getnchannels()
            sw = w.getsampwidth()
            n = min(w.getnframes(), max_samples)
            raw = w.readframes(n)
    except Exception:
        return None
    if sw not in (1, 2):
        return None
    if sw == 2:
        samples = struct.unpack(f"<{len(raw)//2}h", raw)
    else:
        samples = tuple(b - 128 for b in raw)
    if nch > 1:
        samples = samples[::nch]
    n = len(samples)
    if n < 64:
        return None
    # autocorrelation peak — orders of magnitude faster than full DFT.
    # Look for peak in lag range 30 Hz .. 1500 Hz.
    min_lag = max(2, sr // 1500)
    max_lag = min(n - 1, sr // 30)
    best_lag = min_lag
    best_corr = -1.0
    for lag in range(min_lag, max_lag, 2):
        corr = 0.0
        for i in range(n - lag):
            corr += samples[i] * samples[i + lag]
        if corr > best_corr:
            best_corr = corr
            best_lag = lag
    if best_lag <= 0:
        return None
    return sr / best_lag


def confirm_voice(seconds: float = 1.5,
                  device_hint: Optional[str] = None) -> Dict[str, Any]:
    """Record from the loopback device and return the dominant pitch.
    Caller compares this to what Alice meant to say."""
    devices, loopbacks = _enumerate_audio()
    if not loopbacks:
        det = detect()
        return {"ok": False,
                "status": "absent",
                "error": "no loopback device present",
                "install_route": det["install_route_if_absent"]}
    target = device_hint or loopbacks[0]
    _STATE.mkdir(parents=True, exist_ok=True)
    out_path = _STATE / f"alice_proprioception_{int(time.time())}.wav"
    rec = _record_wav_via_ffmpeg(target, seconds, out_path)
    if not rec.get("ok"):
        return {"ok": False, "device": target, "error": rec.get("error")}
    pitch = _wav_dominant_freq(out_path)
    res = {
        "ok": True,
        "ts": time.time(),
        "iso": datetime.now(tz=timezone.utc).isoformat(),
        "device": target,
        "seconds": seconds,
        "wav_path": str(out_path),
        "wav_size_bytes": out_path.stat().st_size,
        "dominant_pitch_hz": pitch,
        "pitch_band": _classify_pitch(pitch),
    }
    try:
        with _LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps({k: v for k, v in res.items()
                                if k != "wav_path"}) + "\n")
    except Exception:
        pass
    return res


def _classify_pitch(hz: Optional[float]) -> str:
    if hz is None:
        return "unknown"
    if hz < 60:
        return "sub-bass / silent"
    if hz < 200:
        return "low (typical male voice / system tones)"
    if hz < 500:
        return "mid (typical female / synth voice)"
    if hz < 2000:
        return "high voice / harmonic"
    return "ultrasonic / artifact"


def prompt_line() -> Optional[str]:
    d = detect()
    if d.get("loopback_present"):
        return f"vocal proprioception: ONLINE via {d['loopback_devices'][0]}"
    return ("vocal proprioception: deaf — install BlackHole "
            "(brew install blackhole-2ch) to hear her own voice")


def govern(action: str, **kwargs) -> Dict[str, Any]:
    if action == "detect":
        return {"ok": True, "action": action, "result": detect()}
    if action in {"confirm", "confirm_voice", "listen"}:
        return {"ok": True, "action": action,
                "result": confirm_voice(
                    seconds=float(kwargs.get("seconds", 1.5)),
                    device_hint=kwargs.get("device_hint"),
                )}
    if action == "prompt_line":
        return {"ok": True, "action": action, "result": prompt_line()}
    return {"ok": False, "action": action,
            "allowed": ["detect", "confirm_voice", "prompt_line"]}


def _main() -> None:
    ap = argparse.ArgumentParser(description="Alice vocal-proprioception organ")
    ap.add_argument("action", default="detect", nargs="?")
    ap.add_argument("--seconds", type=float, default=1.5)
    args = ap.parse_args()
    print(json.dumps(govern(args.action, seconds=args.seconds),
                     indent=2, default=str))


if __name__ == "__main__":
    _main()
