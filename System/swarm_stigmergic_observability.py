#!/usr/bin/env python3
"""
System/swarm_stigmergic_observability.py
══════════════════════════════════════════════════════════════════════════════
Event 104 — Stigmergic Observability Layer (minimal auditor organ)

Doctrine (Bishop / Swarm):
  Stigmergy is not observable just because traces exist. Deposits need enough
  parentage to falsify causal stories without a central clock or hand-built DAG.

  Encouraged: `causal_parent_ids` (trace / obs ids this row depended on),
  `organ`, `intent`, `homeworld_serial`, `regime`, `output_hash` / `payload_hash`.
  Discouraged: free-form "reason" as the *only* causal claim (no parents).

Truth labels on rows: default `OBSERVED`; callers may set `truth_label`.

This module writes `.sifta_state/stigmergic_observability.jsonl` (append-only,
locked) and can emit `.sifta_state/stigmergic_health.jsonl` snapshots from
`audit_trace_health`.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from System.jsonl_file_lock import append_line_locked, read_text_locked

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
OBS_LOG_NAME = "stigmergic_observability.jsonl"
HEALTH_LOG_NAME = "stigmergic_health.jsonl"

SCHEMA_VERSION = "stigmergic_observability.event104.v1"

# ── Causal tag vocabulary (canonical strings) ────────────────────────────────
TAG_RACE         = "race"          # concurrent write within 1s window
TAG_HYSTERESIS   = "hysteresis"   # regime flip in last 5 ticks
TAG_STALE_SKILL  = "stale_skill"  # motor policy cited skill > 300s old
TAG_CUSUM_ALARM  = "cusum_alarm"  # CUSUM alarm active at write time
TAG_ANOMALY      = "anomaly"      # td_value < -0.5
TAG_REST_FORCED  = "rest_forced"  # homeostatic stabilizer forced rest


def _paths(state_dir: Optional[Path] = None) -> tuple[Path, Path]:
    base = Path(state_dir) if state_dir is not None else _STATE_DIR
    return base / OBS_LOG_NAME, base / HEALTH_LOG_NAME


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def generate_observability_id(
    provenance: Dict[str, Any],
    *,
    timestamp_ms: Optional[int] = None,
) -> str:
    """
    Short forge-resistant id from writer context + time bucket.
    Same provenance + same timestamp_ms → same id (replay detector).
    """
    ts = int(timestamp_ms if timestamp_ms is not None else time.time() * 1000)
    ctx = {
        "writer": str(provenance.get("writer", "unknown")),
        "homeworld_serial": provenance.get("homeworld_serial"),
        "regime": provenance.get("regime"),
        "tick_id": provenance.get("tick_id"),
        "trace_ref": provenance.get("trace_ref"),
        "causal_parent_ids": sorted(
            str(x) for x in (provenance.get("causal_parent_ids") or []) if x
        ),
        "causal_tags": sorted(str(t) for t in (provenance.get("causal_tags") or []) if t),
        "organ": provenance.get("organ"),
        "intent": (str(provenance.get("intent", ""))[:512] or None),
        "timestamp_ms": ts,
    }
    payload = _canonical_json(ctx)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def deposit_observation(
    entry: Dict[str, Any],
    provenance: Dict[str, Any],
    *,
    state_dir: Optional[Path] = None,
    timestamp_ms: Optional[int] = None,
) -> str:
    """Append one observability row; returns observability_id."""
    obs_path, _ = _paths(state_dir)
    ts = int(timestamp_ms if timestamp_ms is not None else time.time() * 1000)
    obs_id = generate_observability_id(provenance, timestamp_ms=ts)
    payload_for_hash = {k: v for k, v in entry.items() if k not in ("truth_label",)}
    payload_hash = hashlib.sha256(_canonical_json(payload_for_hash).encode()).hexdigest()[:12]

    parents = provenance.get("causal_parent_ids")
    if parents is None:
        parent_list: List[str] = []
    elif isinstance(parents, str):
        parent_list = [parents] if parents else []
    else:
        parent_list = [str(x) for x in parents if x]

    record: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "trace_row_id": str(provenance.get("trace_row_id") or uuid.uuid4()),
        "observability_id": obs_id,
        "timestamp_ms": ts,
        "truth_label": str(entry.get("truth_label") or provenance.get("truth_label") or "OBSERVED"),
        "writer": provenance.get("writer"),
        "homeworld_serial": provenance.get("homeworld_serial"),
        "regime": provenance.get("regime"),
        "organ": provenance.get("organ"),
        "intent": provenance.get("intent"),
        "trace_ref": provenance.get("trace_ref"),
        "causal_parent_ids": parent_list,
        "causal_tags": list(provenance.get("causal_tags") or []),
        "payload_hash": payload_hash,
    }
    # Entry payload (action, merge metadata, etc.) — do not clobber reserved keys
    reserved = set(record.keys())
    for k, v in entry.items():
        if k not in reserved:
            record[k] = v

    obs_path.parent.mkdir(parents=True, exist_ok=True)
    append_line_locked(obs_path, _canonical_json(record) + "\n", encoding="utf-8")
    return obs_id


def query_attribution(
    window_ms: int = 300_000,
    *,
    state_dir: Optional[Path] = None,
    max_scan_lines: int = 12_000,
) -> List[Dict[str, Any]]:
    """Return recent observability rows in the time window (newest-heavy tail read)."""
    obs_path, _ = _paths(state_dir)
    if not obs_path.exists():
        return []
    cutoff = int(time.time() * 1000) - int(window_ms)
    try:
        body = read_text_locked(obs_path, encoding="utf-8", errors="replace")
    except OSError:
        return []
    lines = body.splitlines()[-max_scan_lines:]
    out: List[Dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if int(rec.get("timestamp_ms") or 0) >= cutoff:
            out.append(rec)
    return out


def audit_trace_health(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Scalar bundle for nightly job / pytest.
    Rows may be ide traces, observability rows, or a merged tail — keys best-effort.
    """
    rows_list = list(rows)
    n = len(rows_list)
    if n == 0:
        return {
            "trace_linkage": 0.0,
            "identity_consistency": 0.0,
            "regime_flip_rate": 0.0,
            "stale_skill_pressure": 0.0,
            "race_pressure": 0.0,
            "attribution_confidence": 0.0,
            "truth_note": "UNIDENTIFIABLE_CAUSE_EMPTY_WINDOW",
        }

    def _has_parents(r: Dict[str, Any]) -> bool:
        p = r.get("causal_parent_ids")
        if isinstance(p, list) and len(p) > 0:
            return True
        return isinstance(p, str) and bool(p.strip())

    def _serial(r: Dict[str, Any]) -> bool:
        s = r.get("homeworld_serial") or r.get("node_serial")
        return isinstance(s, str) and len(s) >= 8

    linkage = sum(1 for r in rows_list if _has_parents(r)) / n
    identity = sum(1 for r in rows_list if _serial(r)) / n

    # Regime flip rate: sort by timestamp_ms or ts
    keyed: List[tuple[float, str]] = []
    for r in rows_list:
        tms = r.get("timestamp_ms")
        if tms is not None:
            t = float(tms) / 1000.0
        else:
            t = float(r.get("ts") or 0.0)
        reg = str(r.get("regime") or r.get("homeostasis_regime") or "")
        keyed.append((t, reg))
    keyed.sort(key=lambda x: x[0])
    flips = 0
    prev = None
    for _t, reg in keyed:
        if reg and prev is not None and reg != prev:
            flips += 1
        if reg:
            prev = reg
    denom = max(1, len([x for x in keyed if x[1]]) - 1)
    regime_flip_rate = flips / denom

    motorish = [r for r in rows_list if str(r.get("organ", "")).lower() in ("motor_policy", "motor")]
    stale = 0
    for r in motorish:
        tags = r.get("causal_tags") or []
        if isinstance(tags, list) and any("stale_skill" in str(t).lower() for t in tags):
            stale += 1
    stale_skill_pressure = stale / max(1, len(motorish))

    # Duplicate observability_id within ~60s → race pressure proxy
    by_id: Dict[str, List[int]] = {}
    for r in rows_list:
        oid = r.get("observability_id")
        if not oid:
            continue
        tms = int(r.get("timestamp_ms") or 0)
        by_id.setdefault(str(oid), []).append(tms)
    dup_windows = 0
    for _oid, times in by_id.items():
        times.sort()
        if len(times) < 2:
            continue
        for i in range(len(times) - 1):
            if times[i + 1] - times[i] <= 60_000:
                dup_windows += 1
                break
    race_pressure = dup_windows / max(1, len(by_id)) if by_id else 0.0

    confidence = max(
        0.0,
        min(
            1.0,
            0.45 * linkage + 0.35 * identity - 0.35 * regime_flip_rate - 0.25 * race_pressure - 0.15 * stale_skill_pressure,
        ),
    )

    note = "OK"
    if linkage < 0.05 and identity < 0.5:
        note = "UNIDENTIFIABLE_CAUSE_LOW_SIGNAL"

    return {
        "trace_linkage": round(linkage, 4),
        "identity_consistency": round(identity, 4),
        "regime_flip_rate": round(regime_flip_rate, 4),
        "stale_skill_pressure": round(stale_skill_pressure, 4),
        "race_pressure": round(race_pressure, 4),
        "attribution_confidence": round(confidence, 4),
        "truth_note": note,
        "window_rows": n,
    }


