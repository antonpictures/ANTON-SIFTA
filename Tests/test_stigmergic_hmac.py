import pytest
from System.swarm_stigmergic_weight_ecology import (
    ReplayEvaluator,
    ReplayExperience,
    AdapterSignal,
    verify_event,
    build_merge_plan
)

def test_hmac_signing_with_secret():
    evaluator = ReplayEvaluator(max_samples=1, secret="test_secret", pass_score=0.0)
    
    signal = AdapterSignal(
        adapter_id="test_id",
        adapter_path="/tmp/test",
        base_model="test_model",
        homeworld="earth",
        task="test",
        conflict_group="test",
        eval_score=1.0,
        regression_score=1.0,
        energy_joules=1.0,
        risk_score=0.0,
        pheromone_strength=1.0,
    )
    
    exp = ReplayExperience("id1", 0.0, "hello", "world")
    
    def responder(prompt, *args):
        return "world"
        
    report = evaluator.evaluate(signal, [exp], responder)
    
    assert report["signer"] == "SIFTA.ReplayEvaluator"
    assert report["signature"] != ""
    assert report["quarantine_reason"] is None
    assert report["passed"] is True
    
    # Verify the signature
    unsigned = {k: v for k, v in report.items() if k != "signature"}
    assert verify_event(unsigned, "test_secret", report["signature"])

def test_require_replay_rejects_missing():
    signal = AdapterSignal(
        adapter_id="test_id",
        adapter_path="/tmp/test",
        base_model="test_model",
        homeworld="earth",
        task="test",
        conflict_group="test",
        eval_score=1.0,
        regression_score=1.0,
        energy_joules=1.0,
        risk_score=0.0,
        pheromone_strength=1.0,
    )
    
    # It should reject it because require_replay=True and replay_reports is empty
    with pytest.raises(ValueError, match="no adapter survived"):
        build_merge_plan([signal])
    
    # But if we pass it manually, it should accept it
    plan = build_merge_plan([signal], replay_reports={"test_id": {"verdict": "PROMOTE"}})
    assert plan["selected"][0]["adapter_id"] == "test_id"
