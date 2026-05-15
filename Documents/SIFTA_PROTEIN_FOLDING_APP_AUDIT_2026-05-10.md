# SIFTA Protein Folding App Audit

**Date:** 2026-05-10  
**Doctor:** CG55M@cursor, GPT-5.5 Medium  
**Lane:** Auditor / proof report  
**Scope:** Four local fold/protein apps plus broker/referee support modules.

## Verdict

The protein folding lane is real executable software, but the strongest defensible claim is precise:

SIFTA has **local protein-folding proof engines**, **PDB artifact generation**, **truth-labeled broker receipts**, **AlphaFold DB integration**, and a **multi-metric referee** that can compare structures and reject bad comparisons. It does **not** currently prove that SIFTA beats AlphaFold 2/3 in biological prediction accuracy or general protein modeling.

The honest commercial line is:

> SIFTA complements DeepMind/OpenFold by wrapping structure prediction and toy/local folding work in a sovereign, receipt-first, proof-of-useful-work operating layer: local execution, hashes, attribution metadata, app focus traces, STGM receipts, and referee checks.

## Apps Tested

| App / module | Role | Result |
|---|---|---|
| `Applications/fold_swarm_widget.py` | Qt app for C-alpha Go-model fold swarm | PASS |
| `Applications/fold_swarm_pouw_sim.py` | Qt app for PoUW fold swarm, LJ/Metropolis/ACO/STGM receipts | PASS |
| `Applications/fold_swarm_sim.py` | Backend for Go-model fold swarm | PASS |
| `Applications/sifta_protein_folder_widget.py` | Protein Fold Colosseum, HP lattice + broker + PDB viewer | PASS |

Manifest note: `Applications/apps_manifest.json` explicitly registers three active protein proof apps. `fold_swarm_sim.py` is the backend for `fold_swarm_widget.py`, not a separate manifest app, but it was tested because it is one of the four fold/protein files on disk.

## Commands Run

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=. python3 -m pytest -q \
  tests/test_sifta_protein_folder_widget.py \
  tests/test_sifta_protein_folding_broker.py \
  tests/test_sifta_protein_referee.py \
  tests/test_swarm_gpu_protein_renderer.py
```

Result:

```text
26 passed in 2.27s
```

```bash
PYTHONPATH=. python3 -m py_compile \
  Applications/fold_swarm_widget.py \
  Applications/fold_swarm_pouw_sim.py \
  Applications/fold_swarm_sim.py \
  Applications/sifta_protein_folder_widget.py \
  System/sifta_protein_folding_broker.py \
  System/sifta_protein_referee.py \
  System/sifta_hp_lattice_folder.py \
  System/sifta_peptide_backbone_demo.py
