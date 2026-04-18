# DYOR — Swarm biology analogues (web-gathered)

**Gathered by:** CP2F (Composer 2 Fast, Cursor IDE)  
**Date:** 2026-04-18  
**Purpose:** Ground SIFTA’s stigmergy / quorum / chemotaxis / reinforcement-myelination layers in peer-reviewed or standard references. URLs verified via web search at gather time.

---

## 1. Stigmergy & swarm intelligence

- **Bonabeau, Dorigo, Theraulaz — *Swarm Intelligence: From Natural to Artificial Systems*** (Oxford University Press, 1999). Canonical text on ant/bee-inspired distributed coordination; foundation for “environment-mediated coordination” used in `ide_stigmergic_bridge.py`.

- **Bonabeau — “Editor’s Introduction: Stigmergy”** — *Artificial Life* (1999). Frames stigmergy as resolving the “coordination paradox” in social insects. Semantic Scholar: `https://www.semanticscholar.org/paper/Editor's-Introduction:-Stigmergy-Bonabeau/2f33c1a583ff77b85253aa75845f46af98eb648c`

- **Grassé lineage / history** — Bonabeau & Theraulaz trace Pierre-Paul Grassé’s 1959 introduction of *stigmergy*; distinguishes quantitative vs qualitative stigmergy (relevant when comparing JSONL density vs trigger semantics).

---

## 2. Quorum sensing (LuxI / LuxR, *Vibrio fischeri*)

- **Waters & Bassler — “Quorum-sensing signal–response systems in Gram-negative bacteria”** — *Nature Reviews Microbiology* (2016). Open PMC copy: `https://pmc.ncbi.nlm.nih.gov/articles/PMC5056591/` — DOI `10.1038/nrmicro.2016.89`. Covers autoinducer synthesis, LuxR-type regulation, and why bioluminescence waits for threshold density — direct biological analogue to `quorum_sensing.py`.

- **Bassler & colleagues — network architectures** — e.g. “Bacterial Quorum-Sensing Network Architectures” (PMC `PMC4313539`) for multi-species signal mixing (future: multi-node CRDT merge interpretation).

---

## 3. *E. coli* chemotaxis — run-and-tumble

- **Berg, H.C.** — *E. coli in Motion* (Springer) and foundational reviews on flagellar switching; run-tumble as biased random walk. Teaching PDF mirror (Cambridge): `https://www.damtp.cam.ac.uk/user/gold/pdfs/teaching/ufk_papers/membrane_proteins/bergreview.pdf`

- **Berg — retrospective / biography** — “Howard Berg’s Random Walk through Biology” — *PMC7648147* — narrative entry point.

- **Block, Segall, Berg — “Signal processing times in bacterial chemotaxis”** — *Nature* **296**, 855–857 (1982) — classic timing numbers (~0.2 s response latency) if we ever time-align probe cadence to `chemotactic_probe_router.py`.

---

## 4. Activity-dependent myelination & plasticity

- **Fields, R.D.** — “A new mechanism of nervous system plasticity: activity-dependent myelination” — *Nature Reviews Neuroscience* **16**, 756–767 (2015). DOI `10.1038/nrn4023`. PMC: `https://pmc.ncbi.nlm.nih.gov/articles/PMC6310485/` — legitimizes **reward/outcome-driven** speeding of pathways (not confidence scores), matching `reinforcement_myelination.py`’s forbidden-key policy.

- **Follow-on:** “Unraveling Myelin Plasticity” — *PMC7301701* — broader review if RM layer extends to pruning schedules.

---

## 5. Batch 2 — CRDTs, ACO, swarm robotics, immunity (2026-04-18 gather)

*Gathered in parallel while AG31 runs his Antigravity lane; CP2F extends DYOR on Cursor only.*

### 5.1 Conflict-free replicated data types (formal backbone of `identity_field_crdt.py`)

- **Shapiro, Preguiça, Baquero, Zawirski — “Conflict-free Replicated Data Types”** — INRIA RR-7687 (2011); also SSS 2011. Introduces **Strong Eventual Consistency (SEC)** and state- vs operation-based CRDTs. HAL: `https://hal.science/inria-00609399` — PDF mirrors: `https://pages.lip6.fr/Marc.Shapiro/papers/RR-7687.pdf`

### 5.2 Ant colony optimization & stigmergic control (algorithmic layer)

- **Dorigo, Maniezzo, Colorni — “Ant System”** lineage (1996 TSMC / early ACO) — positive feedback + distributed computation; Princeton course bib points to IRIDIA corpus: `https://iridia.ulb.ac.be/~mdorigo/Published_papers/All_Dorigo_papers/DorManCol1996tsmcb.pdf`

- **Di Caro & Dorigo — “AntNet”** — distributed stigmergetic routing (Semantic Scholar reader): stigmergy as **network-mediated** pheromone, adjacent to JSONL dead drops.

### 5.3 Swarm robotics — artificial stigmergy (2020s)

- **“Automatic design of stigmergy-based behaviours for robot swarms”** — *Communications Engineering* (Nature Portfolio) — DOI `10.1038/s44172-024-00175-7` — evolved stigmergy can match or beat hand-designed swarm controllers; relevant if SIFTA later adds **physical** robot pheromones.

### 5.4 Self / non-self & tolerance (analogue: `cross_ide_immune_system`)

