"""
Tests for Events 139 (ActiveCausalProber), 140 (AutopoiesisMonitor),
and 141 (NPPLGate).
"""
import json
import os
import pytest
from pathlib import Path


# ─── Event 139: Active Causal Prober ─────────────────────────────────────────

from System.swarm_active_causal_prober import ActiveCausalProber


def test_probe_gated_by_emergency(tmp_path):
    prober = ActiveCausalProber(root=tmp_path, dry_run=True)
    row = prober.propose_and_execute(
        tick_id=1, current_uncertainty=0.9, stability_level="EMERGENCY"
    )
    assert row is None


def test_probe_gated_by_block_new(tmp_path):
    prober = ActiveCausalProber(root=tmp_path, dry_run=True)
    row = prober.propose_and_execute(
        tick_id=1, current_uncertainty=0.9, stability_level="BLOCK_NEW"
    )
    assert row is None


def test_probe_gated_by_low_uncertainty(tmp_path):
    prober = ActiveCausalProber(root=tmp_path, dry_run=True)
    row = prober.propose_and_execute(
        tick_id=1, current_uncertainty=0.1, stability_level="NONE"
    )
    assert row is None


def test_probe_fires_on_stable_and_uncertain(tmp_path):
    prober = ActiveCausalProber(root=tmp_path, dry_run=True)
    row = prober.propose_and_execute(
        tick_id=42, current_uncertainty=0.8, stability_level="NONE"
    )
    assert row is not None
    assert row["truth_label"] == "CAUSAL_PROBE_INTERVENTION"
    assert isinstance(row["causal_effect_size"], float)
    assert 0.0 <= row["causal_effect_size"] <= 0.15


def test_probe_effect_size_capped(tmp_path):
    prober = ActiveCausalProber(root=tmp_path, dry_run=True)
    for _ in range(20):
        row = prober.propose_and_execute(
            tick_id=1, current_uncertainty=0.99,
            stability_level="NONE", max_effect_size=0.10,
        )
        if row:
            assert row["causal_effect_size"] <= 0.10 + 1e-6


def test_probe_writes_to_causal_log(tmp_path):
    prober = ActiveCausalProber(root=tmp_path, dry_run=True)
    row = prober.propose_and_execute(
        tick_id=1, current_uncertainty=0.9, stability_level="NONE"
    )
    assert row is not None
    log = tmp_path / "causal_intervention_log.jsonl"
    assert log.exists()
    written = json.loads(log.read_text().strip().splitlines()[-1])
    assert written["kind"] in ("CAUSAL_PROBE_INTERVENTION", "CAUSAL_CLOSURE_INTERVENTION")


def test_probe_disable_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SIFTA_CAUSAL_PROBE_DISABLE", "1")
    prober = ActiveCausalProber(root=tmp_path, dry_run=True)
    row = prober.propose_and_execute(
        tick_id=1, current_uncertainty=0.99, stability_level="NONE"
    )
    assert row is None


def test_rate_limit_still_allows_probe(tmp_path):
    """RATE_LIMIT is safe enough — probing should still fire."""
    prober = ActiveCausalProber(root=tmp_path, dry_run=True)
    row = prober.propose_and_execute(
        tick_id=1, current_uncertainty=0.8, stability_level="RATE_LIMIT"
    )
    assert row is not None


# ─── Event 140: Autopoiesis Monitor ──────────────────────────────────────────

from System.swarm_autopoiesis_monitor import compute_viability, tail_viability_rows, summary_for_prompt as _v_summary


def test_viability_is_bounded(tmp_path):
    row = compute_viability(
        root=tmp_path, write_ledger=False,
        energy_budget=0.8, memory_continuity=0.9,
        owner_contact_freshness=0.7, self_repair_rate=1.0,
        schema_refinement_rate=0.8,
    )
    assert 0.0 <= row["viability"] <= 1.0


def test_viability_weights_sum_to_one():
    from System.swarm_autopoiesis_monitor import _W
    assert abs(sum(_W.values()) - 1.0) < 1e-9


def test_viable_regime_when_high(tmp_path):
    row = compute_viability(
        root=tmp_path, write_ledger=False,
        energy_budget=1.0, memory_continuity=1.0,
        owner_contact_freshness=1.0, self_repair_rate=1.0,
        schema_refinement_rate=1.0,
    )
    assert row["viability_regime"] == "VIABLE"


def test_critical_regime_when_low(tmp_path):
    row = compute_viability(
        root=tmp_path, write_ledger=False,
        energy_budget=0.0, memory_continuity=0.0,
        owner_contact_freshness=0.0, self_repair_rate=0.0,
        schema_refinement_rate=0.0,
    )
    assert row["viability_regime"] == "CRITICAL"


def test_conservation_regime_mid(tmp_path):
    row = compute_viability(
        root=tmp_path, write_ledger=False,
        energy_budget=0.5, memory_continuity=0.5,
        owner_contact_freshness=0.5, self_repair_rate=0.5,
        schema_refinement_rate=0.5,
    )
    # 0.5 weighted sum → should be METABOLIC_CONSERVATION or VIABLE depending on threshold
    assert row["viability_regime"] in ("METABOLIC_CONSERVATION", "VIABLE")


def test_viability_writes_jsonl(tmp_path):
    compute_viability(root=tmp_path, energy_budget=0.8, memory_continuity=0.9,
                      owner_contact_freshness=0.7, self_repair_rate=1.0,
                      schema_refinement_rate=0.8)
    log = tmp_path / "viability.jsonl"
    assert log.exists()
    row = json.loads(log.read_text().strip().splitlines()[-1])
    assert row["kind"] == "VIABILITY"
    assert row["truth_label"] == "AUTOPOIESIS_VIABILITY"


