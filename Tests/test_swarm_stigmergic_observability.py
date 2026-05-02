"""Event 104 — stigmergic observability / auditor organ."""

import json
import time
from pathlib import Path

from System import swarm_stigmergic_observability as obs


def test_generate_observability_id_stable_for_same_inputs() -> None:
    prov = {
        "writer": "CG55M",
        "homeworld_serial": "GTH4921YP3",
        "regime": "EXPLORATION",
        "tick_id": "t1",
        "causal_tags": ["hysteresis"],
    }
    a = obs.generate_observability_id(prov, timestamp_ms=1_700_000_000_000)
    b = obs.generate_observability_id(prov, timestamp_ms=1_700_000_000_000)
    assert a == b
    assert len(a) == 16


def test_deposit_and_query_window(tmp_path: Path) -> None:
    ts = int(time.time() * 1000)
    oid = obs.deposit_observation(
        {"action": "merge_attempt", "truth_label": "OBSERVED"},
        {
            "writer": "CG55M",
            "homeworld_serial": "GTH4921YP3",
            "regime": "EXPLORATION",
            "tick_id": "test_001",
            "causal_tags": ["hysteresis"],
            "causal_parent_ids": ["parent-trace-1"],
            "organ": "git",
            "intent": "merge",
        },
        state_dir=tmp_path,
        timestamp_ms=ts,
    )
    assert len(oid) == 16
    rows = obs.query_attribution(300_000, state_dir=tmp_path)
    assert rows
    assert rows[-1]["observability_id"] == oid
    assert rows[-1]["causal_parent_ids"] == ["parent-trace-1"]


def test_audit_trace_health_scores() -> None:
    rows = [
        {
            "timestamp_ms": 1000,
            "homeworld_serial": "GTH4921YP3",
            "regime": "EXPLORATION",
            "causal_parent_ids": ["a"],
            "organ": "motor_policy",
            "causal_tags": ["stale_skill"],
        },
        {
            "timestamp_ms": 2000,
            "homeworld_serial": "GTH4921YP3",
            "regime": "CONSOLIDATION",
            "causal_parent_ids": ["b"],
        },
    ]
    h = obs.audit_trace_health(rows)
    assert 0.0 <= h["trace_linkage"] <= 1.0
    assert h["identity_consistency"] == 1.0
    assert h["regime_flip_rate"] >= 0.0
    assert "attribution_confidence" in h


def test_write_health_snapshot(tmp_path: Path) -> None:
    h = obs.audit_trace_health([])
    out = obs.write_health_snapshot(h, state_dir=tmp_path)
    assert out["truth_label"] == "STIGMERGIC_HEALTH_SNAPSHOT"
    p = tmp_path / "stigmergic_health.jsonl"
    assert p.exists()
    line = p.read_text(encoding="utf-8").strip().splitlines()[-1]
    assert json.loads(line)["trace_linkage"] == 0.0
