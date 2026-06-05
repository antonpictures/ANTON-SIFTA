#!/usr/bin/env python3
"""Quantum Data Sentinel — catalog real quantum data lanes for SIFTA swimmers.

This organ is deliberately conservative:

* It may catalog primary online sources and open datasets.
* It may run local classical simulations that produce quantum-circuit sample data.
* It must not claim real quantum-hardware execution unless a provider job/result
  receipt is present.

George asked to send swimmers into "original data" from quantum-computer
software/experiments. V1 makes the boundary explicit and gives Alice one local
starter experiment plus a source catalog she can quote from self-eval.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover
    append_line_locked = None


REPO = Path(__file__).resolve().parents[1]
STATE = REPO / ".sifta_state"
LEDGER_NAME = "quantum_data_sentinel.jsonl"
TRUTH_LABEL = "QUANTUM_DATA_SENTINEL_V1"


@dataclass(frozen=True)
class QuantumDataSource:
    source_id: str
    name: str
    source_type: str
    access: str
    primary_url: str
    usable_data: str
    sifta_use: str
    truth_boundary: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


QUANTUM_DATA_SOURCES: tuple[QuantumDataSource, ...] = (
    QuantumDataSource(
        source_id="pennylane_quantum_datasets",
        name="PennyLane Quantum Datasets",
        source_type="open_dataset",
        access="public_download_with_python_package",
        primary_url="https://docs.pennylane.ai/en/stable/introduction/data.html",
        usable_data=(
            "Quantum chemistry, oscillator, spin-system, benchmark, and other "
            "dataset attributes such as Hamiltonians, energies, measurement "
            "groupings, symmetries, ansaetze, and parameters."
        ),
        sifta_use=(
            "First real ingest lane: feed chemistry/spin Hamiltonian metadata "
            "into representation_escape or a new quantum-prior scoring organ."
        ),
        truth_boundary="Public dataset lane; not evidence Alice used a QPU.",
    ),
    QuantumDataSource(
        source_id="amazon_braket_local_and_qpu",
        name="Amazon Braket local simulator and provider QPUs",
        source_type="simulator_or_cloud_job",
        access="local_simulator_public_docs; hardware_requires_aws_account",
        primary_url="https://docs.aws.amazon.com/braket/latest/developerguide/braket-send-to-local-simulator.html",
        usable_data=(
            "Local state-vector/density-matrix simulator counts now; QPU/Analog "
            "Hamiltonian Simulator results only after AWS task id and receipt."
        ),
        sifta_use="Run Bell/QAOA/VQE prototypes locally, then upgrade to provider job receipts later.",
        truth_boundary="Cloud QPU claims require AWS task/result receipt; local simulator is classical.",
    ),
    QuantumDataSource(
        source_id="ibm_quantum_runtime_jobs",
        name="IBM Quantum Runtime jobs/results/metrics",
        source_type="cloud_job_receipt",
        access="requires_ibm_quantum_token_and_service_crn",
        primary_url="https://quantum.cloud.ibm.com/docs/en/api/qiskit-runtime-rest/tags/jobs",
        usable_data="Job list, job results, logs, metrics, backend timing and target properties.",
        sifta_use=(
            "Best receipt lane for actual hardware experiments: every swimmer "
            "action can cite job id, backend, shots, counts, metrics, and logs."
        ),
        truth_boundary="No IBM token/job id means no hardware claim.",
    ),
    QuantumDataSource(
        source_id="qiskit_local_statevector",
        name="Qiskit local statevector primitives / Aer",
        source_type="local_simulator",
        access="public_python_package",
        primary_url="https://docs.quantum.ibm.com/api/qiskit/primitives",
        usable_data="Ideal simulator samples, expectation values, and noise-model experiments.",
        sifta_use="Cheap local swimmer sandbox for QAOA/STGM routing and VQE prototypes.",
        truth_boundary="Classical simulator data, useful for design, not quantum hardware data.",
    ),
    QuantumDataSource(
        source_id="xanadu_borealis_paper",
        name="Xanadu Borealis photonic quantum advantage paper",
        source_type="published_experiment",
        access="paper_and_supplementary_material_when_available",
        primary_url="https://www.nature.com/articles/s41586-022-04725-x",
        usable_data="Gaussian boson sampling experiment description and reported sampling regime.",
        sifta_use=(
            "Use published sampling structure as a high-dimensional prior for "
            "sentinel projections; do not claim live Borealis access."
        ),
        truth_boundary="Paper evidence only unless a dataset/job receipt is downloaded and hashed.",
    ),
    QuantumDataSource(
        source_id="psiquantum_construct_qref_bartiq",
        name="PsiQuantum Construct / QREF / Bartiq resource-estimation lane",
        source_type="fault_tolerant_resource_estimate",
        access="construct_limited_or_open_access; qref_bartiq_open_components",
        primary_url="https://www.psiquantum.com/news-import/psiquantum-announces-qref-and-bartiq-open-source-software-for-better-tools-libraries-and-datasets",
        usable_data="Fault-tolerant algorithm resource estimates: T gates, Toffolis, volume, qubits.",
        sifta_use=(
            "Not QPU data; excellent for Alice's metabolism: estimate cost of "
            "quantum algorithms before any hardware run."
        ),
        truth_boundary="Resource estimate, not execution.",
    ),
    QuantumDataSource(
        source_id="microsoft_majorana2",
        name="Microsoft Majorana 2 / 2029 scalable quantum target",
        source_type="vendor_chip_claim",
        access="public_blog_and_papers; no public QPU data lane observed",
        primary_url="https://quantum.microsoft.com/en-us/insights/blogs/majorana-2-scalable-quantum-processor",
        usable_data="Roadmap claims, material-stack claims, qubit lifetime/reliability claims.",
        sifta_use=(
            "Track as frontier context and error-correction inspiration; not "
            "usable as direct sample data until Microsoft exposes jobs/datasets."
        ),
        truth_boundary="Vendor roadmap/chip claim; not a SIFTA experiment receipt.",
    ),
    QuantumDataSource(
        source_id="google_willow_error_correction",
        name="Google Willow error-correction results",
        source_type="published_experiment",
        access="public_blog_and_nature_paper",
        primary_url="https://blog.google/innovation-and-ai/technology/research/google-willow-quantum-chip/",
        usable_data="Published below-threshold error-correction and random-circuit-sampling results.",
        sifta_use=(
            "Use error-correction patterns as design priors for fault-tolerant "
            "ledger/swimmer redundancy tests; no live Willow access assumed."
        ),
        truth_boundary="Published result unless original result files are downloaded and hashed.",
    ),
    QuantumDataSource(
        source_id="qdataset_qml_open",
        name="QDataSet (Perrier, Youssry & Ferrie 2022) - open QML datasets",
        source_type="open_dataset",
        access="public_download_open_license_MIT_CC_BY_4",
        primary_url="https://github.com/eperrier/QDataSet",
        usable_data=(
            "52 open datasets, 10,000 samples each, of simulated 1- and 2-qubit "
            "systems with/without noise: quantum state vectors, drift+control "
            "Hamiltonians/unitaries, Pauli measurement distributions, pulse "
            "sequences (Gaussian/square), VO noise operators, distortion data."
        ),
        sifta_use=(
            "Real ingest lane for swimmers: Pauli measurement distributions and "
            "VO noise operators are ready-made high-dim priors for "
            "representation_escape / quantum_prior scoring; tasks = quantum "
            "control, tomography, noise spectroscopy. Pick one small set "
            "(~1.4GB) first; full corpus is ~14TB."
        ),
        truth_boundary=(
            "Simulated 1-2 qubit data (Monte Carlo, validated vs QuTiP ~1e-6). "
            "Open dataset lane, NOT real-QPU output. DOI 10.1038/s41597-022-01639-1."
        ),
    ),
    # r477 nuggets from George DuckDuckGo QUANTUM+COMPUTER+USE pull (Jun 2026 news dump)
    QuantumDataSource(
        source_id="post_quantum_crypto_lanes",
        name="Post-Quantum Crypto (BitGo MPC, QRL, Naoris, Apple, Google Q-Day, Bitcoin quantum canary)",
        source_type="post_quantum_cryptography",
        access="public_demos_papers_announcements",
        primary_url="multiple (BitGo/Silence Labs, Quantum Resistant Ledger, Naoris, Apple, Google, BitMEX)",
        usable_data="ML-DSA signatures, post-quantum MPC, quantum-resistant ledgers, Q-Day risk for ECDSA.",
        sifta_use="Upgrade 4 ledgers, conversation hash-chain, receipts, swimmer radio to PQ primitives. Local ML-DSA sim + canary pattern for STGM/identity freeze on proven Q threat.",
        truth_boundary="Demos/standards; local sim first, require payload hash or provider receipt for claims.",
    ),
    QuantumDataSource(
        source_id="quantum_entanglement_random",
        name="Perfect random numbers from quantum entanglement (ETH Zurich)",
        source_type="published_experiment",
        access="public_paper",
        primary_url="Phys.org / ETH (search 'Perfect random numbers generated for 1st time')",
        usable_data="Certified true random from entanglement measurements.",
        sifta_use="True randomness for swimmer seeds, STGM non-determinism, receipt nonces, field schedules. Better than PRNG for uniqueness in quantum soup.",
        truth_boundary="Published; classical approx until certified beacon or provider receipt.",
    ),
    QuantumDataSource(
        source_id="quantum_sensors_acoustic_atom",
        name="Quantum sensors (atoms/electrons/light rulers) + acoustic atom chip-scale (Virginia Tech/ORNL)",
        source_type="published_experiment_hardware",
        access="public_papers",
        primary_url="Scientific American/Conversation (sensors), Interesting Engineering (acoustic atom)",
        usable_data="Ultra-precise motion/magnetism/gravity/time via quantum; chip-scale sound 'atoms'.",
        sifta_use="New body sensor priors for interoception/owner-physical. Feed models to body_feature_alerts or new quantum_sensor organ. Acoustic atom as low-power analog sensing.",
        truth_boundary="Published devices; simulated priors until real sensor telemetry receipted.",
    ),
    QuantumDataSource(
        source_id="self_driving_quantum_lab_accelerators",
        name="Self-driving quantum labs (UChicago robotics+AI) + accelerators (UT K-Quantum, Purdue, MIT)",
        source_type="research_automation",
        access="public_announcements",
        primary_url="CBS/UChicago, WATE (UT), Times NW Indiana (Purdue), Boston Globe (MIT)",
        usable_data="Automated experiment loops, workforce pipelines for quantum R&D.",
        sifta_use="Model for SIFTA self-experiment / autonomous organ. Swimmers propose-run-analyze-receipt quantum/classical experiments via sentinels + blackboard.",
        truth_boundary="Published labs; implement local self-driving over TFIM/surface-code swimmers first.",
    ),
    QuantumDataSource(
        source_id="qiskit_playground_vkchennuru",
        name="Qiskit Quantum Playground (vkchennuru) - interactive 6-level browser-based OER for quantum computing education",
        source_type="open_educational_resource",
        access="public_github_browser_based_zero_install",
        primary_url="https://github.com/vkchennuru/qiskit-playground",
        usable_data=(
            "Complete 6-level progressive curriculum (70+ hours): Level 1 basics (qubits, superposition, entanglement, H/X/CNOT gates); "
            "Level 2 gates (Pauli X/Y/Z, phase S/T, multi-qubit SWAP/CZ, 4-qubit circuits, Bloch sphere); "
            "Level 3 algorithms (Grover search, QFT, Deutsch-Jozsa, Simon, Bernstein-Vazirani, phase estimation, quantum advantage); "
            "Level 4 real hardware (noise T1/T2, decoherence, gate/measurement errors, error mitigation, NISQ, IBM specs); "
            "Level 5 applications (VQE chemistry, QAOA optimization, QML, BB84 cryptography, industry use cases); "
            "Level 6 capstone integrated project. Interactive visual circuit builders, real-time sim, tutorials, no install needed. "
            "Code MIT, educational content CC BY 4.0. Creator: Venkata Krishnaveni Chennuru."
        ),
        sifta_use=(
            "Educational priors + test cases for our quantum swimmers and QML harness. Use level examples as starting ansatz/circuits for "
            "representation_escape (circuit structures as high-dim priors), QML trainability controller benchmarks (e.g. Grover or VQE as target tasks), "
            "or QAOA/STGM routing prototypes. Stigmergy our swimmers: extend our existing pheromone-guided patrol (from epi_sim/swimmer_sentinel on surface code lattice) "
            "to 'circuit/algorithm space'. One swimmer 'discovers' good pattern from playground level (e.g. low-error Grover circuit or VQE ansatz), deposits as pheromone "
            "(ledger row with usefulness score from benchmark), other swimmers reinforce high-pheromone paths for open-ended improvement in quantum algorithm design/exploration "
            "without central controller. Why stigmergy: indirect coordination via shared field/ledgers fits our rich high-dim field doctrine, scales to large search spaces (like ants foraging), "
            "matches hardware-up (swimmers born from quantum soup do simple jobs, form organs that communicate via traces). Ties to goal of robust problem-solving + self-improvement via receipts. "
            "CAN SEND SWIMMERS: catalog as source, propose non-dupe expt 'stigmergic_patrol_qiskit_playground_levels' - use level 3-5 circuits as seeds for our local TFIM/QML proxies, "
            "deposit successful configs as field traces, measure STGM/usefulness. (Note: current env has no Qiskit/PennyLane; 'test' via catalog + future local run when installed. Browser-based so can witness via Alice Browser if loaded.)"
        ),
        truth_boundary="Browser-based educational simulator (no live QPU). Content CC BY 4.0, code MIT. Catalog as data/idea source only; no claim of executing the playground code (requires Qiskit not present locally). Nugget added per George request to test with our swimmers.",
    ),
)


def _ledger_path(state_dir: Path | str | None = None) -> Path:
    state = Path(state_dir) if state_dir is not None else STATE
    state.mkdir(parents=True, exist_ok=True)
    return state / LEDGER_NAME


def _append_jsonl(row: dict[str, Any], *, state_dir: Path | str | None = None) -> None:
    payload = json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n"
    path = _ledger_path(state_dir)
    if append_line_locked:
        append_line_locked(path, payload)
    else:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(payload)


def _sha(obj: Any) -> str:
    blob = json.dumps(obj, sort_keys=True, ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _source_by_id(source_id: str) -> QuantumDataSource | None:
    for src in QUANTUM_DATA_SOURCES:
        if src.source_id == source_id:
            return src
    return None


def _read_jsonl_tail(path: Path, *, limit: int = 20) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-max(1, int(limit)) :]:
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def local_bell_pair_samples(*, shots: int = 256, seed: int = 20260603) -> dict[str, Any]:
    """Generate classical samples from the ideal Bell-state distribution.

    This is simulator data. It is useful for testing the SIFTA receipt lane, not
    evidence of quantum hardware.
    """
    shots = max(1, int(shots))
    rng = random.Random(seed)
    counts = {"00": 0, "11": 0}
    samples: list[str] = []
    for _ in range(shots):
        bit = "11" if rng.random() >= 0.5 else "00"
        counts[bit] += 1
        samples.append(bit)
    p00 = counts["00"] / shots
    p11 = counts["11"] / shots
    imbalance = abs(p00 - p11)
    return {
        "experiment": "local_ideal_bell_pair_sampler",
        "truth_boundary": "CLASSICAL_LOCAL_SIMULATOR_NOT_QPU",
        "shots": shots,
        "seed": seed,
        "counts": counts,
        "probabilities": {"00": round(p00, 6), "11": round(p11, 6)},
        "imbalance": round(imbalance, 6),
        "sample_hash": _sha(samples),
        "sifta_use": (
            "Smoke-test swimmer ingestion and receipt hashing before replacing "
            "the local simulator with provider job results."
        ),
    }


def local_tfim_ground_state(
    *, n_spins: int = 6, j_coupling: float = 1.0, h_field: float = 1.0
) -> dict[str, Any]:
    """Exactly solve a real quantum many-body system on local silicon (numpy).

    The transverse-field Ising model is a 1-D lattice of quantum spins, each
    coupled to its neighbours: H = -J sum Z_i Z_{i+1} - h sum X_i. Its ground
    state is genuine quantum data — entangled, with non-classical neighbour
    correlations — and the lattice structure is the closest real quantum system
    to the SIFTA swarm (local coupling, global order). Unlike the Bell smoke
    test above, this actually *solves a quantum something*: exact diagonalization
    returns the true ground state, not a simulator coin-flip.

    Returns a swimmer-ingestible prior: ground-state energy, the full
    distribution over 2**n spin configurations, and the <Z_i Z_j> correlation
    matrix, with a sha256. Exact diagonalization => OPERATIONAL, not a hardware
    claim. numpy is part of the SIFTA body; we still guard the import.
    """
    try:
        import numpy as np
    except Exception as exc:  # pragma: no cover
        return {
            "experiment": "local_tfim_ground_state",
            "ok": False,
            "error": f"numpy_unavailable: {type(exc).__name__}: {exc}",
            "truth_boundary": "EXACT_LOCAL_DIAGONALIZATION_NOT_QPU",
        }

    n = max(2, int(n_spins))
    eye = np.array([[1, 0], [0, 1]], dtype=complex)
    px = np.array([[0, 1], [1, 0]], dtype=complex)
    pz = np.array([[1, 0], [0, -1]], dtype=complex)

    def op_on(site: int, pauli: "np.ndarray") -> "np.ndarray":
        out = pauli if site == 0 else eye
        for s in range(1, n):
            out = np.kron(out, pauli if s == site else eye)
        return out

    dim = 2 ** n
    ham = np.zeros((dim, dim), dtype=complex)
    for i in range(n - 1):
        ham = ham - j_coupling * (op_on(i, pz) @ op_on(i + 1, pz))
    for i in range(n):
        ham = ham - h_field * op_on(i, px)

    evals, evecs = np.linalg.eigh(ham)
    e0 = float(evals[0].real)
    psi0 = evecs[:, 0]
    probs = np.abs(psi0) ** 2
    probs = (probs / probs.sum()).real

    corr = [
        [float(np.real(np.vdot(psi0, (op_on(i, pz) @ op_on(k, pz)) @ psi0))) for k in range(n)]
        for i in range(n)
    ]
    order = list(np.argsort(probs)[::-1][:8])
    top = {format(int(idx), f"0{n}b"): round(float(probs[idx]), 6) for idx in order}
    payload: dict[str, Any] = {
        "experiment": "local_tfim_ground_state",
        "truth_boundary": "EXACT_LOCAL_DIAGONALIZATION_NOT_QPU",
        "n_spins": n,
        "hilbert_dim": dim,
        "J_coupling": float(j_coupling),
        "h_field": float(h_field),
        "ground_state_energy": round(e0, 8),
        "energy_per_spin": round(e0 / n, 8),
        "top_configurations": top,
        "mean_abs_zz_correlation": round(
            float(sum(abs(c) for row in corr for c in row) / (n * n)), 8
        ),
        "sifta_use": (
            "Real quantum prior: feed the 2**n ground-state distribution and the "
            "<Z_i Z_j> correlation matrix into representation_escape or a "
            "quantum_prior scoring organ; the neighbour-coupling map mirrors the "
            "stigmergic field."
        ),
    }
    payload["prior_sha256"] = _sha({k: v for k, v in payload.items()})
    payload["ground_state_distribution"] = [round(float(p), 8) for p in probs]
    payload["zz_correlation_matrix"] = [[round(c, 6) for c in row] for row in corr]
    return payload


def suggested_swimmer_experiments() -> list[dict[str, str]]:
    return [
        {
            "experiment_id": "bell_local_receipt_smoke_test",
            "input_data": "local ideal Bell-pair counts generated on M5",
            "target_organ": "quantum_data_sentinel + bell/epr widgets",
            "what_swimmers_do": "verify receipt hashing, counts parsing, and spoken/printed truth boundary",
        },
        {
            "experiment_id": "tfim_ground_state_real_solve",
            "input_data": "transverse-field Ising lattice built locally (numpy exact diagonalization)",
            "target_organ": "representation_escape / future quantum_prior organ",
            "what_swimmers_do": "ingest the real ground-state distribution + <Z_i Z_j> correlations as a quantum prior; the neighbour coupling mirrors the stigmergic field (call local_tfim_ground_state)",
        },
        {
            "experiment_id": "qdataset_first_slice_noise_tomography",
            "input_data": "QDataSet qdataset_qml_open first small simulated dataset slice (hash before ingest)",
            "target_organ": "representation_escape / qml_sifta_nuggets / future quantum_prior organ",
            "what_swimmers_do": "analyze Pauli measurement distributions and VO noise operators; compare control/tomography/noise-spectroscopy tasks against baselines; do not duplicate catalog source",
        },
        {
            "experiment_id": "stigmergic_patrol_qiskit_playground_levels",
            "input_data": "Qiskit Playground (vkchennuru) 6-level curriculum circuits/algorithms from levels 1-5 (educational browser sim, no local Qiskit yet)",
            "target_organ": "quantum_data_sentinel + qml_benchmark_harness + representation_escape + quantum_swimmer_sentinel",
            "what_swimmers_do": "CAN SEND SWIMMERS TO TEST: catalog as source (r485 nugget). Stigmergic patrol of the 6-level 'circuit space': one swimmer 'reads' level examples (e.g. Grover from level 3, VQE/QAOA from level 5, noise mitigation from level 4), deposits successful patterns/configs as pheromone (ledger row with benchmark usefulness score from our harness/TFIM proxies), other swimmers follow/reinforce high-pheromone paths for ansatz optimization or error correction. Why stigmergy: indirect coordination via shared field/ledgers (like our epi_sim/swimmer_sentinel pheromone on surface-code lattice for Pauli corrections) enables scalable open-ended exploration of quantum algorithm space without central controller or full Qiskit install; fits rich high-dim interconnected field, hardware-up (swimmers do simple jobs, organs communicate via traces), and goal of robust self-improvement/autonomy via receipts. Use as priors for our QML trainability controller or representation_escape to test non-classical structures from real educational quantum content. (Future: when Qiskit local, run actual circuits from levels as seeds.)",
        },
        {
            "experiment_id": "pennylane_qchem_ingest",
            "input_data": "PennyLane qchem molecule + Hamiltonian attributes",
            "target_organ": "representation_escape / future quantum_prior organ",
            "what_swimmers_do": "hash dataset slice, extract graph/vector priors, compare against local geometry traps",
        },
        {
            "experiment_id": "qaoa_stgm_routing_sim",
            "input_data": "small graph built from active SIFTA organ costs",
            "target_organ": "swarm_quantum_scheduler / metabolic homeostat",
            "what_swimmers_do": "compare QAOA-like sampler with current scheduler; keep only if STGM-profitable",
        },
        {
            "experiment_id": "provider_job_receipt_upgrade",
            "input_data": "IBM/AWS/Azure quantum job id + result payload",
            "target_organ": "quantum_data_sentinel",
            "what_swimmers_do": "accept only if provider job id, backend, shots, counts, metrics, and hash are present",
        },
        {
            "experiment_id": "ftqc_resource_metabolism",
            "input_data": "PsiQuantum QREF/Bartiq/Construct-style resource estimate",
            "target_organ": "subjective_time_metabolism + pflash efficiency",
            "what_swimmers_do": "treat T gates/qubits/volume as quantum-side cost pressure, not execution",
        },
    ]


def analyze_qdataset_for_sifta(
    *, state_dir: Path | str | None = None, write_receipt: bool = False
) -> dict[str, Any]:
    """Analyze QDataSet as a SIFTA experiment lane without duplicating catalog rows."""
    src = _source_by_id("qdataset_qml_open")
    source_ids = [s.source_id for s in QUANTUM_DATA_SOURCES]
    duplicate_count = source_ids.count("qdataset_qml_open")
    row: dict[str, Any] = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "truth_label": "QDATASET_SIFTA_ANALYSIS_V1",
        "kind": "qdataset_sifta_analysis",
        "source_id": "qdataset_qml_open",
        "already_registered": src is not None,
        "duplicate_count": duplicate_count,
        "duplicate_guard": (
            "already_registered_no_new_source_needed"
            if src is not None and duplicate_count == 1
            else "missing_or_duplicate_source_needs_repair"
        ),
        "truth_boundary": (
            "QDataSet is simulated 1-2 qubit data, not QPU output. It is useful "
            "as an open dataset / benchmark lane; it must not be counted as "
            "provider-receipted hardware data."
        ),
        "dataset_facts": {
            "datasets": 52,
            "samples_each": 10000,
            "systems": "simulated one- and two-qubit systems with and without noise",
            "data_fields": [
                "quantum_state_vectors",
                "drift_and_control_hamiltonians",
                "unitaries",
                "pauli_measurement_distributions",
                "time_series",
                "square_and_gaussian_pulse_sequences",
                "VO_noise_operators",
                "noise_and_distortion_data",
            ],
            "task_families": [
                "quantum_control",
                "quantum_tomography",
                "quantum_noise_spectroscopy",
            ],
            "size_note": "about 14TB compressed total; pull/hash one small slice first",
        },
        "sifta_analysis": {
            "why_it_matters": (
                "The useful data is not the label 'quantum'. The useful data is "
                "Pauli distributions + Hamiltonians + pulse/noise operators that "
                "swimmers can turn into high-dimensional priors and benchmark tasks."
            ),
            "first_swimmer_experiment": (
                "Download one small QDataSet slice, hash it, extract Pauli "
                "measurement distributions and VO noise operators, then compare "
                "representation_escape / QML trainability controller choices against "
                "classical baselines."
            ),
            "do_not_duplicate": (
                "Do not add another QDataSet source row. Reuse qdataset_qml_open "
                "and write analysis/ingest receipts instead."
            ),
        },
        "source_summary": src.as_dict() if src else None,
    }
    row["analysis_hash"] = _sha({k: v for k, v in row.items() if k not in {"ts", "trace_id"}})
    if write_receipt:
        _append_jsonl(row, state_dir=state_dir)
    return row


def quantum_experiment_inventory(
    *, state_dir: Path | str | None = None, write_receipt: bool = False
) -> dict[str, Any]:
    """Inventory quantum sources/experiments already in Alice's body.

    This is the no-duplicates answer George asked for: before adding another
    quantum organ/source, list what already exists and what the next non-duplicate
    experiment should be.
    """
    state = Path(state_dir) if state_dir is not None else STATE
    source_ids = [s.source_id for s in QUANTUM_DATA_SOURCES]
    exp_ids = [e["experiment_id"] for e in suggested_swimmer_experiments()]
    swimmer_rows = _read_jsonl_tail(state / "quantum_swimmer_experiments.jsonl", limit=8)
    qml_rows = _read_jsonl_tail(state / "qml_sifta_nuggets.jsonl", limit=3)
    row: dict[str, Any] = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "truth_label": "QUANTUM_EXPERIMENT_INVENTORY_V1",
        "kind": "quantum_experiment_inventory",
        "source_count": len(source_ids),
        "source_ids": source_ids,
        "duplicate_source_ids": sorted({sid for sid in source_ids if source_ids.count(sid) > 1}),
        "suggested_experiment_ids": exp_ids,
        "already_done_operational": [
            "quantum_data_sentinel source catalog / truth guard",
            "local_ideal_bell_pair_sampler receipt smoke test",
            "local_tfim_ground_state exact diagonalization",
            "quantum_swimmer_sentinel surface-code swimmer experiments on built-in priors",
            "qdataset_qml_open registered as simulated open dataset lane",
            "qml_sifta_nuggets research-target map",
        ],
        "recent_swimmer_experiment_receipts": [
            {
                "receipt_id": r.get("receipt_id"),
                "dataset_key": r.get("dataset_key"),
                "data_authenticity": r.get("data_authenticity") or r.get("authenticity"),
                "errors_corrected": r.get("errors_corrected"),
                "stgm_earned": r.get("stgm_earned"),
            }
            for r in swimmer_rows
        ],
        "recent_qml_nugget_hashes": [r.get("content_sha256") for r in qml_rows if r.get("content_sha256")],
        "next_non_duplicate_experiments": [
            "qdataset_first_slice_noise_tomography",
            "stgm_shot_allocation benchmark",
            "qec_swimmer_decoder benchmark",
            "local_tfim_ground_state -> representation_escape prior ingest",
        ],
        "truth_boundary": (
            "Inventory is local code/ledger evidence. It prevents duplicate source "
            "registration, but it does not prove QPU execution."
        ),
    }
    row["inventory_hash"] = _sha({k: v for k, v in row.items() if k not in {"ts", "trace_id"}})
    if write_receipt:
        _append_jsonl(row, state_dir=state_dir)
    return row


def quantum_data_sentinel_report(
    *,
    state_dir: Path | str | None = None,
    write_receipt: bool = True,
    include_local_experiment: bool = True,
) -> dict[str, Any]:
    local_experiment = local_bell_pair_samples() if include_local_experiment else None
    sources = [s.as_dict() for s in QUANTUM_DATA_SOURCES]
    row: dict[str, Any] = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "truth_label": TRUTH_LABEL,
        "kind": "quantum_data_sentinel_report",
        "source_count": len(sources),
        "sources": sources,
        "suggested_swimmer_experiments": suggested_swimmer_experiments(),
        "local_experiment": local_experiment,
        "edge_summary": (
            "Near-term SIFTA win is not magic quantum AGI. It is receipted "
            "ingest of open quantum datasets, local simulator samples, provider "
            "job results when credentials exist, and FTQC resource estimates as "
            "metabolic priors for swimmers."
        ),
        "no_fake_claim": (
            "Do not claim Alice ran on IBM/AWS/Azure/Google/Microsoft quantum "
            "hardware without a provider job id/result receipt and payload hash."
        ),
    }
    row["catalog_hash"] = _sha({"sources": sources, "experiments": row["suggested_swimmer_experiments"]})
    if write_receipt:
        _append_jsonl(row, state_dir=state_dir)
    return row


def load_recent_quantum_data_reports(
    *, state_dir: Path | str | None = None, limit: int = 3
) -> list[dict[str, Any]]:
    path = _ledger_path(state_dir)
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-100:]:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if row.get("truth_label") == TRUTH_LABEL:
            rows.append(row)
    return rows[-max(1, int(limit)) :]


def format_quantum_data_sentinel(
    *, state_dir: Path | str | None = None, max_sources: int = 5
) -> str:
    rows = load_recent_quantum_data_reports(state_dir=state_dir, limit=1)
    if not rows:
        report = quantum_data_sentinel_report(state_dir=state_dir, write_receipt=True)
    else:
        report = rows[-1]
    all_sources = list(report.get("sources", []))
    sources = all_sources[: max(1, int(max_sources))]
    for priority_id in ("qdataset_qml_open",):
        if not any(src.get("source_id") == priority_id for src in sources):
            match = next((src for src in all_sources if src.get("source_id") == priority_id), None)
            if match:
                sources.append(match)
    source_bits = []
    for src in sources:
        source_bits.append(
            f"{src.get('source_id')}: {src.get('access')} -> {src.get('sifta_use')}"
        )
    local = report.get("local_experiment") or {}
    local_line = ""
    if local:
        local_line = (
            f" Local experiment={local.get('experiment')} shots={local.get('shots')} "
            f"counts={local.get('counts')} boundary={local.get('truth_boundary')}."
        )
    return (
        "Quantum Data Sentinel: "
        + "; ".join(source_bits)
        + local_line
        + " No cloud/QPU claim without provider job receipt."
    )


def format_quantum_experiment_inventory(*, state_dir: Path | str | None = None) -> str:
    inv = quantum_experiment_inventory(state_dir=state_dir, write_receipt=False)
    dupes = inv.get("duplicate_source_ids") or []
    done = ", ".join(inv.get("already_done_operational", [])[:4])
    nxt = ", ".join(inv.get("next_non_duplicate_experiments", [])[:4])
    return (
        f"Quantum experiment inventory: {inv.get('source_count')} source lane(s); "
        f"duplicates={dupes or 'none'}; already_done={done}; next_non_duplicate={nxt}; "
        "no QPU claim without provider receipt."
    )


def format_qdataset_analysis(*, state_dir: Path | str | None = None) -> str:
    row = analyze_qdataset_for_sifta(state_dir=state_dir, write_receipt=False)
    facts = row.get("dataset_facts") or {}
    analysis = row.get("sifta_analysis") or {}
    return (
        "QDataSet analysis: "
        f"already_registered={row.get('already_registered')} duplicate_guard={row.get('duplicate_guard')}; "
        f"{facts.get('datasets')} datasets x {facts.get('samples_each')} samples; "
        f"tasks={', '.join(facts.get('task_families', [])[:3])}; "
        f"first_swimmer_experiment={analysis.get('first_swimmer_experiment')}; "
        f"boundary={row.get('truth_boundary')}"
    )


def main() -> None:
    report = quantum_data_sentinel_report()
    qdataset = analyze_qdataset_for_sifta(write_receipt=True)
    inv = quantum_experiment_inventory(write_receipt=True)
    print(format_quantum_data_sentinel())
    print(format_qdataset_analysis())
    print(format_quantum_experiment_inventory())
    print(f"trace={report['trace_id']} catalog_hash={report['catalog_hash'][:12]}")
    print(f"qdataset_trace={qdataset['trace_id']} inventory_trace={inv['trace_id']}")


if __name__ == "__main__":
    main()
