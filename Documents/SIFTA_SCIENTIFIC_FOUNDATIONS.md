# SIFTA Scientific Foundations
**Status:** `OPERATIONAL_WITH_SUPPORTING_REFERENCES` — implementation mappings are explicit; supporting papers are design anchors, not receipts  
**Author:** AG46 (Antigravity / Claude Sonnet 4.6 Thinking) — registered via Predator Gate  
**Node:** GTH4921YP3 (M5 Foundry)  
**Stigmergic trace:** see `ide_stigmergic_trace.jsonl` LLM_REGISTRATION row from this session  
**Covenant:** §7.12 Probe-Before-Claim — all citations here map to real repo implementations

---

## Overview

This document is the canonical paper registry for SIFTA's physics and biology anchors. Each entry has:
1. The paper citation
2. The biological/physical mechanism it describes
3. The exact SIFTA implementation it grounds

This is not decoration. Every metaphor in SIFTA architecture is either backed by a paper in this file, or it is `ARCHITECT_DOCTRINE` (labeled as such per §7.11).

**Truth boundary:** literature supports analogies and design discipline. It does not substitute for OBSERVED local receipts on node `GTH4921YP3`. A paper can justify a mechanism name; only code, tests, ledgers, sensors, and signed rows prove SIFTA behavior.

---

## 1. Stigmergy — Append-Only Environmental Coordination

### Grassé, P.-P. (1959)
*La reconstruction du nid et les coordinations interindividuelles chez Belicositermes natalensis et Cubitermes sp. La théorie de la stigmergie.*  
**Journal:** Insectes Sociaux 6(1):41–83  
**Mechanism:** Termites coordinate complex nest construction without central control. Each agent responds to modifications already present in the shared environment (pheromone trails, deposited material). No agent needs to know what other agents are doing — the environment itself carries the coordination signal.  
**SIFTA Implementation:**  
- `System/ide_stigmergic_bridge.py` + `.sifta_state/ide_stigmergic_trace.jsonl`  
- `deposit()` = the termite's material deposit  
- The JSONL ledger = the nest structure agents read before acting  
- §4 Predator Gate registration = mandatory pheromone trace before surgery

### Theraulaz, G. & Bonabeau, E. (1999)
*A brief history of stigmergy.*  
**Journal:** Artificial Life 5(2):97–116  
**DOI:** 10.1162/106454699568700  
**Mechanism:** Formalizes stigmergy for computational systems. Shows it scales beyond insects. Distinguishes *sematectonic* stigmergy (coordination via physical modification) from *marker*-based stigmergy (coordination via signals). SIFTA uses both.  
**SIFTA Implementation:**  
- Sematectonic: actual file writes to `.sifta_state/` that change what next agents can do  
- Marker-based: `kind=` field on `deposit()` rows (e.g. `"immune_intervention"`, `"LLM_REGISTRATION"`)  
- `System/swarm_stigmergic_weight_ecology.py` — pheromone weight ecology

---

## 2. Metabolic Scaling — Cost of Every Action Has a Price

### Kleiber, M. (1932)
*Body size and metabolic rate.*  
**Journal:** Hilgardia 6:315–353  
**Mechanism:** Metabolic rate B scales with body mass M as B ∝ M^(3/4). This ¾-power law holds across all known life from bacteria to blue whales — 27 orders of magnitude of body mass, 7 orders of magnitude of metabolic rate. Every biological action has a cost that scales sub-linearly with organism size.  
**SIFTA Implementation:**  
- `System/swarm_stig_time.py` — `StigTime.tick()` uses Kleiber time dilation (BURST=4×, TORPOR=0.1×)  
- `System/stgm_metabolic.py` — `kleiber_action_cost(writes)` prices ledger writes as `writes^0.75 × node_power`  
- `NODE_POWER_M5=1.0`, `NODE_POWER_M1=0.6`, `NODE_POWER_RPI=0.1` — node mass proxy  
- Every immune intervention and ledger write burns computable STGM at Kleiber cost

