#!/usr/bin/env python3
"""Owner-labeled background audio receipts for Alice.

This organ records the owner's live ambient label ("background", "birds in
background", porch sound, etc.) and attaches the newest acoustic receipt if one
exists. It does not pretend to identify species; the owner's label is the fact.
"""
from __future__ import annotations

import json
import re
import struct
import time
import wave
from pathlib import Path
from typing import Any, Mapping, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
LEDGER_NAME = "background_audio_receipts.jsonl"
TRUTH_LABEL = "BACKGROUND_AUDIO_OWNER_LABEL_RECEIPT_V1"
CLIP_DIR_NAME = "background_audio_clips"

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover - fallback for standalone smoke use
    def append_line_locked(path, line, *, encoding="utf-8"):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding=encoding) as f:
            f.write(line)


def _state(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def _tail_jsonl(path: Path, max_rows: int = 80) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    for line in lines[-max(1, max_rows):]:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _row_ts(row: Mapping[str, Any]) -> float:
    for key in ("ts", "timestamp", "ts_captured", "created_at", "time"):
        try:
            return float(row.get(key))
        except Exception:
            continue
    return 0.0


def _short(text: Any, limit: int = 220) -> str:
    s = " ".join(str(text or "").replace("\n", " ").split())
    return s if len(s) <= limit else s[: limit - 3].rstrip() + "..."


def _latest_acoustic_context(base: Path, *, now: float, max_age_s: float) -> dict[str, Any]:
    best: tuple[float, str, dict[str, Any]] = (0.0, "", {})
    for filename in (
        "acoustic_fingerprints.jsonl",
        "acoustic_scene_classifications.jsonl",
        "audio_ingress_log.jsonl",
    ):
        rows = _tail_jsonl(base / filename, max_rows=80)
        if not rows:
            continue
        row = max(rows, key=_row_ts)
        ts = _row_ts(row)
        if ts >= best[0]:
            best = (ts, filename, row)
    ts, filename, row = best
    if not row or now - ts > max_age_s:
        return {
            "attached": False,
            "reason": "no_fresh_acoustic_receipt",
            "max_age_s": max_age_s,
        }
    return {
        "attached": True,
        "ledger": filename,
        "age_s": round(max(0.0, now - ts), 3),
        "ts": ts,
        "source": row.get("source") or row.get("device") or row.get("device_name"),
        "reality_hash": row.get("reality_hash") or row.get("hash") or row.get("audio_hash"),
        "sample_id": row.get("sample_id") or row.get("receipt_id"),
        "rms_amplitude": row.get("rms_amplitude") or row.get("rms"),
        "channel_cue": row.get("channel_cue") or row.get("scene") or row.get("class"),
    }


def _clock() -> dict[str, Any]:
    try:
        from System.swarm_hardware_time_oracle import current_time_for_alice

        reading = current_time_for_alice()
        return reading if isinstance(reading, dict) else {"ok": False}
    except Exception:
        return {"ok": False}


def _save_sample_clip(base: Path, sample: Any) -> dict[str, Any]:
    source = str(getattr(sample, "source", "") or "")
    buffer = list(getattr(sample, "buffer", []) or [])
    if source == "mock" or not buffer:
        return {
            "saved": False,
            "reason": "no_real_audio_clip_available",
            "sample_source": source or "unknown",
            "sample_id": getattr(sample, "sample_id", None),
            "reality_hash": getattr(sample, "reality_hash", None),
        }
    sample_rate = int(getattr(sample, "sample_rate", 48000) or 48000)
    clip_dir = base / CLIP_DIR_NAME
    clip_dir.mkdir(parents=True, exist_ok=True)
    sample_id = str(getattr(sample, "sample_id", f"audio_{int(time.time() * 1000)}"))
    path = clip_dir / f"{sample_id}.wav"
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for value in buffer:
            clipped = max(-1.0, min(1.0, float(value)))
            frames.extend(struct.pack("<h", int(clipped * 32767.0)))
        wf.writeframes(bytes(frames))
    return {
        "saved": True,
        "path": str(path),
        "sample_id": sample_id,
        "sample_source": source,
        "device_name": getattr(sample, "device_name", None),
        "duration_s": getattr(sample, "duration_s", None),
        "sample_rate": sample_rate,
        "reality_hash": getattr(sample, "reality_hash", None),
        "rms_amplitude": getattr(sample, "rms_amplitude", None),
    }


def _capture_optional_clip(base: Path, *, burst_s: float) -> dict[str, Any]:
    try:
        from System.audio_ingress import capture_acoustic_truth

        sample = capture_acoustic_truth(burst_s=burst_s, feed_to_acoustic_field=True)
    except Exception as exc:
        return {"saved": False, "reason": "capture_failed", "error": f"{type(exc).__name__}: {exc}"}
    if sample is None:
        return {"saved": False, "reason": "capture_returned_none"}
    try:
        return _save_sample_clip(base, sample)
    except Exception as exc:
        return {
            "saved": False,
            "reason": "clip_save_failed",
            "error": f"{type(exc).__name__}: {exc}",
            "sample_source": getattr(sample, "source", None),
            "sample_id": getattr(sample, "sample_id", None),
            "reality_hash": getattr(sample, "reality_hash", None),
        }


def record_background_audio_observation(
    owner_text: str,
    *,
    state_dir: Optional[Path | str] = None,
    input_source: str = "",
    stt_conf: float = 0.0,
    now: Optional[float] = None,
    max_age_s: float = 300.0,
    capture_clip: bool = False,
    clip_burst_s: float = 0.75,
) -> dict[str, Any]:
    """Append an owner-labeled ambient sound receipt and return the row."""
    t = float(now if now is not None else time.time())
    base = _state(state_dir)
    labels = ["background_audio"]
    text = str(owner_text or "")
    if re.search(r"\bbirds?\b", text, re.IGNORECASE):
        labels.append("owner_labeled_birds")
    if re.search(r"\bporch\b", text, re.IGNORECASE):
        labels.append("owner_labeled_porch")
    clock = _clock()
    clip = _capture_optional_clip(base, burst_s=clip_burst_s) if capture_clip else {
        "saved": False,
        "reason": "not_requested",
    }
    row = {
        "truth_label": TRUTH_LABEL,
        "ts": t,
        "clock": {
            "source": clock.get("source"),
            "local_human": clock.get("local_human"),
            "timezone": clock.get("timezone"),
            "local_iso": clock.get("local_iso"),
            "signature": clock.get("signature"),
        },
        "source": "owner_labeled_current_turn",
        "input_source": input_source,
        "stt_confidence": round(float(stt_conf), 3) if stt_conf else None,
        "labels": labels,
        "owner_text": _short(text),
        "acoustic_context": _latest_acoustic_context(base, now=t, max_age_s=max_age_s),
        "raw_clip_saved": bool(clip.get("saved")),
        "raw_clip": clip,
    }
    append_line_locked(base / LEDGER_NAME, json.dumps(row, ensure_ascii=False) + "\n")
    return row


def format_background_audio_observation(row: Mapping[str, Any]) -> str:
    labels = ", ".join(str(x) for x in row.get("labels", []) if x)
    clock = row.get("clock") if isinstance(row.get("clock"), Mapping) else {}
    local_human = str(clock.get("local_human") or "").strip()
    timezone = str(clock.get("timezone") or "").strip()
    when = f"{local_human} {timezone}".strip() or f"ts={row.get('ts')}"
    acoustic = row.get("acoustic_context") if isinstance(row.get("acoustic_context"), Mapping) else {}
    if acoustic.get("attached"):
        ledger = acoustic.get("ledger") or "acoustic ledger"
        age = acoustic.get("age_s")
        cue = acoustic.get("channel_cue") or acoustic.get("source") or ""
        tail = f" Attached acoustic receipt={ledger}, age={age}s"
        if cue:
            tail += f", cue={cue}"
        if acoustic.get("reality_hash"):
            tail += f", hash={str(acoustic.get('reality_hash'))[:12]}"
        tail += "."
    else:
        tail = " Acoustic hash attached=none_fresh; owner ambient label is recorded."
    clip = row.get("raw_clip") if isinstance(row.get("raw_clip"), Mapping) else {}
    if clip.get("saved"):
        tail += f" Clip saved={clip.get('path')}."
    elif clip.get("reason") not in {"not_requested", None, ""}:
        tail += f" Clip capture={clip.get('reason')}."
    return f"Receipt: I marked the current background as {labels or 'background_audio'} at {when}.{tail}"


__all__ = [
    "TRUTH_LABEL",
    "LEDGER_NAME",
    "record_background_audio_observation",
    "format_background_audio_observation",
]
