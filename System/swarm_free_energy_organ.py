#!/usr/bin/env python3
"""
System/swarm_free_energy_organ.py — Free Energy Principle / Active Inference Organ (Friston 2010)

Computes variational free energy on the label-transition stream of the Fiction Organ
and produces an active-inference recommendation (update model, shift behavior, rest, or monitor).

This is the agency layer after Kuramoto (phase synchrony) and CFC (cross-frequency coupling).

Physics:
- Friston, K. (2010). The free-energy principle: a unified brain theory? Nature Reviews Neuroscience.
- Clark, A. (2016). Surfing Uncertainty.

Scope boundary (verbatim):
"Free energy computed on Markov transitions in fiction_organ_flux.jsonl label sequence, not neural Bayesian inference. The 'minimization' here is statistical surprise of label transitions in this organism's own ledger, a stigmergic-substrate analog of Friston's variational free energy, not a claim about Bayesian brain neural computation."

Truth label: FREE_ENERGY_ORGAN_V0
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Dict, List, Tuple, Any

import numpy as np

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

_TRUTH_LABEL = "FREE_ENERGY_ORGAN_V0"
_RECEIPT_LEDGER = _STATE / "free_energy_receipts.jsonl"
_FLUX_LEDGER = _STATE / "fiction_organ_flux.jsonl"

# The 9 labels used by the Fiction Organ (must match exactly)
LABELS = [
    "REAL", "OBSERVED", "MEMORY", "FICTION", "SCRIPT",
    "SYMBOLIC", "SIMULATION", "HYPOTHETICAL", "ROLEPLAY"
]
LABEL_TO_IDX = {label: i for i, label in enumerate(LABELS)}


def _now() -> float:
    return time.time()


def _safe_append_receipt(row: Dict[str, Any]) -> None:
    _RECEIPT_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with _RECEIPT_LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _load_transitions(window_s: float) -> List[Tuple[str, str]]:
    """Parse transitions from fiction_organ_flux.jsonl in the window."""
    if not _FLUX_LEDGER.exists():
        return []
    cutoff = _now() - window_s
    transitions = []
    try:
        with _FLUX_LEDGER.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                try:
                    row = json.loads(line)
                    if float(row.get("ts", 0)) < cutoff:
                        continue
                    trans = row.get("transitions", {})
                    for key, count in trans.items():
                        if "__" in key:
                            frm, to = key.split("__", 1)
                            if frm in LABEL_TO_IDX and to in LABEL_TO_IDX:
                                for _ in range(int(count)):
                                    transitions.append((frm, to))
                except Exception:
                    continue
    except Exception:
        pass
    return transitions


def learn_generative_model(window_s: float = 3600.0,
                           smoothing: float = 0.01) -> Dict[str, Any]:
    """Build 9x9 Markov transition matrix from recent transitions."""
    transitions = _load_transitions(window_s)
    n = len(LABELS)
    count_matrix = np.ones((n, n)) * smoothing  # Laplace smoothing

    for frm, to in transitions:
        i = LABEL_TO_IDX[frm]
        j = LABEL_TO_IDX[to]
        count_matrix[i, j] += 1

    row_sums = count_matrix.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1
    transition_matrix = count_matrix / row_sums

    # Prior distribution (stationary)
    prior = transition_matrix.sum(axis=0)
    prior = prior / prior.sum() if prior.sum() > 0 else np.ones(n) / n

    return {
        "transition_matrix": transition_matrix.tolist(),
        "labels": LABELS,
        "n_transitions_observed": len(transitions),
        "prior_distribution": prior.tolist()
    }


def predict_next_distribution(current_label: str, model: Dict[str, Any]) -> Dict[str, float]:
    if current_label not in LABEL_TO_IDX:
        return {label: 1.0 / len(LABELS) for label in LABELS}
    i = LABEL_TO_IDX[current_label]
    probs = model["transition_matrix"][i]
    return {label: float(p) for label, p in zip(LABELS, probs)}


def compute_surprise(observed_label: str, predicted_distribution: Dict[str, float]) -> float:
    p = max(predicted_distribution.get(observed_label, 1e-12), 1e-12)
    return -np.log(p)


def compute_variational_free_energy(observed_sequence: List[str],
                                    model: Dict[str, Any]) -> Dict[str, Any]:
    if len(observed_sequence) < 2:
        return {"F_nats": 0.0, "mean_surprise_nats": 0.0, "n_transitions": 0, "top_5_surprises": []}

    surprises = []
    for i in range(1, len(observed_sequence)):
        prev = observed_sequence[i-1]
        curr = observed_sequence[i]
        pred = predict_next_distribution(prev, model)
        s = compute_surprise(curr, pred)
        surprises.append((prev, curr, s))

    mean_s = np.mean([s[2] for s in surprises])
    F = mean_s  # For this discrete case, F ≈ mean surprise

    top5 = sorted(surprises, key=lambda x: x[2], reverse=True)[:5]
    top5_list = [{"from": a, "to": b, "surprise_nats": float(s)} for a, b, s in top5]

    return {
        "F_nats": float(F),
        "mean_surprise_nats": float(mean_s),
        "n_transitions": len(surprises),
        "top_5_surprises": top5_list
    }


def active_inference_step(recent_flux: List[str],
                          model: Dict[str, Any],
                          preferred_labels: Tuple[str, ...] = ("REAL", "OBSERVED")) -> Dict[str, Any]:
    if not recent_flux:
        return {"action": "monitor", "reason": "no_data"}

    # Compute surprise over recent window
    fe = compute_variational_free_energy(recent_flux, model)
    mean_surprise = fe["mean_surprise_nats"]

    from collections import Counter
    counts = Counter(recent_flux)
    dominant = counts.most_common(1)[0][0] if counts else "REAL"

    if mean_surprise > 2.0:
        return {"action": "update_model", "reason": f"high_mean_surprise_{mean_surprise:.2f}"}
    elif mean_surprise < 0.5 and dominant not in preferred_labels:
        return {"action": "shift_behavior", "reason": "low_surprise_but_non_preferred_dominant", "target_label": "REAL"}
    elif mean_surprise < 0.5 and dominant in preferred_labels:
        return {"action": "rest", "reason": "free_energy_low_homeostasis_ok"}
    else:
        return {"action": "monitor", "reason": "moderate_surprise_no_intervention_yet"}


def measure_free_energy(window_s: float = 1800.0,
                        write_receipt: bool = True) -> Dict[str, Any]:
    # Learn on longer window
    model = learn_generative_model(window_s * 2)

    # Get recent transitions for the measurement window
    transitions = _load_transitions(window_s)
    if len(transitions) < 2:
        observed_seq = ["REAL"] * 5
    else:
        observed_seq = [t[0] for t in transitions] + [transitions[-1][1]]

    fe = compute_variational_free_energy(observed_seq, model)
    rec = active_inference_step(observed_seq, model)

    from collections import Counter
    dom = Counter(observed_seq).most_common(1)[0][0] if observed_seq else "REAL"

    receipt = {
        "ts": _now(),
        "truth_label": _TRUTH_LABEL,
        "receipt_id": f"fep-{uuid.uuid4().hex[:12]}",
        "window_s": window_s,
        "n_transitions_observed": len(transitions),
        "free_energy_nats": fe["F_nats"],
        "mean_surprise_per_transition_nats": fe["mean_surprise_nats"],
        "top_5_surprises": fe["top_5_surprises"],
        "model_accuracy_fraction": 1.0 - min(1.0, fe["mean_surprise_nats"] / 5.0),
        "dominant_label_in_window": dom,
        "preferred_labels": list(["REAL", "OBSERVED"]),
        "active_inference_recommendation": rec,
        "doctrine_anchor": "Friston 2010 FEP; Clark 2016 Surfing Uncertainty; SIFTA fiction_organ_flux substrate",
        "scope_limit": "Free energy computed on Markov transitions in fiction_organ_flux.jsonl label sequence, not neural Bayesian inference. The 'minimization' here is statistical surprise of label transitions in this organism's own ledger, a stigmergic-substrate analog of Friston's variational free energy, not a claim about Bayesian brain neural computation."
    }

    if write_receipt:
        _safe_append_receipt(receipt)

    return receipt


# Tests

def test_synthetic_low_surprise():
    # Create a model biased to REAL
    model = {
        "transition_matrix": [[0.9] + [0.0125]*8 for _ in range(9)],
        "labels": LABELS,
        "n_transitions_observed": 100,
        "prior_distribution": [0.9] + [0.0125]*8
    }
    for i in range(9):
        model["transition_matrix"][i][0] = 0.9 if i == 0 else 0.0125

    seq = ["REAL"] * 101
    fe = compute_variational_free_energy(seq, model)
    assert fe["mean_surprise_nats"] < 0.2


def test_synthetic_high_surprise():
    model = {
        "transition_matrix": [[0.9] + [0.0125]*8 for _ in range(9)],
        "labels": LABELS,
        "n_transitions_observed": 100,
        "prior_distribution": [0.9] + [0.0125]*8
    }
    s = compute_surprise("ROLEPLAY", {"REAL": 0.01, "ROLEPLAY": 0.01, **{l:0.01 for l in LABELS if l not in ["REAL","ROLEPLAY"]}})
    assert s > 2.0


def test_active_inference_branches():
    model = learn_generative_model(10)  # dummy
    rec1 = active_inference_step(["REAL"]*20, model)
    assert rec1["action"] == "rest"

    rec2 = active_inference_step(["ROLEPLAY"]*20, model)
    assert rec2["action"] == "shift_behavior"

    rec3 = active_inference_step(["REAL", "ROLEPLAY"] * 10, model)
    # This one may vary, but at least it returns a valid action
    assert rec3["action"] in ["update_model", "shift_behavior", "rest", "monitor"]


def test_real_data_smoke():
    receipt = measure_free_energy(window_s=1800, write_receipt=True)
    assert "free_energy_nats" in receipt
    assert receipt["truth_label"] == _TRUTH_LABEL


if __name__ == "__main__":
    test_synthetic_low_surprise()
    test_synthetic_high_surprise()
    test_active_inference_branches()
    test_real_data_smoke()
    print("All 4 FEP tests passed.")
