"""
Event 144 — Affective Valence Tag

Receipt-backed fast affect layer for the v8 coherence wave. It tags each tick
with an appetitive/aversive scalar from reward, surprise, threat, and arousal.

Bio-math provenance:
    Schultz, Dayan & Montague (1997): reward prediction error.
    LeDoux (1996): threat/salience tagging.
    Damasio (1994): somatic marker framing for action bias.

This organ does not decide actions. It produces a bounded receipt that other
organs can use as a fast approach/avoid prior.

Kill-switch: SIFTA_VALENCE_DISABLE=1
Ledger: .sifta_state/affective_valence.jsonl
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from System.swarm_persistent_owner_history import state_dir
except ImportError:
    def state_dir(root=None):  # type: ignore
        return Path(root) if root else Path(".sifta_state")

try:
    from System.jsonl_file_lock import append_line_locked, read_text_locked
except ImportError:
    def read_text_locked(path: Path, **kw) -> str:  # type: ignore
        return path.read_text(**kw) if path.exists() else ""

    def append_line_locked(path: Path, line: str, **kw) -> None:  # type: ignore
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", **kw) as f:
            f.write(line)

_DISABLE_ENV = "SIFTA_VALENCE_DISABLE"
LOG_NAME = "affective_valence.jsonl"


def _clamp01(value: Any, default: float = 0.0) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError):
        x = default
    return min(1.0, max(0.0, x))


def _clamp_signed(value: float) -> float:
    return min(1.0, max(-1.0, value))


def _arousal_gain(arousal: float) -> float:
    """
    Mild inverted-U gain around optimal arousal. Keeps valence useful without
    letting stress amplify aversive/approach tags without bound.
    """
    a = _clamp01(arousal, 0.5)
    yerkes = max(0.0, min(1.0, 1.0 - 4.0 * (a - 0.5) ** 2))
    return 0.75 + 0.35 * yerkes


def affective_valence_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / LOG_NAME


def compute_affective_valence(
    *,
    event: str = "body_brain_tick",
    reward: float = 0.5,
    surprise: float = 0.0,
    threat: float = 0.0,
    arousal: float = 0.5,
    root: Optional[Path] = None,
    write_ledger: bool = True,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Compute a bounded Event 144 valence tag.

    valence ∈ [-1, 1]:
      positive → approach/appetitive
      negative → avoid/aversive

    intensity ∈ [0, 1]:
      absolute affect strength, increased by surprise and threat.
    """
    if os.environ.get(_DISABLE_ENV, "").strip() == "1":
        return {
            "disabled": True,
            "kind": "VALENCE_TAG",
            "truth_label": "VALENCE_TAG",
            "valence": 0.0,
            "intensity": 0.0,
            "regime": "NEUTRAL",
        }

    reward01 = _clamp01(reward, 0.5)
    surprise01 = _clamp01(surprise, 0.0)
    threat01 = _clamp01(threat, 0.0)
    arousal01 = _clamp01(arousal, 0.5)

    reward_term = (2.0 * reward01) - 1.0
    surprise_penalty = 0.35 * surprise01
    threat_penalty = 0.70 * threat01
    gain = _arousal_gain(arousal01)

    valence = _clamp_signed((reward_term - surprise_penalty - threat_penalty) * gain)
    intensity = _clamp01((abs(valence) * 0.65) + (surprise01 * 0.15) + (threat01 * 0.25))

    if valence >= 0.20:
        regime = "APPROACH"
    elif valence <= -0.20:
        regime = "AVOID"
    else:
        regime = "NEUTRAL"

    row: Dict[str, Any] = {
        "ts": now or time.time(),
        "trace_id": str(uuid.uuid4()),
        "kind": "VALENCE_TAG",
        "truth_label": "VALENCE_TAG",
        "event": event[:160],
        "valence": round(valence, 4),
        "intensity": round(intensity, 4),
        "regime": regime,
        "components": {
            "reward": round(reward01, 4),
            "surprise": round(surprise01, 4),
            "threat": round(threat01, 4),
            "arousal": round(arousal01, 4),
            "arousal_gain": round(gain, 4),
            "reward_term": round(reward_term, 4),
            "surprise_penalty": round(surprise_penalty, 4),
            "threat_penalty": round(threat_penalty, 4),
        },
        "provenance": [
            "Schultz_Dayan_Montague_1997_RPE",
            "LeDoux_1996_threat_salience",
            "Damasio_1994_somatic_marker",
        ],
    }

    if write_ledger:
        append_line_locked(
            affective_valence_path(root),
            json.dumps(row, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return row


def get_latest_valence_row(*, root: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    path = affective_valence_path(root)
    if not path.exists():
        return None
    try:
        lines = [line for line in read_text_locked(path, encoding="utf-8", errors="replace").splitlines() if line.strip()]
        for line in reversed(lines):
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("kind") == "VALENCE_TAG":
                return row
    except Exception:
        return None
    return None


def summary_for_prompt(*, root: Optional[Path] = None) -> str:
    row = get_latest_valence_row(root=root)
    if not row:
        return ""
    return (
        "AFFECTIVE VALENCE (Event 144 — Schultz/LeDoux/Damasio):\n"
        f"- valence={row.get('valence')} | intensity={row.get('intensity')} | regime={row.get('regime')}"
    )


__all__ = [
    "affective_valence_path",
    "compute_affective_valence",
    "get_latest_valence_row",
    "summary_for_prompt",
]
