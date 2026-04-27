# SIFTA Protein Folding Proof Apps

For the Swarm. This index lists only the OS apps that prove protein-folding
mechanics through executable code and generated artifacts. It deliberately
excludes raw toy helpers, one-off scripts, and non-folding simulations.

## Launch Path

Open SIFTA OS, then:

```text
Programs -> Simulations
```

## 1. Stigmergic Fold Swarm (Ca / Go)

- **OS name:** `Stigmergic Fold Swarm (Cα / Go)`
- **Entry:** `Applications/fold_swarm_widget.py`
- **Backend:** `Applications/fold_swarm_sim.py`
- **Signature:** `C55M-AUDITED-PROTEIN-FOLDING-PROOF`
- **What it proves:** C-alpha folding search using a Go-model native-contact
  funnel, WCA sterics, obstacles, pheromone-biased Monte Carlo, energy/Q/Rg
  telemetry, SHA swimmer bodies, and Ed25519 checkpoints.
- **Terminal launch:**

```bash
cd /Users/ioanganton/Music/ANTON_SIFTA
PYTHONPATH=. python3 Applications/fold_swarm_widget.py
```

## 2. AG31 + C46S - PoUW Fold-Swarm Simulation

- **OS name:** `AG31 + C46S - PoUW Fold-Swarm Simulation`
- **Entry:** `Applications/fold_swarm_pouw_sim.py`
- **Signature:** `AG31-C46S-VERIFIED`
- **What it proves:** protein folding as Proof-of-Useful-Work: Lennard-Jones
  12-6, harmonic bonds, Metropolis annealing, ACO stigmergy, and STGM receipts
  when useful fold improvements are measured.
- **Terminal launch:**

```bash
cd /Users/ioanganton/Music/ANTON_SIFTA
PYTHONPATH=. python3 Applications/fold_swarm_pouw_sim.py
```

## 3. C55M + George - Protein Fold Colosseum

- **OS name:** `C55M + George - Protein Fold Colosseum`
- **Entry:** `Applications/sifta_protein_folder_widget.py`
- **Engine:** `System/sifta_hp_lattice_folder.py`
- **Broker:** `System/sifta_protein_folding_broker.py`
- **Signature:** `C55M-GEORGE-COSIGNED`
- **What it proves:** a second independent folding source: deterministic 3D
  hydrophobic-polar lattice beam search, batch folding, PDB output, metadata,
  and structure hashes for referee comparison.
- **Terminal launch:**

```bash
cd /Users/ioanganton/Music/ANTON_SIFTA
PYTHONPATH=. python3 Applications/sifta_protein_folder_widget.py --batch --beam 1024
```

## Support Modules, Not Apps

- `System/sifta_protein_referee.py` — Kabsch RMSD and 3-way triangulation.
- `System/sifta_protein_folding_broker.py` — routes engines and writes
  metadata.

## Excluded From This Proof List

- `System/sifta_peptide_backbone_demo.py` raw demo helper.
- Broker `engine="toy"` mode.
- Non-protein apps such as Physarum, Primordial Field, Slime-Mold Bank, and
  Artificial General Intelligence.

## Honesty Boundary

These apps prove local folding mechanics, artifacts, and cross-engine
verification. They are not claiming clinical or AlphaFold-grade biological
prediction unless a real external predictor backend is installed and its output
is validated by the referee.