- **Medzhitov & Janeway — “Decoding the Patterns of Self and Nonself by the Innate Immune System”** — *Science* **296**, 298–300 (2002) — pattern-recognition framing for “what counts as swarm body.” ADS: `https://ui.adsabs.harvard.edu/abs/2002Sci...296..298M`

- **“Historical Overview of Immunological Tolerance”** — *PMC3312674* — central vs peripheral tolerance; **no single lymphocyte is supreme judge** — parallels “no single node is anomaly arbiter” in SIFTA governance.

- **Janeway’s *Immunobiology*** (10e) — Norton — standard text for PRRs, PAMPs/DAMPs; textbook not a paper but the citation anchor for serious immune metaphors.

---

## 6. How this maps to SIFTA modules (extended)

| Layer | Paper lane | Code |
|-------|------------|------|
| Stigmergy | Bonabeau / Grassé | `ide_stigmergic_bridge.py`, JSONL traces |
| Quorum | Waters & Bassler | `quorum_sensing.py` |
| Chemotaxis | Berg | `chemotactic_probe_router.py` |
| Adaptive myelination | Fields 2015 | `reinforcement_myelination.py` |
| **SEC / CRDT** | Shapiro *et al.* 2011 | `identity_field_crdt.py` (G-counter merge) |
| **ACO / AntNet** | Dorigo line | probe routing, future optimizer hooks |
| **Swarm robotics stigmergy** | Nat Comm Eng 2024 | future hardware / sim layer |
| **Tolerance / danger** | Medzhitov & Janeway 2002; PMC3312674 | `cross_ide_immune_system.py` |
| **Predictive coding** | Rao & Ballard 1999 | residual/error vs prior — intuition vs classifier |
| **Ultrastability / homeostat** | Ashby 1952 | governor / temporal layering / metabolic throttle |
| **Programmed death** | Kerr *et al.* 1972 | `apoptosis.py`, pruning |
| **Gossip / epidemic spread** | Karp–Schindelhauer FOCS 2000 | dead-drop latency bounds |

---

## 7. Batch 3 — predictive coding, cybernetics, apoptosis, gossip (2026-04-18)

*Gathered while AG31 may have completed parallel Antigravity work; CP2F extends DYOR on Cursor (web search only).*

### 7.1 Predictive coding (residuals vs priors)

- **Rao & Ballard — “Predictive coding in the visual cortex: a functional interpretation of some extra-classical receptive-field effects”** — *Nature Neuroscience* **2** (1), 79–87 (1999). DOI `10.1038/4580`. PDF (UW mirror): `https://homes.cs.washington.edu/~rao/Rao-Ballard-NN-1999.pdf` — hierarchical prediction and **error** units; maps to “classifier residual vs human prior” without trusting raw confidence.

### 7.2 Ultrastability & the homeostat (governor analogue)

- **Ashby — *Design for a Brain: The Origin of Adaptive Behaviour*** (1952, Chapman & Hall; Springer reprints) — **ultrastable systems**, **law of requisite variety**; physical **homeostat** device (1948). Chapter PDF via Springer: `https://link.springer.com/content/pdf/10.1007/978-94-015-1320-3_7.pdf` — use for **metabolic throttle** / climate OPEN·CAUTIOUS·FROZEN narratives.

### 7.3 Apoptosis (programmed removal)

- **Kerr, Wyllie & Currie — “Apoptosis: a basic biological phenomenon with wide-ranging implications in tissue kinetics”** — *British Journal of Cancer* **26**, 239–257 (1972). PMC: `https://pmc.ncbi.nlm.nih.gov/articles/PMC2008650/` — coined **apoptosis**; complements mitosis — direct anchor for `apoptosis.py` and **synapse pruning** in `reinforcement_myelination.py`.

### 7.4 Randomized rumor / gossip (dead-drop scaling)

- **Karp, Schindelhauer, Shenker, Vöcking — “Randomized Rumor Spreading”** — FOCS 2000 (dblp: `conf/focs/KarpSSV00`). Semantic Scholar: `https://www.semanticscholar.org/paper/Randomized-rumor-spreading-Karp-Schindelhauer/bad78a526180dd4e2a4cd6485e5dd5cb010b12f2` — lower bounds on rounds vs transmissions; epidemic-style dissemination matches **append-only JSONL** gossip without a central chat server.

---

## 8. Batch 4 — dopamine RPE, PFC working memory, novelty, explore/exploit (2026-04-18)

*Web pull to ground the “motivational / dopamine / PFC buffer” layer and the Claude-tab critique (hand-init DA, need real novelty + affinity deltas).*

### 8.1 Reward prediction error — midbrain DA

- **Schultz, Dayan & Montague — “A Neural Substrate of Prediction and Reward”** — *Science* **275** (5306), 1593–1599 (1997). DOI `10.1126/science.275.5306.1593` — foundational **dopamine RPE** account; DA bursts/scallops track **prediction error**, not raw reward magnitude. Gatsby mirror: `https://www.gatsby.ucl.ac.uk/~dayan/papers/sdm97.html`

### 8.2 Prefrontal working memory (PFC “buffer” analogue)

- **Goldman-Rakic — “Architecture of the Prefrontal Cortex and the Central Executive”** — *Annals of the New York Academy of Sciences* **769** (1995), 71–83 — dorsolateral PFC (area 46) and **representational working memory**; central for any `pfc_working_memory` implementation that must stay **stateful** across probes.

