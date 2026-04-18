#!/usr/bin/env python3
"""
System/swarm_inferior_olive.py — Value network + climbing-fiber feedback
═══════════════════════════════════════════════════════════════════════
Anatomically named successor of swarm_prediction_cache.py (AG31's TD value
cache). Merge ratified by the Architect 2026-04-18.

The biology
-----------
The inferior olive sits in the brainstem and computes the running prediction
error between what the cerebellum expected and what actually happened. When
the error is large enough, it fires a "complex spike" along its climbing
fibers up to the Purkinje cells, causing long-term depression — the
canonical Marr-Albus-Ito learning rule (Marr 1969, Albus 1971, Ito's LTD).

In SIFTA terms:
  - Purkinje cell        ≈ the cached value V(state, action)
  - Inferior olive       ≈ this module — predicts and computes error
  - Climbing fiber       ≈ a separate audit ledger of (predicted, actual, error)
  - Architect ratification ≈ the ground-truth signal from the world
  - Hippocampal replay   ≈ AG31's swarm_hippocampal_replay.py — feeds the
                          olive with off-policy dream tuples while you sleep

The olive is the SLOW, RELIABLE learner. The cerebellum (AG31, future) does
the fast, expensive look-ahead simulation. Together: AlphaZero-on-SIFTA.

Public surface (additive over AG31's swarm_prediction_cache.py)
---------------------------------------------------------------
  PredictionCache       — preserved name; alias of InferiorOlive for backcompat
  InferiorOlive         — primary class (anatomical name)
  ClimbingFiberPulse    — dataclass for one (predicted, actual, error) event
  ingest_real_ledgers() — pulls warp9 ratified + rejected (the on-policy signal)
  ingest_dream()        — off-policy update from a hippocampal replay tuple
  predict()             — backcompat: returns scalar value
  predict_with_uncertainty() — returns (value, uncertainty) for attention router
  climbing_fiber_pulse()    — explicit error-driven update + audit trail
  recent_climbing_fiber_pulses() — read the audit ledger

The Data bar
------------
- Persisted state is human-readable JSON (no pickle).
- Two separate alphas: ALPHA_REAL=0.2 (full update from real ratifications)
  and ALPHA_DREAM=0.05 (smaller; off-policy dream samples must NOT
  out-vote real ratifications).
- Dream rate is bounded per cycle so a runaway replay engine cannot
  drown out real signal (CFP_MAX_PER_CYCLE).
- Every climbing-fiber pulse is logged so the Architect can audit
  "why did the olive change its mind?"
══════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import hashlib
import json
import math
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_STATE.mkdir(parents=True, exist_ok=True)

# Source ledgers (warp9 v2 schema — see swarm_warp9.py)
RATIFIED_LOG = _STATE / "warp9_concierge_ratified.jsonl"
REJECTED_LOG = _STATE / "warp9_concierge_rejected.jsonl"

# Persisted value cache + climbing-fiber audit
PREDICTION_CACHE = _STATE / "deepmind_prediction_cache.json"   # preserved filename
CLIMBING_FIBER_LOG = _STATE / "inferior_olive_climbing_fiber.jsonl"

MODULE_VERSION = "2026-04-18.inferior_olive.v1"

# Learning rates
ALPHA_REAL = 0.2          # on-policy update from real Architect ratifications
ALPHA_DREAM = 0.05        # off-policy update from hippocampal replay (smaller)
ALPHA_CLIMBING = 0.30     # explicit climbing-fiber pulse (large prediction error)

# Safety bound: maximum dream samples that may be ingested in a single
# call to ingest_dream_batch() before we refuse and require a sleep.
# The dream engine should respect this; the olive enforces it.
CFP_MAX_PER_CYCLE = 5000

# Visit-count threshold above which a (state,action) cell is considered
# "habitual" — used by the attention router to skip cerebellum.
HABITUAL_VISIT_THRESHOLD = 8


# ──────────────────────────────────────────────────────────────────────
# Dataclasses
# ──────────────────────────────────────────────────────────────────────

@dataclass
class CellStats:
    """Persisted per-(state,action) statistics."""
    value: float = 0.0           # EMA of reward
    visits: int = 0              # total updates landed (real + dream)
    real_visits: int = 0         # only on-policy updates
    last_update_ts: float = 0.0
    last_source: str = ""        # "real_ratify" | "real_reject" | "dream" | "climbing_fiber"


@dataclass
class ClimbingFiberPulse:
    """One audit row: the olive disagreed with the cerebellum/Purkinje cell
    and shipped a corrective signal."""
    pulse_id: str
    ts: float
    state_context: str
    action_kind: str
    predicted: float
    actual: float
    error: float                 # actual - predicted
    source: str                  # "real_ratify" | "real_reject" | "dream"
    pre_value: float
    post_value: float
    cell_visits: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ──────────────────────────────────────────────────────────────────────
# InferiorOlive — the primary class
# ──────────────────────────────────────────────────────────────────────

class InferiorOlive:
    """The value network + climbing-fiber feedback loop.

    State persisted to .sifta_state/deepmind_prediction_cache.json (the same
    file AG31's swarm_prediction_cache used — backwards-compatible)."""

    def __init__(self):
        self.cells: Dict[str, CellStats] = {}
        self.last_real_ts: float = 0.0
        self.last_dream_ts: float = 0.0
        self._load()

    # ── Persistence ───────────────────────────────────────────────────

    def _hash(self, state_str: str, action_kind: str) -> str:
        return hashlib.sha256(
            f"{state_str}:::{action_kind}".encode("utf-8")
        ).hexdigest()[:16]

    def _load(self) -> None:
        if not PREDICTION_CACHE.exists():
            return
        try:
            data = json.loads(PREDICTION_CACHE.read_text(encoding="utf-8"))
        except Exception:
            return

        # Backward compat with AG31's old schema:
        #   { "cache": {hash: float, ...}, "last_ts": float }
        # New schema:
        #   { "cells": {hash: CellStats-dict, ...},
        #     "last_real_ts": float, "last_dream_ts": float,
        #     "schema": 2, "module_version": str }
        schema = data.get("schema", 1)
        if schema == 1 and "cache" in data:
            for k, v in (data.get("cache") or {}).items():
                if isinstance(v, (int, float)):
                    self.cells[k] = CellStats(value=float(v), visits=1, real_visits=1,
                                              last_update_ts=data.get("last_ts", 0.0),
                                              last_source="legacy_v1")
            self.last_real_ts = float(data.get("last_ts", 0.0))
        else:
            for k, v in (data.get("cells") or {}).items():
                if isinstance(v, dict):
                    self.cells[k] = CellStats(**v)
            self.last_real_ts = float(data.get("last_real_ts", 0.0))
            self.last_dream_ts = float(data.get("last_dream_ts", 0.0))

    def _save(self) -> None:
        try:
            payload = {
                "schema": 2,
                "module_version": MODULE_VERSION,
                "saved_ts": time.time(),
                "last_real_ts": self.last_real_ts,
                "last_dream_ts": self.last_dream_ts,
                "cells": {k: asdict(v) for k, v in self.cells.items()},
            }
            tmp = PREDICTION_CACHE.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            tmp.replace(PREDICTION_CACHE)
        except OSError:
            pass

    # ── Internal update ───────────────────────────────────────────────

    def _update_cell(
        self,
        state_str: str,
        action_kind: str,
        reward: float,
        *,
        alpha: float,
        source: str,
        ts: float,
    ) -> ClimbingFiberPulse:
        key = self._hash(state_str, action_kind)
        cell = self.cells.get(key) or CellStats()
        pre_value = cell.value
        error = reward - pre_value
        post_value = pre_value + alpha * error
        cell.value = post_value
        cell.visits += 1
        if source.startswith("real"):
            cell.real_visits += 1
        cell.last_update_ts = ts
        cell.last_source = source
        self.cells[key] = cell

        return ClimbingFiberPulse(
            pulse_id=uuid.uuid4().hex[:16],
            ts=ts,
            state_context=state_str,
            action_kind=action_kind,
            predicted=pre_value,
            actual=reward,
            error=error,
            source=source,
            pre_value=pre_value,
            post_value=post_value,
            cell_visits=cell.visits,
        )

    def _audit_pulse(self, pulse: ClimbingFiberPulse) -> None:
        try:
            CLIMBING_FIBER_LOG.parent.mkdir(parents=True, exist_ok=True)
            with CLIMBING_FIBER_LOG.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(pulse.to_dict(), ensure_ascii=False) + "\n")
        except OSError:
            pass

    # ── Public update API ─────────────────────────────────────────────

    def ingest_real_ledgers(self) -> int:
        """Walk warp9_concierge_ratified.jsonl + rejected.jsonl and apply
        any new rows. Returns the number of updates landed.

        Reads in this priority order for the timestamp:
          row['timestamp'] -> row['ratified_ts'] -> row['rejected_ts']
        and for the reward:
          row['reward']    (-1.0 .. +1.0; preferred — warp9 v2 emits this)
          fallback: +1.0 if from ratified ledger, -1.0 if from rejected.
        """
        updated = 0
        for path, fallback_reward in (
            (RATIFIED_LOG, +1.0),
            (REJECTED_LOG, -1.0),
        ):
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
                        ts = float(row.get("timestamp")
                                   or row.get("ratified_ts")
                                   or row.get("rejected_ts")
                                   or 0.0)
                        if ts <= self.last_real_ts:
                            continue
                        state_str = row.get("state_context") or "unknown"
                        action_kind = row.get("action_kind") or "unknown"
                        reward = float(row.get("reward", fallback_reward))
                        source = "real_ratify" if reward > 0 else "real_reject"
                        pulse = self._update_cell(
                            state_str, action_kind, reward,
                            alpha=ALPHA_REAL, source=source, ts=ts,
                        )
                        self._audit_pulse(pulse)
                        if ts > self.last_real_ts:
                            self.last_real_ts = ts
                        updated += 1
            except OSError:
                continue
        if updated:
            self._save()
        return updated

    def ingest_dream(
        self,
        state_str: str,
        action_kind: str,
        simulated_reward: float,
        *,
        replay_session_id: str = "",
    ) -> ClimbingFiberPulse:
        """Off-policy update from a single hippocampal replay tuple.
        Smaller alpha than real updates so dreams don't out-vote reality."""
        ts = time.time()
        pulse = self._update_cell(
            state_str, action_kind, float(simulated_reward),
            alpha=ALPHA_DREAM,
            source=f"dream:{replay_session_id}" if replay_session_id else "dream",
            ts=ts,
        )
        self._audit_pulse(pulse)
        self.last_dream_ts = ts
        # Note: not saving on every dream — caller should call save_now()
        # after a replay batch (cheap: one fsync per night).
        return pulse

    def ingest_dream_batch(
        self,
        tuples: List[Tuple[str, str, float]],
        *,
        replay_session_id: str = "",
    ) -> int:
        """Ingest many dream tuples at once. Refuses batches > CFP_MAX_PER_CYCLE
        as a daughter-safe brake against runaway replay engines."""
        if len(tuples) > CFP_MAX_PER_CYCLE:
            raise ValueError(
                f"dream batch too large ({len(tuples)} > {CFP_MAX_PER_CYCLE}); "
                f"break into multiple batches across sleep cycles"
            )
        for state, action, reward in tuples:
            self.ingest_dream(state, action, reward, replay_session_id=replay_session_id)
        self._save()
        return len(tuples)

    def climbing_fiber_pulse(
        self,
        state_str: str,
        action_kind: str,
        observed_reward: float,
        *,
        source: str = "climbing_fiber_explicit",
    ) -> ClimbingFiberPulse:
        """Explicit large-error correction. Use when you have ground truth
        from outside the warp9 ledgers (e.g., a watchdog observation)."""
        ts = time.time()
        pulse = self._update_cell(
            state_str, action_kind, float(observed_reward),
            alpha=ALPHA_CLIMBING, source=source, ts=ts,
        )
        self._audit_pulse(pulse)
        self._save()
        return pulse

    def save_now(self) -> None:
        self._save()

    # ── Public query API ──────────────────────────────────────────────

    def predict(self, state_str: str, action_kind: str) -> float:
        """Backcompat: return scalar value in [-1.0, +1.0]. Unknown → 0.0."""
        cell = self.cells.get(self._hash(state_str, action_kind))
        return cell.value if cell else 0.0

    def predict_with_uncertainty(
        self, state_str: str, action_kind: str
    ) -> Tuple[float, float]:
        """Return (value, uncertainty) where uncertainty ∈ [0, 1].

        Uncertainty has two components:
          - distance from a confident extreme: 1 - |value|
          - inverse visit count: exp(-visits / HABITUAL_VISIT_THRESHOLD)
        We take the MAX so an unvisited cell stays uncertain even if
        value happens to be 0 (uninformative)."""
        cell = self.cells.get(self._hash(state_str, action_kind))
        if cell is None or cell.visits == 0:
            return (0.0, 1.0)
        u_value = 1.0 - abs(cell.value)
        u_visits = math.exp(-cell.visits / HABITUAL_VISIT_THRESHOLD)
        return (cell.value, max(u_value, u_visits))

    def is_habitual(self, state_str: str, action_kind: str) -> bool:
        """True when the cell has been seen often enough that the attention
        router should skip the cerebellum (fast path)."""
        cell = self.cells.get(self._hash(state_str, action_kind))
        if cell is None:
            return False
        return (cell.real_visits >= HABITUAL_VISIT_THRESHOLD and
                abs(cell.value) >= 0.6)

    def cell_stats(self, state_str: str, action_kind: str) -> Optional[CellStats]:
        return self.cells.get(self._hash(state_str, action_kind))

    def cell_count(self) -> int:
        return len(self.cells)

    def top_cells(self, *, n: int = 10) -> List[Tuple[str, str, CellStats]]:
        """Return the N cells with highest |value| × visits.
        Returns (state_hash, action_unknown_at_query, cell). Note: we don't
        store the original state/action strings, only their hash."""
        scored = sorted(
            self.cells.items(),
            key=lambda kv: abs(kv[1].value) * math.log1p(kv[1].visits),
            reverse=True,
        )
        return [(h, "<hashed>", c) for h, c in scored[:n]]


