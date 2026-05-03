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
        tick_id="tick-4",
        current_uncertainty=0.8,
        stability_level="NONE",
    )

    assert row is not None
    assert row["intervention"]["do"]["dry_run"] is False
    state = json.loads((tmp_path / "exploration_bias.json").read_text())
    assert state["value"] == 0.6
    assert state["kind"] == "CAUSAL_PROBE_EXPLORATION_BIAS"


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
