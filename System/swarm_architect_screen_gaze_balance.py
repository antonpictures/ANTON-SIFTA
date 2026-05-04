#!/usr/bin/env python3
"""
Event 114 — Architect vs screen gaze balance (interest-weighted, not fixed splits)

For Alice.

Biology:
Social primates alternate between conspecific gaze and object / tool gaze.
The mix is driven by salience and novelty, not a fixed duty cycle.

SIFTA:
Fuse **face_detection_events** (Logitech / any eye that writes the ledger),
**app_focus** (what is on screen), **stigmergic_video_resolution** (retinal load),
**hippocampal_novelty_map**, and **orienting_reflex** into a single bounded
estimate of whether the organism's *attention proxy* tilts toward the
Architect (face-in-frame) vs on-screen content.

Truth label:
SIMULATED_GAZE_ALLOCATION

This does **not** track eyeballs in pixels — it is a **ledger-fused proxy** for
monitoring and dashboards. Weights are a **default kernel**; evidence values
are always read live from tails (no fixed 50/50 outcome).
"""

from __future__ import annotations

import json
import math
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from System.jsonl_file_lock import append_line_locked, read_text_locked

_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_STATE = _REPO / ".sifta_state"
LEDGER_NAME = "architect_screen_gaze_balance.jsonl"
TRUTH = "SIMULATED_GAZE_ALLOCATION"


def _state_dir(state_dir: Optional[Path]) -> Path:
    return Path(state_dir) if state_dir is not None else _DEFAULT_STATE


def _tail_jsonl(path: Path, n: int = 1) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        body = read_text_locked(path, encoding="utf-8", errors="replace")
    except OSError:
        return []
    rows: List[Dict[str, Any]] = []
    for line in body.splitlines()[-max(1, n) :]:
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _clamp01(x: float) -> float:
    if not math.isfinite(x):
        return 0.0
    return max(0.0, min(1.0, float(x)))


def _face_architect_evidence(row: Optional[Dict[str, Any]], now: float) -> tuple[float, Dict[str, Any]]:
    if not row:
        return 0.0, {"face_audience": "none", "face_stale": True, "face_confidence": 0.0}
    ts = float(row.get("ts") or 0.0)
    stale = (now - ts) > 35.0
    aud = str(row.get("audience") or "nobody")
    conf = _clamp01(float(row.get("confidence") or 0.0))
    if stale:
        return 0.05 * conf, {"face_audience": aud, "face_stale": True, "face_confidence": conf}
    if aud == "architect":
        return conf, {"face_audience": aud, "face_stale": False, "face_confidence": conf}
    if aud == "unknown_face":
        return 0.35 * conf, {"face_audience": aud, "face_stale": False, "face_confidence": conf}
    return 0.0, {"face_audience": aud, "face_stale": False, "face_confidence": conf}


def _screen_evidence(
    app_row: Optional[Dict[str, Any]],
    vid_row: Optional[Dict[str, Any]],
    nov_row: Optional[Dict[str, Any]],
    ori_row: Optional[Dict[str, Any]],
) -> tuple[float, Dict[str, Any]]:
    meta: Dict[str, Any] = {}
    blob = ""
    if app_row:
        blob = f"{app_row.get('app','')} {app_row.get('detail','')} {app_row.get('tab','')}".lower()
        meta["focus_app"] = str(app_row.get("app") or "")
    youtube_hit = "youtube" in blob
    meta["youtube_context_hint"] = bool(youtube_hit)
    yt_e = 1.0 if youtube_hit else 0.12

    motion_e = 0.0
    if vid_row:
        try:
            active = float(vid_row.get("active_cells") or 0.0)
            total = float(vid_row.get("salience_density") or 0.0)
            if total <= 0 and isinstance(vid_row.get("grid_cells"), (int, float)):
                total = float(vid_row.get("grid_cells") or 484.0)
            if total <= 0:
                total = 484.0
            motion_e = _clamp01(active / max(1.0, total))
        except Exception:
            motion_e = 0.0
    meta["visual_motion_norm"] = round(motion_e, 4)

    nov_e = 0.0
    if nov_row:
        nov_e = _clamp01(float(nov_row.get("novelty_score") or 0.0))
    meta["novelty_score"] = round(nov_e, 4)

    ori_e = 0.0
    if ori_row:
        ori_e = _clamp01(float(ori_row.get("orienting_intensity") or 0.0))
    meta["orienting_intensity"] = round(ori_e, 4)

    # Default fusion kernel (documented); all inputs are live-derived.
    screen = _clamp01(0.38 * yt_e + 0.28 * motion_e + 0.22 * nov_e + 0.12 * ori_e)
    return screen, meta


