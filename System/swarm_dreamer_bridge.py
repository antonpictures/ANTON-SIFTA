#!/usr/bin/env python3
"""
System/swarm_dreamer_bridge.py — LWM ↔ InferiorOlive integration glue
══════════════════════════════════════════════════════════════════════
SIFTA OS — DeepMind Cognitive Suite

The problem this solves
-----------------------
After the Dreamer Protocol ratification (2026-04-18), AG31 shipped two
modules that work brilliantly *in isolation*:

    swarm_latent_world_model.py      — directed transition matrix + Bellman
    swarm_hippocampal_replay.py      — REM-sleep dream rollouts

But the dreamer writes its TD updates into the LWM's `value_table` only.
It does NOT feed the warp9-aware InferiorOlive value network — the one
that respects ALPHA_DREAM=0.05, the CFP_MAX_PER_CYCLE=5000 brake, and
the climbing-fiber audit log.

Without a bridge, SIFTA grows two value functions in parallel that drift
silently apart. The Architect would only discover the divergence when a
proposal arrives that the Concierge thinks is healthy and the dreamer
thinks is catastrophic. That's exactly the failure mode the Contradiction
Engine was built to detect — but it can't catch a divergence between a
class attribute and a JSON file.

What this module does
---------------------
- Provides `replay_with_olive_feedback()` — drop-in superset of
  Hippocampus.enter_rem_sleep() that ALSO emits each dream's
  (state, action, reward) tuple into InferiorOlive.ingest_dream_batch(),
  respecting the daughter-safe brake.
- Reads BOTH `warp9_concierge_ratified.jsonl` AND `warp9_concierge_rejected.jsonl`
  so the dreamer learns from negative ratifications too.
- Wraps the entire dream cycle in a `shadow_session` so any future
  state mutations the dreamer wants to try are sandboxed.
- Adds a circadian gate: refuses to dream if the Architect has been
  active in the last `awake_window_s` seconds (default 2 h, matching
  AG31's design doc).
- Logs a per-cycle bridge audit row to `dreamer_bridge_audit.jsonl`.

Public surface
--------------
- `BridgeReport` — dataclass returned per dream cycle
- `replay_with_olive_feedback(cycles=..., horizon=..., awake_window_s=...)`
- `architect_recently_active(window_s=...)` — circadian helper

Pure additive: AG31's modules are untouched.
══════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from System.swarm_shadow_state import shadow_session
from System.swarm_inferior_olive import InferiorOlive, CFP_MAX_PER_CYCLE
from System.swarm_latent_world_model import LatentWorldModel
from System.swarm_hippocampal_replay import (
    Hippocampus, ReplayMemory,
    RATIFIED_LOG, REPLAY_LOG,
)

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
REJECTED_LOG = _STATE / "warp9_concierge_rejected.jsonl"
BRIDGE_AUDIT = _STATE / "dreamer_bridge_audit.jsonl"

MODULE_VERSION = "2026-04-18.dreamer_bridge.v1"

# Default circadian window. AG31's design doc:
#   "When the Architect steps away (no API activity for >2 hours),
#    the Swarm enters REM sleep."
DEFAULT_AWAKE_WINDOW_S = 2 * 3600

# Default rollout depth (matches AG31's 5-step horizon)
DEFAULT_HORIZON = 5

# Per-cycle dream cap (separate from olive's per-batch CFP_MAX_PER_CYCLE).
# A single REM cycle should not pretend to be a whole night's sleep.
DEFAULT_CYCLES_PER_REM = 100


# ──────────────────────────────────────────────────────────────────────
# Activity heuristic — the circadian gate
# ──────────────────────────────────────────────────────────────────────

# We sniff the most-frequently-touched ledgers for the latest mtime as a
# cheap proxy for "Architect was here recently". No new dependency required.
_ACTIVITY_LEDGERS = (
    "ide_stigmergic_trace.jsonl",
    "warp9_concierge_proposals.jsonl",
    "warp9_concierge_ratified.jsonl",
    "warp9_concierge_rejected.jsonl",
    "memory_ledger.jsonl",
    "factory_ledger.jsonl",
    "decision_trace.log",
)


def latest_activity_ts() -> float:
    """Return the most recent mtime across the activity ledgers, or 0 if none."""
    latest = 0.0
    for name in _ACTIVITY_LEDGERS:
        p = _STATE / name
        if not p.exists():
            continue
        try:
            mt = p.stat().st_mtime
            if mt > latest:
                latest = mt
        except OSError:
            continue
    return latest


def architect_recently_active(window_s: float = DEFAULT_AWAKE_WINDOW_S) -> bool:
    """True if any activity ledger was touched within the last `window_s`."""
    last = latest_activity_ts()
    if last == 0.0:
        return False
    return (time.time() - last) < window_s


# ──────────────────────────────────────────────────────────────────────
# Reject-ledger ingest — closes the negative-reinforcement gap
# ──────────────────────────────────────────────────────────────────────

def _read_warp9_rows(*, include_rejects: bool = True) -> List[Dict[str, Any]]:
    """Read both ratified and rejected warp9 ledgers as a unified row list."""
    out: List[Dict[str, Any]] = []
    for path, fallback_reward in (
        (RATIFIED_LOG, +1.0),
        (REJECTED_LOG, -1.0),
    ):
        if not include_rejects and path is REJECTED_LOG:
            continue
        if not path.exists():
            continue
        try:
            with path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    row.setdefault("reward", fallback_reward)
                    out.append(row)
        except OSError:
            continue
    return out


# ──────────────────────────────────────────────────────────────────────
# BridgeReport — what the bridge returns
# ──────────────────────────────────────────────────────────────────────

@dataclass
class BridgeReport:
    started_ts: float
    finished_ts: float
    cycles_requested: int
    cycles_run: int
    horizon: int
    memories_loaded: int
    rejected_memories_loaded: int
    olive_dream_tuples: int
    olive_cells_after: int
    lwm_states_after: int
    lwm_transitions_after: int
    skipped_reason: str = ""           # non-empty if the gate refused
    sample_trajectories: List[Dict[str, Any]] = field(default_factory=list)
    shadow_session_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ──────────────────────────────────────────────────────────────────────
# The bridge
# ──────────────────────────────────────────────────────────────────────

def replay_with_olive_feedback(
    *,
    cycles: int = DEFAULT_CYCLES_PER_REM,
    horizon: int = DEFAULT_HORIZON,
    awake_window_s: float = DEFAULT_AWAKE_WINDOW_S,
    force: bool = False,
    include_rejects: bool = True,
) -> BridgeReport:
    """A REM-sleep cycle that updates BOTH the LWM (AG31) AND the
    InferiorOlive (C47H) from the same dream rollouts.

    Args:
        cycles: number of dream rollouts to run this REM cycle.
        horizon: depth of each rollout (steps into the future).
        awake_window_s: refuse to dream if Architect activity is more
            recent than this many seconds.
        force: bypass the circadian gate (use for diagnostic smoke).
        include_rejects: also feed warp9_concierge_rejected.jsonl rows
            (with reward=-1.0) into the dreamer. Default True.

    Returns a BridgeReport with everything that happened.
    """
    started = time.time()

    # ── Circadian gate ──
    if not force and architect_recently_active(window_s=awake_window_s):
        idle_for = time.time() - latest_activity_ts()
        return BridgeReport(
            started_ts=started,
            finished_ts=time.time(),
            cycles_requested=cycles,
            cycles_run=0,
            horizon=horizon,
            memories_loaded=0,
            rejected_memories_loaded=0,
            olive_dream_tuples=0,
            olive_cells_after=InferiorOlive().cell_count(),
            lwm_states_after=len(LatentWorldModel().value_table),
            lwm_transitions_after=len(LatentWorldModel().transitions),
            skipped_reason=(
                f"Architect was active {idle_for:.0f}s ago "
                f"(< {awake_window_s:.0f}s window). Refusing to dream."
            ),
        )

    # ── Cycle cap (daughter-safe brake) ──
    if cycles > CFP_MAX_PER_CYCLE:
        raise ValueError(
            f"cycles={cycles} exceeds CFP_MAX_PER_CYCLE={CFP_MAX_PER_CYCLE}; "
            f"break across multiple REM cycles"
        )

    olive = InferiorOlive()
    brain = Hippocampus()

    # ── Load memories from BOTH ledgers (positive + negative) ──
    rows = _read_warp9_rows(include_rejects=include_rejects)
    pos = [r for r in rows if float(r.get("reward", 0.0)) >= 0]
    neg = [r for r in rows if float(r.get("reward", 0.0)) < 0]

    brain.memories = []
    for row in rows:
        state = row.get("state_context", "unknown_state")
        action = row.get("action_kind", "unknown_action")
        reward = float(row.get("reward", 0.0))
        ts = float(row.get("timestamp") or row.get("ratified_ts")
                   or row.get("rejected_ts") or time.time())
        # Teach the LWM the real (s, a) → simulated successor mapping.
        next_state = f"{state}_resolved"   # AG31's MVP convention; preserved
        brain.world_model.observe_reality(state, action, next_state, reward)
        brain.memories.append(ReplayMemory(state, action, reward, ts))
    brain.world_model.save()

    if not brain.memories:
        return BridgeReport(
            started_ts=started,
            finished_ts=time.time(),
            cycles_requested=cycles,
            cycles_run=0,
            horizon=horizon,
            memories_loaded=0,
            rejected_memories_loaded=0,
            olive_dream_tuples=0,
            olive_cells_after=olive.cell_count(),
            lwm_states_after=len(brain.world_model.value_table),
            lwm_transitions_after=len(brain.world_model.transitions),
            skipped_reason="no warp9 memories yet — substrate ready, no dream possible",
        )

    # ── Wrap dream activity in a shadow_session ──
    samples: List[Dict[str, Any]] = []
    olive_tuples: List[Tuple[str, str, float]] = []

    with shadow_session(purpose=f"dreamer_bridge.replay.{int(started)}") as shadow:
        cycles_run = 0
        for _ in range(cycles):
            base = random.choice(brain.memories)
            trajectory, dream_reward = brain._dream_rollout(
                base.original_state, horizon=horizon
            )
            cycles_run += 1

            # Feed the olive: each step in the trajectory becomes an
            # off-policy update at ALPHA_DREAM=0.05.
            for i in range(len(trajectory) - 1):
                latent_step_state = trajectory[i]
                # Map the latent next_state back to a string identity for the
                # olive. We synthesise a stable hash-prefixed string the olive
                # can key on without colliding with real (state, action) cells.
                step_action = f"DREAM::{base.original_action}::step{i}"
                step_state = f"DREAM::{base.original_state}::lat{latent_step_state[:8]}"
                olive_tuples.append((step_state, step_action,
                                     float(dream_reward) / max(1, len(trajectory))))

            if len(samples) < 5:
                samples.append({
                    "start_state_raw": base.original_state,
                    "original_action": base.original_action,
                    "original_reward": base.original_reward,
                    "trajectory_len": len(trajectory),
                    "compounded_reward": dream_reward,
                })

        # Respect the olive's per-batch brake (split if needed)
        olive_landed = 0
        for chunk_start in range(0, len(olive_tuples), CFP_MAX_PER_CYCLE):
            chunk = olive_tuples[chunk_start:chunk_start + CFP_MAX_PER_CYCLE]
            olive.ingest_dream_batch(
                chunk,
                replay_session_id=shadow.session.session_id,
            )
            olive_landed += len(chunk)

        report = BridgeReport(
            started_ts=started,
            finished_ts=time.time(),
            cycles_requested=cycles,
            cycles_run=cycles_run,
            horizon=horizon,
            memories_loaded=len(pos),
            rejected_memories_loaded=len(neg),
            olive_dream_tuples=olive_landed,
            olive_cells_after=olive.cell_count(),
            lwm_states_after=len(brain.world_model.value_table),
            lwm_transitions_after=len(brain.world_model.transitions),
            sample_trajectories=samples,
            shadow_session_id=shadow.session.session_id,
        )

    # Save LWM after the dreams
    brain.world_model.save()

    # Bridge audit row
    try:
        with BRIDGE_AUDIT.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(report.to_dict(), ensure_ascii=False) + "\n")
    except OSError:
        pass

    # AG31's existing replay log (for backwards compat — they read this for the dashboard)
    try:
        with REPLAY_LOG.open("a") as fh:
            fh.write(json.dumps({
                "ts": time.time(),
                "total_dreams": report.cycles_run,
                "via_bridge": True,
                "olive_tuples": report.olive_dream_tuples,
                "shadow_session_id": report.shadow_session_id,
                "sample_logs": samples,
            }) + "\n")
    except OSError:
        pass

    return report


# ──────────────────────────────────────────────────────────────────────
# Smoke
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"[C47H-SMOKE-BRIDGE] {MODULE_VERSION}")

    # 1) Activity sniff — should be very recent (we're talking right now)
    last = latest_activity_ts()
    print(f"[C47H-SMOKE-BRIDGE] latest activity ts: {last:.0f} "
          f"({time.time() - last:.0f}s ago)")
    assert architect_recently_active(window_s=DEFAULT_AWAKE_WINDOW_S), \
        "the Architect IS active right now — gate should report True"
    print("[C47H-SMOKE-BRIDGE] circadian gate correctly reports Architect active")

    # 2) Refuse-to-dream when Architect active
    refused = replay_with_olive_feedback(cycles=10)
    assert refused.skipped_reason, \
        "bridge should refuse to dream while Architect is active"
    print(f"[C47H-SMOKE-BRIDGE] gate refusal: {refused.skipped_reason}")

    # 3) Force-dream (diagnostic) — should run and update both networks
    olive_before = InferiorOlive().cell_count()
    lwm_before = len(LatentWorldModel().value_table)
    report = replay_with_olive_feedback(cycles=20, horizon=5, force=True)
    print(f"[C47H-SMOKE-BRIDGE] force-dream report:")
    print(f"    cycles_run            = {report.cycles_run}")
    print(f"    memories +/-           = {report.memories_loaded} / {report.rejected_memories_loaded}")
    print(f"    olive dream tuples     = {report.olive_dream_tuples}")
    print(f"    olive cells before/after = {olive_before} / {report.olive_cells_after}")
    print(f"    lwm states  before/after = {lwm_before} / {report.lwm_states_after}")
    print(f"    shadow_session_id      = {report.shadow_session_id}")

    assert report.cycles_run == 20
    assert report.olive_dream_tuples > 0, \
        "force-dream should have fed at least 1 dream tuple to the olive"
    assert report.olive_cells_after >= olive_before, \
        "olive cells should not shrink after dreaming"

    # 4) Per-cycle brake
    try:
        replay_with_olive_feedback(cycles=CFP_MAX_PER_CYCLE + 1, force=True)
    except ValueError:
        print(f"[C47H-SMOKE-BRIDGE] cycle-cap brake correctly rejected "
              f"cycles>{CFP_MAX_PER_CYCLE}")
    else:
        print("[C47H-SMOKE-BRIDGE] FAIL: cycle cap did not refuse")
        raise SystemExit(1)

    print("[C47H-SMOKE-BRIDGE OK]")
