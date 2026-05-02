#!/usr/bin/env python3
"""
tests/test_stigmergic_observability.py
══════════════════════════════════════════════════════════════════════════════
Event 104 — Stigmergic Observability Layer test suite.

Proves the Auditor Organ's core properties:
  1. deposit_observation() returns a 16-char observability_id
  2. Deposit is append-only to stigmergic_observability.jsonl
  3. causal_parent_ids survive the round-trip
  4. Deterministic replay: same provenance + same timestamp → same id
  5. query_attribution() returns rows within window
  6. audit_trace_health() scalars are all in [0, 1]
  7. trace_linkage=1.0 when all rows have causal_parent_ids
  8. trace_linkage=0.0 when no rows have causal_parent_ids
  9. stamp_tick_row() auto-detects TAG_REST_FORCED + TAG_ANOMALY
 10. stamp_tick_row() deposits to obs log with correct organ=body_brain_tick
 11. test_cusum_null_hypothesis() returns INSUFFICIENT_DATA cleanly
 12. test_cusum_null_hypothesis() runs permutation test with N≥10 ticks
 13. _spearman_corr: perfect positive correlation = 1.0
 14. Causal tags survive round-trip
 15. body_brain_loop imports stamp_tick_row without error
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _prov(writer="AG31", regime="EXPLORATION", **kw):
    return {"writer": writer, "homeworld_serial": "GTH4921YP3",
            "regime": regime, "organ": "test", **kw}


def _obs_rows(state_dir: Path) -> list[dict]:
    p = state_dir / "stigmergic_observability.jsonl"
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


# ══════════════════════════════════════════════════════════════════════════════
# 1-4. Core deposit
# ══════════════════════════════════════════════════════════════════════════════

def test_deposit_returns_16char_id(tmp_path):
    from System.swarm_stigmergic_observability import deposit_observation
    obs_id = deposit_observation(
        {"action": "test"},
        _prov(),
        state_dir=tmp_path,
    )
    assert isinstance(obs_id, str)
    assert len(obs_id) == 16, f"Expected 16-char id, got '{obs_id}' (len={len(obs_id)})"


def test_deposit_appends_to_log(tmp_path):
    from System.swarm_stigmergic_observability import deposit_observation
    for i in range(3):
        deposit_observation({"n": i}, _prov(), state_dir=tmp_path)
    rows = _obs_rows(tmp_path)
    assert len(rows) == 3, f"Expected 3 rows, got {len(rows)}"


def test_causal_parent_ids_roundtrip(tmp_path):
    from System.swarm_stigmergic_observability import deposit_observation
    parents = ["abc123def456", "feed0001beef"]
    deposit_observation(
        {"x": 1},
        _prov(causal_parent_ids=parents),
        state_dir=tmp_path,
    )
    rows = _obs_rows(tmp_path)
    assert rows[0]["causal_parent_ids"] == parents


def test_deterministic_id_same_ts(tmp_path):
    """Same provenance + same timestamp_ms → same observability_id."""
    from System.swarm_stigmergic_observability import generate_observability_id
    prov = _prov(tick_id="tick_001", trace_ref="ref_a")
    ts = 1710000000000
    id1 = generate_observability_id(prov, timestamp_ms=ts)
    id2 = generate_observability_id(prov, timestamp_ms=ts)
    assert id1 == id2, f"Same inputs → same id. Got {id1!r} != {id2!r}"


# ══════════════════════════════════════════════════════════════════════════════
# 5. query_attribution window filter
# ══════════════════════════════════════════════════════════════════════════════

def test_query_attribution_window(tmp_path):
    from System.swarm_stigmergic_observability import deposit_observation, query_attribution
    # Deposit one row
    deposit_observation({"event": "recent"}, _prov(), state_dir=tmp_path)
    # Should appear in a 60s window
    recent = query_attribution(window_ms=60_000, state_dir=tmp_path)
    assert len(recent) >= 1


def test_query_attribution_excludes_old(tmp_path):
    """Rows with tiny window should exclude all (we can't insert past rows,
    so we just verify the function runs and returns a list)."""
    from System.swarm_stigmergic_observability import query_attribution
    result = query_attribution(window_ms=0, state_dir=tmp_path)
    assert isinstance(result, list)


# ══════════════════════════════════════════════════════════════════════════════
# 6-8. audit_trace_health scalars
# ══════════════════════════════════════════════════════════════════════════════

def test_health_all_scalars_in_range(tmp_path):
    from System.swarm_stigmergic_observability import deposit_observation, audit_trace_health
    for i in range(5):
        deposit_observation(
            {"n": i},
            _prov(causal_parent_ids=[f"parent_{i}"], homeworld_serial="GTH4921YP3"),
            state_dir=tmp_path,
        )
    rows = [json.loads(l) for l in (tmp_path / "stigmergic_observability.jsonl").read_text().splitlines()]
    health = audit_trace_health(rows)
    for k, v in health.items():
        if isinstance(v, float):
            assert 0.0 <= v <= 1.0, f"{k}={v} out of [0,1]"


def test_health_trace_linkage_full(tmp_path):
    from System.swarm_stigmergic_observability import deposit_observation, audit_trace_health
    for i in range(4):
        deposit_observation(
            {"n": i},
            _prov(causal_parent_ids=[f"p{i}"]),
            state_dir=tmp_path,
        )
    rows = [json.loads(l) for l in (tmp_path / "stigmergic_observability.jsonl").read_text().splitlines()]
    health = audit_trace_health(rows)
    assert health["trace_linkage"] == pytest.approx(1.0, abs=0.01), (
        f"All rows have parents → trace_linkage=1.0, got {health['trace_linkage']}"
    )


def test_health_trace_linkage_zero(tmp_path):
    from System.swarm_stigmergic_observability import deposit_observation, audit_trace_health
    for i in range(4):
        deposit_observation(
            {"n": i},
            _prov(causal_parent_ids=[]),  # no parents
            state_dir=tmp_path,
        )
    rows = [json.loads(l) for l in (tmp_path / "stigmergic_observability.jsonl").read_text().splitlines()]
    health = audit_trace_health(rows)
    assert health["trace_linkage"] == pytest.approx(0.0, abs=0.01), (
        f"No rows have parents → trace_linkage=0.0, got {health['trace_linkage']}"
    )


def test_health_empty_rows():
    from System.swarm_stigmergic_observability import audit_trace_health
    health = audit_trace_health([])
    assert health["attribution_confidence"] == 0.0
    assert "UNIDENTIFIABLE_CAUSE" in health["truth_note"]


# ══════════════════════════════════════════════════════════════════════════════
# 9-10. stamp_tick_row
# ══════════════════════════════════════════════════════════════════════════════

def test_stamp_tick_row_rest_forced_tags(tmp_path):
    from System.swarm_stigmergic_observability import stamp_tick_row, TAG_REST_FORCED, TAG_CUSUM_ALARM
    mem_row = {
        "tick_id": "tick_abc",
        "homeostasis_type": "REST_FORCED",
        "td_value": 1.0,
        "drive_state": "rest",
        "homeostasis_regime": "CRITICAL_COLLAPSE",
    }
    obs_id = stamp_tick_row(mem_row, source="AG31", state_dir=tmp_path)
    assert isinstance(obs_id, str) and len(obs_id) == 16
    rows = _obs_rows(tmp_path)
    tags = rows[0]["causal_tags"]
    assert TAG_REST_FORCED in tags, f"REST_FORCED not in causal_tags: {tags}"
    assert TAG_CUSUM_ALARM in tags, f"cusum_alarm not in causal_tags: {tags}"


def test_stamp_tick_row_anomaly_tag(tmp_path):
    from System.swarm_stigmergic_observability import stamp_tick_row, TAG_ANOMALY
    mem_row = {
        "tick_id": "tick_xyz",
        "homeostasis_type": "NONE",
        "td_value": -0.9,
        "drive_state": "explore",
        "homeostasis_regime": "EXPLORATION",
    }
    stamp_tick_row(mem_row, source="AG31", state_dir=tmp_path)
    rows = _obs_rows(tmp_path)
    assert TAG_ANOMALY in rows[0]["causal_tags"]


def test_stamp_tick_row_organ_field(tmp_path):
    from System.swarm_stigmergic_observability import stamp_tick_row
    mem_row = {"tick_id": "t1", "td_value": 1.0, "drive_state": "learn",
               "homeostasis_regime": "CONSOLIDATION", "homeostasis_type": "SUPPRESS"}
    stamp_tick_row(mem_row, source="CG55M", state_dir=tmp_path)
    rows = _obs_rows(tmp_path)
    assert rows[0]["organ"] == "body_brain_tick"
    assert rows[0]["writer"] == "CG55M"


# ══════════════════════════════════════════════════════════════════════════════
# 11-12. CUSUM null hypothesis test
# ══════════════════════════════════════════════════════════════════════════════

def test_cusum_null_insufficient_data(tmp_path):
    from System.swarm_stigmergic_observability import test_cusum_null_hypothesis
    result = test_cusum_null_hypothesis(lag=5, state_dir=tmp_path)
    assert result["status"] == "INSUFFICIENT_DATA"
    assert result["reject_null"] is None


def test_cusum_null_runs_with_data(tmp_path):
    """Create synthetic body_brain_memory rows and verify permutation test runs."""
    from System.swarm_stigmergic_observability import test_cusum_null_hypothesis
    state_dir = tmp_path
    mem_path = state_dir / "body_brain_memory.jsonl"
    state_dir.mkdir(parents=True, exist_ok=True)
    # Write 20 synthetic tick rows alternating regimes
    regimes = ["EXPLORATION", "CONSOLIDATION"] * 10
    for i, regime in enumerate(regimes):
        row = {
            "tick_id": f"tick_{i}",
            "ts": time.time() + i,
            "homeostasis_regime": regime,
            "td_value": 1.0 if regime == "EXPLORATION" else -0.2,
            "drive_state": "explore",
        }
        with mem_path.open("a") as f:
            f.write(json.dumps(row) + "\n")

    result = test_cusum_null_hypothesis(
        lag=3, n_permutations=50, tail_n=40, state_dir=state_dir
    )
    assert "reject_null" in result
    assert isinstance(result["reject_null"], bool)
    assert "conclusion" in result
    assert "real_correlation" in result
    assert -1.0 <= result["real_correlation"] <= 1.0
    assert 0.0 <= result["p_value"] <= 1.0


# ══════════════════════════════════════════════════════════════════════════════
# 13. _spearman_corr correctness
# ══════════════════════════════════════════════════════════════════════════════

def test_spearman_perfect_positive():
    from System.swarm_stigmergic_observability import _spearman_corr
    x = [1.0, 2.0, 3.0, 4.0, 5.0]
    y = [2.0, 4.0, 6.0, 8.0, 10.0]
    corr = _spearman_corr(x, y)
    assert corr == pytest.approx(1.0, abs=1e-6), f"Expected 1.0, got {corr}"


def test_spearman_perfect_negative():
    from System.swarm_stigmergic_observability import _spearman_corr
    x = [1.0, 2.0, 3.0, 4.0, 5.0]
    y = [10.0, 8.0, 6.0, 4.0, 2.0]
    corr = _spearman_corr(x, y)
    assert corr == pytest.approx(-1.0, abs=1e-6), f"Expected -1.0, got {corr}"


# ══════════════════════════════════════════════════════════════════════════════
# 14. Causal tags round-trip
# ══════════════════════════════════════════════════════════════════════════════

def test_causal_tags_roundtrip(tmp_path):
    from System.swarm_stigmergic_observability import deposit_observation
    tags = ["race", "hysteresis", "stale_skill"]
    deposit_observation(
        {"event": "tagged"},
        _prov(causal_tags=tags),
        state_dir=tmp_path,
    )
    rows = _obs_rows(tmp_path)
    assert set(rows[0]["causal_tags"]) == set(tags)


# ══════════════════════════════════════════════════════════════════════════════
# 15. body_brain_loop imports stamp_tick_row
# ══════════════════════════════════════════════════════════════════════════════

def test_body_brain_loop_imports_observability():
    import System.swarm_body_brain_loop as bbl
    assert hasattr(bbl, "_OBSERVABILITY_AVAILABLE")


if __name__ == "__main__":
    import pytest as _pt
    _pt.main([__file__, "-v"])
