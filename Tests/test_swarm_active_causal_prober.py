import json

from System.swarm_active_causal_prober import (
    ActiveCausalProber,
    propose_and_execute_runtime_intervention,
)


class FixedRng:
    def choice(self, items):
        return "exploration_bias"

    def uniform(self, lo, hi):
        return 0.1


def test_active_causal_probe_gates_out_low_uncertainty(tmp_path):
    prober = ActiveCausalProber(root=tmp_path, dry_run=True, rng=FixedRng())
    row = prober.propose_and_execute(
        tick_id="tick-1",
        current_uncertainty=0.1,
        stability_level="NONE",
    )

    assert row is None
    assert not (tmp_path / "causal_intervention_log.jsonl").exists()


def test_active_causal_probe_gates_out_block_new_and_emergency(tmp_path):
    prober = ActiveCausalProber(root=tmp_path, dry_run=True, rng=FixedRng())

    assert prober.propose_and_execute("tick-1", 0.9, "BLOCK_NEW") is None
    assert prober.propose_and_execute("tick-2", 0.9, "EMERGENCY") is None


def test_active_causal_probe_dry_run_logs_without_state_mutation(tmp_path):
    prober = ActiveCausalProber(root=tmp_path, dry_run=True, rng=FixedRng())
    row = prober.propose_and_execute(
        tick_id="tick-3",
        current_uncertainty=0.8,
        stability_level="RATE_LIMIT",
    )

    assert row is not None
    assert row["kind"] == "CAUSAL_PROBE_INTERVENTION"
    assert row["intervention"]["do"]["target"] == "exploration_bias"
    assert row["intervention"]["do"]["dry_run"] is True
    assert row["causal_effect_size"] == 0.1
    assert not (tmp_path / "exploration_bias.json").exists()

    log_row = json.loads((tmp_path / "causal_intervention_log.jsonl").read_text().splitlines()[-1])
    assert log_row["truth_label"] == "CAUSAL_PROBE_INTERVENTION"


def test_active_causal_probe_execute_env_writes_bounded_sidecar(tmp_path, monkeypatch):
    monkeypatch.setenv("SIFTA_CAUSAL_PROBE_EXECUTE", "1")
    prober = ActiveCausalProber(root=tmp_path, rng=FixedRng())
    row = prober.propose_and_execute(
        tick_id=4,
        current_uncertainty=0.8,
        stability_level="NONE",
    )

    assert row is not None
    assert row["intervention"]["do"]["dry_run"] is False
    state = json.loads((tmp_path / "exploration_bias.json").read_text())
    assert state["value"] == 0.6
    assert state["kind"] == "CAUSAL_PROBE_EXPLORATION_BIAS"


def test_active_causal_probe_revert_persists_across_instances(tmp_path):
    prober = ActiveCausalProber(root=tmp_path, dry_run=False, rng=FixedRng())
    row = prober.propose_and_execute(
        tick_id=10,
        current_uncertainty=0.8,
        stability_level="NONE",
    )

    assert row is not None
    assert row["intervention"]["do"]["revert_at_tick"] == 13
    state = json.loads((tmp_path / "exploration_bias.json").read_text())
    assert state["value"] == 0.6

    fresh = ActiveCausalProber(root=tmp_path)
    assert fresh.apply_pending_reverts(12) == 0
    assert json.loads((tmp_path / "exploration_bias.json").read_text())["value"] == 0.6

    assert fresh.apply_pending_reverts(13) == 1
    restored = json.loads((tmp_path / "exploration_bias.json").read_text())
    assert restored["value"] == 0.5
    assert restored["kind"] == "CAUSAL_PROBE_EXPLORATION_BIAS_REVERTED"
    assert (tmp_path / "causal_probe_pending_reverts.jsonl").read_text() == ""

    log_rows = [
        json.loads(line)
        for line in (tmp_path / "causal_probe_revert_log.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert log_rows[-1]["truth_label"] == "CAUSAL_PROBE_REVERT_APPLIED"


def test_active_causal_probe_revert_requires_numeric_tick(tmp_path):
    prober = ActiveCausalProber(root=tmp_path, dry_run=False, rng=FixedRng())
    prober.propose_and_execute(
        tick_id=10,
        current_uncertainty=0.8,
        stability_level="NONE",
    )

    fresh = ActiveCausalProber(root=tmp_path)
    assert fresh.apply_pending_reverts("body-tick-uuid") == 0
    assert json.loads((tmp_path / "exploration_bias.json").read_text())["value"] == 0.6


def test_active_causal_probe_disable_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SIFTA_CAUSAL_PROBE_DISABLE", "1")
    row = propose_and_execute_runtime_intervention(
        tick_id="tick-5",
        current_uncertainty=0.9,
        current_clamp_level="NONE",
        root=tmp_path,
    )

    assert row is None
    assert not (tmp_path / "causal_intervention_log.jsonl").exists()

# ============================================================
# PART 3: Biological Steering (§10.14.28)
# DAM Stage 2 blocks, TME Escape drops threshold, NA>0.8 drives exploration
# ============================================================

def test_biological_steering_dam_stage2_blocks_probe(tmp_path):
    """DAM Stage 2 implies severe brain inflammation; no active experiments."""
    receipt = propose_and_execute_runtime_intervention(
        tick_id=1,
        current_uncertainty=0.9,
        current_clamp_level="NONE",
        root=tmp_path,
        uncertainty_threshold=0.1,
        dam_stage=2,
    )
    assert receipt is None, "Should block probe in DAM stage 2"

def test_biological_steering_dam_stage1_allows_probe(tmp_path):
    """DAM Stage 1 is reactive but allows probing."""
    receipt = propose_and_execute_runtime_intervention(
        tick_id=1,
        current_uncertainty=0.9,
        current_clamp_level="NONE",
        root=tmp_path,
        uncertainty_threshold=0.1,
        dam_stage=1,
    )
    assert receipt is not None, "Should allow probe in DAM stage 1"
    assert receipt["confounder_check"]["dam_stage"] == 1

def test_biological_steering_tme_escape_desperation(tmp_path):
    """TME ESCAPE triggers short, high-variance probes by lowering uncertainty_threshold."""
    # Base threshold is 0.5; uncertainty 0.45 < 0.5 -> normally blocks.
    # But ESCAPE drops threshold by 0.15 -> 0.35. Now 0.45 > 0.35 -> allows probe.
    receipt = propose_and_execute_runtime_intervention(
        tick_id=1,
        current_uncertainty=0.45,
        current_clamp_level="NONE",
        root=tmp_path,
        uncertainty_threshold=0.50,
        tme_phase="ESCAPE",
    )
    assert receipt is not None, "ESCAPE should lower threshold and allow probe"
    assert receipt["confounder_check"]["tme_phase"] == "ESCAPE"
    # Verify duration_ticks is 1
    assert receipt["intervention"]["do"]["duration_ticks"] == 1

def test_biological_steering_high_na_drives_exploration(tmp_path):
    """High NA (>0.8) lowers uncertainty threshold by 0.10."""
    # Base 0.5, uncertainty 0.45 -> blocked. NA drops threshold to 0.40 -> allows probe.
    receipt = propose_and_execute_runtime_intervention(
        tick_id=1,
        current_uncertainty=0.45,
        current_clamp_level="NONE",
        root=tmp_path,
        uncertainty_threshold=0.50,
        na_level=0.85,
    )
    assert receipt is not None, "High NA should lower threshold and allow probe"
    assert receipt["confounder_check"]["na_level"] == 0.85

