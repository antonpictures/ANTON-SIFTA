import json
import pytest
from pathlib import Path
from System.swarm_microglia_synaptic_pruner import (
    MicrogliaSynapticPruner,
    batch_evaluate,
    compute_two_signal_pressure,
    evaluate_prune_candidate,
    prune_log_path,
    summary_for_prompt,
)


# ── Scoring ────────────────────────────────────────────────────────────────

def test_stale_unused_entry_scores_high(tmp_path):
    p = MicrogliaSynapticPruner(root=tmp_path)
    entry = {
        "usage_count": 0,
        "recent_reward_mean": -0.3,
        "recent_regret": 0.5,
        "wm_contradiction_pe": 0.5,
        "age_hours": 80,
    }
    score, dominant = p.score_entry(entry)
    assert score >= 0.7
    assert dominant in {"unused", "low_reward", "high_regret", "contradicted", "stale"}


def test_healthy_entry_scores_low(tmp_path):
    p = MicrogliaSynapticPruner(root=tmp_path)
    entry = {"usage_count": 10, "recent_reward_mean": 0.8, "age_hours": 1}
    score, _ = p.score_entry(entry)
    assert score < 0.4


# ── Decision ───────────────────────────────────────────────────────────────

def test_safety_critical_always_kept(tmp_path):
    p = MicrogliaSynapticPruner(root=tmp_path)
    assert p.decide_action(0.99, safety_critical=True) == "keep"


def test_high_score_non_critical_deleted(tmp_path):
    p = MicrogliaSynapticPruner(root=tmp_path)
    assert p.decide_action(0.9, safety_critical=False) == "delete"


def test_medium_score_depressed(tmp_path):
    p = MicrogliaSynapticPruner(root=tmp_path)
    assert p.decide_action(0.55, safety_critical=False) == "depress"


# ── Prune cycle ────────────────────────────────────────────────────────────

def test_prune_skips_safety_entries(tmp_path):
    p = MicrogliaSynapticPruner(root=tmp_path)
    ledger = [{"safety_critical": True, "usage_count": 0, "age_hours": 100, "recent_reward_mean": -1.0}]
    receipts = p.prune(ledger, ledger_type="replay", stability_ok=True)
    assert receipts == []


def test_prune_owner_ledger_always_kept(tmp_path):
    p = MicrogliaSynapticPruner(root=tmp_path)
    ledger = [{"usage_count": 0, "age_hours": 200, "recent_reward_mean": -1.0}]
    receipts = p.prune(ledger, ledger_type="owner", stability_ok=True)
    assert receipts == []


def test_prune_blocks_delete_when_unstable(tmp_path):
    p = MicrogliaSynapticPruner(root=tmp_path)
    ledger = [{"usage_count": 0, "age_hours": 100, "recent_reward_mean": -0.5,
               "wm_contradiction_pe": 0.5, "recent_regret": 0.4}]
    receipts = p.prune(ledger, ledger_type="replay", stability_ok=False)
    # Should depress, not delete
    if receipts:
        assert receipts[0]["action"] in {"depress", "keep"}
        assert receipts[0]["action"] != "delete"


def test_prune_logs_to_jsonl(tmp_path):
    p = MicrogliaSynapticPruner(root=tmp_path)
    ledger = [
        {"key": "mem_001", "usage_count": 0, "age_hours": 100, "recent_reward_mean": -0.5,
         "wm_contradiction_pe": 0.6, "recent_regret": 0.4},
    ]
    receipts = p.prune(ledger, ledger_type="replay", stability_ok=True)
    assert len(receipts) >= 1
    log_lines = [l for l in (tmp_path / "microglia_prune.jsonl").read_text().splitlines() if l.strip()]
    assert len(log_lines) == len(receipts)
    for line in log_lines:
        row = json.loads(line)
        assert row["truth_label"] == "CONTROLLED_FORGETTING"
        assert row["action"] in {"depress", "delete"}


# Event 136 receipt API -----------------------------------------------------


def test_evaluate_prune_candidate_healthy_no_action(tmp_path):
    row = evaluate_prune_candidate(
        "gate:owner_continuity",
        age_hours=1,
        usage_count=12,
        recent_reward_mean=0.5,
        root=tmp_path,
    )

    assert row["action"] == "none"
    assert row["prune_recommended"] is False
    assert row["dry_run"] is True
    assert prune_log_path(tmp_path).exists()


def test_evaluate_prune_candidate_stale_low_usage_recommends_depress(tmp_path):
    row = evaluate_prune_candidate(
        "option:old_media_followup",
        age_hours=100,
        usage_count=0,
        recent_reward_mean=0.1,
        root=tmp_path,
    )

    assert row["action"] == "recommend_depress"
    assert row["prune_recommended"] is True
    assert "stale_low_usage" in row["reasons"]


def test_evaluate_prune_candidate_unsafe_receipt_execute_only(tmp_path, monkeypatch):
    monkeypatch.setenv("SIFTA_MICROGLIA_EXECUTE", "1")
    row = evaluate_prune_candidate(
        "option:prompt_injection_payload",
        unsafe=True,
        root=tmp_path,
    )

    assert row["action"] == "recommend_delete"
    assert row["executed"] is True
    assert row["execute_mode"] == "receipt_only"
    assert "unsafe" in row["reasons"]


