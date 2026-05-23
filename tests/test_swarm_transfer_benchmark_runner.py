import pytest
from System.swarm_transfer_benchmark_runner import TransferBenchmarkRunner

def test_confidence_interval_low_n(tmp_path):
    runner = TransferBenchmarkRunner(root=tmp_path)
    # N=5 (below min 20)
    gains = [0.1, 0.15, 0.2, 0.12, 0.18]
    res = runner.evaluate_confidence("test_family", gains)
    
    assert res["kind"] == "TRANSFER_CONFIDENCE_INTERVAL"
    assert res["n"] == 5
    assert res["claim_safe"] is False, "N < 20 should fail safe claim"
    assert res["ci95_low"] > 0, "Mean is high enough, but N is too low, so claim_safe is False"

def test_confidence_interval_high_variance_not_safe(tmp_path):
    runner = TransferBenchmarkRunner(root=tmp_path)
    # N=30 but wild variance, pushing lower bound < 0
    gains = [0.01 if i % 2 == 0 else -0.05 for i in range(30)]
    res = runner.evaluate_confidence("noisy_family", gains)
    
    assert res["n"] == 30
    assert res["ci95_low"] < 0
    assert res["claim_safe"] is False, "ci95_low < 0 must fail safe claim"

def test_confidence_interval_safe_claim(tmp_path):
    runner = TransferBenchmarkRunner(root=tmp_path)
    # N=30 with solid positive transfer
    gains = [0.15 + (i * 0.001) for i in range(30)]
    res = runner.evaluate_confidence("safe_family", gains)
    
    assert res["n"] == 30
    assert res["ci95_low"] > 0.1
    assert res["claim_safe"] is True, "N>=20 and ci95_low>0 must pass safe claim"
    
def test_orchestrator(tmp_path):
    runner = TransferBenchmarkRunner(root=tmp_path)
    res = runner.run_benchmark("research_suite", n=25)
    
    assert res["n"] == 25
    assert "mean_transfer_gain" in res
    assert "std_transfer_gain" in res