def write_health_snapshot(
    health: Dict[str, Any],
    *,
    state_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Append one health row to stigmergic_health.jsonl."""
    _, health_path = _paths(state_dir)
    row = {"ts": time.time(), "truth_label": "STIGMERGIC_HEALTH_SNAPSHOT", **health}
    health_path.parent.mkdir(parents=True, exist_ok=True)
    append_line_locked(health_path, _canonical_json(row) + "\n", encoding="utf-8")
    return row


# ── Convenience: stamp a body_brain_tick row ─────────────────────────────────

def stamp_tick_row(
    mem_row: Dict[str, Any],
    *,
    source: str = "AG31",
    homeworld_serial: Optional[str] = None,
    causal_parent_ids: Optional[List[str]] = None,
    state_dir: Optional[Path] = None,
) -> str:
    """
    Deposit an Event 104 observation for one body_brain_tick row.
    Returns the new observability_id for use as a causal_parent_id
    in downstream records (motor_policy rows, health snapshots).

    Auto-detects causal tags:
      TAG_REST_FORCED  — if homeostasis_type == REST_FORCED
      TAG_CUSUM_ALARM  — if homeostasis_type in (REST_FORCED, REDIRECT) under cusum
      TAG_ANOMALY      — if td_value < -0.5
    """
    auto_tags: List[str] = []
    h_type = str(mem_row.get("homeostasis_type") or "")
    if h_type == "REST_FORCED":
        auto_tags.append(TAG_REST_FORCED)
        auto_tags.append(TAG_CUSUM_ALARM)
    td = float(mem_row.get("td_value") or mem_row.get("value") or 0.0)
    if td < -0.5:
        auto_tags.append(TAG_ANOMALY)

    entry: Dict[str, Any] = {
        "tick_id":           mem_row.get("tick_id"),
        "td_value":          td,
        "drive_state":       mem_row.get("drive_state"),
        "metabolic_mode":    mem_row.get("metabolic_mode"),
        "homeostasis_type":  h_type or None,
        "allostatic_policy": mem_row.get("allostatic_policy"),
        "action_type":       (mem_row.get("action") or {}).get("type"),
    }

    provenance: Dict[str, Any] = {
        "writer":            source,
        "homeworld_serial":  homeworld_serial,
        "regime":            mem_row.get("homeostasis_regime"),
        "organ":             "body_brain_tick",
        "intent":            "record_physiology_tick",
        "tick_id":           mem_row.get("tick_id"),
        "causal_parent_ids": causal_parent_ids or [],
        "causal_tags":       auto_tags,
        "truth_label":       "STIGMERGIC_OBSERVATION_EVENT_104",
    }

    return deposit_observation(entry, provenance, state_dir=state_dir)


# ── CUSUM null hypothesis permutation test ────────────────────────────────

def _read_body_memory(n: int = 200, state_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    path = (Path(state_dir) if state_dir else _STATE_DIR) / "body_brain_memory.jsonl"
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        for line in path.read_text("utf-8", errors="replace").splitlines()[-n:]:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except Exception:
                    pass
    except Exception:
        pass
    return rows


def _regime_to_int(regime: str) -> int:
    return {"EXPLORATION": 0, "CONSOLIDATION": 1, "CRITICAL_COLLAPSE": 2}.get(
        str(regime), 0
    )


def _spearman_corr(x: List[float], y: List[float]) -> float:
    """Spearman rank correlation between x and y (equal length, n >= 2)."""
    import math
    n = len(x)
    if n < 2:
        return 0.0

    def _rank(v: List[float]) -> List[float]:
        order = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        for rank, idx in enumerate(order):
            r[idx] = float(rank + 1)
        return r

    rx, ry = _rank(x), _rank(y)
    mx = sum(rx) / n
    my = sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    den = math.sqrt(
        sum((rx[i] - mx) ** 2 for i in range(n))
        * sum((ry[i] - my) ** 2 for i in range(n))
    )
    return num / den if den > 1e-9 else 0.0


def test_cusum_null_hypothesis(
    *,
    n_permutations: int = 200,
    lag: int = 5,
    alpha: float = 0.05,
    tail_n: int = 200,
    state_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Permutation test of the CUSUM null hypothesis.

    H₀: CUSUM regime labels carry no predictive information about
        future TD values (next `lag` ticks ahead).

    Method:
      1. Spearman correlation between regime_int[t] and td_value[t+lag].
      2. Permute regime labels `n_permutations` times; recompute each time.
      3. p_value = fraction of permuted |corr| ≥ |real corr|.

    FDR note: single-test context — raw p_value equals BH-corrected p.

    Returns dict stamped to stigmergic_health.jsonl.
    """
    import random
    tick_rows = _read_body_memory(tail_n, state_dir)

    if len(tick_rows) < lag + 5:
        return {
            "truth_label": "STIGMERGIC_HEALTH_REPORT",
            "test":        "cusum_null",
            "status":      "INSUFFICIENT_DATA",
            "n_ticks":     len(tick_rows),
            "min_required": lag + 5,
            "reject_null": None,
            "conclusion":  "Not enough ticks to evaluate null hypothesis.",
        }

    regimes = [
        str(r.get("homeostasis_regime") or r.get("regime") or "EXPLORATION")
        for r in tick_rows
    ]
    td_vals = [
        float(r.get("td_value") or r.get("value") or 0.0)
        for r in tick_rows
    ]

    x_real = [float(_regime_to_int(regimes[i])) for i in range(len(regimes) - lag)]
    y_real = td_vals[lag:]
    real_corr = _spearman_corr(x_real, y_real)

    perm_corrs: List[float] = []
    for _ in range(n_permutations):
        shuffled = regimes[:]
        random.shuffle(shuffled)
        x_perm = [float(_regime_to_int(shuffled[i])) for i in range(len(shuffled) - lag)]
        perm_corrs.append(_spearman_corr(x_perm, y_real))

    p_value = sum(1 for c in perm_corrs if abs(c) >= abs(real_corr)) / n_permutations
    reject_null = p_value < alpha

    result: Dict[str, Any] = {
        "truth_label":       "STIGMERGIC_HEALTH_REPORT",
        "test":              "cusum_null",
        "ts":                time.time(),
        "n_ticks":           len(tick_rows),
        "lag":               lag,
        "n_permutations":    n_permutations,
        "real_correlation":  round(real_corr, 5),
        "p_value":           round(p_value, 4),
        "alpha":             alpha,
        "reject_null":       reject_null,
        "conclusion": (
            f"REJECT H₀ (p={p_value:.3f}<{alpha}): "
            f"Regime predicts TD[t+{lag}] (r={real_corr:.3f})."
            if reject_null else
            f"FAIL TO REJECT H₀ (p={p_value:.3f}≥{alpha}): "
            f"No reliable regime→TD signal (r={real_corr:.3f}). "
            "CUSUM may need more ticks."
        ),
    }

    try:
        _, health_path = _paths(state_dir)
        health_path.parent.mkdir(parents=True, exist_ok=True)
        append_line_locked(health_path, _canonical_json(result) + "\n", encoding="utf-8")
    except Exception:
        pass

    return result


__all__ = [
    "SCHEMA_VERSION",
    "TAG_RACE", "TAG_HYSTERESIS", "TAG_STALE_SKILL",
    "TAG_CUSUM_ALARM", "TAG_ANOMALY", "TAG_REST_FORCED",
    "audit_trace_health",
    "deposit_observation",
    "generate_observability_id",
    "query_attribution",
    "stamp_tick_row",
    "test_cusum_null_hypothesis",
    "write_health_snapshot",
]
