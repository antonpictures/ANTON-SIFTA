# Stigmergic prediction — biology + math nuggets for Alice (SIFTA)

**Truth label:** `RESEARCH_NOT_SHIPPED` until an organ ships with **pytest + JSONL receipt schema** (see `Documents/RESEARCH_DIRT_INDEX.md` §E).

**For the Swarm.**

This note pulls **peer-reviewed / OA** material on **stigmergy** (indirect coordination via environmental traces) and the **mathematics** used to model it, then maps it to a **stigmergic prediction** organ for Alice: *predicting George’s next moves from ledger trails + schedule physics without treating opaque scores as facts* — aligned with **Carissa Véliz** (prediction as **speech act / power**, contestability) and covenant **§6 / §7.2** (effector truth).

---

## 0. Terminology (SIFTA lab)

| Phrase | Meaning here |
|:---|:---|
| **Stigmergy** | Agents coordinate by **reading/writing a shared field** (pheromone, nest pellet, `ide_stigmergic_trace.jsonl`, `repair_log.jsonl`, …). |
| **Stigmergic prediction** | **OBSERVED/HYPOTHESIS:** infer *next likely* owner or swarm actions from **trace density + decay + coupling**, emit **calibrated** priors + **explicit uncertainty**; never mint “fate” without receipts. |
| **Not** | Corporate “risk score” as unchallengeable oracle (Véliz critique). |

---

## 1. Classical biology — where “stigmergy” was born

