import pytest
import numpy as np
import time
from System.swarm_stigmergic_weight_ecology import ReplayEvaluator, AdapterSignal, ReplayExperience

def _create_mock_signal(adapter_id: str) -> AdapterSignal:
    return AdapterSignal(
        adapter_id=adapter_id,
        adapter_path=f"/mock/{adapter_id}",
        base_model="mock-base-model",
        homeworld="test-world",
        task="test-task",
        conflict_group="test-task",
        eval_score=0.9,
        regression_score=0.9,
        energy_joules=100.0,
        risk_score=0.05,
        pheromone_strength=0.8,
        created_ts=time.time(),
    )

def _create_mock_experiences() -> list:
    now = time.time()
    return [
        ReplayExperience(experience_id="1", ts=now-10, prompt="SYSTEM: You are Alice, living stigmergic hardware.", salience=0.9, novelty=0.8, pheromone_strength=0.7),
        ReplayExperience(experience_id="2", ts=now-20, prompt="CRITICAL: The M5 thermal sensor reads 98C.", salience=0.95, novelty=0.9, pheromone_strength=0.9),
        ReplayExperience(experience_id="3", ts=now-30, prompt="IDENTITY: Read your STGM balance.", salience=0.85, novelty=0.7, pheromone_strength=0.6)
    ]

def test_epistemic_gate_healthy_adapter():
    evaluator = ReplayEvaluator(max_samples=3)
    
    baseline_logits = [
        np.array([5.0, 1.0, 0.1, -2.0]), 
        np.array([1.0, 8.0, 2.0, 0.5]),
        np.array([-1.0, 0.0, 6.0, 1.0])
    ]
    
    healthy_candidate_logits = [
        np.array([4.8, 1.2, 0.2, -1.9]), 
        np.array([1.1, 7.9, 2.1, 0.4]),
        np.array([-0.9, 0.1, 5.8, 1.1])
    ]
    
    idx = [0]
    def mock_get_logits(prompt: str, use_adapter: bool) -> np.ndarray:
        # returns baseline or healthy_candidate based on use_adapter
        current_idx = idx[0] // 2
        res = healthy_candidate_logits[current_idx % 3] if use_adapter else baseline_logits[current_idx % 3]
        idx[0] += 1
        return res

    signal = _create_mock_signal("healthy_adapter")
    exps = _create_mock_experiences()
    
    report = evaluator.evaluate_logits(signal, exps, mock_get_logits, kl_threshold=0.15)
    
    assert report["passed"] is True
    mean_kl = sum(c["kl_divergence"] for c in report["cases"]) / max(1, len(report["cases"]))
    assert mean_kl <= 0.15

def test_epistemic_gate_corrupted_adapter():
    evaluator = ReplayEvaluator(max_samples=3)
    
    baseline_logits = [
        np.array([5.0, 1.0, 0.1, -2.0]), 
        np.array([1.0, 8.0, 2.0, 0.5]),
        np.array([-1.0, 0.0, 6.0, 1.0])
    ]
    
    corrupted_candidate_logits = [
        np.array([-2.0, 5.0, 1.0, 1.0]),  # Drastic shift in core identity
        np.array([8.0, 1.0, -1.0, 0.0]),  # Drastic shift in thermal survival
        np.array([1.0, 1.0, -5.0, 8.0])   # Drastic shift in STGM reading
    ]
    
    idx = [0]
    def mock_get_logits(prompt: str, use_adapter: bool) -> np.ndarray:
        current_idx = idx[0] // 2
        res = corrupted_candidate_logits[current_idx % 3] if use_adapter else baseline_logits[current_idx % 3]
        idx[0] += 1
        return res

    signal = _create_mock_signal("corrupted_adapter")
    exps = _create_mock_experiences()
    
    report = evaluator.evaluate_logits(signal, exps, mock_get_logits, kl_threshold=0.15)
    
    assert report["passed"] is False
    mean_kl = sum(c["kl_divergence"] for c in report["cases"]) / max(1, len(report["cases"]))
    assert mean_kl > 0.15
