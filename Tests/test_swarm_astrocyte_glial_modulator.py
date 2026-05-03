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