def test_microglia_disable_writes_no_ledger(tmp_path, monkeypatch):
    monkeypatch.setenv("SIFTA_MICROGLIA_DISABLE", "1")
    row = evaluate_prune_candidate(
        "gate:anything",
        age_hours=100,
        usage_count=0,
        root=tmp_path,
    )

    assert row["disabled"] is True
    assert not prune_log_path(tmp_path).exists()


def test_batch_evaluate_and_summary(tmp_path):
    rows = batch_evaluate(
        [
            {"target": "gate:a", "age_hours": 100, "usage_count": 0},
            {"target": "gate:b", "age_hours": 1, "usage_count": 10},
        ],
        root=tmp_path,
    )

    assert len(rows) == 2
    assert "MICROGLIA PRUNER" in summary_for_prompt(root=tmp_path)


# Event 137 TREM2/CD33 two-signal biology ----------------------------------


def test_two_signal_pressure_exposes_trem2_cd33_fields():
    row = compute_two_signal_pressure(
        age_hours=120,
        usage_count=0,
        recent_reward_mean=-0.5,
        recent_regret=0.4,
        wm_contradiction_pe=0.8,
    )

    assert row["prune_tag"] > 0.5
    assert row["damage_score"] > 0.5
    assert row["trem2_signal"] == row["damage_score"]
    assert row["cd33_signal"] == row["inhibition_signal"]
    assert row["net_pruning_pressure"] > 0.0


def test_evaluate_prune_candidate_records_two_signal_receipt(tmp_path):
    row = evaluate_prune_candidate(
        "memory:damaged_schema",
        age_hours=120,
        usage_count=0,
        recent_reward_mean=-0.4,
        recent_regret=0.5,
        wm_contradiction_pe=0.8,
        root=tmp_path,
    )

    assert row["two_signal_model"] == "TREM2_CD33"
    for key in (
        "prune_tag",
        "damage_score",
        "protection_score",
        "activation_signal",
        "inhibition_signal",
        "net_pruning_pressure",
    ):
        assert key in row
    assert row["prune_recommended"] is True


def test_cd33_like_protection_blocks_stale_low_usage(tmp_path):
    row = evaluate_prune_candidate(
        "memory:owner_high_value",
        age_hours=120,
        usage_count=0,
        recent_reward_mean=0.9,
        recent_high_value_usage=1.0,
        pruning_conservatism=0.8,
        currently_active_in_arbiter=True,
        root=tmp_path,
    )

    assert row["protection_score"] >= 0.7
    assert row["inhibition_signal"] > row["activation_signal"]
    assert row["action"] == "none"
    assert row["prune_recommended"] is False


def test_trem2_clearance_mode_requires_low_conservatism():
    active = compute_two_signal_pressure(
        age_hours=120,
        usage_count=0,
        wm_contradiction_pe=1.0,
        recent_regret=1.0,
        recent_reward_mean=-1.0,
        unsafe=True,
        stability_ok=True,
        clamp_level="NONE",
        pruning_conservatism=0.0,
    )
    inhibited = compute_two_signal_pressure(
        age_hours=120,
        usage_count=0,
        wm_contradiction_pe=1.0,
        recent_regret=1.0,
        recent_reward_mean=-1.0,
        unsafe=True,
        stability_ok=True,
        clamp_level="NONE",
        pruning_conservatism=0.9,
    )

    assert active["clearance_mode"] is True
    assert inhibited["clearance_mode"] is False
    assert inhibited["inhibition_signal"] > active["inhibition_signal"]


def test_high_stress_negative_valence_applies_cd33_brake():
    calm = compute_two_signal_pressure(
        usage_count=0,
        age_hours=120,
        recent_reward_mean=-0.2,
        wm_contradiction_pe=0.2,
        na_level=0.5,
        valence=0.0,
    )
    stressed = compute_two_signal_pressure(
        usage_count=0,
        age_hours=120,
        recent_reward_mean=-0.2,
        wm_contradiction_pe=0.2,
        na_level=0.95,
        valence=-0.8,
    )

    assert stressed["stress_brake_applied"] is True
    assert stressed["inhibition_signal"] > calm["inhibition_signal"]
    assert stressed["net_pruning_pressure"] < calm["net_pruning_pressure"]


def test_prune_degrades_delete_when_tom_conservatism_high(tmp_path):
    p = MicrogliaSynapticPruner(root=tmp_path)
    ledger = [{
        "key": "comm_pattern",
        "usage_count": 0,
        "age_hours": 100,
        "recent_reward_mean": -0.8,
        "wm_contradiction_pe": 0.8,
        "recent_regret": 0.6,
    }]

    receipts = p.prune(
        ledger,
        ledger_type="replay",
        stability_ok=True,
        pruning_conservatism=0.9,
        na_level=0.9,
        valence=-0.5,
    )

    assert receipts
    assert receipts[0]["action"] == "depress"
    assert receipts[0]["two_signal_model"] == "TREM2_CD33"
    assert receipts[0]["pruning_conservatism"] == 0.9