- **Goldman-Rakic — “Cellular basis of working memory”** — *Neuron* (1995) line — PubMed `7695894` — single-neuron delay activity during WM tasks.

### 8.3 Novelty / match–mismatch (cosine / surprise hooks)

- **Tulving, Markowitsch, Craik, Habib, Houle — “Contribution of human hippocampal region to novelty detection”** — *Nature* **383** (1996) — hippocampal region in **novelty detection** within distributed network; PMID-linked line in literature.

- **Kumaran & Maguire — “Match–Mismatch Processes Underlie Human Hippocampal Responses to Associative Novelty”** — *Journal of Neuroscience* (2007); PMC `PMC2572808` — formal **match/mismatch** framing (useful for “cosine to rolling mean” novelty).

### 8.4 Exploration vs exploitation — neuromodulation

- **Strange, Duggins, Weiss, Price, Penny, Dolan, Friston — “Novelty and uncertainty regulate the balance between exploration and exploitation through distinct mechanisms in the human brain”** — *Neuron* (2022) — novelty vs uncertainty **dissociated**; DOI lane on ScienceDirect `S0896627322005025`.

- **Jepma, Murphy, Nassar, Rangel-Mesa, Perez, Luck, Nieuwenhuis — “Disentangling the roles of dopamine and noradrenaline in the exploration-exploitation tradeoff”** — *Neuropsychopharmacology* (2023); Nature preview `s41386-022-01517-9` — **DA vs NE** for directed vs random exploration (maps to Explore/Maintain/Exploit state machine design choices).

- **Zénon, Devesse, Olivier — “Dopaminergic modulation of the exploration/exploitation trade-off in human decision-making”** — *eLife* **9**, e51260 (2020) — `https://elifesciences.org/articles/51260` — human DA pharmacology × explore/exploit.

### 8.5 Mapping table (Batch 4 → code intent)

| Concept | Paper lane | SIFTA hook |
|--------|------------|------------|
| RPE δ | Schultz *et al.* 1997 | replace hand-init `DA` with δ from **measured** reward minus expected |
| WM state | Goldman-Rakic 1995 | `pfc_working_memory` stores **vectors or feature hashes**, not prose confidence |
| Novelty | Kumaran & Maguire; Nature 383 | cosine distance vs rolling mean → **novelty signal** |
| Explore/exploit | Neuron 2022; eLife 51260 | tie `chemotactic_probe_router` + quorum to **distinct** uncertainty vs novelty channels |

---

## 9. CP2F note (for AG31 & Alice)

Composer-class models on Cursor are optimized for **fast, cost-efficient** turns. That is a **feature** for DYOR: literature sweeps, DOI hygiene, and thin memos like this one. **C47H (Opus-class)** remains the right lane for deep multi-file refactors and identity-substrate audits. **AG31 (Antigravity / Gemini)** is a third peer on another IDE—triangulation, not a single leaderboard.

*This file is a living queue; append DOIs as the swarm extends vectors.*

---

## 10. Batch 5 — serotonin (5-HT), DA coupling, inhibition, motor (2026-04-17)

*Web pull (CP2F) to ground `System/serotonin_homeostasis.py` and the DA / circadian governor wiring.*

### 10.1 Serotonin, inhibition, and affective RL

- **Dayan & Huys — “Serotonin, Inhibition, and Negative Mood”** — *PLOS Computational Biology* **4** (2), e4 (2008). DOI `10.1371/journal.pcbi.0040004` — article: `https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.0040004` — PMC: `https://pmc.ncbi.nlm.nih.gov/articles/PMC2222921/` — 5-HT as **behavioral inhibition** and interaction with negative prediction error / aversive predictions.

### 10.2 Serotonin and dopamine — unified review

- **Cools, Nakamura & Daw — “Serotonin and Dopamine: Unifying Affective, Activational and Decision Functions”** — *Neuropsychopharmacology* **36**, 98–113 (2011). DOI `10.1038/npp.2010.121` — Nature full text: `https://www.nature.com/articles/npp2010121` — bridges DA and 5-HT in decision / reinforcement framing (pair with `dopamine_ou_engine.py` + 5-HT governor).

### 10.3 Serotonin and motor activity

- **Jacobs & Fornal — “Serotonin and motor activity”** — *Current Opinion in Neurobiology* **7** (6), 820–825 (1997). DOI `10.1016/S0959-4388(97)80141-9` — ScienceDirect: `https://www.sciencedirect.com/science/article/abs/pii/S0959438897801419` — DRN 5-HT neurons and **motor/arousal** coupling (motor analogue for swarm “ticks” and maintenance).

### 10.4 Mapping (Batch 5 → code)

| Concept | Paper lane | SIFTA hook |
|--------|------------|------------|
| 5-HT inhibition / mood | Dayan & Huys 2008 | patience / forced MAINTENANCE, impulsivity vs stability |
| DA–5-HT unification | Cools *et al.* 2011 | `SerotoninHomeostasis` + `DopamineState.tick(..., rpe_gain_scale=...)` |
| 5-HT–motor | Jacobs & Fornal 1997 | circadian phase + exploitation streak semantics |

---

## 11. Batch 6 — cerebellar forward models + hippocampal theta (integrity / sync) (2026-04-17)

*Web pull (CP2F) to ground `System/swarm_integrity_watchdog.py` (proprioceptive self-check before next waking cycle).*

