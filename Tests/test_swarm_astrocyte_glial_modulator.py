import pytest
from System.swarm_astrocyte_glial_modulator import AstrocyteGlialModulator

def test_astrocyte_modulation(tmp_path):
    astro = AstrocyteGlialModulator(root=tmp_path)
    
    # Base state
    params1 = astro.get_current_parameters()
    assert params1["lr"] == 0.1
    assert params1["epistemic_weight"] == 0.25
    
    # Observe high surprise (Prediction Error)
    trace = astro.observe_global_state(new_surprise=5.0, compute_expended=100.0)
    params2 = astro.get_current_parameters()
    
    # LR should spike up, epistemic weight should drop
    assert params2["lr"] > params1["lr"]
    assert params2["epistemic_weight"] < params1["epistemic_weight"]
    
    # Observe massive compute burn (Metabolic Heat)
    astro.observe_global_state(new_surprise=0.0, compute_expended=5000.0)
    params3 = astro.get_current_parameters()
    
    # Compute budget should be squeezed down
    assert params3["budget"] < astro.base_compute_budget


def test_astrocyte_state_persistence_and_receipts(tmp_path):
    astro = AstrocyteGlialModulator(root=tmp_path)
    trace = astro.observe_global_state(new_surprise=1.0, compute_expended=200.0)

    assert trace["truth_label"] == "ASTROCYTE_MODULATION"
    assert trace["trace_id"]
    assert astro.state_file.exists()
    assert astro.log_file.exists()

    astro2 = AstrocyteGlialModulator(root=tmp_path)
    assert astro2.get_current_parameters()["lr"] == astro.get_current_parameters()["lr"]
    assert "ASTROCYTE GLIAL MODULATOR" in astro2.summary_for_prompt()


def test_astrocyte_disable_does_not_write(tmp_path, monkeypatch):
    monkeypatch.setenv("SIFTA_ASTROCYTE_DISABLE", "1")
    astro = AstrocyteGlialModulator(root=tmp_path)
    trace = astro.observe_global_state(new_surprise=3.0, compute_expended=900.0)

    assert trace["disabled"] is True
    assert not astro.state_file.exists()
    assert not astro.log_file.exists()


def test_preferences_patch_increases_cost_weight_under_heat(tmp_path):
    astro = AstrocyteGlialModulator(root=tmp_path)
    base = astro.preferences_patch()
    astro.observe_global_state(new_surprise=0.0, compute_expended=2500.0)
    hot = astro.preferences_patch()

    assert hot["cost_weight"] > base["cost_weight"]
    assert hot["uncertainty_weight"] <= astro.base_epistemic_weight