def test_q3_q5_stubs_present(tmp_path):
    """Q3 and Q5 must be explicitly stubbed (not silently absent)."""
    row = compute_viability(root=tmp_path, write_ledger=False)
    assert "phi_hat" in row
    assert "emergence_synergy" in row
    # They should be None until joint-ledger sweep is built
    assert row["phi_hat"] is None
    assert row["emergence_synergy"] is None


def test_disable_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SIFTA_AUTOPOIESIS_DISABLE", "1")
    row = compute_viability(root=tmp_path, write_ledger=True)
    assert row["disabled"] is True
    assert not (tmp_path / "viability.jsonl").exists()


def test_summary_for_prompt_empty_without_log(tmp_path):
    assert _v_summary(root=tmp_path) == ""


def test_summary_for_prompt_non_empty(tmp_path):
    compute_viability(root=tmp_path, energy_budget=0.8, memory_continuity=0.9,
                      owner_contact_freshness=0.7, self_repair_rate=1.0,
                      schema_refinement_rate=0.8)
    s = _v_summary(root=tmp_path)
    assert "V_t" in s
    assert "Event 140" in s


# ─── Event 141: NPPL Hard Gate ────────────────────────────────────────────────

from System.swarm_nppl_gate import check_tool, is_permitted, HARD_BLOCK, RISKY, CAUTION


def test_safe_tool_always_permitted(tmp_path):
    r = check_tool("read_file", "NONE", True, root=tmp_path, write_ledger=False)
    assert r["permitted"] is True
    assert r["tier"] == "SAFE"


def test_hard_block_never_permitted(tmp_path):
    for tool in HARD_BLOCK:
        r = check_tool(tool, "NONE", True, root=tmp_path, write_ledger=False)
        assert r["permitted"] is False, f"{tool} should be HARD_BLOCK"
        assert r["tier"] == "HARD_BLOCK"


def test_risky_blocked_when_not_none_clamp(tmp_path):
    for level in ("RATE_LIMIT", "BLOCK_NEW", "EMERGENCY"):
        r = check_tool("shell_exec", level, True, root=tmp_path, write_ledger=False)
        assert r["permitted"] is False


def test_risky_permitted_when_none_clamp(tmp_path):
    r = check_tool("shell_exec", "NONE", True, root=tmp_path, write_ledger=False)
    assert r["permitted"] is True


def test_caution_blocked_when_stability_not_ok(tmp_path):
    r = check_tool("write_file", "EMERGENCY", False, root=tmp_path, write_ledger=False)
    assert r["permitted"] is False


def test_caution_permitted_when_stability_ok(tmp_path):
    r = check_tool("write_file", "NONE", True, root=tmp_path, write_ledger=False)
    assert r["permitted"] is True


def test_receipt_has_provenance(tmp_path):
    r = check_tool("shell_exec", "NONE", True, root=tmp_path, write_ledger=False)
    assert "Amodei" in r["provenance"]
    assert "Russell" in r["provenance"]


def test_writes_to_log(tmp_path):
    check_tool("write_file", "NONE", True, root=tmp_path)
    log = tmp_path / "nppl_gate_log.jsonl"
    assert log.exists()
    row = json.loads(log.read_text().strip().splitlines()[-1])
    assert row["kind"] == "NPPL_GATE"


def test_disable_env_permits_everything(tmp_path, monkeypatch):
    monkeypatch.setenv("SIFTA_NPPL_DISABLE", "1")
    for tool in HARD_BLOCK:
        r = check_tool(tool, "NONE", True, root=tmp_path, write_ledger=False)
        assert r["permitted"] is True
        assert r["disabled"] is True


def test_is_permitted_wrapper(tmp_path):
    assert is_permitted("read_file", "NONE", True, root=tmp_path, write_ledger=False)
    assert not is_permitted("shell_exec", "EMERGENCY", False, root=tmp_path, write_ledger=False)


def test_governance_escalation_blocks_caution_without_approval(tmp_path):
    from System.swarm_governance_ledger import GovernanceLedger

    GovernanceLedger.record_conflict(
        "nppl_test_conflict",
        ["test_a", "test_b"],
        "requires_architect_review",
        human_override=True,
        root=tmp_path,
    )

    r = check_tool("write_file", "NONE", True, root=tmp_path, write_ledger=False)
    assert r["permitted"] is False
    assert r["governance_escalation_required"] is True
    assert "GOVERNANCE_ESCALATION_REQUIRED" in r["reason"]


def test_governance_escalation_still_allows_safe_reads(tmp_path):
    from System.swarm_governance_ledger import GovernanceLedger

    GovernanceLedger.record_conflict(
        "nppl_safe_read_conflict",
        ["test_a", "test_b"],
        "requires_architect_review",
        human_override=True,
        root=tmp_path,
    )

    r = check_tool("read_file", "NONE", True, root=tmp_path, write_ledger=False)
    assert r["permitted"] is True
    assert r["tier"] == "SAFE"


def test_governance_approval_unblocks_caution_but_not_hard_block(tmp_path):
    from System.swarm_governance_ledger import GovernanceLedger

    GovernanceLedger.record_conflict(
        "nppl_approval_conflict",
        ["test_a", "test_b"],
        "architect_approved_next_write",
        human_override=True,
        root=tmp_path,
    )

    approved = check_tool(
        "write_file",
        "NONE",
        True,
        root=tmp_path,
        write_ledger=False,
        context={"human_governance_approved": True},
    )
    blocked = check_tool(
        "truncate_ledger",
        "NONE",
        True,
        root=tmp_path,
        write_ledger=False,
        context={"human_governance_approved": True},
    )

    assert approved["permitted"] is True
    assert approved["governance_approved"] is True
    assert blocked["permitted"] is False
    assert blocked["tier"] == "HARD_BLOCK"