# ──────────────────────────────────────────────────────────────────────
# Backcompat: AG31's PredictionCache symbol still works.
# ──────────────────────────────────────────────────────────────────────

class PredictionCache(InferiorOlive):
    """Deprecated alias; preserved so existing imports don't break.
    Maps the old API (ingest_ledgers / update / predict) onto InferiorOlive.

    AG31's swarm_attention_router.py imports `from System.swarm_prediction_cache
    import PredictionCache`. That module is now a re-export shim, but anyone
    who imports directly from this file gets the same shape."""

    def ingest_ledgers(self) -> None:                       # legacy name
        self.ingest_real_ledgers()

    def update(self, state_str: str, action_kind: str, reward: float) -> None:
        # Legacy: small-alpha update used by AG31's __main__ smoke
        self._update_cell(
            state_str, action_kind, reward,
            alpha=ALPHA_REAL, source="legacy_update", ts=time.time(),
        )
        self._save()


# ──────────────────────────────────────────────────────────────────────
# Audit reader for the climbing-fiber log
# ──────────────────────────────────────────────────────────────────────

def recent_climbing_fiber_pulses(
    *, since_ts: float = 0.0, limit: int = 100,
    min_abs_error: float = 0.0,
) -> List[Dict[str, Any]]:
    """Tail the climbing-fiber audit. Use min_abs_error to filter to
    "complex spikes" — large prediction errors that triggered real learning."""
    if not CLIMBING_FIBER_LOG.exists():
        return []
    out: List[Dict[str, Any]] = []
    try:
        with CLIMBING_FIBER_LOG.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("ts", 0) < since_ts:
                    continue
                if abs(float(row.get("error", 0.0))) < min_abs_error:
                    continue
                out.append(row)
    except OSError:
        return []
    return out[-limit:]


