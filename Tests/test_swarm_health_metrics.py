"""Event 107 — ledger-derived health metrics."""

import json
from pathlib import Path

from System import swarm_health_metrics as hm


def test_observability_and_parentage_from_ide_and_obs(tmp_path: Path) -> None:
    ide = tmp_path / "ide_stigmergic_trace.jsonl"
    ide.write_text(
        json.dumps({"trace_id": "a", "ts": 1000.0, "meta": {}}) + "\n"
        + json.dumps({"trace_id": "", "ts": 1001.0}) + "\n",
        encoding="utf-8",
    )
    obs = tmp_path / "stigmergic_observability.jsonl"
    obs.write_text(
        json.dumps(
            {
                "timestamp_ms": 1_000_000,
                "observability_id": "oid1",
                "causal_parent_ids": ["x"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    r = hm.score_observability_ledgers(state_dir=tmp_path, ide_tail=50, obs_tail=50)
    assert r["n_ide_rows"] == 2
    assert r["observability_score"] == 0.5
    assert r["parentage_score"] > 0.0


def test_allostatic_score_prefers_ledger_tail(tmp_path: Path) -> None:
    p = tmp_path / "allostatic_load.jsonl"
    p.write_text(
        json.dumps({"allostatic_load": 0.2, "policy": "ALLOW_GROWTH"}) + "\n"
        + json.dumps({"allostatic_load": 0.4, "policy": "ALLOW_GROWTH"}) + "\n",
        encoding="utf-8",
    )
    r = hm.score_allostatic_ledger(state_dir=tmp_path)
    assert r["allostatic_load"] == 0.4
    assert r["allostatic_score"] == 0.6


def test_motor_skill_bias_ratio(tmp_path: Path) -> None:
    p = tmp_path / "motor_policy.jsonl"
    rows = [
        {"truth_label": "SKILL_WEIGHTED_POLICY", "bias": {"explore": 0.9, "forage": 0.1}},
        {"truth_label": "OTHER", "bias": {"explore": 0.51, "forage": 0.49}},
    ]
    p.write_text("\n".join(json.dumps(x) for x in rows) + "\n", encoding="utf-8")
    r = hm.score_motor_policy_ledger(state_dir=tmp_path, tail=10)
    assert r["motor_score"] == 0.5


def test_composite_nightly_score_weights(tmp_path: Path) -> None:
    lo = {"observability_score": 1.0, "parentage_score": 1.0, "race_pressure": 0.0}
    la = {"allostatic_score": 1.0}
    lm = {"motor_score": 1.0}
    tests = {"status": "PASS"}
    bio = {"n_claims": 50}
    c = hm.composite_nightly_score(
        ledger_obs=lo,
        ledger_allo=la,
        ledger_motor=lm,
        test_section=tests,
        bio_section=bio,
    )
    assert 0.0 < c <= 1.0