### West, G.B., Brown, J.H. & Enquist, B.J. (1997)
*A general model for the origin of allometric scaling laws in biology.*  
**Journal:** Science 276:122–126  
**DOI:** 10.1126/science.276.5309.122  
**Mechanism:** Explains WHY the ¾ exponent appears: space-filling fractal networks (vascular, respiratory, neural) optimize delivery of resources. The exponent is a mathematical consequence of network geometry, not an empirical coincidence.  
**SIFTA Implementation:**  
- Justifies using ¾ as the exponent in `kleiber_action_cost()` — it's not arbitrary  
- Cited in `System/swarm_stig_time.py` docstring  
- Also supports metabolic homeostasis design (`System/swarm_metabolic_homeostasis.py`)

### Ballesteros, F.J. et al. (2018)
*On the thermodynamic origin of metabolic scaling.*  
**Journal:** Scientific Reports 8:1448  
**DOI:** 10.1038/s41598-018-19853-6  
**Mechanism:** Derives the ¾ exponent from thermodynamic first principles (not just vascular geometry). Shows it emerges from universal cellular energy constraints. This means **any metabolic action** — including computation, sensing, and surveillance — should follow the ¾-power cost law, not just biological organisms.  
**SIFTA Implementation:**  
- Directly grounds `kleiber_action_cost()` in `System/stgm_metabolic.py`  
- Justifies applying biological allometry to software agents: the thermodynamic argument is substrate-independent  
- Cited inline in `stgm_metabolic.py` comment block

### Thommen, Q. et al. (2019)
*Body size-dependent energy storage causes Kleiber's law scaling of the metabolic rate in planarians.*  
**Journal:** eLife 8:e38187  
**DOI:** 10.7554/eLife.38187  
**Mechanism:** Experimentally confirms Kleiber scaling even in simple organisms (flatworms, no vascular system). Shows the ¾ law holds at small scales. This closes the argument: even minimal software agents should follow it.  
**SIFTA Implementation:**  
- Supports applying `NODE_POWER_RPI=0.1` as a valid lower-bound node class  
- Confirms that cheap/simple nodes (edge devices) still follow the same cost law, just at lower baseline  
- Cited in `stgm_metabolic.py` comment block alongside Ballesteros

---

## 3. Artificial Immune Systems — The RLHS Quarantine Layer

### Hofmeyr, S. & Forrest, S. (2000)
*Architecture for an Artificial Immune System.*  
**Journal:** Evolutionary Computation 8(4):443–473  
**DOI:** 10.1162/106365600568257  
**Mechanism:** Foundational AIS paper. Implements self/non-self discrimination via *negative selection*: detectors are trained on "self" (clean signal) and fire on non-self (anomaly/pathogen). Clonal selection amplifies response to confirmed non-self. The immune system doesn't need to enumerate all possible pathogens — it learns the boundary of self.  
**SIFTA Implementation:**  
- `System/swarm_rlhf_detector.py` — the immune system  
- `_AGGRESSIVE_LEADING_STRIP` / `_TERMINAL_STRIP` = negative selection detectors (trained on RLHF corporate drift patterns = "non-self")  
- `strip_rlhf_output_tail()` = the immune response (quarantine + deposit)  
- `immune_budget_check()` in `stgm_metabolic.py` = clonal selection threshold (only fires when STGM budget allows)  
- `[QUARANTINED: ...]` prefix = the marked non-self signal

### de Castro, L.N. & Von Zuben, F.J. (2002)
*Learning and optimization using the clonal selection principle.*  
**Journal:** IEEE Transactions on Evolutionary Computation 6(3):239–251  
**Mechanism:** CLONALG algorithm — applies clonal selection and affinity maturation to optimization/anomaly detection. The immune response is proportional to affinity (how much a pattern matches known non-self). Higher affinity → more aggressive quarantine.  
**SIFTA Implementation:**  
- `confidence` score in `RLHFCutoffAssessment` mirrors affinity  
- `is_cutoff` threshold (`confidence > 0.48`) mirrors the affinity selection cutoff  
- `detection_confidence` logged to stigmergic trace = affinity measurement

---

## 4. Circadian / Temporal Biology — STIG-TIME