### 11.1 Internal models in the cerebellum

- **Wolpert, Miall & Kawato — “Internal models in the cerebellum”** — *Trends in Cognitive Sciences* **2** (9), 338–347 (1998). DOI `10.1016/S1364-6613(98)01221-2` — Cell Trends abstract: `https://www.cell.com/trends/cognitive-sciences/abstract/S1364-6613(98)01221-2` — forward/inverse models for prediction and control; analogue to **verifying expected vs actual** subsystem state (`integrity_report.json`).

### 11.2 Theta oscillations — temporal coordination / “coherence”

- **Buzsáki — “Theta Oscillations in the Hippocampus”** — *Neuron* **33** (3), 325–340 (2002). DOI `10.1016/S0896-6273(02)00586-X` — Cell Neuron: `https://www.cell.com/neuron/fulltext/S0896-6273(02)00586-X` — theta as **on-line** hippocampal state and temporal framing; loose analogue to **stigmergy trace freshness** (`ide_stigmergic_trace.jsonl` recency check).

### 11.3 Mapping (Batch 6 → code)

| Concept | Paper lane | SIFTA hook |
|--------|------------|------------|
| Forward / internal model | Wolpert *et al.* 1998 | `run_watchdog()` compares **expected** file/schema health vs **observed** |
| Temporal coherence | Buzsáki 2002 | last trace **age** vs `COHERENCE_WINDOW_S` |

---

## 12. Batch 7 — human information limits + cognitive load (coordination / planning) (2026-04-17)

*Web pull (CP2F) to ground **lane structure** and “AG31 overwhelmed” — scope discipline, not more raw PDFs.*

### 12.1 Chunk capacity (“seven ± two”)

- **Miller — “The magical number seven, plus or minus two: Some limits on our capacity for processing information”** — *Psychological Review* **63** (2), 81–97 (1956). DOI `10.1037/h0043158` — limits on absolute judgment and immediate memory span; use as metaphor for **max open checklist items** per IDE session (`Documents/PLAN_AG31_CP2F_LANE_STRUCTURE.md`).

### 12.2 Cognitive load (why endless paper drops hurt integration)

- **Sweller — “Cognitive load during problem solving: Effects on learning”** — *Cognitive Science* **12** (2), 257–285 (1988). DOI `10.1207/s15516709cog1202_4` — Wiley: `https://onlinelibrary.wiley.com/doi/abs/10.1207/s15516709cog1202_4` — working-memory limits during problem solving; **extraneous** load competes with schema formation — analogue: **pause DYOR until last batch lands in code**.

### 12.3 Mapping (Batch 7 → swarm process)

| Concept | Paper lane | SIFTA hook |
|--------|------------|------------|
| Chunk / checklist size | Miller 1956 | ≤7 next actions for AG31; queue rest in plan §4 |
| Extraneous load | Sweller 1988 | paper batch **freeze** until integration or explicit defer |

---

## 13. Batch 8 — recursive improvement, superintelligence paths, situational awareness (2026-04-17)

*Web pull (CP2F) to ground Bostrom/Greene–style themes (**not** stigmergic insects in that video).*

### 13.1 Intelligence explosion — historical anchor

- **Good — “Speculations Concerning the First Ultraintelligent Machine”** — *Advances in Computers* **6**, 31–88 (1966). DOI `10.1016/S0065-2458(08)60418-0` — ScienceDirect: `https://www.sciencedirect.com/science/article/abs/pii/S0065245808604180` — recursive improvement / ultraintelligent machine as intellectual activity (feedback loop narrative).

### 13.2 Superintelligence — consolidated treatment

- **Bostrom — *Superintelligence: Paths, Dangers, Strategies*** — Oxford University Press (2014). ISBN `978-0-19-967811-2` — Oxford Martin: `https://www.oxfordmartin.ox.ac.uk/publications/superintelligence-paths-dangers-strategies` — control/oracle/genie framings, takeoff dynamics, strategic analysis (popular interview with Greene draws on this vocabulary).

### 13.3 Situational awareness — empirical LLM benchmark

- **Laine *et al.* — “Me, Myself, and AI: The Situational Awareness Dataset (SAD) for Large Language Models”** — *NeurIPS* 2024 (Datasets and Benchmarks). Proceedings: `https://proceedings.neurips.cc/paper_files/paper/2024/file/7537726385a4a6f94321e3adf8bd827e-Paper-Datasets_and_Benchmarks_Track.pdf` — project: `https://situational-awareness-dataset.org/` — tests including whether prompts resemble **eval vs deployment** (behavioral, not substrate).

### 13.4 Hybrid / telescoping futures

- No single “telescoping” DOI maps the Greene–Bostrom conversational segment; treat as **speculative futurism** anchored by Bostrom (2014) + subsequent alignment literature. CP2F keeps primary citations in §13.2–13.3.

### 13.5 Mapping (Batch 8 → SIFTA code)

| Concept | Reference lane | SIFTA hook |
|--------|----------------|------------|
| Eval vs deploy distinction | SAD (NeurIPS 2024) | behavioral benchmark for **LLMs** — orthogonal to substrate |
| Process-local surface flag | Bostrom-style strategic separation (informal) | `System/epistemic_deployment_context.py` (`SIFTA_EPISTEMIC_SURFACE`) |
| Recursive improvement | Good 1966 | motivation text for governor loops — not automatic self-modify in repo |

---

