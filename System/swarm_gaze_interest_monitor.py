#!/usr/bin/env python3
"""Gaze interest monitor: Architect vs screen dwell from receipts.

This organ does not do biometric recognition and does not inspect raw frames.
It reads the existing sensory receipts and estimates where Alice's active
attention is pointed:

    ARCHITECT  fresh face/near-field/social evidence dominates
    SCREEN     YouTube/app-focus/visual-active-matter/screen-eye evidence dominates
    MIXED      both channels are similarly strong
    IDLE       no fresh evidence

The goal is dwell accounting, not control. Camera leases are left to
swarm_sensor_attention_director / swarm_camera_target.
"""
from __future__ import annotations

import json
import math
import time
import argparse
from pathlib import Path
from typing import Any, Mapping, Optional

from System.jsonl_file_lock import append_line_locked, read_text_locked, rewrite_text_locked

_REPO = Path(__file__).resolve().parent.parent
DEFAULT_STATE = _REPO / ".sifta_state"
LEDGER_NAME = "gaze_interest_monitor.jsonl"
SUMMARY_NAME = "gaze_interest_summary.json"
TRUTH_LABEL = "GAZE_INTEREST_MONITOR_V1"

TARGET_ARCHITECT = "ARCHITECT"
TARGET_SCREEN = "SCREEN"
TARGET_MIXED = "MIXED"
TARGET_IDLE = "IDLE"
TARGET_UNKNOWN = "UNKNOWN"

_SCREEN_EYE_HINTS = ("usb camera", "logitech", "vid:1133", "room", "screen")
_ARCHITECT_EYE_HINTS = ("macbook", "facetime", "built-in", "close", "owner")


def _state_dir(state_dir: Optional[Path] = None) -> Path:
    return Path(state_dir) if state_dir is not None else DEFAULT_STATE