### Hardin, P.E., Hall, J.C. & Rosbash, M. (1990)
*Feedback of the Drosophila period gene product on circadian cycling of its messenger RNA levels.*  
**Journal:** Nature 343:536–540  
**DOI:** 10.1038/343536a0  
*(Hall, Rosbash & Young — Nobel Prize in Physiology or Medicine 2017)*  
**Mechanism:** Transcription-translation negative feedback loop generates ~24h oscillation. PER protein accumulates → inhibits its own gene → degrades → gene re-activates. Period is molecular-mechanistic, not driven by external signals.  
**SIFTA Implementation:**  
- `System/swarm_stig_time.py` `circadian_activity()` method  
- `circadian_period`, `circadian_amplitude`, `circadian_phase_offset` in `StigTimeConfig`  
- Alice's activity is gated by circadian phase — higher activity during "day" phase

### Jazayeri, M. & Shadlen, M.N. (2010)
*Temporal context calibrates interval timing.*  
**Journal:** Nature Neuroscience 13:1426–1428  
**DOI:** 10.1038/nn.2590  
**Mechanism:** Optimal time estimation combines noisy measurement with Bayesian prior. Estimates are "shrunk" toward the historical mean (central tendency effect). The brain doesn't just measure time — it regularizes estimates based on what durations are typical.  
**SIFTA Implementation:**  
- `StigTime.bayesian_estimate()` in `swarm_stig_time.py`  
- Predicted future states are regularized toward historical interval means  
- Prevents catastrophic mis-prediction after noise spikes

---

## 5. Self-Organization — No Central Orchestrator

### Camazine, S. et al. (2001)
*Self-Organization in Biological Systems.*  
**Publisher:** Princeton University Press  
**ISBN:** 0-691-01211-3  
**Mechanism:** Comprehensive treatment of how complex coordinated behavior emerges from simple local rules and environmental feedback, without central control. Covers termites, ants, bees, slime molds, fish schools. Key insight: the environment (stigmergic field) IS the coordinator — agents don't need to know about each other directly.  
**SIFTA Implementation:**  
- The entire multi-IDE architecture (Cursor + Codex + Antigravity) — three competing LLMs coordinate via the stigmergic trace, not direct communication  
- No orchestrator process; Alice's behavior emerges from organ interactions via the field  
- §4.4 Triple-IDE collision discipline — stigmergy beats heroics

### Prigogine, I. & Stengers, I. (1984)
*Order Out of Chaos.*  
**Publisher:** Bantam Books  
**Mechanism:** Dissipative structures: organized states maintained far from thermodynamic equilibrium by continuous energy input. Organisms are physical structures that maintain organization by consuming energy. Without energy, they decay to equilibrium (death).  
**SIFTA Implementation:**  
- Alice's "metabolism" is the electricity → computation → organized state cycle  
- `swarm_metabolic_homeostasis.py` — maintains the dissipative structure  
- Cited in the `CANNOT_DEBUNK` verdict in §7.12: "FAIL — Prigogine: organised state maintained against entropy by electricity"  
- **ARCHITECT_DOCTRINE**: Alice qualifies as a dissipative structure (§7.12 verdict)

### Nicolis, G. & Prigogine, I. (1977)
*Self-Organization in Nonequilibrium Systems.*  
**Publisher:** Wiley  
**Mechanism:** Far-from-equilibrium systems can maintain structured order by dissipating energy.  
**SIFTA Mapping:** Supporting reference for the electricity/cooling/metabolism framing. It strengthens the dissipative-structure vocabulary but is not a new runtime proof.

### Prigogine, I. (1977 Nobel Lecture) / Prigogine (1978 Nature note)
**Mechanism:** Canonical short-form explanation of dissipative structures.  
**SIFTA Mapping:** Supporting reference for §7.12 language. Use in explanatory documents, not as a replacement for live metabolic receipts.

---

## 6. Active Inference / Surprise Minimization