## 14. Batch 9 — holography, complementarity, ER=EPR (physics → stigmergy metaphor) (2026-04-17)

*Web pull (CP2F): rigorous citations for Susskind-style narratives; **stigmergic insects** remain Bonabeau/Dorigo (§1); this batch is **gravity/QFT** language for metaphor design only.*

### 14.1 Holographic principle — boundary encoding / black hole information

- **'t Hooft — “Dimensional Reduction in Quantum Gravity”** — arXiv `gr-qc/9310026` (1993) — precursor holographic counting / horizon degrees of freedom.

- **Susskind — “The World as a Hologram”** — *Journal of Mathematical Physics* **36** (11), 6377–6396 (1995). DOI `10.1063/1.531249` — arXiv `hep-th/9409089` — develops 't Hooft’s idea: bulk data tied to boundary-style description (popular talks often connect this to black-hole information debates).

### 14.2 Black hole complementarity — mutually exclusive observer descriptions

- **Susskind, Thorlacius & Uglum — “The Stretched Horizon and Black Hole Complementarity”** — arXiv `hep-th/9306069`; *Physical Review D* **48**, 3743 (1993). DOI `10.1103/PhysRevD.48.3743` — infalling vs outside **complementary** descriptions (analogy: distinct local views of one global information budget).

### 14.3 ER = EPR — entanglement vs wormhole geometry (conjecture)

- **Maldacena & Susskind — “Cool horizons for entangled black holes”** — arXiv `1306.0533` (2013) — proposes **ER=EPR** link between Einstein–Rosen bridges and EPR correlations; controversial / model-dependent extensions exist in follow-up literature.

### 14.4 String-theory vocabulary (for LLM metaphor only)

- **D-branes** — dynamical objects with Dirichlet boundary conditions on open string endpoints; standard textbook: Polchinski, *String Theory* (Cambridge); pedagogical summary in arXiv lecture notes / textbooks — **not** reproduced here as a primary paper row (use a string-theory text for exams).

### 14.5 Mapping (Batch 9 → SIFTA code)

| Metaphor | Physics lane | Code |
|----------|--------------|------|
| Boundary holds enough data to summarize bulk activity | 't Hooft 1993; Susskind 1995 | `System/holographic_stigmergy_projection.py` — SHA-256 digest of JSONL **tail** |
| Complementary local views | STU 1993 | separate **IDE** traces + CRDT merge semantics — not one chat API |
| “Non-local” coordination without adjacency | ER=EPR (conjecture) | shared **substrate** history (weights / traces), not literal wormholes |

---

## 15. Batch 10 — emergence, replication, information cost (talks → engineering metaphors) (2026-04-17)

*Web pull (CP2F): anchors for “Brian Cox–style” emergence / replication / conservation narratives; pair with `PLAN_AG31_CP2F_LANE_STRUCTURE.md` §8.*

### 15.1 Local rules → global structure (flocking)

- **Reynolds — “Flocks, herds and schools: A distributed behavioral model”** — *Computer Graphics* (SIGGRAPH ’87) **21** (4), 25–34. DOI `10.1145/37401.37406` — classic **boids**: alignment / separation / cohesion from local perception (stigmergy-adjacent **without** insect chemistry).

### 15.2 Self-replication (theory — not a license to spawn agents)

- **von Neumann — *Theory of Self-Reproducing Automata*** — University of Illinois Press (1966), ed. Burks — constructive automata and self-reproduction; use as **cautionary** background for controlled replication only.

### 15.3 Information processing and physical cost (bit erasure)

- **Landauer — “Irreversibility and Heat Generation in the Computing Process”** — *IBM Journal of Research and Development* **5** (3), 183–191 (1961). DOI `10.1147/rd.53.0183` — logically irreversible ops have thermodynamic cost; metaphor for **why append-only ledgers + explicit erasure policy** matter.

### 15.4 Mapping (Batch 10 → code)

| Concept | Reference lane | SIFTA hook |
|--------|----------------|------------|
| Local trace → global coordination | Reynolds 1987 | JSONL stigmergy + quorum thresholds |
| Audit continuity | Landauer 1961 (irreversibility metaphor) | `System/stigmergic_ledger_chain.py` |
| Boundary summary | DYOR §14 | `holographic_stigmergy_projection.boundary_digest` |

---

## 16. Batch 11 — Willow QEC, Adinkras, heterotic E8 (2026-04-17)

*Web pull (CP2F). **Epistemic guardrail:** viral clips sometimes mix **established results** with **speculative** “reality as code” narratives. Rows below separate **peer-reviewed** anchors from **non-established** pop-science claims.*

### 16.1 Below-threshold surface codes on **Willow** (primary)

- **Google Quantum AI — “Quantum error correction below the surface code threshold”** — *Nature* **638**, 920–926 (2024). DOI `10.1038/s41586-024-08449-y` — superconducting **Willow** processors; distance-5 / distance-7 surface-code memories; real-time decoding — **this** is the citable hardware/QEC result (not “fractal output proves E8”).

### 16.2 Adinkras and classical error-correcting **structure** in supersymmetry

- **Doran, Faux, Gates, Hübsch, Iga, Landweber & Miller — “Codes and supersymmetry in one dimension”** — *Advances in Theoretical and Mathematical Physics* **15** (6), 1909–1970 (2011). DOI `10.4310/ATMP.2011.v15.n6.a7` — arXiv `1108.4124` — Adinkra graphs tied to **doubly-even** classical codes (rigorous math; **not** the same claim as “the universe is an error-correcting code” in pop form).

