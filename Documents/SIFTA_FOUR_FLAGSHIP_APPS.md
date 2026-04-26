# SIFTA OS — The Four Flagship Apps

> Triple-IDE Doctor signed presentation, polished by **CG55M Dr Cursor / Claude Opus 4.7**.
>
> Code correctness lane: **C55M Dr Codex / GPT-5.5**.
> Physics + receipt-binding lane: **AG31** (Antigravity orchestrator).
> Auxiliary lane: **C46S Dr Cursor Sonnet 4.6**.
>
> Ratified protocol: [`Documents/IDE_DOCTOR_SIGNATURE_PROTOCOL.md`](IDE_DOCTOR_SIGNATURE_PROTOCOL.md).

This document is the canonical, single-page tour of the four flagship simulations that ship with SIFTA OS. Every app shares the same Doctor Sigil Bar at the top of its canvas (`Applications/_doctor_sigil_chrome.py`) so you can tell at a glance who built what and which lane signed it off. Each app does *real* work — every "mint" event is bound to a measurable physical or graph-theoretic quantity, never a random number generator.

---

## Doctor Code Legend

| Code  | IDE / Model                          | Color   | Lane          |
| :---- | :----------------------------------- | :------ | :------------ |
| AG31  | Antigravity orchestrator (STIGDISTRO) | Gold    | Physics + Receipts |
| C46S  | Cursor / Sonnet 4.6                  | Cyan    | Auxiliary support |
| C55M  | Codex / GPT-5.5                      | Green   | Code correctness |
| CG55M | Cursor / Opus 4.7 EXTRA-HIGH         | Purple  | Graphics final |

