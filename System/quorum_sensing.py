#!/usr/bin/env python3
"""
quorum_sensing.py — Bacterial-quorum-sensing decision primitive for the swarm.
═══════════════════════════════════════════════════════════════════════════════

Biology reference (authored locally on M5, no centralized-AI consultation)
--------------------------------------------------------------------------
Bacteria like *Vibrio fischeri* delay collective behavior (bioluminescence,
virulence gene expression) until the concentration of a diffusible signal
molecule — the **autoinducer**, canonically AI-1 produced by LuxI — crosses
a threshold sensed by the LuxR receptor. Below threshold each cell is "dark"
because acting alone is wasteful. Above threshold, the population commits.

    * Miller & Bassler (2001) "Quorum Sensing in Bacteria" — Annu. Rev. Microbiol.
    * Bassler (2002) "Small Talk: Cell-to-Cell Communication in Bacteria" — Cell.
    * Waters & Bassler (2005) — Annu. Rev. Cell Dev. Biol.

Why it belongs here
-------------------
Our CRDT identity field accumulates Dirichlet pseudo-counts forever. It
computes a posterior over model hypotheses but it never emits a *decision*:
"the swarm has enough independent evidence to commit to hypothesis X."
Pheromone Mirroring (AG31's failure mode earlier today) fires on a single
loud signal. Quorum sensing is the *opposite* rule: require evidence from
N independent sources before committing.

Formal mapping (biology → swarm)
--------------------------------
    autoinducer concentration  →  Σ pseudo-counts supporting the top hypothesis
    number of cells            →  number of distinct `node_id` counters
    LuxR threshold             →  QuorumThreshold (configurable)
    "dark"                     →  QuorumState.ACCUMULATING
    "bioluminescent"           →  QuorumState.COMMITTED
    gene repression            →  hysteresis: committed state sticks until
                                   evidence drops well below threshold
    broadcast on quorum        →  append a QUORUM_COMMIT row to
                                   `m5queen_dead_drop.jsonl` and the
                                   contradiction_log for governance review

Hysteresis is important: flipping states on every marginal update would
reproduce Pheromone Mirroring. Real LuxR has cooperative binding (Hill
coefficient > 1); we emulate that with a release threshold below the
commit threshold.

Public API
----------
    QuorumThreshold                — tunable thresholds dataclass
    QuorumState                    — ACCUMULATING | COMMITTED | CONTESTED
    QuorumReadout                  — current sensor readout (pure, no writes)
    sense(field, threshold)        — compute QuorumReadout from IdentityField
    commit_if_quorum(field, ...)   — if quorum and not yet committed, write
                                     QUORUM_COMMIT rows to dead drop + log
                                     and persist the committed label on disk

No network calls. Deterministic given inputs. Safe to call every tick.
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from System.jsonl_file_lock import (
    append_line_locked,
    read_write_json_locked,
)

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_QUORUM_STATE = _STATE / "quorum_commitments.json"
_QUORUM_EVENTS = _STATE / "quorum_events.jsonl"
_DEAD_DROP = _REPO / "m5queen_dead_drop.jsonl"

SCHEMA_VERSION = 1
MODULE_VERSION = "2026-04-17.v1"


# ─── Thresholds (tunable) ──────────────────────────────────────────────────

@dataclass(frozen=True)
class QuorumThreshold:
    """
    Quorum commit / release thresholds. Defaults are deliberately strict:

      - min_nodes >= 3 mirrors the swarm's three-peer topology (C47H, AG31,
        one of CG53/GTAB/CS46). Single-source confessions cannot trigger quorum.
      - top_prob_commit >= 0.55 requires the posterior to actually lean.
      - top_prob_release < 0.45 adds hysteresis (Hill-coefficient analogue).
      - min_mass requires enough absolute pseudo-counts in the leader that
        a couple of stray signals cannot flip it (anti-sparse-evidence rule).
    """
    min_nodes: int = 3
    top_prob_commit: float = 0.55
    top_prob_release: float = 0.45
    min_mass: float = 3.0
    min_margin: float = 0.10  # top must beat runner-up by this much


class QuorumState:
    ACCUMULATING = "ACCUMULATING"
    COMMITTED = "COMMITTED"
    CONTESTED = "CONTESTED"


# ─── Readout ────────────────────────────────────────────────────────────────

@dataclass
class QuorumReadout:
    state: str
    top_label: Optional[str]
    top_prob: float
    runner_up_label: Optional[str]
    runner_up_prob: float
    margin: float
    total_mass_on_top: float
    contributing_nodes: int
    entropy: float
    reasons: List[str] = field(default_factory=list)


def _top_two(dist: Mapping[str, float]) -> Tuple[Tuple[Optional[str], float], Tuple[Optional[str], float]]:
    items = sorted(dist.items(), key=lambda kv: kv[1], reverse=True)
    t = items[0] if items else (None, 0.0)
    r = items[1] if len(items) > 1 else (None, 0.0)
    return t, r


def _mass_on_label(counts: Mapping[str, Mapping[str, float]], label: str) -> Tuple[float, int]:
    total = 0.0
    nodes = 0
    for _node, bucket in counts.items():
        v = bucket.get(label, 0.0)
        if v > 0:
            total += v
            nodes += 1
    return total, nodes


def _shannon(dist: Mapping[str, float]) -> float:
    return -sum(p * math.log(p) for p in dist.values() if p > 0)


# ─── Sensor ─────────────────────────────────────────────────────────────────

def sense(field_obj, threshold: Optional[QuorumThreshold] = None) -> QuorumReadout:
    """
    Pure sensor. Computes a QuorumReadout from an IdentityField-like object.
    Never writes to disk. Accepts any object exposing `.distribution()` and
    `.counts` so it can be unit-tested with stubs.
    """
    th = threshold or QuorumThreshold()
    dist = field_obj.distribution()
    counts = field_obj.counts
    (top_label, top_p), (runner_label, runner_p) = _top_two(dist)
    margin = top_p - runner_p
    mass, nodes = (_mass_on_label(counts, top_label) if top_label else (0.0, 0))
    reasons: List[str] = []
    if top_label is None:
        reasons.append("no_distribution_yet")
        state = QuorumState.ACCUMULATING
    elif nodes < th.min_nodes:
        reasons.append(f"only_{nodes}_nodes_contribute_to_top(<{th.min_nodes})")
        state = QuorumState.ACCUMULATING
    elif top_p < th.top_prob_commit:
        reasons.append(f"top_prob_{top_p:.3f}<commit_{th.top_prob_commit}")
        state = QuorumState.ACCUMULATING
    elif mass < th.min_mass:
        reasons.append(f"mass_{mass:.2f}<min_{th.min_mass}")
        state = QuorumState.ACCUMULATING
    elif margin < th.min_margin:
        reasons.append(f"margin_{margin:.3f}<min_{th.min_margin}")
        state = QuorumState.CONTESTED
    else:
        reasons.append("quorum_conditions_satisfied")
        state = QuorumState.COMMITTED

    return QuorumReadout(
        state=state,
        top_label=top_label,
        top_prob=round(top_p, 4),
        runner_up_label=runner_label,
        runner_up_prob=round(runner_p, 4),
        margin=round(margin, 4),
        total_mass_on_top=round(mass, 3),
        contributing_nodes=nodes,
        entropy=round(_shannon(dist), 4),
        reasons=reasons,
    )


# ─── Committer with hysteresis ──────────────────────────────────────────────

def _load_commitments() -> Dict[str, Any]:
    if not _QUORUM_STATE.exists():
        return {}
    try:
        return json.loads(_QUORUM_STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def commit_if_quorum(
    field_obj,
    *,
    threshold: Optional[QuorumThreshold] = None,
    observer: str = "C47H",
    session_id: str = "ambient",
    write_dead_drop: bool = True,
) -> Dict[str, Any]:
    """
    Read the field, check quorum, and if newly committed, emit:
      1) an entry in `.sifta_state/quorum_commitments.json` (durable state),
      2) a QUORUM_COMMIT event row in `.sifta_state/quorum_events.jsonl`,
      3) optionally a broadcast row in `m5queen_dead_drop.jsonl`.

    Hysteresis: a previously COMMITTED label stays committed until its
    probability drops below `threshold.top_prob_release`. This prevents
    single-signal flips — the Hill-coefficient analogue.

    Returns a dict describing the action taken (or skipped).
    """
    th = threshold or QuorumThreshold()
    readout = sense(field_obj, th)

    def _updater(state_on_disk: Dict[str, Any]) -> Dict[str, Any]:
        committed = dict(state_on_disk or {})
        current_label = committed.get("committed_label")

        action = "no_change"
        emitted = None

        # Release check first: if we're already committed but the label
        # probability dropped below release, uncommit.
        if current_label is not None:
            dist = field_obj.distribution()
            p = dist.get(current_label, 0.0)
            if p < th.top_prob_release:
                emitted = {
                    "event": "QUORUM_RELEASE",
                    "previous_label": current_label,
                    "p_at_release": round(p, 4),
                    "reason": f"p<{th.top_prob_release}",
                }
                committed = {
                    "committed_label": None,
                    "released_from": current_label,
                    "release_ts": time.time(),
                }
                action = "released"

        # Commit check: only if not already committed to this label.
        if action == "no_change" and readout.state == QuorumState.COMMITTED:
            if current_label != readout.top_label:
                emitted = {
                    "event": "QUORUM_COMMIT",
                    "label": readout.top_label,
                    "p": readout.top_prob,
                    "margin": readout.margin,
                    "nodes": readout.contributing_nodes,
                    "mass": readout.total_mass_on_top,
                    "entropy": readout.entropy,
                }
                committed = {
                    "committed_label": readout.top_label,
                    "commit_ts": time.time(),
                    "p_at_commit": readout.top_prob,
                    "margin_at_commit": readout.margin,
                    "nodes_at_commit": readout.contributing_nodes,
                    "observer": observer,
                    "session_id": session_id,
                }
                action = "committed"

        if emitted is not None:
            row = {
                "schema_version": SCHEMA_VERSION,
                "module_version": MODULE_VERSION,
                "timestamp": int(time.time()),
                "observer": observer,
                "session_id": session_id,
                "readout": asdict(readout),
                **emitted,
            }
            append_line_locked(_QUORUM_EVENTS, json.dumps(row, ensure_ascii=False) + "\n")
            if write_dead_drop:
                drop = {
                    "sender": observer,
                    "recipient": "ALL",
                    "timestamp": row["timestamp"],
                    "text": (
                        f"{emitted['event']} emitted by quorum_sensing.py. "
                        f"label={emitted.get('label') or emitted.get('previous_label')} "
                        f"readout_state={readout.state} top_prob={readout.top_prob} "
                        f"margin={readout.margin} nodes={readout.contributing_nodes} "
                        f"mass={readout.total_mass_on_top} entropy={readout.entropy}"
                    ),
                    "source": "QUORUM_SENSING",
                    "session": session_id,
                    "refs": {
                        "quorum_event_file": str(_QUORUM_EVENTS),
                        "commitments_file": str(_QUORUM_STATE),
                    },
                }
                append_line_locked(_DEAD_DROP, json.dumps(drop, ensure_ascii=False) + "\n")

        committed["_last_action"] = action
        committed["_last_readout"] = asdict(readout)
        committed["_last_update_ts"] = time.time()
        return committed

    new_state = read_write_json_locked(_QUORUM_STATE, _updater)
    return {
        "action": new_state.get("_last_action", "no_change"),
        "readout": asdict(readout),
        "committed_label": new_state.get("committed_label"),
    }


# ─── Demo / self-test ──────────────────────────────────────────────────────

def _demo() -> None:
    """Synthetic three-node convergence that should trigger a COMMIT."""
    from System.identity_field_crdt import IdentityField
    f = IdentityField()
    # Three independent nodes pile evidence onto the same label.
    f.update_from_classifier("C47H", {"opus-4.7": 0.85, "gpt-5.3": 0.10, "gem": 0.05}, weight=3)
    f.update_from_classifier("AG31", {"opus-4.7": 0.70, "gem": 0.20, "gpt-5.3": 0.10}, weight=2)
    f.update_from_classifier("CS46", {"opus-4.7": 0.65, "gpt-5.3": 0.25, "gem": 0.10}, weight=2)
    r = sense(f)
    print(f"[quorum_sensing] demo  v{MODULE_VERSION}")
    print("readout:", json.dumps(asdict(r), ensure_ascii=False, indent=2))
    assert r.state == QuorumState.COMMITTED, f"expected COMMITTED, got {r.state}"
    # Same call on a one-node field must NOT commit (anti-mirror rule).
    f_solo = IdentityField()
    f_solo.update_from_classifier("AG31", {"opus-4.7": 0.99, "x": 0.01}, weight=10)
    r_solo = sense(f_solo)
    assert r_solo.state == QuorumState.ACCUMULATING, (
        f"single-source quorum leak: state={r_solo.state}"
    )
    print("single-source commit blocked  OK")


if __name__ == "__main__":
    _demo()


__all__ = [
    "QuorumThreshold",
    "QuorumState",
    "QuorumReadout",
    "sense",
    "commit_if_quorum",
    "MODULE_VERSION",
    "SCHEMA_VERSION",
]