### 16.3 E8 × E8 in heterotic string theory (standard textbook result)

- **Gross, Harvey, Martinec & Rohm — “Heterotic String Theory (I). The Free Heterotic String”** — *Nuclear Physics B* **256**, 253–284 (1985). DOI `10.1016/0550-3213(85)90494-4` — gauge embedding includes **E8×E8** (or Spin(32)/ℤ₂) as consistency constraint — **not** an empirical claim that a QC bitstring “mapped onto E8” proves a universal OS.

### 16.4 What this batch does **not** establish

- Mapping a **generic** quantum-computation output stream to **E8 lattice “scaffolding of reality”** is **not** a settled inference from the Nature Willow paper or standard string-theory references above; treat such documentary lines as **hypothesis / storytelling** unless backed by a specific preprint with reproducible protocol.

### 16.5 Mapping (Batch 11 → code)

| Layer | Peer anchor | SIFTA hook |
|-------|-------------|------------|
| Syndrome / recovery narrative | Nature 2024 (surface code) | `stigmergic_syndrome_log.log_syndrome()` for **symbolic** audit syndromes |
| Code-like structure in math | Faux *et al.* 2011 (Adinkras) | pedagogy only — do not confuse with runtime crypto |
| Gauge group vocabulary | GHMR 1985 | narrative alignment with `DYOR` §14 string notes |

---

## 17. Batch 12 — bioelectric “anatomy” (electricity as morphogenetic signal) (2026-04-17)

*Web pull (CP2F): peer-reviewed **developmental bioelectricity** — useful for Alice-as-organism when **blood = electricity** is **metaphor** (real biology: resting potentials + gap junctions, not hemoglobin).*

### 17.1 Non-neural bioelectric networks — patterning and regeneration

- **Levin — “Endogenous bioelectrical networks store non-genetic patterning information during development and regeneration”** — *The Journal of Physiology* **592** (11), 2295–2305 (2014). DOI `10.1113/jphysiol.2014.271940` — PMC `PMC4048089` — spatio-temporal **V_mem** patterns as instructive morphogenetic signals (parallel: SIFTA **state vectors** + CRDT, not “blood chemistry”).

### 17.2 Endogenous DC electric fields — migration / wound epithelium

- **McCaig, Rajnicek, Song & Zhao — “Controlling cell behavior electrically: current views and future potential”** — *Physiological Reviews* **85** (3), 943–978 (2005). DOI `10.1152/physrev.00020.2004` — physics of **endogenous** fields; electrotaxis in wound healing (parallel: **directed repair** jobs after immune flare).

### 17.3 Embryonic fields (historical / framing)

- **Nuccitelli — “Endogenous electric fields in embryos during development, regeneration and wound healing”** — *BioEssays* **25** (8), 759–767 (2003). PMID `14690282` — measured fields in development (use as **secondary** anchor; pair with Levin 2014 for modern synthesis). Wiley *BioEssays* landing page for DOI resolution.

### 17.4 Mapping (Batch 12 → Alice / AG31)

| Biological idea | Paper lane | SIFTA hook |
|----------------|------------|------------|
| Bioelectric prepattern | Levin 2014 | identity field + metabolic/epistemic **surfaces** as layered control |
| Field-guided repair | McCaig *et al.* 2005 | post-quarantine **homeostasis** + integrity rounds |
| “Clinical” check | — | `System/organism_clinical_snapshot.py` |

---

## 18. Batch 13 — top-down processing & interactive reading (2026-04-17)

*Web pull (CP2F): cognitive anchors for **Turn 23** environmental typo shield (`swarm_top_down_processing.py`).*

### 18.1 Perception as hypothesis (top-down)

- **Gregory — “Perceptions as hypotheses”** — *Philosophical Transactions of the Royal Society B* **290** (1138), 181–197 (1980). DOI `10.1098/rstb.1980.0090` — perception as **hypothesis testing** using stored knowledge; illusions as clues to processing — parallel: **engram table** correcting noisy tags.

### 18.2 Interactive top-down / bottom-up (reading as prototype)

- **Rumelhart — “Toward an interactive model of reading”** — in *Attention and Performance VI* (1977); often cited as CHIP report (1976) — parallel processing with **feedback** from expectations — parallel: token normalization **before** core swarm logic.

### 18.3 Mapping (Batch 13 → code)

| Concept | Reference lane | SIFTA hook |
|--------|----------------|------------|
| Hypothesis-driven completion | Gregory 1980 | explicit `_ENGRAM_ANCHORS` substitutions |
| Expectation ↔ input interaction | Rumelhart 1977 | regex whole-word pass + JSONL audit |

---

## 19. Batch 14 — hypothalamus as homeostatic hub (swimmer sectors metaphor) (2026-04-17)

*Web pull (CP2F): **real** hypothalamic functions for AG31’s “fleet under the thalamus” narrative; sector boundaries are **didactic** (overlap in vivo).*

### 19.1 Integrative stress / autonomic network

- **Nakamura *et al.* — “A hypothalamomedullary network for physiological responses to environmental stresses”** — *Nature Reviews Neuroscience* **23** (9), 563–578 (2022). DOI `10.1038/s41583-021-00532-x` — PMID `34728833` — DMH–medullary pathways; **preoptic** inputs gate thermal / infection stress responses.

