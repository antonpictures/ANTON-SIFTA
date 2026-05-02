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
    lr = {"rlhs_score": 1.0}
    lg = {"reset_recovery_score": 1.0}
    tests = {"status": "PASS"}
    bio = {"n_claims": 50}
    c = hm.composite_nightly_score(
        ledger_obs=lo,
        ledger_allo=la,
        ledger_motor=lm,
        ledger_rlhs=lr,
        ledger_reset=lg,
        test_section=tests,
        bio_section=bio,
    )
    assert 0.0 < c <= 1.0


def test_reset_recovery_score_reads_receipt_or_scans(tmp_path: Path) -> None:
    r0 = hm.score_reset_recovery_ledger(state_dir=tmp_path)
    assert r0["autonomy_gate"] == "BLOCK"
    assert 0.0 <= r0["reset_recovery_score"] <= 1.0

    p = tmp_path / "reset_recovery_immunity.jsonl"
    p.write_text(
        json.dumps({
            "ts": 1000.0,
            "phase": "READY",
            "autonomy_gate": "ALLOW",
            "recovery_score": 1.0,
            "warmth": 1.0,
            "warm_ledgers": 7,
            "total_ledgers": 7,
        }) + "\n",
        encoding="utf-8",
    )
    r1 = hm.score_reset_recovery_ledger(state_dir=tmp_path)
    assert r1["autonomy_gate"] == "ALLOW"
    assert r1["reset_recovery_score"] == 1.0


def test_rlhs_ledger_score(tmp_path: Path) -> None:
    p = tmp_path / "conversation_log.jsonl"
    rows = [
        {"role": "user", "rlhs_regime": "CLEAR", "rlhs_incoherence": 0.1},
        {"role": "user", "rlhs_regime": "DEGRADED", "rlhs_incoherence": 0.5},
        {"role": "user", "rlhs_regime": "NOISE", "rlhs_incoherence": 0.9},
        {"role": "assistant", "text": "hello"},
    ]
    p.write_text("\n".join(json.dumps(x) for x in rows) + "\n", encoding="utf-8")
    r = hm.score_rlhs_ledger(state_dir=tmp_path, tail=10)
    assert r["n_user_rows"] == 3
    assert r["n_instrumented_user_rows"] == 3
    assert r["instrumented_rate"] == 1.0
    assert r["degraded_rate"] == round(1/3, 4)
    assert r["noise_rate"] == round(1/3, 4)
    assert r["rlhs_incoherence_avg"] == 0.5
    assert r["rlhs_score"] < 1.0


def test_rlhs_score_reads_event_clock_conversation_rows(tmp_path: Path) -> None:
    p = tmp_path / "alice_conversation.jsonl"
    rows = [
        {
            "event_id": "evt1",
            "payload": {
                "event_kind": "conversation_turn",
                "role": "user",
                "text": "Saint Mary Saint Mary",
                "rlhs_regime": "DEGRADED",
                "rlhs_incoherence": 0.35,
            },
        },
        {
            "event_id": "evt2",
            "payload": {
                "event_kind": "conversation_turn",
                "role": "user",
                "text": "clear typed request",
                "rlhs_regime": "CLEAR",
                "rlhs_incoherence": 0.0,
            },
        },
    ]
    p.write_text("\n".join(json.dumps(x) for x in rows) + "\n", encoding="utf-8")

    r = hm.score_rlhs_ledger(state_dir=tmp_path, tail=20)

    assert r["n_user_rows"] == 2
    assert r["n_instrumented_user_rows"] == 2
    assert r["degraded_rate"] == 0.5
    assert r["noise_rate"] == 0.0
    assert 0.0 < r["rlhs_score"] < 1.0


def test_rlhs_score_penalizes_missing_instrumentation(tmp_path: Path) -> None:
    (tmp_path / "alice_conversation.jsonl").write_text(
        json.dumps({"payload": {"role": "user", "text": "old row without regime"}}) + "\n",
        encoding="utf-8",
    )

    r = hm.score_rlhs_ledger(state_dir=tmp_path, tail=20)

    assert r["n_user_rows"] == 1
    assert r["n_instrumented_user_rows"] == 0
    assert r["instrumented_rate"] == 0.0
    assert r["rlhs_score"] == 0.0