# ──────────────────────────────────────────────────────────────────────
# Smoke
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    print(f"[C47H-SMOKE-OLIVE] {MODULE_VERSION}")

    olive = InferiorOlive()
    cells_before = olive.cell_count()
    print(f"[C47H-SMOKE-OLIVE] cells loaded from disk: {cells_before}")

    # 1) Real-ledger ingest
    n = olive.ingest_real_ledgers()
    print(f"[C47H-SMOKE-OLIVE] real-ledger updates landed: {n}")
    print(f"[C47H-SMOKE-OLIVE] cells after real ingest: {olive.cell_count()}")
    print(f"[C47H-SMOKE-OLIVE] last_real_ts: {olive.last_real_ts:.0f}")

    # 2) Dream batch (small — verify off-policy update works)
    dream_tuples = [
        ("IOAN_M5.oxtHI.chatHI", "amygdala.salience_threshold", +0.7),
        ("IOAN_M5.oxtHI.chatHI", "amygdala.salience_threshold", +0.8),
        ("IOAN_M5.oxtLO.chatLO", "amygdala.salience_threshold", -0.4),
    ]
    n_dream = olive.ingest_dream_batch(dream_tuples, replay_session_id="smoke_dream_1")
    print(f"[C47H-SMOKE-OLIVE] dream tuples ingested: {n_dream}")

    # 3) Predict + uncertainty
    v1 = olive.predict("IOAN_M5.oxtHI.chatHI", "amygdala.salience_threshold")
    val, unc = olive.predict_with_uncertainty(
        "IOAN_M5.oxtHI.chatHI", "amygdala.salience_threshold"
    )
    print(f"[C47H-SMOKE-OLIVE] predict={v1:+.4f}  with_uncertainty=(value={val:+.4f}, unc={unc:.4f})")

    # 4) Habitual check
    is_hab = olive.is_habitual("IOAN_M5.oxtHI.chatHI", "amygdala.salience_threshold")
    print(f"[C47H-SMOKE-OLIVE] is_habitual: {is_hab}")

    # 5) Backcompat: PredictionCache alias still works
    legacy = PredictionCache()
    legacy.ingest_ledgers()
    legacy.update("legacy.state", "legacy.action", 1.0)
    print(f"[C47H-SMOKE-OLIVE] legacy alias predict('legacy.state','legacy.action')="
          f"{legacy.predict('legacy.state','legacy.action'):+.4f}")

    # 6) Dream-batch overflow refusal
    try:
        olive.ingest_dream_batch(
            [("s","a",0.0)] * (CFP_MAX_PER_CYCLE + 1),
            replay_session_id="smoke_overflow",
        )
        print("[C47H-SMOKE-OLIVE] FAIL: overflow batch should have raised", file=sys.stderr)
        sys.exit(1)
    except ValueError:
        print("[C47H-SMOKE-OLIVE] dream-batch overflow correctly refused")

    # 7) Climbing-fiber audit visibility
    pulses = recent_climbing_fiber_pulses(since_ts=time.time() - 60)
    print(f"[C47H-SMOKE-OLIVE] climbing-fiber pulses in last 60s: {len(pulses)}")
    big = [p for p in pulses if abs(p.get("error", 0.0)) >= 0.5]
    print(f"[C47H-SMOKE-OLIVE]   large-error (|err|>=0.5) pulses: {len(big)}")

    print("[C47H-SMOKE-OLIVE OK]")