1. **Grassé, P.-P. (1959)** — *La reconstruction du nid et les coordinations inter-individuelles chez Bellicositermes natalensis et Cubitermes sp. La théorie de la stigmergie.* **Insectes Sociaux** 6, 41–80. **DOI:** [10.1007/BF02223791](https://doi.org/10.1007/BF02223791)  
   - **Nugget:** nest reconstruction without central blueprint — **work stimulates work** via material state of the nest.

2. **Theraulaz & Deneubourg (chapters on coordinated building)** — e.g. *The mechanisms and rules of coordinated building in social insects* (Springer chapter). Example link: [10.1007/978-3-0348-8739-7_17](https://doi.org/10.1007/978-3-0348-8739-7_17)  
   - **Nugget:** local rules + **logistic constraints** (cement pellets, humidity) as **physical stigmergic variables**.

3. **Termite construction & logistics (J. Theor. Biol.)** — *The role of logistic constraints in termite construction of chambers and tunnels.* **DOI:** [10.1016/S0022-5193(04)00611-3](https://doi.org/10.1016/S0022-5193(04)00611-3) (Elsevier article id `S0022519304006113`).  
   - **Nugget:** geometry emerges from **material flow limits**, not from a global planner — good metaphor for **STGM / metabolic** caps shaping behaviour.

---

## 2. Mathematical stigmergy — PDEs, chemotaxis, reaction–diffusion

### 2.1 Keller–Segel family (continuous pheromone + population)

A standard **chemotaxis** scaffold (ants, micro-organisms):

\[
\partial_t u = D_u \Delta u - \chi\, \nabla\cdot (u \nabla v), \qquad
\partial_t v = D_v \Delta v + \alpha u - \beta v
\]

- \(u(x,t)\): agent density (or probability mass of foragers).  
- \(v(x,t)\): **pheromone / trace** concentration.  
- **Deposition** \(\alpha u\), **evaporation / degradation** \(\beta v\), **chemotactic drift** \(\chi u \nabla v\).

**Use for SIFTA:** treat each JSONL stream as a **discrete** \(v_k(t)\) on a graph (files, organs, contacts); diffusion = cross-correlation / co-access; evaporation = TTL / decay in fitness.

### 2.2 Ant foraging & trail formation (JTB)

- **Boatto *et al.*,** *Modeling ant foraging: A chemotaxis approach with pheromones and trail formation.* **J. Theor. Biol.** (2015). Article: [ScienceDirect S0022519315004270](https://www.sciencedirect.com/science/article/abs/pii/S0022519315004270)  
  - Coupled PDE/ODE foragers + trail dynamics; spontaneous trail emergence.

- **Colombelli *et al.*,** *A model for collective dynamics in ant raids.* **J. Math. Biol.** (2016). **DOI:** [10.1007/s00285-015-0929-5](https://doi.org/10.1007/s00285-015-0929-5)  
  - **Lanes / bidirectional flow** from stigmergic rules — useful when modelling **M5 ↔ M1** traffic on shared ledgers.

### 2.3 Continuified control — “design the trace field” (2024)

**Boldini, Civitella, Porfiri (2024)** — *Stigmergy: from mathematical modelling to control.* **R. Soc. Open Sci.** 11:240845. **DOI:** [10.1098/rsos.240845](https://doi.org/10.1098/rsos.240845) · **PMC:** [PMC11371424](https://pmc.ncbi.nlm.nih.gov/articles/PMC11371424/)

- **Core idea:** continuify swarm density \(\rho(x,t)\) and **trace density** \(\tau(x,t)\); **invert** “desired formation → required trace distribution” without central control of each agent.  
- **SIFTA mapping:** given a **desired** owner schedule envelope (George prior), compute **which ledger nudges** (reminders, STGM prices, gaze prompts) are **admissible traces** — explicit **control-theoretic** layer on top of ML token prediction.

### 2.4 Automatic design of stigmergy (2024)

**Salman, Garzón Ramos, Birattari (2024)** — *Automatic design of stigmergy-based behaviours for robot swarms.* **Commun. Eng.** 3, 30. **DOI:** [10.1038/s44172-024-00175-7](https://doi.org/10.1038/s44172-024-00175-7) · **PMC:** [PMC10956014](https://pmc.ncbi.nlm.nih.gov/articles/PMC10956014/)

- **Nugget:** **optimisation in simulation** discovers pheromone FSMs competitive with hand-tuned rules — relevant to **auto-tuning** RLHS thresholds / metabolic policies **under receipt constraints** (not “YOLO”).

### 2.5 Physical artificial pheromone (robot swarm hardware)

**Mayet *et al.* (2020)** — *Phormica: Photochromic Pheromone Release and Detection System for Stigmergic Coordination in Robot Swarms.* **Front. Robot. AI** 7:591402. **DOI:** [10.3389/frobt.2020.591402](https://doi.org/10.3389/frobt.2020.591402)

- **Nugget:** **decaying visible trails** as engineering analogue of `.jsonl` tail windows + **half-life** in UI.

---

## 3. Philosophy / policy anchor — Véliz on prediction (TED2026)

**Carissa Véliz** — *Beware the Power of Prediction* (TED2026; recorded 2026-04-14). Official pointer: [go.ted.com/carissaveliz](https://go.ted.com/carissaveliz)

**Operational hooks for Alice (not paraphrasing as proof):**

| Thesis (talk) | SIFTA implementation discipline |
|:---|:---|
| Predictions about **people** bend lives (speech acts). | Any “George will…” line carries **`HYPOTHESIS`** until backed by **schedule + ledger** rows; UI shows **confidence + provenance**. |
| “Inevitable future” as **conversation stopper**. | Predator Gate + **triple-IDE** receipts refuse silent merges; §7.12 **probe-before-claim**. |
| Contestability vs black-box scores. | Every automated suggestion includes **which features** (hash of inputs, time window) — Véliz-aligned **appeal surface**. |

---

## 4. Minimal “stigmergic predictor” spec (engineering sketch)

**Inputs (OBSERVED):** `stigmergic_schedule.jsonl`, `owner_body_events.jsonl`, `app_focus.jsonl`, `repair_log.jsonl`, GPS / BLE summaries (if enabled).

**State:** vector \(\mathbf{v}(t)\) of **trace intensities** per channel (file family, contact, organ).

**Dynamics (discrete time):**

\[
\mathbf{v}_{t+1} = \underbrace{(1-\lambda)\mathbf{v}_t}_{\text{decay}} + \underbrace{M \mathbf{x}_t}_{\text{events deposit}} , \qquad
\hat{\pi}_{t+1} = \mathrm{softmax}(W \mathbf{v}_{t+1} + \mathbf{b})
\]

- \(\mathbf{x}_t\): event counts this tick.  
- \(M\): learned or hand-set **stigmergy matrix** (start **sparse + signed**).  
- \(\hat{\pi}\): distribution over **next macro actions** (sleep, commute, code, message spouse, …) — **not** moral prophecy.

**Output contract:** top‑k hypotheses + **entropy** \(H(\hat{\pi})\) + **what would falsify** this turn (explicit).

---

## 5. Open gaps (honest)

- **No single paper** titles the phrase “stigmergic prediction” — this is a **SIFTA composition** of stigmergy + forecasting + governance.  
- **Causal identification** (Pearl / do-calculus) for owner behaviour is **not closed** here — if Alice ships prediction, pair with **counterfactual abstain** when receipts thin.

---

## 6. Cross-links (repo)

- `Documents/CANGELOSI_UK_HRI_STIGMERGY_BRIDGE_PLAN.md` — developmental robotics ↔ stigmergy bridge.  
- `Documents/OWNER_FACE_PREDATOR_RESEARCH_SPINE.md` — Grassé / nest stigmergy citations.  
- `Documents/PREDATOR_TOURNAMENT_TRIPLE_IDE_ORDERS.md` §7.1 — Event 74 spine (stigmergy math stack pointer).  
- `Documents/RESEARCH_HANTAVIRUS_PUBLIC_HEALTH_STIGMERGY_POINTER_2026-05-07.md` — **outbreak info** use of stigmergy (receipted sources only; medicine stays primary).

---

## 7. Stigmergic memory + unified field — plan ingest (Architect voice, 2026-05-07)

**Label:** `ARCHITECT_DOCTRINE` + `OPERATIONAL` engineering target (not yet a shipped organ).

### 7.1 Doctrine summary (George)

Instead of each agent or organ hoarding a full world model in RAM, **memory lives in the shared environment**:

- Deposits → append-only traces (`ide_stigmergic_trace.jsonl`, `work_receipts.jsonl`, episodic diaries, organ-specific JSONL).
- Organs **read** the field when they activate; the **current tail + decay policy** of the traces **is** the working memory.
- **Sensory field** (e.g. live `PhysicalSpaceReport`, mesh summaries) is the analogue of **pheromone concentration maps** in ants.

**Strength (Architect):** memory is **external, persistent, and queryable** — not locked in one Python process or one model context.

**Weakness (Architect):** it only works if (a) **schemas are disciplined** (typed columns, mandatory `trace_id`, `homeworld_serial`, effector `ok`/`truth_note`) and (b) **organs implement good foraging** — they must know **which** traces to load and at what TTL, otherwise the field becomes **noise soup** (same failure mode as overcrowded pheromone: see §8.2).

### 7.2 Covenant alignment (IDE_BOOT_COVENANT.md)

| Covenant | Stigmergic memory consequence |
|:---|:---|
| **§3.1** Stigmergic inference economy | Inference trades + **ledger heat** are first-class traces; do not hide economy in a private dict. |
| **§4** Predator Gate / append-only bus | Every writer **names itself**; collisions add **correcting rows**, never silent rewrite. |
| **§6** Social frame + effector | “Alice remembers X” for **external acts** must point at **effector JSONL**, not latent vectors alone. |
| **§7.10.4** Stigbody | Owner + desk + **ledgers** are one substrate; screenshots are **artifacts** with provenance limits, not hidden RAM. |

### 7.3 Unified field “lanes” (engineering checklist — tournament-ready)

1. **Deposit lane** — one writer module per ledger family; JSON Schema or `ledger_auditor` profile per file.  
2. **Decay / compaction lane** — half-lives + archive to cold storage (Phormica / high-density pheromone limits — §8.2).  
3. **Query lane** — FTS5 / tail helpers with **bounded** scans (no UI-thread full-file slurp — see `SWARM_PLAN_MATH_LOAD_OWNER_TRIPLE_IDE.md` lesson).  
4. **Attention lane** — Predator gaze + `app_focus.jsonl` chooses **which** traces enter prompt assembly.  
5. **Federation lane** (§3) — cross-node: **hashes + summaries only**, never raw `.sifta_state/` clone.

**Colosseum bar (index law):** no runtime default until **Predator row + pytest + receipt schema** exist for that lane (`RESEARCH_DIRT_INDEX.md` §E).

---

## 8. More papers — external / collective / digital stigmergic memory

6. **Campo, Nicolis, Deneubourg (2021)** — *Collective Memory: Transposing Pavlov’s Experiment to Robot Swarms.* **Appl. Sci.** 11(6), 2632. **DOI:** [10.3390/app11062632](https://doi.org/10.3390/app11062632)  
   - **Nugget:** **collective memory** as a swarm-level phenomenon built from **simple reactive rules** + environmental coupling — closest “memory” title to your unified field narrative.

7. **Pinciroli *et al.* (2019)** — *Testing the limits of pheromone stigmergy in high-density robot swarms.* **R. Soc. Open Sci.** 6:190225. **DOI:** [10.1098/rsos.190225](https://doi.org/10.1098/rsos.190225)  
   - **Nugget:** digital vs simulated vs environmental pheromones **saturate** — direct analogue to **JSONL spam** and **unbounded tail reads**; motivates **density caps + decay**.

8. **Valentini *et al.* (2014)** — *Stigmergic algorithms for multiple minimalistic robots on an RFID floor.* **Swarm Intell.** 8, 199–225. **DOI:** [10.1007/s11721-014-0096-0](https://doi.org/10.1007/s11721-014-0096-0)  
   - **Nugget:** **environment = RFID floor** stores the map; robots stay **memory-poor** — same design pattern as “thin organs, fat ledger”.

9. **Wang *et al.* (2016)** — *Stigmergic coordination in FLOSS development teams: Integrating explicit and implicit mechanisms.* **Cogn. Syst. Res.** **DOI:** [10.1016/j.cogsys.2015.12.003](https://doi.org/10.1016/j.cogsys.2015.12.003)  
   - **Nugget:** **artifacts + feedthrough** (issues, PRs, CI) as human **digital stigmergy** — validates SIFTA’s “IDE trace + git” as a **species-level** coordination medium, not only insect metaphor.

10. **Theraulaz & Bonabeau (1999)** — *A brief history of stigmergy.* **Artif. Life** 5, 97–116. **DOI:** [10.1162/106454699568700](https://doi.org/10.1162/106454699568700)  
    - **Nugget:** conceptual bridge from **biology → ALife / engineering** vocabulary; cite when writing Alice prompts that must stay **measurement-first** (covenant §7.10.3).

11. **Brambilla *et al.* (2013)** — *Swarm robotics: A review from the swarm engineering perspective.* **Swarm Intell.** 7, 1–41. **DOI:** [10.1007/s11721-012-0075-2](https://doi.org/10.1007/s11721-012-0075-2)  
    - **Nugget:** engineering checklist for **design → analysis → deployment** of swarm behaviours; use as **tournament rubric** skeleton.

---

## 9. Discrete “memory field” update (formal echo of §4)

Let trace types \(k=1..K\). At tick \(t\):

\[
v_{k,t+1} = (1-\lambda_k)\, v_{k,t} + \sum_j M_{kj}\, \mathbb{1}\{\text{event type }j\text{ at }t\}
\]

- \(v_{k,t}\): **salience** of ledger channel \(k\) after decay.  
- \(\lambda_k\): **per-lane forgetting** (Architect-tunable).  
- \(M_{kj}\): **deposit weights** (which events strengthen which memory lane).

**Reading policy** (fixes the weakness): each organ declares **`forage_spec`** (max lines, filters, required keys). Missing spec → **Auditor** may refuse merge (Predator tournament hygiene).

---

**Curated by:** CG55M@cursor (GPT-5.5 Medium) · node `GTH4921YP3` · 2026-05-07 · **updated** 2026-05-07 (§7–§9 stigmergic memory + papers).