def _clamp01(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except Exception:
        return default
    if not math.isfinite(number):
        return default
    return max(0.0, min(1.0, number))


def _coerce_ts(row: Mapping[str, Any], default: float = 0.0) -> float:
    for key in ("ts", "timestamp", "time", "ts_captured", "created_at"):
        try:
            value = float(row.get(key, default) or default)
        except Exception:
            continue
        if math.isfinite(value):
            return value
    return default


def _age_weight(ts: Any, now: float, *, half_life_s: float) -> float:
    try:
        age = max(0.0, now - float(ts))
    except Exception:
        return 0.0
    if not math.isfinite(age):
        return 0.0
    if half_life_s <= 0:
        return 0.0
    return math.exp(-age / half_life_s)


def _tail_jsonl(path: Path, n: int = 1) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = read_text_locked(path, encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in lines[-max(1, int(n)) :]:
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _latest_jsonl(path: Path) -> dict[str, Any]:
    rows = _tail_jsonl(path, 1)
    return rows[-1] if rows else {}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        row = json.loads(read_text_locked(path, encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return row if isinstance(row, dict) else {}


def _camera_channel(target: Mapping[str, Any]) -> str:
    text = " ".join(
        str(target.get(key) or "") for key in ("name", "writer", "target_role", "purpose")
    ).lower()
    index = target.get("index")
    if any(hint in text for hint in _SCREEN_EYE_HINTS):
        return TARGET_SCREEN
    if any(hint in text for hint in _ARCHITECT_EYE_HINTS):
        return TARGET_ARCHITECT
    try:
        idx = int(index)
    except Exception:
        return TARGET_UNKNOWN
    if idx == 0:
        return TARGET_SCREEN
    if idx == 1:
        return TARGET_ARCHITECT
    return TARGET_UNKNOWN


def collect_gaze_evidence(
    *,
    state_dir: Optional[Path] = None,
    now: Optional[float] = None,
) -> dict[str, Any]:
    state = _state_dir(state_dir)
    t = time.time() if now is None else float(now)

    face = _latest_jsonl(state / "face_detection_events.jsonl")
    target = _read_json(state / "active_saccade_target.json")
    sensory = _read_json(state / "sensory_attention_status.json")
    app_focus = _latest_jsonl(state / "app_focus.jsonl")
    active_window = _latest_jsonl(state / "active_window.jsonl")
    visual = _latest_jsonl(state / "visual_active_matter.jsonl")
    orienting = _latest_jsonl(state / "orienting_reflex.jsonl")
    youtube = _read_json(state / "youtube_context_latest.json")
    watch = _latest_jsonl(state / "youtube_watch_memory.jsonl")
    acoustic = _latest_jsonl(state / "acoustic_fingerprints.jsonl")

    return {
        "now": t,
        "face": face,
        "camera_target": target,
        "camera_channel": _camera_channel(target),
        "sensory_attention": sensory,
        "app_focus": app_focus,
        "active_window": active_window,
        "visual_active_matter": visual,
        "orienting_reflex": orienting,
        "youtube_context": youtube,
        "youtube_watch_memory": watch,
        "acoustic_fingerprint": acoustic,
    }


def _text_has_screen_context(*parts: Any) -> bool:
    text = " ".join(str(p or "") for p in parts).lower()
    return any(
        token in text
        for token in (
            "youtube",
            "video",
            "screen",
            "safari",
            "browser",
            "movie",
            "fictional_media_clip",
            "watching",
            "app focus",
        )
    )


def _active_sense_role(row: Mapping[str, Any]) -> str:
    return str(row.get("active_sense") or row.get("target_role") or "").lower()


def _acoustic_scores(row: Mapping[str, Any]) -> tuple[float, float]:
    fp = row.get("playback_fingerprint") if isinstance(row.get("playback_fingerprint"), dict) else row
    if not isinstance(fp, Mapping):
        return 0.0, 0.0
    near = _clamp01(fp.get("nearfield_voice_likelihood", 0.0))
    far = _clamp01(fp.get("farfield_replay_likelihood", 0.0))
    return near, far


def compute_interest_from_evidence(evidence: Mapping[str, Any]) -> dict[str, Any]:
    now = float(evidence.get("now") or time.time())
    architect = 0.0
    screen = 0.0
    reasons: list[str] = []
    signal_rows: dict[str, Any] = {}

    face = evidence.get("face") if isinstance(evidence.get("face"), Mapping) else {}
    face_ts = _coerce_ts(face, 0.0)
    face_w = _age_weight(face_ts, now, half_life_s=18.0)
    audience = str(face.get("audience") or "")
    face_conf = _clamp01(face.get("confidence", face.get("max_confidence", 0.0)))
    faces_detected = int(float(face.get("faces_detected", 0) or 0))
    if face_w > 0.05 and audience == "architect":
        architect += 0.55 * max(face_conf, 0.65) * face_w
        reasons.append("fresh_architect_face")
    elif face_w > 0.05 and faces_detected > 0:
        architect += 0.18 * max(face_conf, 0.35) * face_w
        reasons.append("fresh_face_nonidentity")
    signal_rows["face"] = {
        "age_weight": round(face_w, 4),
        "audience": audience,
        "faces_detected": faces_detected,
        "confidence": round(face_conf, 4),
    }

    camera = evidence.get("camera_target") if isinstance(evidence.get("camera_target"), Mapping) else {}
    cam_ts = _coerce_ts(camera, now)
    cam_w = _age_weight(cam_ts, now, half_life_s=45.0)
    camera_channel = str(evidence.get("camera_channel") or TARGET_UNKNOWN)
    if camera_channel == TARGET_ARCHITECT:
        architect += 0.24 * cam_w
        reasons.append("active_eye_close_owner")
    elif camera_channel == TARGET_SCREEN:
        screen += 0.24 * cam_w
        reasons.append("active_eye_screen_room")
    signal_rows["camera_target"] = {
        "age_weight": round(cam_w, 4),
        "channel": camera_channel,
        "name": str(camera.get("name") or ""),
        "writer": str(camera.get("writer") or ""),
    }

    sensory = evidence.get("sensory_attention") if isinstance(evidence.get("sensory_attention"), Mapping) else {}
    sense_role = _active_sense_role(sensory)
    sense_desire = _clamp01(sensory.get("desire", 0.0))
    sense_ts = _coerce_ts(sensory, now)
    sense_w = _age_weight(sense_ts, now, half_life_s=30.0)
    if "close_owner" in sense_role:
        architect += 0.18 * max(sense_desire, 0.25) * sense_w
        reasons.append("attention_director_owner")
    elif "room" in sense_role or "patrol" in sense_role:
        screen += 0.18 * max(sense_desire, 0.25) * sense_w
        reasons.append("attention_director_room")
    signal_rows["sensory_attention"] = {
        "role": sense_role,
        "desire": round(sense_desire, 4),
        "age_weight": round(sense_w, 4),
    }

    app_focus = evidence.get("app_focus") if isinstance(evidence.get("app_focus"), Mapping) else {}
    active_window = evidence.get("active_window") if isinstance(evidence.get("active_window"), Mapping) else {}
    app_w = _age_weight(_coerce_ts(app_focus, 0.0), now, half_life_s=90.0)
    win_w = _age_weight(_coerce_ts(active_window, 0.0), now, half_life_s=90.0)
    if app_w > 0.05 and _text_has_screen_context(
        app_focus.get("app"), app_focus.get("detail"), app_focus.get("selection"), app_focus.get("metadata")
    ):
        screen += 0.24 * app_w
        reasons.append("screen_app_focus")
    if win_w > 0.05 and _text_has_screen_context(
        active_window.get("app"), active_window.get("window"), active_window.get("browser")
    ):
        screen += 0.18 * win_w
        reasons.append("screen_active_window")
    signal_rows["screen_focus"] = {
        "app_focus_age_weight": round(app_w, 4),
        "active_window_age_weight": round(win_w, 4),
        "app": str(app_focus.get("app") or ""),
        "window": str(active_window.get("window") or "")[:120],
    }

    youtube = evidence.get("youtube_context") if isinstance(evidence.get("youtube_context"), Mapping) else {}
    watch = evidence.get("youtube_watch_memory") if isinstance(evidence.get("youtube_watch_memory"), Mapping) else {}
    yt_w = _age_weight(_coerce_ts(youtube, 0.0), now, half_life_s=300.0)
    watch_w = _age_weight(_coerce_ts(watch, 0.0), now, half_life_s=1800.0)
    if yt_w > 0.02 and (youtube.get("title") or youtube.get("status")):
        screen += 0.36 * yt_w
        reasons.append("youtube_context_recent")
    if watch_w > 0.02 and watch.get("truth_label"):
        screen += 0.20 * watch_w
        reasons.append("youtube_cowatch_memory")
    signal_rows["youtube"] = {
        "context_age_weight": round(yt_w, 4),
        "watch_age_weight": round(watch_w, 4),
        "title": str(youtube.get("title") or watch.get("title") or "")[:160],
        "reality_frame": str(
            youtube.get("reality_frame")
            or ((watch.get("reality_frame") or {}).get("reality_frame") if isinstance(watch.get("reality_frame"), dict) else "")
        ),
    }

    visual = evidence.get("visual_active_matter") if isinstance(evidence.get("visual_active_matter"), Mapping) else {}
    vis_w = _age_weight(_coerce_ts(visual, 0.0), now, half_life_s=12.0)
    visual_interest = _clamp01(
        0.45 * _clamp01(visual.get("field_energy", 0.0) * 3.0)
        + 0.35 * _clamp01(visual.get("persistence", 0.0))
        + 0.20 * _clamp01(visual.get("novelty", 0.0) * 3.0)
    )
    if vis_w > 0.05 and visual_interest > 0.05:
        screen += 0.30 * visual_interest * vis_w
        reasons.append("visual_active_matter_interest")
    signal_rows["visual_active_matter"] = {
        "age_weight": round(vis_w, 4),
        "field_energy": _clamp01(visual.get("field_energy", 0.0)),
        "persistence": _clamp01(visual.get("persistence", 0.0)),
        "novelty": _clamp01(visual.get("novelty", 0.0)),
        "visual_interest": round(visual_interest, 4),
    }

    acoustic = evidence.get("acoustic_fingerprint") if isinstance(evidence.get("acoustic_fingerprint"), Mapping) else {}
    acoustic_w = _age_weight(_coerce_ts(acoustic, 0.0), now, half_life_s=20.0)
    near, far = _acoustic_scores(acoustic)
    if acoustic_w > 0.05 and near > 0.45:
        architect += 0.18 * near * acoustic_w
        reasons.append("nearfield_voice_audio")
    if acoustic_w > 0.05 and far > 0.45:
        screen += 0.18 * far * acoustic_w
        reasons.append("farfield_media_audio")
    signal_rows["acoustic"] = {
        "age_weight": round(acoustic_w, 4),
        "nearfield": round(near, 4),
        "farfield": round(far, 4),
    }

    orient = evidence.get("orienting_reflex") if isinstance(evidence.get("orienting_reflex"), Mapping) else {}
    orient_w = _age_weight(_coerce_ts(orient, 0.0), now, half_life_s=25.0)
    orient_intensity = _clamp01(orient.get("orienting_intensity", 0.0))
    if orient_w > 0.05 and orient_intensity > 0.05:
        # Orienting energy follows the evidence winner; it does not dictate a
        # fixed target. This keeps "interest" evidence-bound instead of a rule.
        if screen >= architect:
            screen += 0.14 * orient_intensity * orient_w
            reasons.append("orienting_reflex_screen_weighted")
        else:
            architect += 0.14 * orient_intensity * orient_w
            reasons.append("orienting_reflex_architect_weighted")
    signal_rows["orienting"] = {
        "age_weight": round(orient_w, 4),
        "intensity": round(orient_intensity, 4),
        "trigger": bool(orient.get("orient_trigger", False)),
    }

    architect = _clamp01(architect)
    screen = _clamp01(screen)
    max_score = max(architect, screen)
    gap = abs(architect - screen)
    if max_score < 0.12:
        target = TARGET_IDLE
    elif gap <= 0.10 and min(architect, screen) >= 0.18:
        target = TARGET_MIXED
    elif architect > screen:
        target = TARGET_ARCHITECT
    else:
        target = TARGET_SCREEN
    confidence = 0.0 if target == TARGET_IDLE else _clamp01(0.35 + gap + 0.35 * max_score)

    return {
        "target": target,
        "confidence": round(confidence, 4),
        "architect_interest": round(architect, 4),
        "screen_interest": round(screen, 4),
        "interest_gap": round(gap, 4),
        "reasons": reasons,
        "evidence": signal_rows,
        "privacy_boundary": (
            "No raw frames, raw audio, face embeddings, or biometric identity are stored; "
            "this row uses bounded ledger receipts only."
        ),
    }


def _empty_summary() -> dict[str, Any]:
    return {
        "truth_label": TRUTH_LABEL,
        "schema_version": "gaze_interest_summary.v1",
        "total_observed_s": 0.0,
        "dwell_seconds": {
            TARGET_ARCHITECT: 0.0,
            TARGET_SCREEN: 0.0,
            TARGET_MIXED: 0.0,
            TARGET_IDLE: 0.0,
            TARGET_UNKNOWN: 0.0,
        },
        "last_target": TARGET_UNKNOWN,
        "last_ts": 0.0,
    }


def _latest_monitor_row(state: Path) -> dict[str, Any]:
    return _latest_jsonl(state / LEDGER_NAME)


def _credit_dwell(summary: dict[str, Any], target: str, dt_s: float) -> dict[str, Any]:
    out = dict(summary or _empty_summary())
    dwell = dict(out.get("dwell_seconds") or {})
    for key in (TARGET_ARCHITECT, TARGET_SCREEN, TARGET_MIXED, TARGET_IDLE, TARGET_UNKNOWN):
        dwell.setdefault(key, 0.0)
    target = target if target in dwell else TARGET_UNKNOWN
    dwell[target] = round(float(dwell.get(target, 0.0) or 0.0) + dt_s, 4)
    total = round(float(out.get("total_observed_s", 0.0) or 0.0) + dt_s, 4)
    effective_architect = float(dwell[TARGET_ARCHITECT]) + 0.5 * float(dwell[TARGET_MIXED])
    effective_screen = float(dwell[TARGET_SCREEN]) + 0.5 * float(dwell[TARGET_MIXED])
    denom = max(1e-9, effective_architect + effective_screen)
    out.update(
        {
            "truth_label": TRUTH_LABEL,
            "schema_version": "gaze_interest_summary.v1",
            "total_observed_s": total,
            "dwell_seconds": dwell,
            "effective_architect_s": round(effective_architect, 4),
            "effective_screen_s": round(effective_screen, 4),
            "architect_ratio": round(effective_architect / denom, 4) if total > 0 else 0.0,
            "screen_ratio": round(effective_screen / denom, 4) if total > 0 else 0.0,
        }
    )
    return out


def write_gaze_interest_sample(
    *,
    state_dir: Optional[Path] = None,
    now: Optional[float] = None,
    max_dt_s: float = 15.0,
) -> dict[str, Any]:
    state = _state_dir(state_dir)
    state.mkdir(parents=True, exist_ok=True)
    t = time.time() if now is None else float(now)
    evidence = collect_gaze_evidence(state_dir=state, now=t)
    interest = compute_interest_from_evidence(evidence)

    previous = _latest_monitor_row(state)
    previous_target = str(previous.get("target") or TARGET_UNKNOWN)
    previous_ts = float(previous.get("ts", t) or t) if previous else t
    dt_s = max(0.0, min(float(max_dt_s), t - previous_ts)) if previous else 0.0

    summary_path = state / SUMMARY_NAME
    summary = _read_json(summary_path) or _empty_summary()
    summary = _credit_dwell(summary, previous_target, round(dt_s, 4))
    summary["last_target"] = interest["target"]
    summary["last_ts"] = t
    summary["last_reasons"] = interest["reasons"][:8]
    summary["last_confidence"] = interest["confidence"]
    rewrite_text_locked(summary_path, json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")

    row = {
        "ts": t,
        "truth_label": TRUTH_LABEL,
        "schema_version": "gaze_interest_monitor.v1",
        "target": interest["target"],
        "confidence": interest["confidence"],
        "architect_interest": interest["architect_interest"],
        "screen_interest": interest["screen_interest"],
        "interest_gap": interest["interest_gap"],
        "reasons": interest["reasons"][:12],
        "dwell_update": {
            "credited_target": previous_target if previous else TARGET_UNKNOWN,
            "dt_s": round(dt_s, 4),
            "max_dt_s": float(max_dt_s),
        },
        "summary": {
            "total_observed_s": summary["total_observed_s"],
            "effective_architect_s": summary.get("effective_architect_s", 0.0),
            "effective_screen_s": summary.get("effective_screen_s", 0.0),
            "architect_ratio": summary.get("architect_ratio", 0.0),
            "screen_ratio": summary.get("screen_ratio", 0.0),
        },
        "evidence": interest["evidence"],
        "privacy_boundary": interest["privacy_boundary"],
    }
    append_line_locked(state / LEDGER_NAME, json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return row


def summary_for_alice(*, state_dir: Optional[Path] = None, max_age_s: float = 120.0) -> str:
    state = _state_dir(state_dir)
    summary = _read_json(state / SUMMARY_NAME)
    if not summary:
        return ""
    try:
        age = time.time() - float(summary.get("last_ts", 0.0))
    except Exception:
        return ""
    if age > max_age_s:
        return ""
    return (
        "GAZE INTEREST MONITOR: "
        f"target={summary.get('last_target', TARGET_UNKNOWN)} "
        f"conf={float(summary.get('last_confidence', 0.0) or 0.0):.2f} "
        f"screen={float(summary.get('effective_screen_s', 0.0) or 0.0):.1f}s "
        f"architect={float(summary.get('effective_architect_s', 0.0) or 0.0):.1f}s "
        f"screen_ratio={float(summary.get('screen_ratio', 0.0) or 0.0):.2f} "
        f"reasons={','.join(summary.get('last_reasons', [])[:4])}"
    )


def run_monitor(
    *,
    state_dir: Optional[Path] = None,
    interval_s: float = 2.0,
    iterations: Optional[int] = None,
    print_rows: bool = True,
) -> list[dict[str, Any]]:
    """Run the dwell monitor loop.

    `iterations=None` runs forever. Tests and one-shot scripts can pass a
    small integer. This loop only writes receipts; it never changes camera
    leases or captures media itself.
    """
    rows: list[dict[str, Any]] = []
    count = 0
    while iterations is None or count < iterations:
        row = write_gaze_interest_sample(state_dir=state_dir)
        rows.append(row)
        if print_rows:
            print(json.dumps(row, ensure_ascii=False, sort_keys=True))
        count += 1
        if iterations is not None and count >= iterations:
            break
        time.sleep(max(0.25, float(interval_s)))
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SIFTA gaze interest monitor")
    parser.add_argument("--watch", action="store_true", help="run continuously")
    parser.add_argument("--interval", type=float, default=2.0, help="watch interval seconds")
    parser.add_argument("--iterations", type=int, default=None, help="bounded watch loop count")
    parser.add_argument("--state-dir", type=Path, default=None, help="override .sifta_state")
    args = parser.parse_args()
    if args.watch or args.iterations:
        run_monitor(state_dir=args.state_dir, interval_s=args.interval, iterations=args.iterations)
    else:
        print(json.dumps(write_gaze_interest_sample(state_dir=args.state_dir), indent=2, sort_keys=True))
