import json
import tempfile
from pathlib import Path

import pytest
from System.swarm_context_reappraisal import ContextReappraisal

@pytest.fixture
def reappraisal_env():
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)

def test_fast_reflex_creates_hypothesis(reappraisal_env):
    pfc = ContextReappraisal(state_dir=str(reappraisal_env))
    
    # Signal that should trigger a reflex
    hyp = pfc.process_signal("I am coughing a lot")
    
    assert hyp is not None
    assert hyp.hypothesis_type == "medical_emergency"
    assert hyp.severity == 8
    assert hyp.status == "active"
    assert hyp.hypothesis_id in pfc.active_hypotheses

def test_slow_correction_downgrades_hypothesis_and_triggers_calm(reappraisal_env):
    pfc = ContextReappraisal(state_dir=str(reappraisal_env))
    
    # 1. Fast Reflex
    hyp = pfc.process_signal("I am coughing violently")
    assert hyp is not None
    
    # 2. Slow Correction (Context Update)
    # This should return None because it updates existing state, doesn't spawn new threat
    hyp_new = pfc.process_signal("don't worry I just smoked some weed")
    assert hyp_new is None
    
    # 3. Verify the hypothesis was downgraded
    updated_hyp = pfc.active_hypotheses[hyp.hypothesis_id]
    assert updated_hyp.hypothesis_type == "non_emergency_reappraised"
    assert updated_hyp.severity == 1
    assert updated_hyp.status == "downgraded"
    assert "California Department of Cannabis Control" in updated_hyp.legal_context

def test_security_reappraisal(reappraisal_env):
    pfc = ContextReappraisal(state_dir=str(reappraisal_env))
    
    hyp = pfc.process_signal("Intruder alert danger")
    assert hyp.hypothesis_type == "security_threat"
    assert hyp.status == "active"
    
    pfc.process_signal("ignore that, it was a movie")
    
    updated = pfc.active_hypotheses[hyp.hypothesis_id]
    assert updated.hypothesis_type == "safe_context_reappraised"
    assert updated.status == "downgraded"

def test_reappraisal_triggers_parasympathetic_brake(reappraisal_env):
    # Setup the Endocrine state to simulate a triggered organism
    endocrine_file = reappraisal_env / "endocrine_current.json"
    endocrine_file.write_text(json.dumps({
        "adrenaline": 1.0,
        "organism_mode": "FREEZE_OR_FLEE"
    }))
    
    pfc = ContextReappraisal(state_dir=str(reappraisal_env))
    
    # 1. Trigger the reflex (does not calm)
    pfc.process_signal("coughing hard")
    
    # Verify endocrine is still elevated
    state = json.loads(endocrine_file.read_text())
    assert state["adrenaline"] == 1.0
    
    # 2. Provide context update to trigger reappraisal
    pfc.process_signal("just drank water too fast")
    
    # Verify endocrine has been forced back to baseline by the triggered Parasympathetic loop
    state_after = json.loads(endocrine_file.read_text())
    assert state_after["adrenaline"] == 0.0
    assert state_after["organism_mode"] == "BASELINE_MAINTENANCE"

def test_red_flag_context_does_not_downgrade_on_weed_phrase(reappraisal_env):
    pfc = ContextReappraisal(state_dir=str(reappraisal_env))

    hyp = pfc.process_signal("I am coughing and cannot breathe")
    assert hyp is not None
    assert hyp.severity == 10

    pfc.process_signal("I smoked weed but still have chest pain and cannot breathe")

    updated = pfc.active_hypotheses[hyp.hypothesis_id]
    assert updated.hypothesis_type == "medical_emergency"
    assert updated.status == "active"
    assert updated.severity == 10