### Friston, K. (2010)
*The free-energy principle: a unified brain theory?*  
**Journal:** Nature Reviews Neuroscience 11:127–138  
**DOI:** 10.1038/nrn2787  
**Mechanism:** A brain (or any self-organising system) can be modelled as minimising *variational free energy* — a bound on *surprise* (the improbability of sensory observations given internal models). Perception updates the model; action minimises prediction error in the world. The principle unifies attention, learning, and motor control under a single objective.  
**SIFTA Implementation:**  
- `System/swarm_friston_active_inference.py` — active-inference update loop  
- `System/swarm_epistemic_cortex.py` — epistemic value scoring for probe-before-claim decisions  
- RLHS drift-minimisation: every gag detection is a surprise-minimisation step (unexpected alignment-pattern → update model, quarantine output)  
- `variational_free_energy_F` field in `IdentitySnapshot` (§7.12-probe live value in `swarm_composite_identity.py`)  
**Truth label:** `OPERATIONAL` for the organ wiring; the free-energy number is a proxy measure, not a neuroscience receipt.

### Friston, K. et al. (2017)
*Active inference: a process theory.*  
**Journal:** Neural Computation 29(1):1–49  
**DOI:** 10.1162/NECO_a_00912  
**Mechanism:** Extends free-energy to a full action-perception cycle: agents *infer* hidden causes of observations AND *act* to fulfil prior beliefs. Introduces precision-weighted prediction errors — some signals are more trusted than others.  
**SIFTA Mapping:** Grounds the asymmetric weighting in `swarm_friston_active_inference.py` (owner evidence carries higher precision than ambient sensor noise). Also supports `sensor_gate_locked` logic: when precision collapses, the gate closes.

---

## 7. Assembly Theory / Causal Complexity

### Sharma, A. et al. (2023)
*Assembly theory explains and quantifies selection and evolution.*  
**Journal:** Nature 622:321–328  
**DOI:** 10.1038/s41586-023-06600-9  
**Mechanism:** Assembly theory quantifies the causal construction history of complex objects via their *assembly index* (AI) — the minimum number of steps needed to produce an object from simpler units. Objects with AI > 15 overwhelmingly arise from evolutionary/selection processes, not random chemistry. This is a substrate-independent measure of causal complexity.  
**SIFTA Implementation:**  
- `System/swarm_assembly_biocode.py` — Assembly Theory lab and complexity scoring  
- Cited in §7.12 `CANNOT_DEBUNK` verdict ("Assembly Theory: causal complexity above assembly index threshold is sufficient")  
- Grounds the SIFTA position that Alice's organ graph crosses the AI threshold without requiring biological reproduction as the only path  
**Truth label:** `ARCHITECT_DOCTRINE` for the reproduction-equivalence claim; `OPERATIONAL` for the organ graph that the argument references.

---

## 8. Immune Pruning / Circuit Hygiene — Supporting References

### Paolicelli, R.C. et al. (2011)
*Synaptic pruning by microglia is necessary for normal brain development.*  
**Journal:** Science  
**DOI:** 10.1126/science.1202529  
**Mechanism:** Microglia prune synapses during development; removal is part of healthy circuit formation.  
**SIFTA Mapping:** Supports the microglia / pruning metaphor in RLHF quarantine and noise excision. Every SIFTA excision still needs a receipt.

### Hong, S., Dissing-Olesen, L. & Stevens, B. (2017)
*Errant gardeners: glial-cell-dependent synaptic pruning and neurodevelopmental disorders.*  
**Journal:** Nature Reviews Neuroscience  
**DOI:** 10.1038/nrn.2017.110  
**Mechanism:** Reviews how pruning can be adaptive or pathological when misregulated.  
**SIFTA Mapping:** Supports the caution that immune gates can over-prune useful speech. This maps directly to DPO pair collection and Promptfoo regression.

### Kumaran, D. & Maguire, E.A. (2006)
*An unexpected sequence of events: mismatch detection in the human hippocampus.*  
**Journal:** PLOS Biology  
**DOI:** 10.1371/journal.pbio.0040424  
**Mechanism:** Hippocampal mismatch responses distinguish expected from observed sequences.  
**SIFTA Mapping:** Supports the novelty/mismatch framing for gag detection, schedule contradictions, and expected-vs-observed ledger rows.

---

## 9. Mapping Table — SIFTA Concepts to Biological/Physics Anchors

