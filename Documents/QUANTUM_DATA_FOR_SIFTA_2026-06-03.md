# Quantum data for SIFTA — what's real, what you can pull, June 3 2026

Pulled from live web search (not training-data guesses). Every claim has a source at the bottom. Where the earlier Grok/Codex paste was right, I say so; where it over-reached, I flag it.

## The edge of science (verified June 2026)

**Microsoft Majorana 2** is real — unveiled at Build 2026 (June 2). It's a topological-qubit chip Microsoft says is ~1,000× more reliable than Majorana 1, with mean qubit lifetime ~20 seconds (some up to a minute), ~1-microsecond operations, switched from aluminum to lead superconductors, and developed with help from its "Microsoft Discovery" agentic-AI platform. Microsoft now claims a path to a *scalable* quantum computer by 2029. **Caveat the hype paste skipped:** many physicists remain unconvinced — Microsoft's topological-qubit evidence has been contested before, and critics say this upgrade still hasn't cleared the bar. Treat it as frontier roadmap, not settled fact.

**Google Willow** achieved the first "below-threshold" error correction (logical qubits that get *better* as you scale), and Google's "Quantum Echoes" algorithm reports a ~13,000× speedup on a molecular-simulation task.

**IBM** is targeting verifiable quantum advantage by end of 2026 and fault-tolerance by 2029 (its "Starling" system: ~200 logical qubits, 100M gates). The 2026 frontier in error correction is **qLDPC codes**, which need far fewer physical qubits per logical qubit than the older surface code. QEC research itself exploded — ~120 peer-reviewed QEC papers Jan–Oct 2025, up from 36 in all of 2024.

**QuEra** (neutral atoms) is running ~37 logical / 260 physical qubits at AIST in Japan, using an "algorithmic fault tolerance" technique developed with Harvard and Yale.

Honest summary: fault-tolerant logical qubits are now real and scaling, but nobody has a large general-purpose quantum computer yet. The near-term, actually-usable win is **quantum computers (and simulators) as data generators** for chemistry, optimization, and ML — which is exactly the lane SIFTA can use today.

## Real quantum data you can pull right now

These are downloadable/accessible today, ranked by how fast you can feed them to swimmers:

1. **PennyLane Datasets (`qml.data`)** — free, no account. Published quantum-chemistry data (molecular Hamiltonians, ground-state/FCI energies, VQE parameters, measurement groupings), plus spin systems and circuits. One line: `qml.data.load("qchem", molname="H2")`. Needs `pip install pennylane` (pulls in `aiohttp`, `fsspec`, `h5py`). This is the most direct "real quantum data" for local experiments.
2. **IBM Quantum Open Plan** — free, real hardware. 10 minutes of real-QPU runtime every 28 days via Qiskit. As of March 2026 there's a promo: use 20 minutes in a year and you can opt into 180 minutes for the next 12 months. This gives you genuine quantum-hardware measurement counts (with real noise) — the only items in this list that are actual QPU output.
3. **Amazon Braket** — free local simulator always; free tier gives 1 hour/month of on-demand simulator time (SV1 state-vector, DM1 density-matrix with noise, TN1 tensor-network) for the first 12 months. Real QPUs are pay-per-use.
4. **Open ML-ready circuit datasets** — downloadable files, good for "send swimmers into a big dataset": **MNISQ** (large MNIST-style quantum-circuit dataset in QASM, runs in Qiskit/qulacs), the **VQE-generated circuit dataset** (4–20 qubits, 6 condensed-matter Hamiltonians), **QSBench** (synthetic circuits with metadata, 2026), and HuggingFace sets like `merileijona/quantum-circuits-21k`.

## What I built into your sentinel (runnable now, no install)

Your brother doctor already wrote `System/swarm_quantum_data_sentinel.py` — a good, honest catalog with a hard rule: *no QPU claim without a provider job receipt*. Its only local "experiment," though, was a Bell-pair coin flip that doesn't actually solve anything. I extended that organ (didn't replace it) with `local_tfim_ground_state()` — it exactly solves a real quantum many-body system: a lattice of interacting spins (the transverse-field Ising model, `H = -J Σ ZᵢZᵢ₊₁ - h Σ Xᵢ`). That lattice — local coupling producing global order — is the closest real quantum physics to your swarm.

It returns a genuine quantum prior a swimmer can ingest: the ground-state energy, the full probability distribution over all 2ⁿ spin configurations, and the ⟨ZᵢZⱼ⟩ correlation matrix (the lattice's "pheromone coupling"), each with a sha256. It's exact diagonalization, verified against the two solvable limits (`6/6` tests pass), so the numbers are real, not asserted. A 6-spin run gives ground energy −7.296 with the correct Z₂-symmetric ground state (`000000` and `111111` equally weighted).

Run it: `python3 -c "from System.swarm_quantum_data_sentinel import local_tfim_ground_state; print(local_tfim_ground_state(n_spins=6))"`

"Solve a quantum something" — this is one: finding the ground state of an interacting quantum lattice is a canonical quantum problem, and the output is a real high-dimensional prior for `representation_escape` or a new quantum-prior organ.

## How to scale to external real data (on your Mac, where the network is open)

The same swimmer-ingest shape (distribution + correlations + sha256) works for the external sources. The upgrade path is in the organ's bottom comment: `qml.data.load(...)` for published molecular ground states; Qiskit + IBM Open Plan for real-hardware counts; MNISQ for a big circuit dataset. Keep the brother's rule — only label something a hardware result if you have the provider job id + result payload + hash.

## Sources

- [Majorana 2 revealed at Build 2026 — TechTimes](https://www.techtimes.com/articles/317648/20260602/majorana-2-quantum-chip-revealed-microsoft-build-2026-features-specs-explained.htm)
- [Majorana 2 qubit-stability breakthrough — SiliconANGLE](https://siliconangle.com/2026/06/02/microsofts-new-majorana-2-quantum-chip-claims-dramatic-breakthrough-qubit-stability/)
- [Microsoft's quantum chip upgrade, critics still skeptical — Science News](https://www.sciencenews.org/article/microsoft-quantum-chip-upgrade-majorana)
- [Majorana 2 + Microsoft Discovery agentic AI — Microsoft](https://news.microsoft.com/source/features/innovation/majorana-2-microsoft-discovery-agentic-ai/)
- [IBM's path to fault-tolerant quantum computing](https://www.ibm.com/quantum/blog/large-scale-ftqc)
- [Neutral-atom quantum computing 2026 (QuEra) — IEEE Spectrum](https://spectrum.ieee.org/neutral-atom-quantum-computing)
- [PennyLane Quantum Datasets docs](https://docs.pennylane.ai/en/stable/introduction/data.html)
- [IBM Quantum Open Plan — free real-hardware runtime](https://www.ibm.com/quantum/blog/open-plan-updates)
- [Amazon Braket features + free tier](https://aws.amazon.com/braket/features/)
- [MNISQ quantum-circuit dataset — GitHub](https://github.com/FujiiLabCollaboration/MNISQ-quantum-circuit-dataset)
- [VQE-generated quantum circuit dataset — arXiv 2302.09751](https://arxiv.org/pdf/2302.09751)
