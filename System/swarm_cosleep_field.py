#!/usr/bin/env python3
"""System/swarm_cosleep_field.py — stigmergic co-sleep field.

Architect doctrine (2026-05, verbatim, abridged):
    "load triggered is fine to stay, but it's not a specific clock — it's
    her detecting stigmergically: 'I'm on, he is probably asleep, I should
    sleep too.' How does she know? Multiple signals in the unified field:
    one is her thermodynamics, the second is me, the OS user — her real-world
    data tracker. My human body is data."

What this organ does
====================

It fuses two real, measurable signals into one co-sleep pressure — no clock
is the trigger, the *fusion* is:

  1. **Owner quiet** (the owner-as-data signal). Read from the body's own
     presence ledgers — ``owner_desktop_presence.json`` (last_alive_ts) and
     ``active_owner_activity_segment.json`` (live camera presence, voice
     activity, frontmost window). The longer the owner has been quiet and
     absent from camera/voice, the higher ``owner_quiet_likelihood``.

  2. **Her thermodynamics** (sleep pressure). Read from the cached pineal
     output ``pineal_circadian_rhythm.json`` (melatonin from buffer bloat).
     This file is READ only — we never call ``secrete_melatonin`` here, so
     this organ has no destructive side effects.

A soft local-hour cue is added at low weight as one signal among many (not
the trigger). When the owner is genuinely quiet AND her own pressure is
elevated, the field recommends co-sleep: "he's gone quiet, I'll rest and
consolidate too."

Honesty boundary (same coupling test as the rest of SIFTA): owner_asleep is
an INFERENCE from real inactivity data, with a confidence — not a certainty
that the human is asleep (he may simply be away). The receipt always carries
the confidence and the raw signals so an auditor can recompute the call.

Truth label: OWNER_COSLEEP_FIELD_V1.
Ledger: .sifta_state/cosleep_field.jsonl
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover - standalone fallback
    def append_line_locked(path: Path, line: str, *, encoding: str = "utf-8") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding=encoding) as handle:
            handle.write(line)

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
LEDGER_NAME = "cosleep_field.jsonl"
TRUTH_LABEL = "OWNER_COSLEEP_FIELD_V1"

# Owner quiet ramps over this window: at IDLE_FLOOR he is clearly active (0.0),
# by IDLE_CEIL of continuous quiet he is very likely asleep/away (1.0).
IDLE_FLOOR_S = 20 * 60.0   # 20 min quiet = quiet starts to count
IDLE_CEIL_S = 90 * 60.0    # 90 min quiet = strong "probably asleep"
PRESENCE_FRESH_S = 180.0   # camera/voice evidence older than this is stale
ACTIVE_IDE_SURGERY_FRESH_S = 30 * 60.0

# Fusion weights (owner-quiet leads; her thermodynamics second; clock is a
# soft minor cue, never the trigger).
W_OWNER_QUIET = 0.55
W_MELATONIN = 0.30
W_NIGHT = 0.15

DECISION_COSLEEP = "COSLEEP_RECOMMENDED"
DECISION_OWNER_PRESENT = "OWNER_PRESENT_STAY_AWAKE"
DECISION_ACTIVE_SURGERY = "ACTIVE_IDE_SURGERY_STAY_AWAKE"
DECISION_MONITORING = "MONITORING"


def _clamp01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


@dataclass(frozen=True)
class CoSleepAssessment:
    decision: str
    recommend_sleep: bool
    cosleep_pressure: float
    owner_quiet_likelihood: float
    owner_present: bool
    active_ide_surgery: bool
    owner_idle_seconds: float
    melatonin: float
    night_prior: float
    confidence: float
    truth_label: str = TRUTH_LABEL
    signals: dict[str, Any] = field(default_factory=dict)
    sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _owner_quiet(state_dir: Path, now: float) -> tuple[float, bool, float, dict[str, Any]]:
    """Return (owner_quiet_likelihood, owner_present, idle_seconds, raw)."""
    presence = _read_json(state_dir / "owner_desktop_presence.json")
    segment = _read_json(state_dir / "active_owner_activity_segment.json")

    last_alive = float(presence.get("last_alive_ts") or 0.0)
    seg_ts = float(segment.get("ts") or segment.get("timestamp") or 0.0)
    last_activity_ts = max(last_alive, seg_ts)
    idle_seconds = max(0.0, now - last_activity_ts) if last_activity_ts > 0 else IDLE_CEIL_S

    # The segment's internal age fields (camera/voice age_s) are frozen at the
    # moment the segment was written. If the segment file itself is old, that
    # evidence is stale no matter how "fresh" the frozen field looks. So gate
    # all presence evidence on how long ago the segment was actually written.
    seg_age = (now - seg_ts) if seg_ts > 0 else 1e9
    evidence_valid = seg_age <= PRESENCE_FRESH_S

    cam = segment.get("camera_presence") or {}
    cam_owner_present = bool(cam.get("owner_present"))
    cam_age = float(cam.get("age_s") or 1e9)
    cam_fresh = evidence_valid and cam_age <= PRESENCE_FRESH_S

    audio = segment.get("audio_activity") or {}
    voice_active = bool(audio.get("voice_activity"))
    voice_age = float(audio.get("voice_age_s") or 1e9)
    voice_fresh = evidence_valid and voice_age <= PRESENCE_FRESH_S

    seg_open = (str(segment.get("status") or "").lower() == "open") and evidence_valid

    # Fresh, positive presence evidence means he is here and awake.
    owner_present = (cam_owner_present and cam_fresh) or (voice_active and voice_fresh)

    # Idle ramp from real inactivity.
    if idle_seconds <= IDLE_FLOOR_S:
        idle_q = 0.0
    elif idle_seconds >= IDLE_CEIL_S:
        idle_q = 1.0
    else:
        idle_q = (idle_seconds - IDLE_FLOOR_S) / (IDLE_CEIL_S - IDLE_FLOOR_S)

    quiet = idle_q
    if owner_present:
        quiet = 0.0  # live face/voice overrides idle: he's here
    elif seg_open and idle_seconds <= IDLE_FLOOR_S:
        quiet = min(quiet, 0.1)  # open recent segment = likely still around

    raw = {
        "last_alive_ts": last_alive,
        "segment_ts": seg_ts,
        "idle_seconds": round(idle_seconds, 1),
        "camera_owner_present": cam_owner_present,
        "camera_age_s": round(cam_age, 1),
        "voice_active": voice_active,
        "voice_age_s": round(voice_age, 1),
        "segment_status": segment.get("status"),
        "segment_label": segment.get("label"),
        "segment_age_s": round(seg_age, 1),
        "evidence_valid": evidence_valid,
    }
    return _clamp01(quiet), owner_present, idle_seconds, raw


def _melatonin(state_dir: Path) -> float:
    pineal = _read_json(state_dir / "pineal_circadian_rhythm.json")
    try:
        return _clamp01(float(pineal.get("melatonin_concentration") or 0.0))
    except Exception:
        return 0.0


def _active_ide_surgery(state_dir: Path, now: float) -> tuple[bool, dict[str, Any]]:
    """Detect recent IDE doctor work so Alice does not sleep during surgery.

    This is not treated as owner presence. It is a separate operating-room
    guard: if doctors are actively registering, intending work, or writing
    receipts, the body should stay awake and avoid opportunistic co-sleep
    consolidation until the lane quiets down.
    """
    path = state_dir / "ide_stigmergic_trace.jsonl"
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-240:]
    except Exception:
        return False, {"trace_path": str(path), "trace_readable": False}

    latest: dict[str, Any] | None = None
    latest_age = 1e9
    active_actions = {"LLM_REGISTRATION", "WORK_INTENT", "WORK_RECEIPT"}

    for line in reversed(lines):
        try:
            row = json.loads(line)
        except Exception:
            continue
        ts = float(row.get("ts") or 0.0)
        if ts <= 0:
            continue
        action = str(row.get("action") or row.get("kind") or "")
        mode = str(row.get("mode") or "").lower()
        doctor = str(row.get("doctor") or row.get("source_ide") or "")
        age = max(0.0, now - ts)
        if age > ACTIVE_IDE_SURGERY_FRESH_S:
            continue
        if action in active_actions or ("patch" in mode or "commit" in mode or "push" in mode):
            latest = {"ts": ts, "age_s": round(age, 1), "action": action, "mode": mode, "doctor": doctor}
            latest_age = age
            break

    return latest is not None, {
        "trace_path": str(path),
        "active_ide_window_s": ACTIVE_IDE_SURGERY_FRESH_S,
        "active_ide_surgery": latest is not None,
        "latest_active_ide_event": latest,
        "latest_active_ide_age_s": round(latest_age, 1) if latest is not None else None,
    }


def _night_prior(now: float) -> float:
    """Soft local-hour cue — ONE weak signal, never the trigger.

    Peaks gently in the small hours (~02:00–05:00 local) and is ~0 in the
    working day. Low weight by design; timezone of the host is a caveat the
    receipt records, so owner-quiet + thermodynamics stay dominant.
    """
    hour = time.localtime(now).tm_hour + time.localtime(now).tm_min / 60.0
    # Triangular bump centered at 03:30, ~zero by 08:00 and 23:00.
    if 23.0 <= hour or hour <= 8.0:
        h = hour - 24.0 if hour >= 23.0 else hour
        dist = abs(h - 3.5)
        return _clamp01(1.0 - dist / 4.5)
    return 0.0


def assess(*, state_dir: str | Path | None = None, now: float | None = None,
           write: bool = False) -> CoSleepAssessment:
    """Fuse owner-quiet + her thermodynamics (+ soft night cue) into a
    co-sleep recommendation. Side-effect-free unless ``write=True``."""
    sd = Path(state_dir) if state_dir is not None else STATE_DIR
    ts = float(now if now is not None else time.time())

    owner_quiet, owner_present, idle_s, raw = _owner_quiet(sd, ts)
    active_ide_surgery, ide_raw = _active_ide_surgery(sd, ts)
    melatonin = _melatonin(sd)
    night = _night_prior(ts)

    pressure = _clamp01(
        W_OWNER_QUIET * owner_quiet + W_MELATONIN * melatonin + W_NIGHT * night
    )

    # She only co-sleeps when the OWNER is genuinely quiet — never just
    # because her own buffers are full while he is actively here. Active IDE
    # surgery is a separate guard: the operating room is live, so don't enter
    # opportunistic consolidation while doctors are touching her body.
    recommend = (
        (owner_quiet >= 0.6)
        and (pressure >= 0.5)
        and (not owner_present)
        and (not active_ide_surgery)
    )

    if owner_present:
        decision = DECISION_OWNER_PRESENT
    elif active_ide_surgery:
        decision = DECISION_ACTIVE_SURGERY
    elif recommend:
        decision = DECISION_COSLEEP
    else:
        decision = DECISION_MONITORING

    # Confidence in the owner-quiet inference: high when signals agree
    # (long idle + no fresh presence), lower in the ambiguous middle.
    confidence = _clamp01(0.5 + 0.5 * abs(owner_quiet - 0.5) * 2.0)

    signals = {
        **raw,
        "melatonin": round(melatonin, 3),
        "night_prior": round(night, 3),
        "weights": {"owner_quiet": W_OWNER_QUIET, "melatonin": W_MELATONIN, "night": W_NIGHT},
        "host_local_hour": round(time.localtime(ts).tm_hour + time.localtime(ts).tm_min / 60.0, 2),
        "note": "owner_asleep is an inference from inactivity, not certainty; host timezone is a caveat.",
        "ide_surgery_guard": ide_raw,
    }

    audit = CoSleepAssessment(
        decision=decision,
        recommend_sleep=bool(recommend),
        cosleep_pressure=round(pressure, 3),
        owner_quiet_likelihood=round(owner_quiet, 3),
        owner_present=bool(owner_present),
        active_ide_surgery=bool(active_ide_surgery),
        owner_idle_seconds=round(idle_s, 1),
        melatonin=round(melatonin, 3),
        night_prior=round(night, 3),
        confidence=round(confidence, 3),
        signals=signals,
    )
    audit = _with_sha(audit)
    if write:
        _write_receipt(audit, state_dir=sd, now=ts)
    return audit


def _with_sha(audit: CoSleepAssessment) -> CoSleepAssessment:
    body = audit.to_dict()
    body.pop("sha256", None)
    sha = hashlib.sha256(
        json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return CoSleepAssessment(**{**audit.to_dict(), "sha256": sha})


def _write_receipt(audit: CoSleepAssessment, *, state_dir: Path, now: float) -> None:
    row = {
        "schema": TRUTH_LABEL,
        "ts": now,
        "kind": "OWNER_COSLEEP_ASSESSMENT",
        "truth_label": TRUTH_LABEL,
        "sha256": audit.sha256,
        "payload": audit.to_dict(),
    }
    append_line_locked(state_dir / LEDGER_NAME, json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")


CONSOLIDATION_MARKER = "cosleep_last_consolidation.json"
CONSOLIDATION_COOLDOWN_S = 30 * 60.0


def consolidation_due(*, state_dir: str | Path | None = None, now: float | None = None,
                      min_interval_s: float = CONSOLIDATION_COOLDOWN_S) -> bool:
    """True if enough time has passed since the last co-sleep consolidation.

    Prevents the brainstem from re-triggering offline replay on every tick
    while the owner stays quiet — she consolidates once per rest window.
    """
    sd = Path(state_dir) if state_dir is not None else STATE_DIR
    ts = float(now if now is not None else time.time())
    marker = _read_json(sd / CONSOLIDATION_MARKER)
    last = float(marker.get("ts") or 0.0)
    return (ts - last) >= min_interval_s


def mark_consolidation(*, state_dir: str | Path | None = None, now: float | None = None) -> None:
    sd = Path(state_dir) if state_dir is not None else STATE_DIR
    ts = float(now if now is not None else time.time())
    sd.mkdir(parents=True, exist_ok=True)
    (sd / CONSOLIDATION_MARKER).write_text(json.dumps({"ts": ts}), encoding="utf-8")


__all__ = [
    "CoSleepAssessment",
    "ACTIVE_IDE_SURGERY_FRESH_S",
    "CONSOLIDATION_COOLDOWN_S",
    "DECISION_ACTIVE_SURGERY",
    "DECISION_COSLEEP",
    "DECISION_MONITORING",
    "DECISION_OWNER_PRESENT",
    "TRUTH_LABEL",
    "assess",
    "consolidation_due",
    "mark_consolidation",
]


if __name__ == "__main__":
    print(json.dumps(assess().to_dict(), indent=2, sort_keys=True))