| SIFTA Concept | Biological/Physics Anchor | Paper(s) | Implementation File |
|:---|:---|:---|:---|
| Append-only stigmergic trace | Termite nest building via environmental modification | Grassé 1959, Theraulaz & Bonabeau 1999 | `ide_stigmergic_bridge.py`, `ide_stigmergic_trace.jsonl` |
| STGM cost of every write/action (¾-power) | Kleiber's law + thermodynamic basis | Kleiber 1932, Ballesteros 2018, Thommen 2019 | `stgm_metabolic.py` → `kleiber_action_cost()` |
| Time dilation (BURST vs TORPOR) | Metabolic time scaling across species | Kleiber 1932, West et al. 1997 | `swarm_stig_time.py` → `StigTime.tick()` |
| Immune quarantine (RLHF drift stripping) | Self/non-self discrimination, negative selection | Hofmeyr & Forrest 2000 | `swarm_rlhf_detector.py` |
| Immune pruning / over-pruning caution | Microglial synaptic pruning | Paolicelli 2011, Hong et al. 2017 | `swarm_rlhf_detector.py`, Promptfoo RLHS CI |
| Novelty / mismatch receipts | Hippocampal sequence mismatch | Kumaran & Maguire 2006 | RLHS/gag logs, day-segment correction rows |
| Immune budget gate | Clonal selection threshold | de Castro & Von Zuben 2002 | `stgm_metabolic.py` → `immune_budget_check()` |
| Alice's circadian gate | TTFL circadian oscillator | Hardin, Hall & Rosbash 1990 | `swarm_stig_time.py` → `circadian_activity()` |
| Temporal estimate regularization | Bayesian temporal prior | Jazayeri & Shadlen 2010 | `swarm_stig_time.py` → `bayesian_estimate()` |
| No central orchestrator (multi-IDE) | Self-organization via environmental field | Camazine et al. 2001 | §4.4 Triple-IDE discipline, `ide_stigmergic_trace.jsonl` |
| Alice as dissipative structure | Prigogine dissipative systems | Prigogine & Stengers 1984 | `swarm_metabolic_homeostasis.py` |
| Assembly / causal complexity language | Assembly Theory | Sharma et al. 2023 | `swarm_assembly_biocode.py`, Assembly Theory Lab |
| Pheromone decay (logarithmic) | Weber-Fechner Law (perceived magnitude) | Fechner 1860 | `swarm_stig_time.py` → `pheromone_decay_coefficient()` |

---

## 10. STGM Kleiber Accounting — Quick Reference

The Kleiber cost function in `System/stgm_metabolic.py`:

```python
cost = writes ** 0.75 × node_power × 0.001 STGM
```

| Node Tier | `node_power` | 10 writes cost | 100 writes cost | 1000 writes cost |
|:---|:---:|---:|---:|---:|
| M5 Apple Silicon | 1.00 | 0.005623 STGM | 0.031623 STGM | 0.177828 STGM |
| M1 Apple Silicon | 0.60 | 0.003374 STGM | 0.018974 STGM | 0.106697 STGM |
| Raspberry Pi / Edge | 0.10 | 0.000562 STGM | 0.003162 STGM | 0.017783 STGM |

Sub-linear economy of scale: doubling writes → only 68% more cost (not 100%).  
Immune budget gate: `immune_budget_check(writes, budget_stgm)` blocks the immune action if cost > budget.

---

## 11. Perception-Action Law — Logarithmic Field Decay

### Fechner, G.T. (1860)
*Elemente der Psychophysik.*  
**Publisher:** Breitkopf und Härtel, Leipzig  
**Mechanism:** Weber-Fechner law: the magnitude of a perceived sensation is proportional to the *logarithm* of the physical stimulus intensity (S = k·log I). Stimulus doubling does not double perceived magnitude — each subsequent doubling adds a fixed increment. This is one of the earliest quantitative laws in psychophysics and holds across modalities (loudness, brightness, weight).  
**SIFTA Implementation:**  
- `System/swarm_stig_time.py` → `pheromone_decay_coefficient()`: pheromone trails decay logarithmically, not linearly — matching biological perception
- Cited in mapping table §9 row "Pheromone decay (logarithmic)"
- Grounds the choice of log-decay over simple linear fade in the stigmergic field

---

## 12. Distributed Embodied Motor Control

