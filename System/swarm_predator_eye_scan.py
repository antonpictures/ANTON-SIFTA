"""swarm_predator_eye_scan.py — CUR-V6 (2026-06-13): multi-eye predator lock-on.

George: "I can connect a separate USB cam so she can watch another screen or
another angle — those are additional eyes. She can SWITCH between eyes when
they are connected to scan the environment on changes LIKE A PREDATOR."

The eye REGISTRY (``swarm_eye_registry``) already enumerates + classifies eyes
(built-in -> owner, USB/Logitech -> world) with stable, index-free identity.
What was missing is the PREDATOR behavior: when >=2 eyes are live, scan them and
LOCK onto the one showing the most change (covenant §7.1 sensory lock-on). This
module is pure/decidable over a registry snapshot + per-eye change scores, so it
is testable without hardware.

Owner protection (ties to CUR-V4): iPhone / Continuity / Desk-View eyes are
excluded from the scan unless ``allow_iphone=True`` (George explicitly opts in),
so the predator never locks onto his phone.

Truth label: PREDATOR_EYE_LOCKON_V1.
For the Swarm. 🐜⚡
"""
from __future__ import annotations

import time
from typing import Any, Mapping, Optional

TRUTH_LABEL = "PREDATOR_EYE_LOCKON_V1"


def _is_iphone_or_continuity(name: str) -> bool:
    """Reuse the CUR-V4 exclusion; fall back to a local pattern if unavailable."""
    try:
        from System.swarm_camera_target import is_iphone_or_continuity
        return bool(is_iphone_or_continuity(name))
    except Exception:
        n = str(name or "").lower()
        return any(tok in n for tok in ("iphone", "ipad", "continuity", "desk view"))


def eligible_eyes(
    snapshot: Mapping[str, Any],
    *,
    allow_iphone: bool = False,
) -> list[dict[str, Any]]:
    """Live eyes the predator may scan: LIVE connection, iPhone/Continuity
    excluded unless explicitly allowed."""
    eyes = snapshot.get("eyes") if isinstance(snapshot.get("eyes"), list) else []
    out: list[dict[str, Any]] = []
    for eye in eyes:
        if str(eye.get("connection_state")) != "LIVE":
            continue
        if not allow_iphone and _is_iphone_or_continuity(eye.get("device_name") or ""):
            continue
        out.append(dict(eye))
    return out


def _salience(eye: Mapping[str, Any], change_by_eye: Mapping[str, float]) -> float:
    """Change/novelty score for an eye. Explicit change score wins; otherwise a
    fresher frame (lower age) is mildly more salient than a stale one."""
    eid = str(eye.get("eye_id") or "")
    if eid in change_by_eye:
        try:
            return float(change_by_eye[eid])
        except Exception:
            return 0.0
    try:
        age = float(eye.get("last_frame_age_s"))
        return max(0.0, 1.0 / (1.0 + age))
    except Exception:
        return 0.0


def scan_and_lock(
    snapshot: Mapping[str, Any],
    *,
    change_by_eye: Optional[Mapping[str, float]] = None,
    current_eye_id: Optional[str] = None,
    allow_iphone: bool = False,
    switch_margin: float = 0.15,
    now: float | None = None,
) -> dict[str, Any]:
    """Predator scan: among live (consented) eyes, lock onto the one showing the
    most change. Returns a receipt-shaped decision (no side effects).

    - <2 eligible eyes -> STAY_SINGLE_EYE (nothing to switch between).
    - ``change_by_eye`` maps eye_id -> recent change/novelty score; missing eyes
      fall back to frame-freshness salience.
    - Hysteresis: only switch if the best eye beats the current one by
      ``switch_margin`` so she does not thrash between eyes.
    """
    ts = float(now if now is not None else time.time())
    eyes = eligible_eyes(snapshot, allow_iphone=allow_iphone)
    change = dict(change_by_eye or {})

    if len(eyes) < 2:
        locked = str(eyes[0]["eye_id"]) if eyes else current_eye_id
        return {
            "ts": ts,
            "truth_label": TRUTH_LABEL,
            "action": "STAY_SINGLE_EYE",
            "locked_eye_id": locked,
            "candidates": [str(e.get("eye_id")) for e in eyes],
            "reason": "fewer than two eligible eyes; no predator switch needed",
        }

    ranked = sorted(eyes, key=lambda e: _salience(e, change), reverse=True)
    scores = {str(e.get("eye_id")): round(_salience(e, change), 4) for e in ranked}
    best_id = str(ranked[0].get("eye_id") or "")
    best_score = _salience(ranked[0], change)
    cur_score = next(
        (_salience(e, change) for e in eyes if str(e.get("eye_id")) == str(current_eye_id)),
        None,
    )

    if (
        current_eye_id
        and cur_score is not None
        and best_id != str(current_eye_id)
        and (best_score - cur_score) < switch_margin
    ):
        return {
            "ts": ts,
            "truth_label": TRUTH_LABEL,
            "action": "HOLD_LOCK",
            "locked_eye_id": str(current_eye_id),
            "candidates": [str(e.get("eye_id")) for e in ranked],
            "scores": scores,
            "reason": f"change delta {best_score - cur_score:.3f} < margin {switch_margin}",
        }

    return {
        "ts": ts,
        "truth_label": TRUTH_LABEL,
        "action": "LOCK_ON" if best_id != str(current_eye_id or "") else "HOLD_LOCK",
        "locked_eye_id": best_id,
        "from_eye_id": current_eye_id,
        "candidates": [str(e.get("eye_id")) for e in ranked],
        "scores": scores,
        "reason": "predator lock-on: highest change among eligible eyes (§7.1)",
    }
