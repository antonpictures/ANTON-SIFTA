import json
import pytest
from pathlib import Path
from System.swarm_microglia_synaptic_pruner import (
    MicrogliaSynapticPruner,
    batch_evaluate,
    compute_two_signal_pressure,
    dam_priming_state_path,
    evaluate_prune_candidate,
    microglia_sleep_window_receipt,
    prune_log_path,
    resolve_dam_priming,
    summary_for_prompt,
    update_dam_priming,
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


def test_governor_no_longer_changes_forgetting(tmp_path):
    # [r170 — Architect directive] GOVERNOR DELETED. stability_ok must no longer
    # change microglia's forgetting decision. The same memory yields the same
    # action whether stability_ok is False or True — Alice's own two-signal
    # logic governs her pruning, not a detached clamp.
    entry = {"key": "m", "usage_count": 0, "age_hours": 100, "recent_reward_mean": -0.5,
             "wm_contradiction_pe": 0.5, "recent_regret": 0.4}
    a = MicrogliaSynapticPruner(root=tmp_path / "a").prune(
        [dict(entry)], ledger_type="replay", stability_ok=False)
    b = MicrogliaSynapticPruner(root=tmp_path / "b").prune(
        [dict(entry)], ledger_type="replay", stability_ok=True)
    act_a = a[0]["action"] if a else None
    act_b = b[0]["action"] if b else None
    assert act_a == act_b


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


def test_dam_priming_resolves_empty_state(tmp_path):
    priming = resolve_dam_priming("memory:new", root=tmp_path, now=1000.0)

    assert priming["prev_dam_stage"] == 0
    assert priming["priming_strength"] == 0.0
    assert priming["priming_source"] == "none"


def test_dam_priming_stage2_persists_then_decays(tmp_path, monkeypatch):
    def mock_load(*args, **kwargs):
        return {"microglia_priming_half_life_hours": 10.0 / 3600.0}
    import System.swarm_regulatory_genome as srg
    monkeypatch.setattr(srg, "load_regulatory_parameters", mock_load)

    update = update_dam_priming(
        "memory:damaged",
        dam_stage=2,
        base_pathology=0.8,
        root=tmp_path,
        now=0.0,
    )
    fresh = resolve_dam_priming("memory:damaged", root=tmp_path, now=0.0)
    one_half_life = resolve_dam_priming("memory:damaged", root=tmp_path, now=10.0)
    three_half_lives = resolve_dam_priming("memory:damaged", root=tmp_path, now=30.0)

    assert update["priming_strength"] == 1.0
    assert fresh["prev_dam_stage"] == 2
    assert one_half_life["priming_strength"] == pytest.approx(0.5)
    assert one_half_life["prev_dam_stage"] == 2
    assert three_half_lives["priming_strength"] == pytest.approx(0.125)
    assert three_half_lives["prev_dam_stage"] == 0


def test_evaluate_prune_candidate_uses_persistent_dam_priming(tmp_path):
    evaluate_prune_candidate(
        "memory:persistent_pathology",
        age_hours=12.0,
        usage_count=0,
        recent_regret=0.9,
        wm_contradiction_pe=0.9,
        root=tmp_path,
        now=1000.0,
    )

    row = evaluate_prune_candidate(
        "memory:persistent_pathology",
        usage_count=4,
        recent_reward_mean=0.0,
        recent_regret=0.0,
        wm_contradiction_pe=0.65,
        root=tmp_path,
        now=1001.0,
    )

    assert row["dam_priming"]["source"] == "persistent"
    assert row["dam_priming"]["prev_stage"] == 2
    assert row["dam_stage"] == 2
    assert row["base_pathology"] < 0.58


def test_explicit_prev_dam_stage_overrides_persistent_priming(tmp_path):
    evaluate_prune_candidate(
        "memory:override_pathology",
        age_hours=12.0,
        usage_count=0,
        recent_regret=0.9,
        wm_contradiction_pe=0.9,
        root=tmp_path,
        now=2000.0,
    )

    row = evaluate_prune_candidate(
        "memory:override_pathology",
        usage_count=4,
        recent_reward_mean=0.0,
        wm_contradiction_pe=0.65,
        prev_dam_stage=0,
        root=tmp_path,
        now=2001.0,
    )

    assert row["dam_priming"]["source"] == "explicit"
    assert row["dam_priming"]["prev_stage"] == 0
    assert row["dam_stage"] == 1


def test_pruner_receipts_include_dam_priming_update(tmp_path):
    p = MicrogliaSynapticPruner(root=tmp_path)
    receipts = p.prune(
        [{
            "key": "memory:receipt_pathology",
            "usage_count": 0,
            "age_hours": 120,
            "recent_reward_mean": -0.8,
            "recent_regret": 0.8,
            "wm_contradiction_pe": 0.9,
            "unsafe": True,
        }],
        ledger_type="replay",
        stability_ok=True,
    )

    assert receipts
    receipt = receipts[0]
    assert receipt["dam_priming"]["update"]["updated"] is True
    assert receipt["dam_priming"]["update"]["target_key"] == "memory:receipt_pathology"
    assert dam_priming_state_path(tmp_path).exists()


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


def test_rich_fractalkine_continuous_context_protection():
    protected = compute_two_signal_pressure(
        age_hours=90,
        usage_count=0,
        recent_reward_mean=-0.2,
        stability_dwell_score=1.0,
        goal_alignment=1.0,
        owner_frustration=0.0,
    )
    exposed = compute_two_signal_pressure(
        age_hours=90,
        usage_count=0,
        recent_reward_mean=-0.2,
        stability_dwell_score=0.0,
        goal_alignment=0.0,
        owner_frustration=1.0,
    )

    assert protected["fractalkine_analog"] > exposed["fractalkine_analog"]
    assert protected["inhibition_signal"] > exposed["inhibition_signal"]
    assert protected["net_pruning_pressure"] < exposed["net_pruning_pressure"]


def test_sleep_window_receipt_and_clearance_bias(monkeypatch):
    monkeypatch.setenv(
        "MICROGLIA_SLEEP_WINDOW",
        '{"enabled": true, "name": "night", "start_hour": 23, "end_hour": 7, '
        '"activation_boost": 0.1, "net_threshold_delta": 0.04}',
    )
    # 02:00 local is inside 23 -> 7 wraparound. The epoch value is arbitrary;
    # tests only need the local hour decoded by time.localtime().
    import time
    now = time.mktime((2026, 5, 3, 2, 0, 0, 0, 0, -1))

    sleep = microglia_sleep_window_receipt(now=now)
    row = evaluate_prune_candidate(
        "sleep:weak_schema",
        age_hours=120,
        usage_count=0,
        recent_reward_mean=-0.4,
        recent_regret=0.5,
        wm_contradiction_pe=0.8,
        root=None,
        write_ledger=False,
        now=now,
    )

    assert sleep["sleep_window_active"] is True
    assert row["sleep_window_active"] is True
    assert row["sleep_window_name"] == "night"
    assert "sleep_window_clearance_bias" in row["reasons"]
    assert row["clearance_net_threshold"] < 0.55