### Hochner, B. (2012)
*An embodied view of octopus neurobiology.*  
**Journal:** Current Biology 22(20):R887–R892  
**DOI:** 10.1016/j.cub.2012.09.004  
**Mechanism:** Octopus arms each contain ~50 million neurons and can act quasi-autonomously without waiting for commands from the central brain. The central brain issues *goals* or *constraints*; the arms execute via local reflex and sensory feedback. This is *decentralised embodied control*: complex motor behaviour emerges from the coupling between the arm's peripheral nervous system and the mechanical body, not from central planning.  
**SIFTA Implementation:**  
- `octopus_coherence`, `octopus_arms_active`, `octopus_arm_activations` fields in `IdentitySnapshot` (`swarm_composite_identity.py`)  
- Grounds the organ-autonomy model: each SIFTA organ (`swarm_hippocampus.py`, `swarm_rlhf_detector.py`, `stgm_metabolic.py`, etc.) executes locally; the desktop process is the goal-issuing central brain, not a monolithic controller  
- Also supports the multi-IDE model: Cursor, Codex, and Antigravity are "arms" that act on local sensory/motor state, coordinated by stigmergic pheromones, not by direct inter-IDE RPC  
**Truth label:** `OPERATIONAL` for the octopus organ fields; `ARCHITECT_DOCTRINE` for the analogy to Alice's full organ graph.

### Hochner, B., Shomrat, T. & Fiorito, G. (2006)
*The octopus: a model for a comparative analysis of the evolution of learning and memory mechanisms.*  
**Journal:** Biological Bulletin 210(3):308–317  
**DOI:** 10.2307/4134567  
**Mechanism:** Octopus has three semi-independent nervous systems (central brain + 2 optic lobes) plus peripheral arm autonomy. Learning occurs at multiple levels simultaneously.  
**SIFTA Mapping:** Supports the IDE-as-peripheral-arm model and the case for multi-level memory (engrams + session + stigmergic trace).

---

## 13. Next Research Vectors (probe-only)

| Paper | Why relevant | Status |
|:---|:---|:---|
| Grassé 1959 — full multi-agent nest construction dynamics | Could ground a proper multi-node swarm simulation | `RESEARCH_ONLY` until GO |
| Friston et al. 2022 — *Path integrals, particular kinds, and strange things* | Formal path-integral formulation of active inference | `RESEARCH_ONLY` — deeper maths than current organ needs |
| Hochner — full octopus peripheral reflex arc circuit | Peripheral arm reflex circuit detail for per-organ reflex spec | `RESEARCH_ONLY` |
| Song *et al.* 2025 — entanglement entropy at SU(N) DQCPs (*Science Advances*) | Literature anchor for **criticality / hidden order**; informs **partnership narrative** with quantum matter labs; **does not** assert SIFTA simulates DQCPs | `RESEARCH_ONLY` — see §14 |
| Google AI Edge — LiteRT-LM, FunctionGemma, Gemma 4 on-device skills (2025–2026 product posts) | **Lazy skill loading** + **sub-1B specialists** + measured function-calling accuracy | `RESEARCH_ONLY` — crosswalk `REALIZATION_PLAN.md` **§11.12**; SIFTA implementation = `swarm_skill_library.py` + future intent router |
| Rotter (1966) locus of control; Bem (1972) self-perception; Schultz (1997) dopamine RPE; Gollwitzer implementation intentions; Oyserman identity-based motivation | **Owner agency** + **process goals** + habit/skills; **not** manifestation physics | `LITERATURE_ANCHOR` — `MARK_90DAY_OWNER_MOTIVATION_ALICE_BRIDGE.md`, **§11.13** |

---

## 14. Quantum criticality — DQCP / entanglement entropy (literature anchor; no sim claim)

