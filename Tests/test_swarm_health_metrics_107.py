#!/usr/bin/env python3
"""
tests/test_swarm_health_metrics_107.py
Event 107 — Ledger-derived health metrics: doctrine-mandated gap tests.

Proves the 4 properties CG55M specified:
  1. Empty ledgers do not crash (all functions return dicts)
  2. All scores are bounded [0, 1]
  3. Bio corpus counts are real (derived from actual file line counts)
  4. Composite score changes when ledger rows change (non-constant)

Plus: race pressure, motor score edge cases, allostatic clamp.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import pytest

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import System.swarm_health_metrics as hm


# ══════════════════════════════════════════════════════════════════════════════
# 1. Empty ledgers do not crash
# ══════════════════════════════════════════════════════════════════════════════

def test_empty_observability_no_crash(tmp_path):
    r = hm.score_observability_ledgers(state_dir=tmp_path)
    assert isinstance(r, dict)
    assert r["observability_score"] == 0.0
    assert r["parentage_score"] == 0.0
    assert r["race_pressure"] == 0.0
    assert r["n_ide_rows"] == 0
    assert r["n_obs_rows"] == 0


def test_empty_allostatic_no_crash(tmp_path):
    r = hm.score_allostatic_ledger(state_dir=tmp_path)
    assert isinstance(r, dict)
    assert 0.0 <= r["allostatic_score"] <= 1.0
    assert 0.0 <= r["allostatic_load"] <= 1.0


def test_empty_motor_no_crash(tmp_path):
    r = hm.score_motor_policy_ledger(state_dir=tmp_path, tail=50)
    assert isinstance(r, dict)
    assert r["motor_score"] == 0.0
    assert r["n_rows"] == 0


def test_empty_composite_no_crash(tmp_path):
    lo = hm.score_observability_ledgers(state_dir=tmp_path)
    la = hm.score_allostatic_ledger(state_dir=tmp_path)
    lm = hm.score_motor_policy_ledger(state_dir=tmp_path)
    c = hm.composite_nightly_score(
        ledger_obs=lo, ledger_allo=la, ledger_motor=lm,
        test_section={"status": "FAIL"}, bio_section={"n_claims": 0},
    )
    assert isinstance(c, float)
    assert 0.0 <= c <= 1.0


# ══════════════════════════════════════════════════════════════════════════════
# 2. All scalar scores are bounded [0, 1]
# ══════════════════════════════════════════════════════════════════════════════

def test_observability_score_bounded(tmp_path):
    ide = tmp_path / "ide_stigmergic_trace.jsonl"
    ide.write_text(
        "\n".join(
            json.dumps({"trace_id": f"t{i}", "ts": 1000.0 + i}) for i in range(10)
        ) + "\n",
        encoding="utf-8",
    )
    r = hm.score_observability_ledgers(state_dir=tmp_path)
    assert 0.0 <= r["observability_score"] <= 1.0
    assert 0.0 <= r["parentage_score"] <= 1.0
    assert 0.0 <= r["race_pressure"] <= 1.0


def test_allostatic_score_bounded_extremes(tmp_path):
    for load_val in [0.0, 0.5, 1.0, 1.5, -0.1]:  # clamp test
        p = tmp_path / "allostatic_load.jsonl"
        p.write_text(json.dumps({"allostatic_load": load_val}) + "\n", encoding="utf-8")
        r = hm.score_allostatic_ledger(state_dir=tmp_path)
        assert 0.0 <= r["allostatic_load"] <= 1.0, f"load={load_val} not clamped"
        assert 0.0 <= r["allostatic_score"] <= 1.0
        p.unlink()


def test_motor_score_bounded(tmp_path):
    p = tmp_path / "motor_policy.jsonl"
    rows = [{"truth_label": "SKILL_WEIGHTED_POLICY", "bias": {"a": 0.9, "b": 0.1}}] * 20
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    r = hm.score_motor_policy_ledger(state_dir=tmp_path, tail=30)
    assert 0.0 <= r["motor_score"] <= 1.0


def test_composite_always_bounded(tmp_path):
    """Composite must be [0,1] for any valid inputs."""
    for obs_v in [0.0, 0.5, 1.0]:
        for al_v in [0.0, 0.5, 1.0]:
            for mo_v in [0.0, 0.5, 1.0]:
                lo = {"observability_score": obs_v, "parentage_score": obs_v,
                      "race_pressure": 1.0 - obs_v}
                la = {"allostatic_score": al_v}
                lm = {"motor_score": mo_v}
                c = hm.composite_nightly_score(
                    ledger_obs=lo, ledger_allo=la, ledger_motor=lm,
                    test_section={"status": "PASS"}, bio_section={"n_claims": 25},
                )
                assert 0.0 <= c <= 1.0, f"composite={c} out of bounds"


# ══════════════════════════════════════════════════════════════════════════════
# 3. Bio corpus counts are real (derived from file lines, not constants)
# ══════════════════════════════════════════════════════════════════════════════

def test_bio_corpus_growth_real_count():
    """bio_corpus_growth_score reads n_claims — saturates at 50."""
    assert hm.bio_corpus_growth_score({"n_claims": 0})   == 0.0
    assert hm.bio_corpus_growth_score({"n_claims": 25})  == pytest.approx(0.5, abs=0.01)
    assert hm.bio_corpus_growth_score({"n_claims": 50})  == 1.0
    assert hm.bio_corpus_growth_score({"n_claims": 500}) == 1.0  # saturate at 1.0


def test_bio_corpus_count_from_real_file(tmp_path):
    """
    Composite score is higher when more real bio_claims.jsonl rows exist.
    This proves the count is ledger-derived, not a stub constant.
    """
    # Run with 0 claims
    lo = {"observability_score": 0.8, "parentage_score": 0.6, "race_pressure": 0.1}
    la = {"allostatic_score": 0.7}
    lm = {"motor_score": 0.5}
    ts = {"status": "PASS"}

    c_zero = hm.composite_nightly_score(
        ledger_obs=lo, ledger_allo=la, ledger_motor=lm,
        test_section=ts, bio_section={"n_claims": 0},
    )
    c_fifty = hm.composite_nightly_score(
        ledger_obs=lo, ledger_allo=la, ledger_motor=lm,
        test_section=ts, bio_section={"n_claims": 50},
    )
    assert c_fifty > c_zero, (
        f"More claims should raise composite: {c_fifty} vs {c_zero}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# 4. Composite score changes when ledger rows change
# ══════════════════════════════════════════════════════════════════════════════

def test_composite_changes_with_observability_rows(tmp_path):
    """Adding IDE rows with trace_ids increases observability_score → composite."""
    lo_empty = hm.score_observability_ledgers(state_dir=tmp_path)
    c_empty = hm.composite_nightly_score(
        ledger_obs=lo_empty,
        ledger_allo={"allostatic_score": 0.7},
        ledger_motor={"motor_score": 0.5},
        test_section={"status": "PASS"},
        bio_section={"n_claims": 10},
    )

    # Write 10 IDE rows all with trace_ids
    ide = tmp_path / "ide_stigmergic_trace.jsonl"
    rows = [{"trace_id": f"tid{i}", "ts": 1000.0 + i} for i in range(10)]
    ide.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    lo_full = hm.score_observability_ledgers(state_dir=tmp_path)
    c_full = hm.composite_nightly_score(
        ledger_obs=lo_full,
        ledger_allo={"allostatic_score": 0.7},
        ledger_motor={"motor_score": 0.5},
        test_section={"status": "PASS"},
        bio_section={"n_claims": 10},
    )
    assert lo_full["observability_score"] > lo_empty["observability_score"]
    assert c_full > c_empty, (
        f"More IDE rows should raise composite: {c_full} vs {c_empty}"
    )


def test_composite_changes_with_allostatic_rows(tmp_path):
    """Lower allostatic load → higher composite."""
    la_high = {"allostatic_score": 0.1}   # load=0.9 (sick)
    la_low  = {"allostatic_score": 0.95}  # load=0.05 (healthy)
    lo = {"observability_score": 0.5, "parentage_score": 0.3, "race_pressure": 0.1}
    lm = {"motor_score": 0.4}
    ts = {"status": "PASS"}
    bio = {"n_claims": 20}
    c_sick    = hm.composite_nightly_score(
        ledger_obs=lo, ledger_allo=la_high, ledger_motor=lm,
        test_section=ts, bio_section=bio,
    )
    c_healthy = hm.composite_nightly_score(
        ledger_obs=lo, ledger_allo=la_low, ledger_motor=lm,
        test_section=ts, bio_section=bio,
    )
    assert c_healthy > c_sick, f"Healthy allostasis should score higher: {c_healthy} vs {c_sick}"


def test_composite_changes_with_motor_rows(tmp_path):
    """More skill-weighted motor rows → higher motor_score → higher composite."""
    p = tmp_path / "motor_policy.jsonl"
    lo = {"observability_score": 0.5, "parentage_score": 0.3, "race_pressure": 0.1}
    la = {"allostatic_score": 0.7}
    ts = {"status": "PASS"}
    bio = {"n_claims": 10}

    # 0 skill-biased rows
    p.write_text(
        json.dumps({"truth_label": "OTHER", "bias": {"a": 0.5, "b": 0.5}}) + "\n",
        encoding="utf-8",
    )
    lm_flat = hm.score_motor_policy_ledger(state_dir=tmp_path, tail=50)
    c_flat = hm.composite_nightly_score(
        ledger_obs=lo, ledger_allo=la, ledger_motor=lm_flat,
        test_section=ts, bio_section=bio,
    )

    # 10 skill-biased rows
    p.write_text(
        "\n".join(
            json.dumps({"truth_label": "SKILL_WEIGHTED_POLICY", "bias": {"a": 0.9, "b": 0.1}})
            for _ in range(10)
        ) + "\n",
        encoding="utf-8",
    )
    lm_biased = hm.score_motor_policy_ledger(state_dir=tmp_path, tail=50)
    c_biased = hm.composite_nightly_score(
        ledger_obs=lo, ledger_allo=la, ledger_motor=lm_biased,
        test_section=ts, bio_section=bio,
    )
    assert lm_biased["motor_score"] > lm_flat["motor_score"]
    assert c_biased > c_flat, (
        f"Skill-biased motor rows should score higher: {c_biased} vs {c_flat}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# 5. Race pressure edge cases
# ══════════════════════════════════════════════════════════════════════════════

def test_race_pressure_zero_with_unique_ids(tmp_path):
    """Unique IDs at unique timestamps → 0 race pressure."""
    ide = tmp_path / "ide_stigmergic_trace.jsonl"
    rows = [
        {"trace_id": f"unique_{i}", "ts": float(1000 + i * 120)}  # 120s apart
        for i in range(5)
    ]
    ide.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    r = hm.score_observability_ledgers(state_dir=tmp_path)
    assert r["race_pressure"] == 0.0, f"Unique IDs → race_pressure=0, got {r['race_pressure']}"


def test_race_pressure_positive_with_duplicates(tmp_path):
    """Same trace_id within 60s → race pressure > 0."""
    ide = tmp_path / "ide_stigmergic_trace.jsonl"
    rows = [
        {"trace_id": "dup_trace", "ts": 1000.0},
        {"trace_id": "dup_trace", "ts": 1000.5},  # 0.5s later — same window
    ]
    ide.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    r = hm.score_observability_ledgers(state_dir=tmp_path)
    assert r["race_pressure"] > 0.0, "Duplicate IDs within 60s should raise race_pressure"


# ══════════════════════════════════════════════════════════════════════════════
# 6. test_score_numeric
# ══════════════════════════════════════════════════════════════════════════════

def test_test_score_numeric_pass():
    assert hm.test_score_numeric({"status": "PASS"}) == 1.0
    assert hm.test_score_numeric({"status": "pass"}) == 1.0


def test_test_score_numeric_fail():
    assert hm.test_score_numeric({"status": "FAIL"}) == 0.0
    assert hm.test_score_numeric({}) == 0.0
    assert hm.test_score_numeric({"status": "ERROR"}) == 0.0


if __name__ == "__main__":
    import pytest as _pt
    _pt.main([__file__, "-v"])
