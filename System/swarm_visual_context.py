#!/usr/bin/env python3
"""
System/swarm_visual_context.py — truth-labeled visual context for Alice.

This is deliberately not a glasses detector and not identity cosplay.
It converts existing ledgers into a compact prompt block that tells Alice:

  - whether live camera photons are fresh,
  - which physical eye is selected,
  - whether the face detector has fresh owner-grade evidence,
  - what she must NOT claim yet (glasses/clothing/object semantics).

The goal is to stop the false binary of "I can see everything" vs.
"I only process text". Alice has low-level live vision now; semantic
recognition is only allowed when a detector ledger proves it.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_VISUAL_LOG = _STATE / "visual_stigmergy.jsonl"


def _tail_jsonl(path: Path, n: int = 1) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    try:
        with path.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - 65536))
            raw_rows = fh.read().splitlines()[-n:]
        for raw in raw_rows:
            try:
                row = json.loads(raw.decode("utf-8", "replace"))
            except Exception:
                continue
            if isinstance(row, dict):
                rows.append(row)
    except OSError:
        return []
    return rows


def _fmt_age(ts: Any, *, now: Optional[float] = None) -> tuple[float, str]:
    current = time.time() if now is None else float(now)
    try:
        age = max(0.0, current - float(ts))
    except Exception:
        age = float("inf")
    if age == float("inf"):
        return age, "unknown"
    if age < 1:
        return age, "<1s"
    if age < 90:
        return age, f"{int(age)}s"
    return age, f"{age / 60:.1f}m"


def _camera_target_line() -> str:
    try:
        from System.swarm_camera_target import read_target

        rec = read_target()
    except Exception as exc:
        return f"- active_eye=unknown reason={type(exc).__name__}"
    if not rec:
        return "- active_eye=unknown reason=no active_saccade_target.json"
    name = rec.get("name") or "(unnamed)"
    idx = rec.get("index")
    writer = rec.get("writer") or "unknown"
    age, age_text = _fmt_age(rec.get("ts"))
    stale = " stale=true" if age > 120 else ""
    return f"- active_eye={name} idx={idx if idx is not None else '?'} writer={writer} age={age_text}{stale}"


def _visual_line(max_age_s: float) -> str:
    rows = _tail_jsonl(_VISUAL_LOG, 1)
    if not rows:
        return "- camera_photons=fresh:false reason=no visual_stigmergy.jsonl rows"
    row = rows[-1]
    age, age_text = _fmt_age(row.get("ts"))
    fresh = age <= max_age_s
    return (
        f"- camera_photons=fresh:{str(fresh).lower()} age={age_text} "
        f"frame={row.get('w', '?')}x{row.get('h', '?')} "
        f"entropy_bits={float(row.get('entropy_bits', 0.0) or 0.0):.2f} "
        f"saliency_peak={float(row.get('saliency_peak', 0.0) or 0.0):.2f} "
        f"motion_mean={float(row.get('motion_mean', 0.0) or 0.0):.3f}"
    )


def _face_line() -> tuple[str, str]:
    try:
        from System.swarm_face_detection import current_presence_safe

        fp = current_presence_safe()
    except Exception as exc:
        return (
            f"- face_detection=fresh:false reason={type(exc).__name__}",
            "unknown",
        )

    stale = bool(getattr(fp, "stale", True))
    audience = str(getattr(fp, "audience", "nobody"))
    faces = int(getattr(fp, "faces_detected", 0) or 0)
    conf = float(getattr(fp, "max_confidence", 0.0) or 0.0)
    age_s = getattr(fp, "age_s", None)
    age_text = "unknown"
    if age_s is not None:
        try:
            age_val = max(0.0, float(age_s))
            age_text = f"{int(age_val)}s" if age_val < 90 else f"{age_val / 60:.1f}m"
        except Exception:
            age_text = "unknown"
    owner_state = "verified_recent_face" if (not stale and audience == "architect") else "unknown"
    return (
        f"- face_detection=fresh:{str(not stale).lower()} audience={audience} "
        f"faces={faces} max_conf={conf:.2f} age={age_text}",
        owner_state,
    )


def summary_for_alice(*, max_visual_age_s: float = 15.0) -> str:
    """Return a compact prompt block. Read-only and non-blocking."""
    try:
        from System.swarm_kernel_identity import owner_name

        owner = owner_name()
    except Exception:
        owner = "the Architect"

    face_line, owner_visual_state = _face_line()
    return (
        "LIVE VISUAL CONTEXT (truth-labeled, current camera substrate):\n"
        f"- owner_name={owner}\n"
        + _camera_target_line() + "\n"
        + _visual_line(max_visual_age_s) + "\n"
        + face_line + "\n"
        f"- owner_visual_identity={owner_visual_state}\n"
        "- semantic_limits=no verified glasses/clothing/object classifier is wired into the prompt yet.\n"
        "- If the Architect asks whether they are wearing glasses, do not infer from text alone. "
        "If face/object evidence is missing or stale, say the camera photons are live but "
        "the glasses classifier is not yet available."
    )


if __name__ == "__main__":
    print(summary_for_alice())