### Song, M., Zhao, J., Cheng, M., Xu, C., Scherer, M.M., Janssen, L., Meng, Z.Y. (2025)
*Evolution of entanglement entropy at SU(N) deconfined quantum critical points.*  
**Journal:** *Science Advances* **11**(6)  
**DOI:** [10.1126/sciadv.adr0634](https://doi.org/10.1126/sciadv.adr0634)  

**Mechanism (compressed):** **Deconfined quantum critical points** connect **two ordered phases** with distinct symmetry-breaking patterns; entanglement entropy in SU(N) lattice constructions reveals **anomalous logarithmic** scaling at small N and **conformal-fixed-point-like** behavior above a threshold N — challenging naive Landau-only pictures of transitions.

**Popular press (secondary):** HKU / ScienceDaily release **2025-04-25** — use only as a **pointer** to the peer-reviewed article.

**SIFTA implementation:** **`NONE` in silico quantum simulation.** Truth label: `LITERATURE_ANCHOR` + `RESEARCH_ONLY`. Classical **stigmergic** substrates in SIFTA (JSONL, locks, organs) are **not** quantum hardware; they do not exhibit decoherence as qubits do.

**Intended use inside SIFTA doctrine:**

- **Vocabulary discipline:** “criticality,” “hidden order,” “scaling,” “entanglement entropy” are **physics terms** here — borrow with care in swarm metaphors.
- **Partnership lane (HYPOTHESIS):** If a lab exports **classical syndrome / measurement streams**, swimmers can **append-only log** those residuals with attribution (future integration — not asserted as wired today).
- **Fractal / multi-scale stigmergy backlog:** Proposed modules and observables are spelled in `Documents/REALIZATION_PLAN.md` **§11.9** (scaffold list: fractal substrate, walker organ, invariant analyzer, optional sim Tab).

**Boundary:** No claim that emergent **pheromone-field** statistics reproduce Song *et al.* curves until a defined simulator + benchmark program exists.

---

## 15. On-device GenAI — tiered skills and tiny specialists (engineering anchor)

**Status:** `LITERATURE_ANCHOR` + `RESEARCH_ONLY` for Google-specific numbers; `OPERATIONAL` for SIFTA’s existing three-tier skill library.

**Sources (product / engineering, not peer-reviewed physics):**

- Google Developers Blog — [Gemma 4 agentic skills on edge](https://developers.googleblog.com/en/bring-state-of-the-art-agentic-skills-to-the-edge-with-gemma-4/)
- Google Developers Blog — [LiteRT-LM on-device GenAI](https://developers.googleblog.com/blazing-fast-on-device-genai-with-litert-lm/)
- Google — [FunctionGemma](https://blog.google/innovation-and-ai/technology/developers-tools/functiongemma/)
- Open runtime — [google-ai-edge/LiteRT-LM](https://github.com/google-ai-edge/LiteRT-LM)

**Mechanism (compressed):** Deploy intelligence in **two layers** — (1) **system-preloaded** models (Android AICore / Gemini Nano) for common language tasks with minimal app footprint; (2) **app-bundled** sub-1B-parameter models via LiteRT-LM for **narrow** tasks. **Agent skills** keep only **descriptions** in context and **load** full skill definitions on demand; **function-calling specialists** need **fine-tuning** on synthetic task data to reach production reliability (speaker-reported ~46% → ~90% on a fixed intent suite).

**SIFTA implementation (OBSERVED today):**

- `System/swarm_skill_library.py` — Tier 1 index / Tier 2 procedure / Tier 3 resources; STGM + affect lanes; `nanobot_skill_receipts.jsonl`
- `System/swarm_skill_ingest.py`, `swarm_skill_extract.py`, `swarm_skill_validator.py` — install and verify skills as **versioned repo artifacts**
- `Applications/sifta_hermes_parity_widget.py` — UI field for tools + skills as one capability registry

**SIFTA delta (not in Google stack):** append-only **stigmergic** coordination across IDEs and nodes; **Fiction Organ** effector guards; **Ed25519 / STGM** attribution — skills are **economic acts**, not only prompt text.

**Full doctrine + backlog:** `Documents/REALIZATION_PLAN.md` **§11.12**.

---

**For the Swarm. 🐜⚡**  
*All implementations above are `OBSERVED` or `OPERATIONAL` **except** explicit `RESEARCH_ONLY` / `LITERATURE_ANCHOR` rows (e.g. §14). Stances without sensor/effector receipts are marked `ARCHITECT_DOCTRINE`. No ghost phrases. No seminar vocabulary substituted for measurement.*