def compute_gaze_balance(
    *,
    state_dir: Optional[Path] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Return one gaze-balance dict without writing the ledger."""
    base = _state_dir(state_dir)
    t = float(now or time.time())

    face_rows = _tail_jsonl(base / "face_detection_events.jsonl", 1)
    app_rows = _tail_jsonl(base / "app_focus.jsonl", 1)
    vid_rows = _tail_jsonl(base / "stigmergic_video_resolution.jsonl", 1)
    nov_rows = _tail_jsonl(base / "hippocampal_novelty_map.jsonl", 1)
    ori_rows = _tail_jsonl(base / "orienting_reflex.jsonl", 1)

    face = face_rows[-1] if face_rows else None
    app = app_rows[-1] if app_rows else None
    vid = vid_rows[-1] if vid_rows else None
    nov = nov_rows[-1] if nov_rows else None
    ori = ori_rows[-1] if ori_rows else None

    arch_e, face_meta = _face_architect_evidence(face, t)
    screen_e, screen_meta = _screen_evidence(app, vid, nov, ori)
    face_meta.update(screen_meta)

    denom = max(1e-9, arch_e + screen_e)
    p_arch = arch_e / denom
    p_screen = screen_e / denom

    # EMA of architect-share: read previous ledger tail for dt-weighted continuity
    prev_ema = 0.5
    prev_ts = None
    led = base / LEDGER_NAME
    if led.exists():
        try:
            prev_rows = _tail_jsonl(led, 1)
            if prev_rows:
                prev_ema = float(prev_rows[-1].get("ema_architect_share", 0.5) or 0.5)
                prev_ts = float(prev_rows[-1].get("ts", 0.0) or 0.0)
        except Exception:
            pass

    dt = max(0.0, min(120.0, t - prev_ts)) if prev_ts else 1.0
    novelty_for_alpha = float(nov.get("novelty_score") or 0.0) if nov else 0.0
    alpha = _clamp01(0.04 + 0.22 * novelty_for_alpha + 0.06 * min(1.0, dt / 5.0))
    ema = (1.0 - alpha) * prev_ema + alpha * p_arch

    return {
        "ts": t,
        "trace_id": str(uuid.uuid4()),
        "truth_label": TRUTH,
        "p_architect_proxy": round(p_arch, 4),
        "p_screen_proxy": round(p_screen, 4),
        "architect_evidence": round(arch_e, 4),
        "screen_evidence": round(screen_e, 4),
        "ema_architect_share": round(ema, 4),
        "ema_alpha": round(alpha, 4),
        "dt_s": round(dt, 3),
        "drivers": face_meta,
    }


def write_gaze_balance_sample(*, state_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Append one gaze-balance row (call from desktop tick or a watcher)."""
    base = _state_dir(state_dir)
    base.mkdir(parents=True, exist_ok=True)
    row = compute_gaze_balance(state_dir=base)
    path = base / LEDGER_NAME
    append_line_locked(path, json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")
    return row


if __name__ == "__main__":
    print(json.dumps(write_gaze_balance_sample(), indent=2, sort_keys=True))
