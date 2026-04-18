#!/usr/bin/env python3
"""
dopamine_state.py — DA level + Explore / Exploit / Maintain from three inputs only.
══════════════════════════════════════════════════════════════════════════════════

Biology: midbrain DA bursts encode **reward prediction error** (Schultz–Dayan–
Montague 1997), not raw reward magnitude.

Architect contract (this stage)
-------------------------------
`step()` accepts **only**:

    1. novelty_score      — from `PFCWorkingMemory.cosine_novelty()` [0, 2]
    2. affinity_delta     — outcome-only, e.g. `identity_outcome_contract.affinity_delta_identity_field`
    3. time_since_last_update — seconds; drives OU decay toward baseline DA

No other parameters at this API surface. **Do not** pass model confidence.

Glymphatic / sleep note
-----------------------
If an upstream sleep cycle **clears** `PFCWorkingMemory`, rolling mean resets and
`cosine_novelty()` **spikes on wake** — biologically plausible (post-sleep
curiosity). Treat as **feature** unless you persist a compressed summary
vector through sleep; see `Documents/PLAN_DOPAMINE_RPE_PFC_NEXT.md`.
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from System.jsonl_file_lock import read_write_json_locked

_REPO = Path(__file__).resolve().parent.parent
_STATE_PATH = _REPO / ".sifta_state" / "dopamine_state.json"

MODULE_VERSION = "2026-04-18.v3"

BASELINE_DA = 0.5
# OU: characteristic time constant (seconds) for decay toward baseline.
TAU_OU_SECONDS = 30.0
# RPE contribution: affinity_delta scaled into DA units.
W_RPE = 0.35
# Novelty drives exploration branch; optionally nudges DA down when very high (conflict resolution).
W_NOVELTY_SUPPRESS = 0.08

# State thresholds (tunable).
NOVELTY_EXPLORE = 0.55
RPE_EXPLOIT = 0.08
DA_EXPLOIT_FLOOR = 0.52


class MotivationState(str, Enum):
    EXPLORE = "EXPLORE"
    EXPLOIT = "EXPLOIT"
    MAINTAIN = "MAINTAIN"


@dataclass
class DopamineSnapshot:
    """Serializable state for persistence across ticks."""

    da: float = BASELINE_DA
    last_ts: float = 0.0
    last_rpe: float = 0.0
    last_state: str = MotivationState.MAINTAIN.value
    module_version: str = MODULE_VERSION


def _ou_decay(da: float, dt_s: float, baseline: float = BASELINE_DA) -> float:
    """Discrete OU step: relax toward baseline over dt_s."""
    if dt_s <= 0:
        return da
    # alpha in (0,1): fraction moved toward baseline this tick
    alpha = 1.0 - math.exp(-dt_s / TAU_OU_SECONDS)
    return da + alpha * (baseline - da)


def _classify(da: float, novelty_score: float, affinity_delta: float) -> MotivationState:
    """Explore / Exploit / Maintain from current DA, novelty, and measured RPE proxy."""
    if novelty_score >= NOVELTY_EXPLORE:
        return MotivationState.EXPLORE
    if affinity_delta >= RPE_EXPLOIT and da >= DA_EXPLOIT_FLOOR:
        return MotivationState.EXPLOIT
    return MotivationState.MAINTAIN


def step(
    snap: DopamineSnapshot,
    novelty_score: float,
    affinity_delta: float,
    time_since_last_update: float,
) -> Tuple[DopamineSnapshot, Dict[str, Any]]:
    """
    Single motivational tick. **Only** the three named inputs (+ persisted snap)
    influence the update.

    Returns (new_snapshot, debug_dict).
    """
    now = time.time()
    da = float(snap.da)
    dt = max(0.0, float(time_since_last_update))

    da = _ou_decay(da, dt)
    rpe = float(affinity_delta)
    da = da + W_RPE * rpe
    # High novelty slightly pulls DA toward exploration (reduce exploitation pressure).
    da = da - W_NOVELTY_SUPPRESS * max(0.0, float(novelty_score) - NOVELTY_EXPLORE)
    da = max(0.0, min(1.0, da))

    st = _classify(da, float(novelty_score), rpe)
    out_snap = DopamineSnapshot(
        da=da,
        last_ts=now,
        last_rpe=rpe,
        last_state=st.value,
    )
    debug = {
        "da": round(da, 4),
        "rpe_input": round(rpe, 4),
        "novelty_input": round(float(novelty_score), 4),
        "dt_s": round(dt, 4),
        "state": st.value,
        "baseline": BASELINE_DA,
        "note": "DA encodes RPE-shaped pressure; magnitude is not raw reward.",
    }
    return out_snap, debug


def load_snapshot(path: Path = _STATE_PATH) -> DopamineSnapshot:
    if not path.exists():
        return DopamineSnapshot(last_ts=time.time())
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return DopamineSnapshot(
            da=float(raw.get("da", BASELINE_DA)),
            last_ts=float(raw.get("last_ts", 0.0)),
            last_rpe=float(raw.get("last_rpe", 0.0)),
            last_state=str(raw.get("last_state", MotivationState.MAINTAIN.value)),
        )
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return DopamineSnapshot(last_ts=time.time())


def persist_snapshot(snap: DopamineSnapshot, path: Path = _STATE_PATH) -> None:
    def _upd(_: Dict[str, Any]) -> Dict[str, Any]:
        return asdict(snap)

    read_write_json_locked(path, _upd)


def tick_from_three_inputs(
    novelty_score: float,
    affinity_delta: float,
    time_since_last_update: float,
    *,
    path: Path = _STATE_PATH,
) -> Dict[str, Any]:
    """Load → step → persist. Convenience for scripts."""
    s = load_snapshot(path)
    s_new, dbg = step(s, novelty_score, affinity_delta, time_since_last_update)
    persist_snapshot(s_new, path)
    dbg["persisted"] = True
    return dbg


def _demo() -> None:
    s = DopamineSnapshot()
    s, d = step(s, novelty_score=0.8, affinity_delta=0.05, time_since_last_update=5.0)
    print("[dopamine_state]", d)
    s, d = step(s, novelty_score=0.2, affinity_delta=0.12, time_since_last_update=10.0)
    print("[dopamine_state]", d)


if __name__ == "__main__":
    _demo()


# ── Claude-tab OU engine (internal RPE EMA) — re-export ─────────────────────
from System.dopamine_ou_engine import (  # noqa: E402
    BehavioralState,
    DAState,
    DopamineState as OrnsteinUhlenbeckDopamine,
    DIRECTIVES,
    load_ou_engine,
    persist_ou_engine,
)
from System.swarm_rosetta_map import SWARM_TICKER_MAP  # noqa: E402

__all__ = [
    "DopamineSnapshot",
    "MotivationState",
    "step",
    "tick_from_three_inputs",
    "load_snapshot",
    "persist_snapshot",
    "BASELINE_DA",
    "MODULE_VERSION",
    "BehavioralState",
    "DAState",
    "OrnsteinUhlenbeckDopamine",
    "DIRECTIVES",
    "load_ou_engine",
    "persist_ou_engine",
    "SWARM_TICKER_MAP",
]