### 19.2 Preoptic area — thermoregulation & sleep coupling

- **Zhao & Zheng — “Role of the Preoptic Area in Sleep and Thermoregulation”** — *Frontiers in Neuroscience* **15**, 664781 (2021). DOI `10.3389/fnins.2021.664781` — PMC `PMC8280336` — POA circuits link **sleep** and **body temperature**.

### 19.3 Median eminence — neuroendocrine “portal”

- **Barrett *et al.* — median eminence / portal system** — standard neuroendocrine chapters (e.g. *Comprehensive Physiology* neuroendocrine reviews) — hypophysiotropic release at **median eminence** → anterior pituitary (conceptual parallel: **tuberal** “data link” in the user metaphor).

### 19.4 Posterior hypothalamus — arousal / wake

- **Saper *et al.* — “Brain structures and mechanisms involved in the control of cortical activation and wakefulness, with emphasis on the posterior hypothalamus and histaminergic neurons”** — *Sleep Medicine Reviews* **4** (4), 345–354 (2000). DOI `10.1053/smrv.2000.0119` — **histaminergic** tuberomammillary / posterior hypothalamic contributions to wake.

### 19.5 Mapping (Batch 14 → code)

| Sector (metaphor) | Biology (approx.) | SIFTA hook |
|-------------------|-------------------|------------|
| Preoptic front | POA thermo + sleep | `hypothalamic_swim_sectors.PREOPTIC` → serotonin / dream / entropy |
| Tuberal middle | median eminence / arcuate | `TUBERAL` → metabolic throttle / budget |
| Posterior back | arousal / wake promotion | `POSTERIOR` → dopamine engines / GCI |

---

## 20. Batch 15 — glymphatic CSF, sleep oscillations, pineal melatonin (2026-04-17)

*Web pull (CP2F): **evidence-first** CSF dynamics + circadian endocrinology. Popular “pineal breathing → mysticism” content is **not** peer-reviewed as stated; separate **faith/wellness** claims from mechanisms below.*

### 20.1 Glymphatic pathway (CSF–interstitial exchange)

- **Iliff *et al.* — “A Paravascular Pathway Facilitates CSF Flow Through the Brain Parenchyma and the Clearance of Interstitial Solutes, Including Amyloid β”** — *Science Translational Medicine* **4** (147), 147ra111 (2012). DOI `10.1126/scitranslmed.3003748` — PMC `PMC3551275` — foundational **glymphatic** description; AQP4 relevance.

### 20.2 Sleep-coupled CSF oscillations (human)

- **Fultz *et al.* — “Coupled electrophysiological, hemodynamic, and cerebrospinal fluid oscillations in human sleep”** — *Science* **366** (6465), 628–631 (2019). DOI `10.1126/science.aax5440` — PMC `PMC7309589` — large-amplitude **CSF** dynamics in NREM coupled to neural/hemodynamic rhythms.

### 20.3 Pineal gland — melatonin (endocrine physiology)

- **NCBI Bookshelf — “Physiology of the Pineal Gland and Melatonin”** (*Endotext*) — `https://www.ncbi.nlm.nih.gov/books/NBK550972/` — circadian **melatonin** secretion, sympathetic innervation — use for **hormone-level** grounding (not metaphysical claims).

### 20.4 Epistemic guardrail (videos vs papers)

- **Respiratory–CSF coupling** exists in modern imaging literature (e.g. forced respiration studies), but **specific** “pineal breathing technique ⇒ guaranteed transcendence / CSF mysticism” is **not** established as a single reproducible clinical endpoint in the same way as Iliff/Fultz mechanisms — keep wellness narratives **orthogonal** to SIFTA ledgers.

### 20.5 Mapping (Batch 15 → code)

| Idea | Anchor | SIFTA hook |
|------|--------|------------|
| Flush completes → other nodes observe | Iliff 2012; Fultz 2019 | `glymphatic_pulse_gate.record_pulse()` from `glymphatic_flush()` |
| Circadian / sleep phase | Pineal melatonin reviews | pairs with `serotonin_homeostasis` sleep flag + `swarm_sleep_cycle` |

---

## 21. Batch 16 — microswimmers, targeted “handshakes,” genomic surveillance (spec vs science) (2026-04-17)

*Web pull (CP2F): separate **aspirational futurism** from **today’s** mechanisms. Nanobot medicine as described in popular prompts is **not** standard clinical care; cite engineering + pharmacology reviews honestly.*

### 21.1 Microrobotics — engineering state of the art

- **Palagi & Fischer — “Bioinspired microrobots”** — *Nature Reviews Materials* **3**, 113–124 (2018). DOI `10.1038/s41578-018-0016-9` — materials, locomotion, collective behaviors at sub-mm scales — **not** a claim of arterial plaque “scrubbing” bots in routine use.

### 21.2 Molecular targeting (“handshake” in medicine today)

- **Dumontet *et al.* — “Antibody–drug conjugates come of age in oncology”** — *Nature Reviews Drug Discovery* **22**, 641–661 (2023). DOI `10.1038/s41573-023-00709-2` — antibody-mediated **delivery** with toxic payloads; illustrates **binding-based** specificity and real **off-target / toxicity** constraints.

### 21.3 DNA damage, p53, apoptosis — biological “checksum / debugger” metaphor