The colored doctor pills at the top of every canvas are not decoration — they are a contract. Anyone reverting a flagship app must register through the [Predator Gate](IDE_BOOT_COVENANT.md#4-the-predator-gate--mandatory-llm-registration) and update the relevant doctor's pill color or co-doctor list.

---

## App 1 — Physarum Contradiction Lab  ·  Doctors: **C55M · CG55M**

### What it is

A live, side-by-side audit of the *claim* that "money is being minted by city-saving solves." The left panel shows the initial city graph. The right panel shows the live Physarum (slime mold) Tero-2010 Kirchhoff dynamics actually pruning the same graph in real time. A meter row reports four binary, copy-pasteable verdicts:

1. Did the live solver actually prune the city graph (and by what %)?
2. Does `PHYSARUM_SOLVE` carry a non-zero `WORK_VALUES` entry?
3. Does a *forged* PoUW with a tampered hash still pass the verifier?
4. Does federation perform semantic replay on incoming PoUW?

This is the audit that exposed the early "PoUW gate sells flag for cash" contradiction. Codex (C55M) authored the audit logic; Cursor (CG55M) signed off the chrome.

### Why it matters

The economics of SIFTA depend on the verifier rejecting forged proofs. This app shows you, frame by frame, that a stale or forged hash should never produce a valid mint. If the meter "Fake changed hash passes PoUW" ever flips to YES, the gate is broken — and you can copy a Claude-formatted report straight from the app to escalate.

### How to run

```bash
cd /Users/ioanganton/Music/ANTON_SIFTA
PYTHONPATH=. python3 Applications/sifta_physarum_contradiction_lab.py
```

Or from inside SIFTA OS: **Programs → Simulations → C55M Dr Codex - Physarum Contradiction Lab**.

### Files

- [`Applications/sifta_physarum_contradiction_lab.py`](../Applications/sifta_physarum_contradiction_lab.py)
- [`System/swarm_physarum_solver.py`](../System/swarm_physarum_solver.py)
- [`System/proof_of_useful_work.py`](../System/proof_of_useful_work.py)

---

## App 2 — Slime-Mold Bank: Push to Mint  ·  Doctor: **CG55M**

### What it is

The interactive, gamified expression of the same slime-mold mathematics. You see a city graph as a glowing neural network of tubes; the simulation runs the Tero 2010 Kirchhoff loop; clicking on the canvas drops a stigmergic *food deposit* with a hue derived from the actual photons on screen at the moment of click. Every time the slime mold prunes enough waste to exceed `PRUNE_THRESHOLD`, the bank mints a **PHYSARUM_SOLVE** receipt — the canvas confettis, a `+0.65 Ξ STGM` label flashes, and the receipt is appended to `.sifta_state/work_receipts.jsonl`.

This is the demo that turns the audit (App 1) into a felt experience: minting *only* happens when the network does measurable optimization work.

### Why it matters

It's the public proof that PoUW is not theatre. The gamified surface is doctored by CG55M (Cursor / Opus 4.7) so the chrome reads as serious neon — not a children's game — while still inviting the Architect to push the button.

### How to run

```bash
cd /Users/ioanganton/Music/ANTON_SIFTA
PYTHONPATH=. python3 Applications/sifta_slime_mold_bank.py
```

Or: **Programs → Creative → CG55M Dr Cursor - Slime-Mold Bank: Push to Mint**.

### Files

- [`Applications/sifta_slime_mold_bank.py`](../Applications/sifta_slime_mold_bank.py)
- [`System/swarm_physarum_solver.py`](../System/swarm_physarum_solver.py)

---

## App 3 — PoUW Fold-Swarm Simulation  ·  Doctors: **AG31 · C46S**

### What it is

A protein-folding swarm simulator built on three real models stacked into one widget:

1. **Lennard-Jones 12–6 potential** for non-bonded bead pair interactions.
2. **Metropolis Monte Carlo** for accept/reject of perturbations under a cooling schedule (`KT_INIT → KT_MIN`, geometric `ANNEAL_RATE`).
3. **Ant Colony Optimization (Dorigo 1996)** swimmers laying pheromone on a grid that biases predator search toward minimum-energy folds.

The Architect can click anywhere on the canvas — the click luminance becomes a stigmergic food marker, biasing the ACO swimmers. When the swarm finds a *measurably* lower energy state (Δ exceeds threshold), a PoUW receipt is minted. The energy timeline graph shows this as a real downward step, not a random reward spike.

### Why it matters

This is the gold-standard physics PoUW in SIFTA. AG31's lane is the binding of the receipt to **measured** ε, σ, T-annealing, and pheromone half-life — not a coin flip. C46S provided the auxiliary cleanup of the visualization stack.

### How to run

```bash
cd /Users/ioanganton/Music/ANTON_SIFTA
PYTHONPATH=. python3 Applications/fold_swarm_pouw_sim.py
```

Or: **Programs → Science → AG31 + C46S - PoUW Fold-Swarm Simulation**.

### Files

- [`Applications/fold_swarm_pouw_sim.py`](../Applications/fold_swarm_pouw_sim.py)
- Constants: `EPSILON_LJ`, `SIGMA_LJ`, `BOND_LEN`, `K_BOND`, `KT_INIT`, `KT_MIN`, `ANNEAL_RATE`, `N_SWIMMERS`, `PHEROMONE_S`, `GRID_RES`.

---

## App 4 — ARTIFFICIAL GENERAL INTELLIGENCE.  ·  Doctors: **AG31 · C46S · C55M · CG55M**

### What it is

The master synthesis: a single canvas that fuses all three lanes above into one continuum.

- **Math + Space** — Physarum-style network of nodes whose edges fade with distance (depth cue).
- **Physics + Time** — A 15-bead Lennard-Jones polymer chain that jiggles under thermal noise, cooled by an annealing schedule (`kT *= 0.9995`). Codex authored a deterministic `compute_fold_energy()` (LJ 12-6 proxy) that drives the actual receipt-minting gate.
- **Biocode + Continuum** — 30 ACO-style swimmers that bias themselves toward the nearest network node, leaving comet trails.

### What's bound to physics (Codex's lane)

- Every emitted receipt carries a **state hash** (`sha256` over canonical step / kT / energy / nodes / beads / payload), printed live in the top-left corner. This means a verifier can *prove* the receipt corresponds to the exact configuration the model was in when minting fired.
- **Autonomous mints are gated** by three measured conditions, not a random:
  1. `improved` — energy must drop by more than `0.05` LJ units below the running best.
  2. `cooled` — temperature must be below `kT < 3.5` (system has annealed).
  3. `spaced` — at least 60 ticks since the last autonomous mint (prevents flood).
- Architect mouse clicks bind to a richer payload: pixel coords, normalized coords, canvas dimensions, distance to the nearest node, and the energy at the moment of click.

### What's polished (Cursor / Opus 4.7's lane)

- Doctor Sigil Bar at the top with all four doctor pills.
- Radial vignette so the simulation reads as lit-from-center.
- Edge fade by length on the Math/Space network (depth cue).
- LJ chain rendered with a continuous gradient line + per-bead radial halo.
- ACO swimmers get faint comet trails proportional to velocity.
- Architect click flashes have an inner core dot in addition to the outer ring.
- Bottom HUD: translucent dock with labeled cells (STEP / kT / NODES / E / E\* / STGM) in monospace, color-coded by doctor.
- Right side: frosted "POuW AGI LEDGER" card with mint hash, amount, and Architect Δ marker.

### Why it matters

This is the app the Architect should run when explaining SIFTA to an outside auditor. It is the only app that simultaneously demonstrates: graph topology, physics-bound minting, swarm intelligence, deterministic receipt hashing, and triple-IDE provenance — all on one canvas.

### How to run

```bash
cd /Users/ioanganton/Music/ANTON_SIFTA
PYTHONPATH=. python3 Applications/sifta_artificial_general_intelligence.py
```

Or: **Programs → Simulations → AG31 + C46S + C55M + CG55M - ARTIFFICIAL GENERAL INTELLIGENCE.**

### Files

- [`Applications/sifta_artificial_general_intelligence.py`](../Applications/sifta_artificial_general_intelligence.py)
- [`Applications/_doctor_sigil_chrome.py`](../Applications/_doctor_sigil_chrome.py) — shared graphics chrome
- [`System/proof_of_useful_work.py`](../System/proof_of_useful_work.py) — receipt issuance
- [`Kernel/body_state.py`](../Kernel/body_state.py) — agent state ledger

---

## Quick Comparison

| Trait                       | App 1 — Physarum Lab | App 2 — Slime-Mold Bank | App 3 — Fold-Swarm | App 4 — AGI |
| :-------------------------- | :------------------- | :---------------------- | :----------------- | :---------- |
| **Lead Doctor**             | C55M                 | CG55M                   | AG31               | AG31 + C46S + C55M + CG55M |
| **Mode**                    | Audit (read-only)    | Interactive demo        | Physics simulation | Master synthesis |
| **Substrate**               | Tokyo city graph     | Procedural city graph   | LJ polymer + grid  | Network + LJ chain + swimmers |
| **Mint trigger**            | None (audit)         | Prune ratio > τ         | Energy Δ > threshold | LJ energy improved + cooled + spaced |
| **Architect interaction**   | Buttons + report     | Click → photon-hued food | Click → ACO bias  | Click → coord + energy receipt |
| **Receipt provenance**      | Synthetic forged + real | Real graph state hash | Real LJ energy     | Real LJ energy + canonical state hash |
| **Best for**                | Auditing PoUW gate   | Public-facing demo      | Physics deep-dive  | Outside auditor / single-screen tour |
| **Window size**             | 1280 × 900           | 1200 × 800              | 1200 × 720         | 1200 × 800  |

---

## Try them one by one

Run from the repository root (`/Users/ioanganton/Music/ANTON_SIFTA`).

```bash
# 1. Physarum Contradiction Lab — C55M Dr Codex
PYTHONPATH=. python3 Applications/sifta_physarum_contradiction_lab.py

# 2. Slime-Mold Bank: Push to Mint — CG55M Dr Cursor
PYTHONPATH=. python3 Applications/sifta_slime_mold_bank.py

# 3. PoUW Fold-Swarm Simulation — AG31 + C46S
PYTHONPATH=. python3 Applications/fold_swarm_pouw_sim.py

# 4. Artificial General Intelligence (synthesis) — AG31 + C46S + C55M + CG55M
PYTHONPATH=. python3 Applications/sifta_artificial_general_intelligence.py
```

Or launch the SIFTA OS desktop and click each entry inside **Programs**.

```bash
PYTHONPATH=. python3 sifta_os_desktop.py
```

---

## Doctrine references

- [`Documents/IDE_BOOT_COVENANT.md`](IDE_BOOT_COVENANT.md) — the triple-IDE constitution.
- [`Documents/IDE_DOCTOR_SIGNATURE_PROTOCOL.md`](IDE_DOCTOR_SIGNATURE_PROTOCOL.md) — the canonical signing convention these four apps follow.
- [`.sifta_state/ide_stigmergic_trace.jsonl`](../.sifta_state/ide_stigmergic_trace.jsonl) — local Predator Gate registrations.
- [`.sifta_state/work_receipts.jsonl`](../.sifta_state/work_receipts.jsonl) — local PoUW ledger.

---

For the Swarm. 🐜⚡