```

Result: PASS, no compile errors.

## Offscreen Smoke Results

### 1. Stigmergic Fold Swarm

`FoldSwarmWidget` constructed successfully offscreen and its `FoldSwarmSim` backend ran 40 steps.

```json
{
  "status": "ok",
  "backend": "FoldSwarmSim",
  "initial_energy": 1.54,
  "final_energy_after_40_steps": -2.3839,
  "initial_Q": 0.0,
  "final_Q_after_40_steps": 0.0833,
  "history_len": 40,
  "native_pairs": 12
}
```

What this proves: the Go-model/WCA/pheromone Monte Carlo backend runs and moves toward lower energy on the tested seed. It is a simplified C-alpha model, not an AlphaFold replacement.

### 2. PoUW Fold-Swarm Simulation

`PredatorSimWindow` constructed successfully offscreen and ran 120 steps.

```json
{
  "status": "ok",
  "initial_best_energy": 1726299802356.9043,
  "final_best_energy_after_120_steps": 275.5571,
  "receipt_mint_ok": true,
  "receipt_chain_len": 1,
  "total_stgm": 0.05
}
```

What this proves: the LJ/Metropolis/ACO visualization and receipt chain work. The huge initial energy is from an unstable random starting geometry; the simulation rapidly relaxes it. During the smoke test, a real PoUW/STGM mint message was emitted by the local SIFTA economy path. That is a receipt-side effect of testing, not a new scientific discovery.

### 3. Raw `FoldSwarmSim`

The backend ran 120 steps with a smaller deterministic config and checkpoint interval of 50.

```json
{
  "status": "ok",
  "tick": 120,
  "initial_energy": 1.012,
  "final_energy": -1.6197,
  "final_Q": 0.1,
  "final_Rg": 4.5551,
  "checkpoints": 2,
  "swimmer_hash_sample": "d30b333be61c982c7b6f"
}
```

What this proves: backend swimmers produce body hashes and Ed25519 checkpoint attempts, and the search produces lower energy on this deterministic run.

### 4. Protein Fold Colosseum

`ProteinFolderWidget` constructed successfully offscreen. The deterministic HP lattice broker folded `ACFLIVGPGKTYL`.

```json
{
  "status": "ok",
  "engine": "c55m_hp_lattice",
  "truth_label": "c55m_george_hp_lattice_beam_search",
  "energy": -4,
  "hydrophobic_contacts": 4,
  "states_expanded": 6885,
  "pdb_exists": true,
  "pdb_bytes": 1155,
  "structure_hash": "567d4698f754d132"
}
```

What this proves: SIFTA can deterministically turn a short sequence into a PDB artifact with a stable structure hash and truth label.

## Local Batch Result

At beam width 96, the local HP lattice engine folded the default six-protein panel in 0.41 seconds.

| Name | Length | Energy | H contacts | States expanded | Time |
|---|---:|---:|---:|---:|---:|
| `sifta_demo_peptide` | 13 | -4 | 4 | 799 | 0.04s |
| `oxytocin_like_nonapeptide` | 9 | -3 | 3 | 415 | 0.01s |
| `insulin_a_chain` | 21 | -10 | 10 | 1567 | 0.06s |
| `insulin_b_chain` | 30 | -14 | 14 | 2431 | 0.11s |
| `calmodulin_fragment` | 30 | -11 | 11 | 2431 | 0.11s |
| `albumin_signal_fragment` | 24 | -11 | 11 | 1855 | 0.08s |

This is the "faster" claim that is currently defensible: **SIFTA can produce simplified deterministic local fold artifacts for short sequences in milliseconds to sub-second time.** It is not comparable to AlphaFold accuracy because HP lattice folding is a coarse model.

## AlphaFold DB Probe

SIFTA's broker successfully fetched AlphaFold DB entry `P69905` through the `alphafold_db` backend.

```json
{
  "status": "ok",
  "truth_label": "alphafold2_ebi_database",
  "source": "https://alphafold.ebi.ac.uk/files/AF-P69905-F1-model_v6.pdb",
  "reference": "Jumper et al. Nature 596(7873) 2021",
  "pdb_exists": true,
  "pdb_bytes": 92096,
  "compliance_license": "CC-BY-4.0",
  "requires_attribution": true,
  "elapsed_seconds": 0.46
}
```

This is the complement path: SIFTA can ingest a real AlphaFold DB structure, preserve attribution/compliance metadata, hash the PDB, and route it into local verification/referee tools.

## What SIFTA Solved

SIFTA did **not** solve "protein folding" in the DeepMind sense of high-accuracy general structure prediction across biology.

SIFTA did solve a different useful layer:

1. **A local execution envelope** for folding experiments inside the SIFTA OS.
2. **Multiple simplified engines** with different assumptions: Go-model/WCA/pheromone search, LJ/Metropolis/ACO, toy CA Monte Carlo, HP lattice beam search.
3. **Truth labels** that mark toy/local/AlphaFold/ESMFold/backend-unavailable results instead of pretending all outputs are equal.
4. **PDB artifacts and metadata** that can be hashed, stored, compared, and audited.
5. **Referee metrics**: Kabsch RMSD, approximate TM-score, contact-map precision/recall, pairwise and N-way consensus/outlier logic.
6. **Proof-of-useful-work hooks**: fold improvements and artifacts can become receipt-bearing work units inside the STGM economy.

## How SIFTA Complements DeepMind / AlphaFold / OpenFold

AlphaFold 3 is the frontier predictor. The 2024 Nature paper describes a diffusion-based model that predicts biomolecular complexes involving proteins, nucleic acids, ligands, ions, and modified residues. SIFTA should not claim to outpredict it.

OpenFold is the open-source/retrainable AlphaFold-style lane. OpenFold and OpenFold3-preview are the best technical collaboration targets if the goal is "ants doing useful work" on open structure prediction infrastructure.

SIFTA's role is the operating and verification layer around predictors:

- Run local coarse models cheaply before waking expensive models.
- Submit or cache real predictor outputs with attribution.
- Compare multiple engines with TM-score/contact-map referee checks.
- Turn useful folding jobs into signed, auditable PoUW receipts.
- Preserve provenance: who ran what, when, on which hardware, with which backend and license.

## What To Tell Carlton

Use this line:

> We do not claim to beat AlphaFold at biological prediction. We claim SIFTA is a receipt-first local operating system for scientific work. In protein folding, it can run local fold engines, fetch AlphaFold DB structures with attribution, produce PDB artifacts, compare structures with scientific metrics, and mint proof-of-useful-work when useful computation is verified.

Use this demo order:

1. Open `C55M + George - Protein Fold Colosseum`.
2. Fold `ACFLIVGPGKTYL` with HP lattice and show PDB/hash/energy.
3. Open `Stigmergic Fold Swarm` and show live energy/Q/Rg improving.
4. Show `System/sifta_protein_referee.py` tests passing.
5. Show AlphaFold DB P69905 receipt metadata and CC-BY attribution.
6. Say the big line: "DeepMind predicts; SIFTA remembers, verifies, receipts, routes, and pays useful work."

## Research Spine Pulled

- AlphaFold 3: Abramson et al., "Accurate structure prediction of biomolecular interactions with AlphaFold 3", Nature 2024.
- AlphaFold 2 / AlphaFold DB: Jumper et al., Nature 2021; EMBL-EBI AlphaFold Protein Structure Database.
- OpenFold: "OpenFold: retraining AlphaFold2 yields new insights into its learning mechanisms and capacity for generalization", Nature Methods 2024.
- TM-score / TM-align: Zhang & Skolnick 2004; TM-align NAR 2005. TM-score above 0.5 generally indicates same fold.
- Kabsch alignment: optimal rigid-body molecular superposition.
- CASP-style contact-map comparison: topological fold agreement beyond raw RMSD.

## Claim Boundary

**Allowed:**

- "SIFTA has executable protein folding proof apps."
- "SIFTA produces local PDB artifacts and metadata."
- "SIFTA can fetch AlphaFold DB structures and preserve CC-BY attribution."
- "SIFTA can compare structures with TM-score/contact maps/Kabsch RMSD."
- "SIFTA can turn verified useful folding work into STGM receipts."
- "SIFTA folded the six short default HP-lattice panel locally in 0.41 seconds at beam 96."

**Not allowed yet:**

- "SIFTA beats AlphaFold."
- "SIFTA solved clinical protein folding."
- "SIFTA discovered a medicine."
- "SIFTA unfolded proteins faster than DeepMind" without a matched benchmark, same sequence, same target, same metric, same hardware, and ground-truth structure.
- "STGM mint equals biological validity."

## Next Real Benchmark

The clean next proof is a matched benchmark:

1. Pick 10 short public proteins with known experimental structures.
2. Run SIFTA HP lattice / toy / Go-model, ESMFold, and AlphaFold DB where available.
3. Compare every output against experimental PDB with TM-score, RMSD, and contact overlap.
4. Record wall-clock, energy, hashes, receipts, backend labels, and license metadata.
5. Publish a truth table: speed, cost, accuracy, and epistemic flag.

That benchmark would turn the current proof apps into an investor-safe scientific demo.
