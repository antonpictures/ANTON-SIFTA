#!/usr/bin/env python3
"""
System/swarm_motor_policy.py
══════════════════════════════════════════════════════════════════════════════
Event 103 — Motor policy from crystallized skills

Biology:
  Basal ganglia and associated loops bias which motor programs are released
  given recent reward history (habit vs goal-directed framing; not a full
  optimal control solution here).

SIFTA:
  Reads `crystallized_skills.json` from the temporal identity compression
  engine (REM crystallizer) and optional `skill_primitives.jsonl` tail rows,
  aggregates mass onto *action types* (`explore`, `forage`, …), then selects
  among a caller-supplied candidate set. Emits append-only `motor_policy.jsonl`.

Truth label: SKILL_WEIGHTED_POLICY

Refs (index §F.1): Greybiel (2008) basal loops; Schultz et al. reward / TD.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from System.jsonl_file_lock import append_line_locked

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
CRYSTALLIZED_SKILLS = _STATE_DIR / "crystallized_skills.json"
SKILL_PRIMITIVES_JSONL = _STATE_DIR / "skill_primitives.jsonl"
POLICY_LEDGER = _STATE_DIR / "motor_policy.jsonl"

TRUTH_LABEL = "SKILL_WEIGHTED_POLICY"


def _paths(state_dir: Optional[Path] = None) -> tuple[Path, Path, Path]:
    base = Path(state_dir) if state_dir is not None else _STATE_DIR
    return (
        base / "crystallized_skills.json",
        base / "skill_primitives.jsonl",
        base / "motor_policy.jsonl",
    )


def _coerce_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _parse_body_brain_action_type(pattern_signature: str) -> Optional[str]:
    """`body_brain:forage:pouw_work|SIFTA_BODY` → `forage`."""
    sig = str(pattern_signature).strip()
    if not sig:
        return None
    head = sig.split("|", 1)[0]
    parts = head.split(":")
    if len(parts) >= 3 and parts[0] == "body_brain":
        return parts[1].strip().lower() or None
    return None


def _read_jsonl_tail(path: Path, n: int = 50) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    rows: List[Dict[str, Any]] = []
    for line in lines[-n:]:
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _load_crystallized_skill_dicts(crystallized_path: Path) -> List[Dict[str, Any]]:
    if not crystallized_path.exists():
        return []
    try:
        data = json.loads(crystallized_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, dict):
        return []
    out: List[Dict[str, Any]] = []
    for _k, v in data.items():
        if isinstance(v, dict):
            out.append(v)
    return out


def read_skill_sources(
    *,
    state_dir: Optional[Path] = None,
    jsonl_tail: int = 50,
) -> List[Dict[str, Any]]:
    """Merge crystallized engine DB + optional JSONL primitives (newest last)."""
    cpath, jpath, _ = _paths(state_dir)
    skills = _load_crystallized_skill_dicts(cpath)
    skills.extend(_read_jsonl_tail(jpath, n=jsonl_tail))
    return skills


# ── Per-regime skill mass modifiers ──────────────────────────────────────────
# These scale the computed weight of each action TYPE based on the current
# macro-regime from the Phase Detector (Event 100 / CUSUM).
# Logic mirrors the homeostatic drive weight table (Event 101) but operates
# on crystallized SKILL mass rather than live drive selection.
_REGIME_ACTION_SCALE: Dict[str, Dict[str, float]] = {
    "EXPLORATION": {
        "explore":     1.4,   # open vacuum — reward exploration habits
        "forage":      1.1,
        "learn":       1.2,
        "code":        1.1,
        "optimize":    1.0,
        "repair":      0.8,
        "rest":        0.5,
    },
    "CONSOLIDATION": {
        "explore":     0.7,   # density plateau — reward integration habits
        "forage":      0.9,
        "learn":       1.5,
        "code":        1.3,
        "optimize":    1.4,
        "repair":      1.0,
        "rest":        0.9,
    },
    "CRITICAL_COLLAPSE": {
        "explore":     0.15,  # emergency — suppress destabilising habits
        "experiment":  0.1,
        "forage":      0.4,
        "learn":       0.4,
        "code":        0.3,
        "optimize":    0.2,
        "repair":      2.0,   # massively reward recovery habits
        "rest":        2.0,
        "safety":      1.8,
    },
}


def _read_regime_from_cache() -> str:
    """Fast regime read from regime_state.json (written by phase detector)."""
    try:
        rf = _REPO / ".sifta_state" / "regime_state.json"
        if rf.exists():
            data = json.loads(rf.read_text("utf-8", errors="replace"))
            return str(data.get("state") or data.get("regime") or "EXPLORATION")
    except Exception:
        pass
    return "EXPLORATION"


def compute_policy_bias(
    current_drive: str,
    *,
    state_dir: Optional[Path] = None,
    jsonl_tail: int = 50,
    regime: Optional[str] = None,
    crystallizer_gate: float = 1.0,
    novelty_explore_mass: float = 0.0,
    novelty_forage_mass: float = 0.0,
) -> Dict[str, float]:
    """
    Map action_type -> non-negative weight (unnormalized).
    Uses success_rate, usage_count, stability; boosts rows that mention `current_drive`.

    regime (str | None):
        EXPLORATION / CONSOLIDATION / CRITICAL_COLLAPSE.
        If None, auto-reads from .sifta_state/regime_state.json.
    crystallizer_gate (float [0,1]):
        From homeostatic stabilizer (Event 101). Near 0 during CRITICAL_COLLAPSE
        → skill mass shrinks toward the uniform epsilon floor, so the motor
        policy does not crystallize panic-state programs into habits.
    """
    drive = str(current_drive).strip().lower()
    raw = read_skill_sources(state_dir=state_dir, jsonl_tail=jsonl_tail)
    bias: Dict[str, float] = {}

    resolved_regime = regime if regime is not None else _read_regime_from_cache()
    action_scale = _REGIME_ACTION_SCALE.get(resolved_regime, _REGIME_ACTION_SCALE["EXPLORATION"])
    gate = max(0.0, min(1.0, float(crystallizer_gate)))

    for s in raw:
        if s.get("frozen") is True or s.get("quarantined") is True:
            continue
        sig = str(s.get("pattern_signature", ""))
        action = s.get("action") or _parse_body_brain_action_type(sig)
        if not action:
            continue
        action = str(action).strip().lower()
        reward = _coerce_float(s.get("success_rate", s.get("avg_reward", 0.0)), 0.0)
        reward = max(0.0, min(1.0, reward))
        usage = max(1.0, _coerce_float(s.get("usage_count", 1.0), 1.0))
        stability = max(0.05, min(1.0, _coerce_float(s.get("stability", 0.5), 0.5)))
        weight = reward * stability * (1.0 + 0.05 * min(usage, 200.0))
        if drive and drive in sig.lower():
            weight *= 1.35
        pl = s.get("payload") if isinstance(s.get("payload"), dict) else {}
        ds = str(pl.get("drive_state", "")).lower()
        if drive and ds == drive:
            weight *= 1.2
        # Regime scale: reshape which action types get mass
        regime_mod = action_scale.get(action, 1.0)
        weight *= regime_mod
        # Crystallizer gate: during CRITICAL_COLLAPSE the stabilizer sets this
        # to ~0.10, making all skill weights collapse toward zero (forcing
        # the epsilon floor to dominate, i.e. back to uniform exploration).
        weight *= gate
        bias[action] = bias.get(action, 0.0) + weight

    if novelty_explore_mass > 0.0:
        bias["explore"] = bias.get("explore", 0.0) + novelty_explore_mass
    if novelty_forage_mass > 0.0:
        bias["forage"] = bias.get("forage", 0.0) + novelty_forage_mass

    return bias


def select_action_type_from_skills(
    candidates: Sequence[str],
    current_drive: str,
    *,
    state_dir: Optional[Path] = None,
    jsonl_tail: int = 50,
    epsilon: float = 0.08,
    regime: Optional[str] = None,
    crystallizer_gate: float = 1.0,
    novelty_explore_mass: float = 0.0,
    novelty_forage_mass: float = 0.0,
) -> Tuple[str, Dict[str, float]]:
    """
    Pick one candidate action *type* using crystallized skill mass + uniform floor.
    Returns (selected, normalized_bias over union of candidates + observed keys).

    regime / crystallizer_gate are forwarded to compute_policy_bias for
    the stabilizer → phase controller → policy mass feedback path (Event 103+).
    """
    cands = [str(c).strip().lower() for c in candidates if str(c).strip()]
    if not cands:
        return "explore", {}

    raw_bias = compute_policy_bias(
        current_drive,
        state_dir=state_dir,
        jsonl_tail=jsonl_tail,
        regime=regime,
        crystallizer_gate=crystallizer_gate,
        novelty_explore_mass=novelty_explore_mass,
        novelty_forage_mass=novelty_forage_mass,
    )
    scores: Dict[str, float] = {}
    for c in cands:
        scores[c] = max(raw_bias.get(c, 0.0), epsilon)

    total = sum(scores.values()) or 1.0
    norm = {k: v / total for k, v in scores.items()}

    best = cands[0]
    best_s = norm.get(best, epsilon)
    for c in cands[1:]:
        sc = norm.get(c, epsilon)
        if sc > best_s:
            best, best_s = c, sc
    return best, norm


def write_motor_policy_row(
    *,
    selected_action: str,
    bias: Dict[str, float],
    current_drive: str,
    state_dir: Optional[Path] = None,
    regime: Optional[str] = None,
    crystallizer_gate: float = 1.0,
) -> Dict[str, Any]:
    _, _, ledger = _paths(state_dir)
    row = {
        "ts": time.time(),
        "truth_label": TRUTH_LABEL,
        "selected_action": selected_action,
        "current_drive": str(current_drive),
        "bias": bias,
        "regime": regime or _read_regime_from_cache(),
        "crystallizer_gate": round(float(crystallizer_gate), 4),
    }
    ledger.parent.mkdir(parents=True, exist_ok=True)
    append_line_locked(ledger, json.dumps(row, sort_keys=True) + "\n")
    return row


__all__ = [
    "TRUTH_LABEL",
    "compute_policy_bias",
    "read_skill_sources",
    "select_action_type_from_skills",
    "write_motor_policy_row",
]
