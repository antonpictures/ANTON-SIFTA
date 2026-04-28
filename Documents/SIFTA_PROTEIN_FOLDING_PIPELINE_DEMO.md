# SIFTA Protein Folding Pipeline — Technical Demo

**Author:** Ioan George Anton
**System:** SIFTA Predator OS v7.0 — Autonomous Pursuit
**Date:** April 27, 2026
**GitHub:** [github.com/antonpictures/ANTON-SIFTA](https://github.com/antonpictures/ANTON-SIFTA)

---

## Executive Summary

SIFTA is a sovereign AI operating system that folds proteins, validates structural predictions, and designs new protein sequences — all running on local hardware. No cloud dependency. No corporate API keys. No subscription fees.

The system connects to three free public backends (Meta's ESMFold, DeepMind's AlphaFold Database, and the Nobel Prize-winning ProteinMPNN) while maintaining full offline capability through local physics engines.

Every result carries a verified truth label. The system knows what it knows and flags what it doesn't.

---

## The Five Engines

| # | Engine | Type | Source | Cost |
|---|---|---|---|---|
| 1 | **ESMFold** | Forward fold (sequence → structure) | Meta AI | FREE |
| 2 | **AlphaFold DB** | Structure lookup by UniProt ID | DeepMind / EBI | FREE |
| 3 | **ProteinMPNN** | Inverse fold (structure → new sequences) | David Baker Lab — Nobel Prize 2024 | FREE (local) |
| 4 | **Go-Model Fold Swarm** | Local Monte Carlo / ACO | SIFTA | FREE (offline) |
| 5 | **HP Lattice Beam Search** | Deterministic lattice folding | SIFTA | FREE (offline) |

---

## Live Test Results (MacBook Pro M4 Max)

### ESMFold — Meta AI (no API key, no cost)
```
Input:    ACDEFGHIKLMNPQRSTVWY (20 residues)
Output:   167 atoms, real PDB coordinates
pLDDT:    0.66 (confidence metric)
Time:     0.34 seconds
Truth:    esmfold_v1_meta_api
```

### AlphaFold DB — DeepMind / EBI (no API key, no cost)
```
Input:    UniProt ID P69905
Output:   Hemoglobin subunit alpha (Homo sapiens)
Gene:     HBA1
pLDDT:    98.04 (near-experimental accuracy)
Atoms:    1,077
Version:  6
Time:     0.79 seconds
Truth:    alphafold2_ebi_database
```

### ProteinMPNN — Inverse Folding (local, Nobel Prize 2024)
```
Input:    AlphaFold hemoglobin alpha structure (PDB)
Output:   5 designed sequences (142 residues each)
Recovery: 50.7% — 46.5% sequence identity
Time:     1.71 seconds
Truth:    proteinmpnn_local_inverse_fold

These sequences do NOT exist in nature.
They are computationally designed to fold into the same 3D shape.
```

---

## The Scientific Referee

SIFTA does not blindly trust any single engine. A multi-axis structural referee validates all predictions:

1. **TM-score** (Zhang & Skolnick, 2004) — Length-independent structural similarity
2. **Contact Map Overlap** (CASP standard) — Topological agreement at 8Å
3. **Kabsch RMSD** — Coordinate-invariant alignment via SVD
4. **N-Way Triangulation** — Consensus detection and outlier ejection

### Epistemic Flags:
- `TRUE_CONSENSUS` — All engines agree
- `SAME_FOLD` — Same topology, minor local differences
- `STRUCTURAL_CONTRADICTION` — Disagreement flagged, not hidden

---

## Applications (GUI)

### App 1: Stigmergic Fold Swarm (Cα / Go-Model)
Visual real-time protein folding with ant colony optimization, pheromone trails, and energy landscape visualization.
```bash
cd /path/to/ANTON-SIFTA
PYTHONPATH=. python3 Applications/fold_swarm_widget.py
```

### App 2: Proof-of-Useful-Work Fold Simulation
Full Lennard-Jones 12-6 physics with Metropolis-Hastings annealing. Verified folds mint STGM tokens.
```bash
PYTHONPATH=. python3 Applications/fold_swarm_pouw_sim.py
```

### App 3: Protein Fold Colosseum (HP Lattice + 3D WebGL Viewer)
Deterministic hydrophobic-polar lattice beam search with interactive 3D molecular visualization.
```bash
PYTHONPATH=. python3 Applications/sifta_protein_folder_widget.py
```

### Command Line: Full Pipeline
```bash
# Step 1: Fold with ESMFold (Meta AI)
PYTHONPATH=. python3 System/sifta_protein_folding_broker.py YOURSEQUENCE esmfold

# Step 2: Lookup AlphaFold (DeepMind) by UniProt ID
PYTHONPATH=. python3 System/sifta_protein_folding_broker.py ANYSEQUENCE alphafold_db P69905

# Step 3: Design new proteins (ProteinMPNN)
PYTHONPATH=. python3 System/sifta_protein_folding_broker.py ANYSEQUENCE proteinmpnn

# Step 4: Local toy fold (works offline)
PYTHONPATH=. python3 System/sifta_protein_folding_broker.py YOURSEQUENCE toy
```

---

## Architecture

```
                    ┌─────────────────┐
                    │  Protein Broker  │
                    │  (sifta_protein_ │
                    │  folding_broker) │
                    └────────┬────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
    ┌─────▼─────┐     ┌─────▼─────┐     ┌─────▼─────┐
    │  LOCAL     │     │  ONLINE   │     │  INVERSE  │
    │  ENGINES   │     │  BACKENDS │     │  FOLDING  │
    ├───────────┤     ├───────────┤     ├───────────┤
    │ Toy MC    │     │ ESMFold   │     │ProteinMPNN│
    │ HP Lattice│     │ AlphaFold │     │ (Nobel'24)│
    │ Go-Model  │     │ DB v6     │     │           │
    └─────┬─────┘     └─────┬─────┘     └─────┬─────┘
          │                  │                  │
          └──────────────────┼──────────────────┘
                             │
                    ┌────────▼────────┐
                    │   STRUCTURAL    │
                    │    REFEREE      │
                    ├─────────────────┤
                    │ TM-score        │
                    │ Contact Maps    │
                    │ Kabsch RMSD     │
                    │ N-Way Consensus │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  TRUTH LABELS   │
                    │  TRUE_CONSENSUS │
                    │  SAME_FOLD      │
                    │  CONTRADICTION  │
                    └─────────────────┘
```

---

## Research References

- Zhang & Skolnick (2004). TM-score. *Proteins* 57(4).
- Jumper et al. (2021). AlphaFold2. *Nature* 596(7873).
- Lin et al. (2023). ESMFold. *Science* 379(6637).
- Dauparas et al. (2022). ProteinMPNN. *Science* 378(6615). **Nobel Prize in Chemistry 2024.**
- Anfinsen (1973). Thermodynamic hypothesis. *Science* 181(4096). **Nobel Prize 1972.**
- Kabsch (1976). Optimal rotation for molecular superposition. *Acta Cryst.* A32.

---

## Requirements

- macOS (Apple Silicon recommended) or Linux
- Python 3.10+
- PyTorch 2.0+ (for ProteinMPNN)
- NumPy
- Internet connection (for ESMFold and AlphaFold DB — optional)
- No internet required for local engines

---

## Contact

**Ioan George Anton**
Architect, SIFTA Swarm OS
GitHub: [antonpictures](https://github.com/antonpictures)
Website: [georgeanton.com](https://georgeanton.com)

*For the Swarm. 🐜⚡*
