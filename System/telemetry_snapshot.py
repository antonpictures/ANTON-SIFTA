#!/usr/bin/env python3
"""
System/telemetry_snapshot.py — Unified Organism Telemetry
══════════════════════════════════════════════════════════════════

Consolidates the entire V8–V15 organism state into a single JSON file:

    .sifta_state/telemetry_snapshot.json

Written atomically via rewrite_text_locked (POSIX flock).
Consumable by:
    - Flutter/Dart (dart:io FileSystemEntity.watch)
    - PyQt6 widgets (QFileSystemWatcher)
    - HTML dashboards (fetch + poll)
    - Any process that can read JSON

Called on each heartbeat cycle or on-demand.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.jsonl_file_lock import rewrite_text_locked

_STATE = _REPO / ".sifta_state"
SNAPSHOT_FILE = _STATE / "telemetry_snapshot.json"


def _safe_call(fn, *args, default=None, **kwargs):
    """Call fn, return default on any error."""
    try:
        return fn(*args, **kwargs)
    except Exception:
        return default


def capture_snapshot() -> dict[str, Any]:
    """
    Reads all live subsystem states and returns a unified dict.
    Does NOT write to disk — use write_snapshot() for that.
    """
    ts = time.time()
    snap: dict[str, Any] = {
        "snapshot_ts": ts,
        "snapshot_iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "homeworld": "M5_STUDIO",
    }

    # ── V8: Lagrangian Constraint Manifold ──────────────────────────
    def _read_manifold():
        from System.lagrangian_constraint_manifold import get_manifold
        dual = get_manifold().compute_dual_ascent()
        total_lam = dual.get("total_lambda_penalty", 0.0)
        return {
            "total_lambda": round(total_lam, 6),
            "lambda_norm": round(min(1.0, total_lam / 1.5), 6),
            "constraints": {
                k: round(v, 6) for k, v in dual.items()
                if k.startswith("lambda_") and k != "total_lambda_penalty"
            },
        }
    snap["manifold"] = _safe_call(_read_manifold, default={"total_lambda": 0, "lambda_norm": 0, "constraints": {}})

    lam_norm = snap["manifold"]["lambda_norm"]

    # ── V14: Metabolic Economy ──────────────────────────────────────
    def _read_metabolism():
        from System.stgm_metabolic import (
            calculate_metabolic_mint_rate,
            calculate_dynamic_store_fee,
            metabolic_regime_label,
        )
        mint = calculate_metabolic_mint_rate(lam_norm)
        store = calculate_dynamic_store_fee(lam_norm)
        return {
            "regime": metabolic_regime_label(lam_norm),
            "mint_rate": round(mint, 6),
            "store_fee": round(store, 6),
            "deflation_active": store > mint,
        }
    snap["metabolism"] = _safe_call(_read_metabolism, default={"regime": "UNKNOWN", "mint_rate": 0.05, "store_fee": 0.05, "deflation_active": False})

    # ── PPO entropy bridge (advisory until SwarmRL trainer consumes this) ──
    def _read_entropy_bridge():
        from System.lagrangian_entropy_controller import recommended_entropy_schedule

        return recommended_entropy_schedule(lam_norm)

    snap["ppo_entropy_bridge"] = _safe_call(
        _read_entropy_bridge,
        default={
            "schedule": "exponential_lambda",
            "lambda_norm": lam_norm,
            "entropy_coefficient_c2": 0.01,
            "c2_max": 0.01,
            "exploration_headroom": 1.0,
            "law_summary": "fallback",
            "swarmrl_param": "ProximalPolicyLoss.entropy_coefficient",
        },
    )

    # ── Track B: stigmergic rollout trace → c₂ (optional JSONL) ─────────────
    def _read_stigmergic_trace_summary():
        from System.stigmergic_entropy_trace import DEFAULT_EVENTS_PATH, summarize_trace_file

        return summarize_trace_file(DEFAULT_EVENTS_PATH, tail_lines=800)

    snap["stigmergic_entropy_trace_summary"] = _safe_call(
        _read_stigmergic_trace_summary,
        default={"events_loaded": 0, "mean_entropy": None, "mean_reward": None, "trace_entropy_coefficient_c2": None},
    )

    # ── V12: Memory Fitness Overlay ─────────────────────────────────
    def _read_fitness():
        fitness_file = _STATE / "memory_fitness.json"
        if not fitness_file.exists():
            return {"total_traces": 0, "top_5": []}
        from System.jsonl_file_lock import read_text_locked
        raw = read_text_locked(fitness_file)
        if not raw.strip():
            return {"total_traces": 0, "top_5": []}
        data = json.loads(raw)
        # Handle nested schema
        traces = data.get("traces", data) if isinstance(data, dict) else {}
        if not isinstance(traces, dict):
            return {"total_traces": 0, "top_5": []}

        entries = []
        for tid, entry in traces.items():
            if isinstance(entry, dict) and "fitness" in entry:
                entries.append({
                    "trace_id": tid,
                    "fitness": round(float(entry.get("fitness", 1.0)), 4),
                    "usage_count": int(entry.get("usage_count", 0)),
                })
        entries.sort(key=lambda e: e["fitness"], reverse=True)
        return {
            "total_traces": len(entries),
            "top_5": entries[:5],
        }
    snap["memory_fitness"] = _safe_call(_read_fitness, default={"total_traces": 0, "top_5": []})

    # ── V15: Apoptosis Graveyard ────────────────────────────────────
    def _read_graveyard():
        death_log = _STATE / "apoptosis" / "death_certificates.jsonl"
        if not death_log.exists():
            return {"total_deaths": 0, "recent": [], "by_reason": {}}
        from System.jsonl_file_lock import read_text_locked
        raw = read_text_locked(death_log)
        certs = []
        for line in raw.splitlines():
            line = line.strip()
            if line:
                try:
                    certs.append(json.loads(line))
                except Exception:
                    pass
        by_reason: dict[str, int] = {}
        for c in certs:
            r = c.get("reason", "UNKNOWN")
            by_reason[r] = by_reason.get(r, 0) + 1

        recent = sorted(certs, key=lambda c: c.get("timestamp", 0), reverse=True)[:5]
        return {
            "total_deaths": len(certs),
            "by_reason": by_reason,
            "recent": [
                {
                    "swimmer_id": c.get("swimmer_id"),
                    "reason": c.get("reason"),
                    "epitaph": c.get("epitaph", "")[:120],
                    "age_hours": c.get("age_hours"),
                }
                for c in recent
            ],
        }
    snap["graveyard"] = _safe_call(_read_graveyard, default={"total_deaths": 0, "recent": [], "by_reason": {}})

    # ── Ledger Stats ────────────────────────────────────────────────
    def _read_ledger_stats():
        ledger = _STATE / "memory_ledger.jsonl"
        if not ledger.exists():
            return {"total_memories": 0, "size_bytes": 0}
        size = ledger.stat().st_size
        count = sum(1 for line in ledger.read_text().splitlines() if line.strip())
        return {"total_memories": count, "size_bytes": size}
    snap["ledger"] = _safe_call(_read_ledger_stats, default={"total_memories": 0, "size_bytes": 0})

    # ── Climate summary ─────────────────────────────────────────────
    if lam_norm > 0.7:
        snap["climate"] = "BUNKER"
    elif lam_norm > 0.3:
        snap["climate"] = "STRESSED"
    else:
        snap["climate"] = "CALM"

    return snap


def write_snapshot() -> Path:
    """Capture and atomically write the telemetry snapshot."""
    snap = capture_snapshot()
    _STATE.mkdir(parents=True, exist_ok=True)
    rewrite_text_locked(SNAPSHOT_FILE, json.dumps(snap, indent=2) + "\n")
    return SNAPSHOT_FILE


# ── CLI / Self-Test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    path = write_snapshot()
    snap = json.loads(path.read_text())

    print("═" * 65)
    print("  TELEMETRY SNAPSHOT — Unified Organism State")
    print("═" * 65)
    print(f"  Time:       {snap['snapshot_iso']}")
    print(f"  Climate:    {snap['climate']}")
    print(f"  λ norm:     {snap['manifold']['lambda_norm']}")
    print(f"  Regime:     {snap['metabolism']['regime']}")
    print(f"  Mint Rate:  {snap['metabolism']['mint_rate']}")
    print(f"  Store Fee:  {snap['metabolism']['store_fee']}")
    print(f"  Deflation:  {snap['metabolism']['deflation_active']}")
    peb = snap.get("ppo_entropy_bridge", {})
    print(f"  PPO c₂:     {peb.get('entropy_coefficient_c2')}  headroom={peb.get('exploration_headroom')}")
    tes = snap.get("stigmergic_entropy_trace_summary", {})
    print(f"  Trace c₂:  {tes.get('trace_entropy_coefficient_c2')}  events={tes.get('events_loaded')}")
    print(f"  Memories:   {snap['ledger']['total_memories']}")
    print(f"  Fit Traces: {snap['memory_fitness']['total_traces']}")
    print(f"  Deaths:     {snap['graveyard']['total_deaths']}")
    print()

    if snap["memory_fitness"]["top_5"]:
        print("  Top Fitness:")
        for e in snap["memory_fitness"]["top_5"]:
            print(f"    [{e['trace_id'][:8]}] fitness={e['fitness']:.4f} used={e['usage_count']}")

    print()
    print(f"  Written to: {path}")
    print(f"  ✅ ANY FRONTEND CAN NOW READ THE ORGANISM'S MIND. 🐜⚡")