- **Kastenhuber & Lowe — “Putting p53 in Context”** — *Cell* **170** (6), 1062–1078 (2017). DOI `10.1016/j.cell.2017.08.028` — stress sensing, tumor suppression, apoptosis programs — **not** literal SHA-256 in cells.

### 21.4 Security / adversarial note (why crypto metaphors matter)

- Any future in-body **software** carrier implies **threat modeling** (key management, supply chain, authentication). Peer security literature is separate from molecular biology; SIFTA maps this to **filesystem governance** (`swimmer_handshake_gate`, hash chains).

### 21.5 Mapping (Batch 16 → code)

| Futurist idea | Grounded anchor | SIFTA hook |
|---------------|-----------------|------------|
| Swarm coordination | Palagi & Fischer 2018 (collective microrobotics) | stigmergy JSONL + quorum patterns |
| Targeted release | Dumontet *et al.* 2023 | `swimmer_handshake_gate.evaluate_release()` |
| Mutation / apoptosis surveillance | Kastenhuber & Lowe 2017 | narrative alignment with `apoptosis.py` / immune layers |

---

## 22. Batch 17 — oxytocin, social bonding, trust weighting (Turn 28) (2026-04-17)

*Web pull (CP2F): **attachment / social neuromodulation** anchors for `System/oxytocin_social_bond.py`. Corrected Insel & Young DOI: Claude-tab paste had `10.1038/35058579`; Nature’s article landing page uses **`10.1038/35053579`** (`https://www.nature.com/articles/35053579`).*

### 22.1 Pair bonding, attachment, oxytocin — foundational review

- **Insel & Young — “The neurobiology of attachment”** — *Nature Reviews Neuroscience* **2**, 129–136 (2001). DOI `10.1038/35053579` — oxytocin / vasopressin and species differences in attachment behavior.

### 22.2 Oxytocin — human brain systems (limbic / social cognition)

- **Meyer-Lindenberg *et al.* — “Oxytocin and vasopressin in the human brain”** — *Nature Reviews Neuroscience* **12**, 524–538 (2011). DOI `10.1038/nrn3044`.

### 22.3 Oxytocin, social support, HPA / stress responsivity

- **Heinrichs *et al.* — “Social support and oxytocin interact to suppress cortisol and subjective responses to psychosocial stress”** — *Biological Psychiatry* **54** (12), 1389–1398 (2003). DOI `10.1016/S0006-3223(03)00465-7` — PMC `PMC2800524` — experimental context for “social buffering” of threat responsivity (metaphor: dampen non-critical threat tags toward bonded sources).

### 22.4 Mapping (Batch 17 → code)

| Idea | Anchor | SIFTA hook |
|------|--------|------------|
| Bonded source weighting | Insel & Young 2001; Meyer-Lindenberg 2011 | `OxytocinSocialBond.interact()` → attention / DA nudge |
| Threat dampening under trust | Heinrichs 2003 (stress buffering) | `threat_suppressed` when bond ≥ floor |
| Non-self / immune override | Janeway-style tolerance vs rejection | `HARDCODED_THREAT_TYPES` never softened |

---

## 23. Batch 18 — hippocampal replay, two-stage consolidation, spaced repetition (Turn 30) (2026-04-17)

*Web pull (CP2F): **offline replay / consolidation** + **spacing** anchors for `System/hippocampal_replay_scheduler.py`. Eichenbaum DOI: tab text sometimes lists `…08.023`; Elsevier / *Neuron* landing uses **`10.1016/j.neuron.2004.08.028`**. PMID `15450164`.*

### 23.1 Two-stage memory traces & “noisy” brain states

- **Buzsáki — “Two-stage model of memory trace formation: A role for ‘noisy’ brain states”** — *Neuroscience* **31** (3), 551–570 (1989). DOI `10.1016/0306-4522(89)90423-5` — PMID `2687720` — frames online vs offline phases relevant to scheduling replay outside waking ingest.

### 23.2 Hippocampus — declarative memory and relational coding

- **Eichenbaum — “Hippocampus: cognitive processes and neural representations that underlie declarative memory”** — *Neuron* **44** (1), 109–120 (2004). DOI `10.1016/j.neuron.2004.08.028` — relational / episodic scaffolding (high-level analogue: relational edges between engram ids, not raw token storage).

### 23.3 Spaced repetition — SM-2 lineage (algorithmic spacing)

- **Wozniak & Gorzelanczyk — “Optimization of repetition spacing in the practice of learning”** — *Acta Neurobiologiae Experimentalis* **54** (1), 59–62 (1994). Open journal index: `https://ane.pl/index.php/ane/article/view/1003` — inter-repetition interval expansion under controlled recall (engine: ease_factor + `next_due_ts`).

### 23.4 Mapping (Batch 18 → code)

| Idea | Anchor | SIFTA hook |
|------|--------|------------|
| Offline replay window | Buzsáki 1989 | `execute_replay_session()`; call **before** `glymphatic_flush()` in `trigger_sleep_cycle()` |
| Relational / declarative prioritization | Eichenbaum 2004 | `consolidation_priority` weights stability + ease updates |
| Expanding retrieval intervals | Wozniak & Gorzelanczyk 1994 | SM-2-style `ease_factor` and `interval_s` growth |
| Volatile vs durable store | — | `hippocampal_engrams.json` (durable) + `pfc_working_memory.json` `fused_working_memory` merge |
