#!/usr/bin/env python3
"""
System/swarm_health_metrics.py
══════════════════════════════════════════════════════════════════════════════
Event 107 — Ledger-derived health metrics (truthful scores, no painted thermometer)

Reads append-only JSONL / JSON state under `.sifta_state/` and returns scalar
scores suitable for nightly audit compositing. All denominators guard zero.

Truth label: LEDGER_HEALTH_METRICS_EVENT_107
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from System.jsonl_file_lock import read_text_locked

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"

TRUTH_LABEL = "LEDGER_HEALTH_METRICS_EVENT_107"
MOTOR_TRUTH = "SKILL_WEIGHTED_POLICY"


def _base(state_dir: Optional[Path] = None) -> Path:
    return Path(state_dir) if state_dir is not None else _STATE_DIR


def _jsonl_tail(path: Path, max_lines: int) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        body = read_text_locked(path, encoding="utf-8", errors="replace")
    except OSError:
        return []
    out: List[Dict[str, Any]] = []
    for line in body.splitlines()[-max_lines:]:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def score_observability_ledgers(
    *,
    state_dir: Optional[Path] = None,
    ide_tail: int = 800,
    obs_tail: int = 800,
) -> Dict[str, Any]:
    """
    observability_score = rows_with_trace_id / total_ide_rows
    parentage_score     = rows_with_nonempty causal_parent_ids / total_audit_rows
    race_pressure         = duplicate id pressure in ~60s windows (0..1)
    """
    root = _base(state_dir)
    ide_path = root / "ide_stigmergic_trace.jsonl"
    obs_path = root / "stigmergic_observability.jsonl"

    ide_rows = _jsonl_tail(ide_path, ide_tail)
    obs_rows = _jsonl_tail(obs_path, obs_tail)

    n_ide = len(ide_rows)
    if n_ide == 0:
        obs_score = 0.0
    else:
        with_tid = sum(1 for r in ide_rows if str(r.get("trace_id", "")).strip())
        obs_score = with_tid / n_ide

    merged: List[Dict[str, Any]] = []
    for r in ide_rows:
        ts_ms = None
        if r.get("ts") is not None:
            try:
                ts_ms = int(float(r["ts"]) * 1000)
            except (TypeError, ValueError):
                pass
        meta = r.get("meta") if isinstance(r.get("meta"), dict) else {}
        parents = meta.get("causal_parent_ids") or r.get("causal_parent_ids") or []
        if isinstance(parents, str):
            parents = [parents] if parents else []
        merged.append(
            {
                "trace_id": r.get("trace_id"),
                "timestamp_ms": ts_ms,
                "homeworld_serial": r.get("homeworld_serial") or meta.get("node_serial"),
                "causal_parent_ids": list(parents) if isinstance(parents, list) else [],
                "source": "ide",
            }
        )
    for r in obs_rows:
        merged.append(
            {
                "observability_id": r.get("observability_id"),
                "trace_id": r.get("trace_row_id") or r.get("trace_id"),
                "timestamp_ms": int(r.get("timestamp_ms") or 0),
                "causal_parent_ids": list(r.get("causal_parent_ids") or []),
                "source": "obs",
            }
        )

    n_audit = len(merged)
    if n_audit == 0:
        parentage = 0.0
    else:
        with_parents = sum(
            1
            for r in merged
            if isinstance(r.get("causal_parent_ids"), list) and len(r["causal_parent_ids"]) > 0
        )
        parentage = with_parents / n_audit

    # Race pressure: duplicate observability_id or trace_id within 60s
    by_oid: Dict[str, List[int]] = {}
    by_tid: Dict[str, List[int]] = {}
    for r in merged:
        tms = r.get("timestamp_ms")
        if tms is None:
            continue
        try:
            tmi = int(tms)
        except (TypeError, ValueError):
            continue
        oid = r.get("observability_id")
        if oid:
            by_oid.setdefault(str(oid), []).append(tmi)
        tid = r.get("trace_id")
        if tid:
            by_tid.setdefault(str(tid), []).append(tmi)

    def _dup_pressure(groups: Dict[str, List[int]]) -> int:
        hits = 0
        for _k, times in groups.items():
            times = sorted(times)
            if len(times) < 2:
                continue
            for i in range(len(times) - 1):
                if times[i + 1] - times[i] <= 60_000:
                    hits += 1
                    break
        return hits

    dup_o = _dup_pressure(by_oid)
    dup_t = _dup_pressure(by_tid)
    denom = max(1, len(by_oid) + len(by_tid))
    race_pressure = min(1.0, (dup_o + dup_t) / denom)

    return {
        "truth_label": TRUTH_LABEL,
        "observability_score": round(obs_score, 4),
        "parentage_score": round(parentage, 4),
        "race_pressure": round(race_pressure, 4),
        "n_ide_rows": n_ide,
        "n_obs_rows": len(obs_rows),
        "n_merged_audit_rows": n_audit,
    }


def score_allostatic_ledger(*, state_dir: Optional[Path] = None) -> Dict[str, Any]:
    """allostatic_score = 1.0 - latest allostatic load (clamped)."""
    root = _base(state_dir)
    path = root / "allostatic_load.jsonl"
    load = 0.0
    policy = "UNKNOWN"
    tail = _jsonl_tail(path, 5) if path.exists() else []
    if tail:
        try:
            load = float(tail[-1].get("allostatic_load", 0.0))
        except (TypeError, ValueError):
            load = 0.0
        policy = str(tail[-1].get("policy", "UNKNOWN"))
    else:
        try:
            from System.swarm_allostatic_load import compute_allostatic_load

            row = compute_allostatic_load(state_dir=root)
            load = float(row.get("allostatic_load", 0.0))
            policy = str(row.get("policy", "UNKNOWN"))
        except Exception:
            pass
    load = max(0.0, min(1.0, load))
    return {
        "truth_label": TRUTH_LABEL,
        "allostatic_load": load,
        "policy": policy,
        "allostatic_score": round(1.0 - load, 4),
    }


def score_motor_policy_ledger(*, state_dir: Optional[Path] = None, tail: int = 50) -> Dict[str, Any]:
    """
    motor_score = fraction of recent motor_policy rows that reflect skill-weighted
    selection (truth_label or non-uniform bias mass).
    """
    root = _base(state_dir)
    path = root / "motor_policy.jsonl"
    rows = _jsonl_tail(path, tail)
    n = len(rows)
    if n == 0:
        return {"truth_label": TRUTH_LABEL, "motor_score": 0.0, "n_rows": 0}

    def _is_skill_biased(r: Dict[str, Any]) -> bool:
        if str(r.get("truth_label", "")).upper() == MOTOR_TRUTH:
            return True
        bias = r.get("bias")
        if not isinstance(bias, dict) or not bias:
            return False
        vals: List[float] = []
        for v in bias.values():
            try:
                vals.append(float(v))
            except (TypeError, ValueError):
                continue
        if len(vals) < 2:
            return False
        return (max(vals) - min(vals)) > 0.08

    biased = sum(1 for r in rows if _is_skill_biased(r))
    return {
        "truth_label": TRUTH_LABEL,
        "motor_score": round(biased / n, 4),
        "n_rows": n,
        "n_skill_biased_rows": biased,
    }


def test_score_numeric(test_section: Dict[str, Any]) -> float:
    """test_score = 1.0 if pytest gate PASS else 0.0"""
    return 1.0 if str(test_section.get("status", "")).upper() == "PASS" else 0.0


def bio_corpus_growth_score(bio_section: Dict[str, Any]) -> float:
    """Saturate at 50 claims → 1.0 (same spirit as nightly)."""
    try:
        n = int(bio_section.get("n_claims", 0))
    except (TypeError, ValueError):
        n = 0
    return min(1.0, n / 50.0)


def composite_nightly_score(
    *,
    ledger_obs: Dict[str, Any],
    ledger_allo: Dict[str, Any],
    ledger_motor: Dict[str, Any],
    test_section: Dict[str, Any],
    bio_section: Dict[str, Any],
) -> float:
    """
    Weighted composite from ledger-derived metrics (Event 107) + test + bio.
    """
    o = float(ledger_obs.get("observability_score", 0.0))
    p = float(ledger_obs.get("parentage_score", 0.0))
    rp = float(ledger_obs.get("race_pressure", 0.0))
    rp_term = max(0.0, 1.0 - rp)
    a = float(ledger_allo.get("allostatic_score", 0.5))
    m = float(ledger_motor.get("motor_score", 0.0))
    t = test_score_numeric(test_section)
    b = bio_corpus_growth_score(bio_section)
    raw = (
        0.18 * o
        + 0.12 * p
        + 0.15 * rp_term
        + 0.22 * a
        + 0.18 * m
        + 0.10 * t
        + 0.05 * b
    )
    return round(max(0.0, min(1.0, raw)), 4)


__all__ = [
    "MOTOR_TRUTH",
    "TRUTH_LABEL",
    "bio_corpus_growth_score",
    "composite_nightly_score",
    "score_allostatic_ledger",
    "score_motor_policy_ledger",
    "score_observability_ledgers",
    "test_score_numeric",
]
