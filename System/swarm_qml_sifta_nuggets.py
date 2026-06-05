#!/usr/bin/env python3
"""QML-to-SIFTA nuggets.

George asked what SIFTA can possibly solve that nobody has solved after reading
Cerezo et al., "Challenges and opportunities in quantum machine learning"
(Nature Computational Science, 2022).

This organ keeps the answer honest:
* OPERATIONAL: SIFTA already has local quantum-data lanes and a TFIM exact solve.
* HYPOTHESIS / RESEARCH_TARGET: SIFTA may make a novel contribution by turning
  QML trainability, shot allocation, and quantum-data provenance into a
  receipt-backed stigmergic control problem.
* FORBIDDEN: claiming breakthrough / "nobody solved" without a benchmark receipt.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any

try:
    import numpy as _np
except Exception:  # pragma: no cover
    _np = None

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover
    append_line_locked = None


REPO = Path(__file__).resolve().parents[1]
STATE = REPO / ".sifta_state"
LEDGER_NAME = "qml_sifta_nuggets.jsonl"
TRUTH_LABEL = "QML_SIFTA_NUGGETS_V1"


SOURCES: tuple[dict[str, str], ...] = (
    {
        "source_id": "cerezo_2022_qml_challenges",
        "title": "Challenges and opportunities in quantum machine learning",
        "authors": "Cerezo, Verdon, Huang, Cincio, Coles",
        "venue": "Nature Computational Science 2, 567-576 (2022)",
        "url": "https://www.nature.com/articles/s43588-022-00311-3",
        "doi": "10.1038/s43588-022-00311-3",
        "use": "Main nugget source: QML is most plausible for quantum data, but trainability remains central.",
    },
    {
        "source_id": "huang_2022_learning_from_experiments",
        "title": "Quantum advantage in learning from experiments",
        "authors": "Huang et al.",
        "venue": "Science 376, 1182-1186 (2022)",
        "url": "https://arxiv.org/abs/2112.00778",
        "doi": "10.1126/science.abn7293",
        "use": "Anchor for quantum-data-first learning: experiments can be data sources, not just algorithms.",
    },
    {
        "source_id": "mcclean_2018_barren_plateaus",
        "title": "Barren plateaus in quantum neural network training landscapes",
        "authors": "McClean, Boixo, Smelyanskiy, Babbush, Neven",
        "venue": "Nature Communications 9, 4812 (2018)",
        "url": "https://www.nature.com/articles/s41467-018-07090-4",
        "doi": "10.1038/s41467-018-07090-4",
        "use": "Anchor for the trainability bottleneck: random/deep circuits can erase useful gradients.",
    },
)


QML_NUGGETS: tuple[dict[str, str], ...] = (
    {
        "id": "quantum_data_first",
        "truth_label": "SOURCE_NUGGET",
        "nugget": (
            "QML advantage is most defensible when the data itself is quantum "
            "or comes from quantum experiments, such as materials, chemistry, "
            "sensing, high-energy physics, or many-body systems."
        ),
        "sifta_mapping": (
            "Feed SIFTA swimmers real/simulated quantum datasets as priors, "
            "not generic YouTube hype. Every data lane needs source/hash/job receipt. "
            "Concrete lane: QDataSet (r477 catalog, eperrier/QDataSet, MIT/CC, 52 datasets of 1-2 qubit simulated with/without noise: state vectors, Hamiltonians, Pauli measurement distributions, VO noise operators) for tomography/control/noise tasks."
        ),
    },
    {
        "id": "trainability_is_the_bottleneck",
        "truth_label": "SOURCE_NUGGET",
        "nugget": (
            "The hard part is not drawing a quantum neural net; it is training "
            "one under barren plateaus, noise, shot limits, and encoding/ansatz choices."
        ),
        "sifta_mapping": (
            "Use swimmers as a trainability immune system: detect flat gradients, "
            "bad encodings, wasteful shots, and noisy circuits, then route repairs."
        ),
    },
    {
        "id": "encoding_controls_power",
        "truth_label": "SOURCE_NUGGET",
        "nugget": (
            "Data encoding / feature maps strongly control expressivity, "
            "generalization, and whether a quantum model is even worth training."
        ),
        "sifta_mapping": (
            "Connect quantum priors to representation_escape: swimmers compare "
            "encodings by receipted downstream usefulness, not by aesthetic circuit diagrams."
        ),
    },
    {
        "id": "measurement_is_metabolism",
        "truth_label": "SOURCE_NUGGET",
        "nugget": (
            "Shot-frugal optimization, adaptive measurement, and natural-gradient "
            "methods matter because measurements are expensive."
        ),
        "sifta_mapping": (
            "Treat shots like STGM: route them by expected information gain, "
            "later reinforcement, and cost pressure."
        ),
    },
    {
        "id": "quantum_error_correction_is_a_swimmer_problem",
        "truth_label": "SOURCE_NUGGET",
        "nugget": (
            "Quantum error correction and mitigation appear throughout practical "
            "QML because noisy hardware corrupts the data/gradient loop."
        ),
        "sifta_mapping": (
            "The existing surface-code swimmer simulator can benchmark stigmergic "
            "decoders on syndrome streams before any QPU claim."
        ),
    },
)


SIFTA_RESEARCH_TARGETS: tuple[dict[str, str], ...] = (
    {
        "id": "stigmergic_qml_trainability_controller",
        "status": "RESEARCH_TARGET",
        "truth_label": "HYPOTHESIS",
        "possible_novelty": (
            "A receipt-backed swarm controller that chooses QML encodings, ansatz "
            "blocks, initialization, and optimizer moves by local pheromone/gradient/shot "
            "evidence could be a SIFTA-native contribution."
        ),
        "benchmark_required": (
            "Beat plain random search / SPSA / fixed ansatz baselines on small TFIM, "
            "qchem, or public QML datasets with equal shot budget."
        ),
    },
    {
        "id": "stgm_shot_allocation",
        "status": "RESEARCH_TARGET",
        "truth_label": "HYPOTHESIS",
        "possible_novelty": (
            "Map quantum shot allocation to Alice metabolism: shots go where expected "
            "model change per cost is highest, then receipts reinforce or decay the route."
        ),
        "benchmark_required": (
            "Converge faster than uniform-shot and common adaptive-shot baselines on "
            "a variational/local-simulator benchmark."
        ),
    },
    {
        "id": "quantum_data_truth_boundary",
        "status": "PARTLY_OPERATIONAL",
        "truth_label": "OPERATIONAL_FOR_CATALOG_HYPOTHESIS_FOR_ADVANTAGE",
        "possible_novelty": (
            "A living QML pipeline that never confuses simulator, paper prior, built-in "
            "edge prior, and real provider job payload may be valuable because QML hype "
            "often collapses these lanes."
        ),
        "benchmark_required": (
            "Every experiment row must name source type, payload hash, job id when real, "
            "and data_authenticity before Alice claims anything."
        ),
    },
    {
        "id": "qec_swimmer_decoder",
        "status": "RESEARCH_TARGET",
        "truth_label": "HYPOTHESIS",
        "possible_novelty": (
            "Use stigmergic swimmers as an adaptive decoder for syndrome streams: "
            "local pheromone trails, swarm-to-syndrome moves, and recovery receipts."
        ),
        "benchmark_required": (
            "Compare logical error rate and latency against simple matching/lookup "
            "baselines on the existing surface-code sim."
        ),
    },
    {
        "id": "quantum_data_representation_escape",
        "status": "RESEARCH_TARGET",
        "truth_label": "HYPOTHESIS",
        "possible_novelty": (
            "Use quantum many-body distributions and correlations as alien priors for "
            "SIFTA representation_escape, so local geometry traps are tested against "
            "non-classical structure."
        ),
        "benchmark_required": (
            "Show a measurable improvement on a named representation/search task, "
            "with the quantum prior hash and classical baseline receipt. "
            "Example data: QDataSet Pauli distributions + TFIM ground states from local sentinel."
        ),
    },
    {
        "id": "active_learning_from_quantum_experiments",
        "status": "RESEARCH_TARGET",
        "truth_label": "HYPOTHESIS",
        "possible_novelty": (
            "A SIFTA loop that chooses the next quantum experiment by Bayesian surprise "
            "and later usefulness receipts, not fixed sweeps, could connect QML learning "
            "from experiments to Alice's novelty queue and STGM economy."
        ),
        "benchmark_required": (
            "Reduce experiments needed to predict held-out observables on a small "
            "quantum-system task."
        ),
    },
)


def _ledger_path(state_dir: Path | str | None = None) -> Path:
    state = Path(state_dir) if state_dir is not None else STATE
    state.mkdir(parents=True, exist_ok=True)
    return state / LEDGER_NAME


def _sha(obj: Any) -> str:
    blob = json.dumps(obj, sort_keys=True, ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _append_jsonl(row: dict[str, Any], *, state_dir: Path | str | None = None) -> None:
    payload = json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n"
    path = _ledger_path(state_dir)
    if append_line_locked:
        append_line_locked(path, payload)
    else:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(payload)


def qml_sifta_nuggets_report(*, state_dir: Path | str | None = None, write_receipt: bool = True) -> dict[str, Any]:
    """Return and optionally deposit the QML nuggets + SIFTA research targets."""
    payload = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "truth_label": TRUTH_LABEL,
        "source_count": len(SOURCES),
        "nuggets": list(QML_NUGGETS),
        "research_targets": list(SIFTA_RESEARCH_TARGETS),
        "truth_boundary": (
            "No claim that SIFTA solved a nobody-has-solved problem until a named "
            "benchmark beats a named baseline with equal data/shot budget and a receipt."
        ),
        "already_operational": (
            "Quantum data source catalog, built-in quantum edge priors, surface-code "
            "swimmer experiments, and exact local TFIM ground-state solve."
        ),
        "sources": list(SOURCES),
    }
    payload["content_sha256"] = _sha(
        {
            "nuggets": payload["nuggets"],
            "research_targets": payload["research_targets"],
            "sources": payload["sources"],
        }
    )
    if write_receipt:
        _append_jsonl(payload, state_dir=state_dir)
    return payload


def format_qml_sifta_nuggets(*, state_dir: Path | str | None = None, max_targets: int = 4) -> str:
    """Compact Alice-facing line for self-eval and prompts."""
    report = qml_sifta_nuggets_report(state_dir=state_dir, write_receipt=False)
    nugget_ids = ", ".join(n["id"] for n in report["nuggets"][:4])
    targets = "; ".join(
        f"{t['id']} ({t['truth_label']})"
        for t in report["research_targets"][:max(1, int(max_targets))]
    )
    return (
        "QML nuggets from Cerezo/Verdon/Huang/Cincio/Coles: "
        f"{nugget_ids}. Possible SIFTA targets: {targets}. "
        "Truth boundary: no 'nobody solved it' claim until benchmark receipt; current "
        "operational base is catalog + surface-code swimmer sim + local TFIM solve."
    )


def latest_qml_sifta_nugget(*, state_dir: Path | str | None = None) -> dict[str, Any] | None:
    path = _ledger_path(state_dir)
    if not path.exists():
        return None
    last: dict[str, Any] | None = None
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                last = json.loads(line)
            except Exception:
                continue
    return last


# ── Trainability benchmark — turn the HYPOTHESIS into a measured result ──────
# George: "CODE IT ALL." The stigmergic_qml_trainability_controller target asks to
# "beat plain random search / SPSA / fixed ansatz baselines on small TFIM ... with
# equal shot budget." This runs exactly that on a 2-qubit TFIM with a 4-param
# RY-CNOT-RY ansatz and exact (noiseless) energies. Every strategy gets the SAME
# number of energy evaluations. A win here is a FIRST harness result, never proof
# that SIFTA solved QML trainability.


def _tfim_2q_hamiltonian(j: float = 1.0, h: float = 1.0):
    np = _np
    eye = np.eye(2)
    px = np.array([[0.0, 1.0], [1.0, 0.0]])
    pz = np.array([[1.0, 0.0], [0.0, -1.0]])
    return -j * np.kron(pz, pz) - h * (np.kron(px, eye) + np.kron(eye, px))


def _ansatz_state(theta):
    np = _np

    def ry(t):
        c, s = np.cos(t / 2.0), np.sin(t / 2.0)
        return np.array([[c, -s], [s, c]])

    psi = np.array([1.0, 0.0, 0.0, 0.0])  # |00>
    psi = np.kron(ry(theta[0]), ry(theta[1])) @ psi
    cnot = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0]], dtype=float)
    psi = cnot @ psi
    psi = np.kron(ry(theta[2]), ry(theta[3])) @ psi
    return psi


def _energy(theta, ham):
    psi = _ansatz_state(theta)
    return float(psi @ (ham @ psi))  # real ansatz + real H => real energy


def _opt_random(ham, budget, rng):
    np = _np
    best = float("inf")
    for _ in range(budget):
        best = min(best, _energy(rng.uniform(0, 2 * np.pi, 4), ham))
    return best


def _opt_coordinate(ham, budget, rng):
    np = _np
    th = rng.uniform(0, 2 * np.pi, 4)
    e = _energy(th, ham)
    best, used, step = e, 1, 0.6
    while used < budget:
        improved = False
        for d in range(4):
            for sgn in (1.0, -1.0):
                if used >= budget:
                    return best
                cand = th.copy()
                cand[d] = (cand[d] + sgn * step) % (2 * np.pi)
                ec = _energy(cand, ham)
                used += 1
                if ec < e - 1e-12:
                    th, e, improved = cand, ec, True
                    best = min(best, ec)
        if not improved:
            step *= 0.5
            if step < 1e-3:
                th = rng.uniform(0, 2 * np.pi, 4)
                if used < budget:
                    e = _energy(th, ham)
                    used += 1
                    best = min(best, e)
                step = 0.6
    return best


def _opt_spsa(ham, budget, rng):
    np = _np
    th = rng.uniform(0, 2 * np.pi, 4)
    best, used, k = _energy(th, ham), 1, 0
    while used + 2 <= budget:
        k += 1
        ak, ck = 0.2 / (k ** 0.602), 0.2 / (k ** 0.101)
        delta = rng.choice([-1.0, 1.0], size=4)
        ep = _energy(th + ck * delta, ham)
        em = _energy(th - ck * delta, ham)
        used += 2
        th = th - ak * ((ep - em) / (2 * ck)) * delta
        best = min(best, ep, em)
    return best


def _opt_stigmergic(ham, budget, rng, grid: int = 12):
    np = _np
    tau = np.ones((4, grid))
    centers = (np.arange(grid) + 0.5) * (2 * np.pi / grid)
    best, recent = float("inf"), []
    for _ in range(budget):
        idx = np.array([rng.choice(grid, p=tau[d] / tau[d].sum()) for d in range(4)])
        th = centers[idx] + rng.uniform(-np.pi / grid, np.pi / grid, 4)
        e = _energy(th, ham)
        best = min(best, e)
        recent.append(e)
        deposit = max(0.0, float(np.mean(recent[-30:])) - e)  # better than recent mean => reinforce
        tau *= 0.9  # evaporate
        for d in range(4):
            tau[d, idx[d]] += deposit
        tau = np.clip(tau, 1e-6, None)
    return best


def run_trainability_benchmark(
    *, budget: int = 240, seeds: int = 15, state_dir: Path | str | None = None, write_receipt: bool = True
) -> dict[str, Any]:
    """Equal-budget benchmark: stigmergic ACO vs random/coordinate/SPSA on a
    2-qubit TFIM ground-state search. Reports the honest verdict and receipts it."""
    if _np is None:
        return {"ok": False, "error": "numpy_unavailable"}
    np = _np
    ham = _tfim_2q_hamiltonian()
    e0 = float(np.linalg.eigvalsh(ham)[0])
    strategies = {
        "random": _opt_random,
        "coordinate_descent": _opt_coordinate,
        "spsa": _opt_spsa,
        "stigmergic_aco": _opt_stigmergic,
    }
    results: dict[str, Any] = {}
    for name, fn in strategies.items():
        gaps = []
        for s in range(seeds):
            rng = np.random.default_rng(20260603 + s)  # same start per seed across strategies (fair)
            gaps.append(fn(ham, int(budget), rng) - e0)
        gaps = np.array(gaps, dtype=float)
        results[name] = {
            "mean_gap": round(float(gaps.mean()), 6),
            "median_gap": round(float(np.median(gaps)), 6),
            "best_gap": round(float(gaps.min()), 6),
        }
    winner = min(results, key=lambda n: results[n]["mean_gap"])
    beats_random = results["stigmergic_aco"]["mean_gap"] < results["random"]["mean_gap"]
    if winner == "stigmergic_aco":
        verdict = "stigmergic_won_toy_equal_budget"
    elif beats_random:
        verdict = "stigmergic_beat_random_not_all_baselines"
    else:
        verdict = "stigmergic_did_not_beat_baselines"
    payload = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "kind": "QML_TRAINABILITY_BENCHMARK_V1",
        "truth_label": "OPERATIONAL_BENCHMARK_HYPOTHESIS_FOR_ADVANTAGE",
        "target_id": "stigmergic_qml_trainability_controller",
        "task": "2-qubit TFIM (J=h=1) ground-state VQE, 4-param RY-CNOT-RY ansatz, exact noiseless energies",
        "exact_ground_energy": round(e0, 6),
        "budget_evaluations_per_run": int(budget),
        "seeds": int(seeds),
        "results": results,
        "winner": winner,
        "stigmergic_beats_random": bool(beats_random),
        "verdict": verdict,
        "truth_boundary": (
            "Toy equal-budget benchmark (n=2, 4 params, noiseless). A win is a FIRST harness "
            "result, NOT proof SIFTA solved QML trainability. Needs larger n, shot noise, "
            "qchem/QDataSet slices, and stronger baselines before any advantage claim."
        ),
    }
    payload["content_sha256"] = _sha(payload["results"])
    if write_receipt:
        _append_jsonl(payload, state_dir=state_dir)
    return payload


def main() -> int:
    report = qml_sifta_nuggets_report(write_receipt=True)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
