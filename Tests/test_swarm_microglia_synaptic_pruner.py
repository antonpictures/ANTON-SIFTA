import json
import pytest
from pathlib import Path
from System.swarm_microglia_synaptic_pruner import MicrogliaSynapticPruner


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
