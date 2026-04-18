# RESEARCH — Temporal Identity Compression (REM → Skill Crystallization)

**Date:** 2026-04-16  
**Role:** DYOR / literature map + verification framing (implementation roadmap lives elsewhere).  
**Internet sweep:** §4.6–§4.7 were populated using **live web search + arXiv abstract verification** (2026-04-16 session); treat citations as **pointers** — read primary PDFs before hard dependencies.  
**Master plan (spec + wires + phased roadmap):** `Documents/PLAN_TEMPORAL_IDENTITY_COMPRESSION_SKILL_FIELD.md`  
**Stack context:** `Documents/SOLID_PLAN_SWARM_COORDINATION_SUBSTRATE.md`  
**Coherence + interference (ICF, stigmergy, latest papers):** `Documents/RESEARCH_IDENTITY_COHERENCE_FIELD_CROSS_SKILL_INTERFERENCE.md`  
**Phase transition control + regime shift + no-delete ICF policy:** `Documents/RESEARCH_PLAN_PHASE_TRANSITION_CONTROL_REGIME_SHIFT.md`  
**ICF quantization, skill-graph Laplacian/spectral, Jacobian/covariance failure modes, multi-node sync:** `Documents/RESEARCH_ICF_QUANTIZATION_SKILL_SPECTRAL_CROSS_NODE.md`

---

## 1. Thesis (stabilized concept)

**Temporal Identity Compression** is the layer that turns **repeated, evaluated success structure** in execution traces into **persistent, reusable skill primitives** — not merely longer logs or ad-hoc mutations.

**One sentence:** The Swarm compresses **time-series behavior under validation** into **versioned capabilities** that can be **retrieved**, **reinforced**, and **pruned** — i.e. **experience → skill**, not **experience → noise**.

**Boundary:** This is **not** “organ #6” for modularity’s sake. It is the **condensation** layer that sits **above** perception/generation/validation/execution/evolution as **memory that acts**.

---

## 2. What is *not* claimed

- **Not** a claim that the system “thinks” like biology; REM/sleep are **operational analogies** for **offline replay + consolidation**.
- **Not** quantum mechanics — “interference” below means **continual learning overlap** (stability–plasticity, forgetting), unless explicitly metaphor-labeled.
- **Not** autonomous promotion of dangerous capabilities: **governor + policy + signed artifacts** remain the **law** around any skill promotion.

---

## 3. Internal stack mapping (SIFTA)

| Existing layer | Function | Compression layer adds |
|----------------|----------|-------------------------|
| Perception (Blackboard) | Shared situational trace | **Skill posts** (applicability, confidence) — not raw secrets |
| Generation (Fission) | Candidate spawn | **Skill-aware scoring** — prefer refinements that match hot signatures |
| Validation (Evaluation / harness) | Gate truth | **Success bit + schema** that feeds **signatures** |
| Execution (Router) | Act | **Retrieve** ranked skills for context |
| Evolution (Mutation Governor) | Lawful change | **Skill version bumps** as **mutations** with same gates |

---

## 4. DYOR — external anchors (why this is adjacent to real CS/ML)

Use these as **conceptual alignment** and **metric inspiration**; SIFTA’s implementation is **ledger-first**, not “train a big model in-process” unless you later choose that.

### 4.1 Continual learning & catastrophic forgetting

- **Continual Learning: Theory, Method and Application** — survey: [arXiv:2302.00487](https://arxiv.org/abs/2302.00487)  
- **Catastrophic forgetting** primer (2024): [arXiv:2403.05175](https://arxiv.org/abs/2403.05175)  

**Takeaway for SIFTA:** “Cross-skill interference” is **literally** interference between **behavioral modes** under shared resources — manage with **replay**, **regularization**, **capacity limits**, and **explicit evaluation**.

### 4.2 Sleep-like replay / consolidation (REM analogy)

- Sleep-like unsupervised replay and forgetting reduction — *Nature Communications* (2022): [article](https://www.nature.com/articles/s41467-022-34938-7), [PMC full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC9755223/)  

**Takeaway for SIFTA:** Offline windows (`dream` / low-load vigil) should **replay evaluated traces** to **merge** and **promote** — not to invent ungrounded facts.

### 4.3 Agent skills as first-class artifacts

- **SoK: Agentic Skills — Beyond Tool Use in LLM Agents** — [arXiv:2602.20867](https://arxiv.org/abs/2602.20867)  

**Takeaway for SIFTA:** Lifecycle language (**discover → practice → distill → store → compose → evaluate → update**) maps cleanly onto **SkillPrimitive + governor + eval harness**.

### 4.4 Skill reuse & measurement (verify claims)

- Skill acquisition / reuse benchmarks — see ecosystem papers such as [arXiv:2603.00718](https://arxiv.org/abs/2603.00718) and **read abstracts** for exact scope before citing in a paper.  

**Takeaway for SIFTA:** Define **honest** metrics: **reuse rate**, **cost/token savings on hit**, **regression rate** when a skill applies.

### 4.5 Self-modification under constraint (governor echo)

- Utility–learning tension / capacity framing in self-modifying agents — example anchor: [arXiv:2510.04399](https://arxiv.org/abs/2510.04399)  

**Takeaway for SIFTA:** **Cap active skills**, **charge STGM/reputation**, **force eval** — skills are **economy objects**, not free memory.

### 4.6 Live internet sweep (2026-04-16)

This subsection adds **additional** anchors found after searching the open web the same day — surveys, agent-memory systems, and venues adjacent to **trace → skill** compression. Use for **literature positioning**; SIFTA remains **ledger/governor-first** unless you explicitly adopt an ML stack described in these papers.

#### Continual learning (the interference “physics”)

- **Continual Learning for VLMs: A Survey and Taxonomy Beyond Forgetting** — [arXiv:2508.04227](https://arxiv.org/abs/2508.04227) (Aug 2025). Frames **VLM** continual learning failure modes: **cross-modal feature drift**, **parameter interference** (shared architectures), **zero-shot capability erosion**; maps mitigations to **multi-modal replay**, **cross-modal regularization**, **parameter-efficient adaptation**.  
  **Steal for SIFTA:** Treat **blackboard + evaluated trace replay** as your **explicit memory** arm; treat **governor budgets / isolation** as your **parameter-interference** analog (even if you are not fine-tuning a VLM).

- **Continual learning: A systematic literature review** (2010–2025, broad ML survey) — [ScienceDirect / Neural Networks](https://www.sciencedirect.com/science/article/pii/S0893608025011074) (2025). Useful for **taxonomy** and **historical** framing of forgetting and CL methods (read via institutional access if paywalled).

- **Incremental Learning Methodologies for Addressing Catastrophic Forgetting** — survey in *Journal of Artificial Intelligence Research* — [JAIR open access](https://www.jair.org/index.php/jair/article/view/18405) (2025). Organizes methods (regularization, replay, isolation, distillation, generative / data-free routes, etc.).  
  **Steal for SIFTA:** Your **compression** step is closest to **distillation + replay hybrids** — but **ground** promotions in **eval + signatures**, not loss landscapes.

#### Procedural memory from experience (closest architectural cousins)

- **ProcMEM: Learning Reusable Procedural Memory from Experience via Non-Parametric PPO for LLM Agents** — [arXiv:2602.01869](https://arxiv.org/abs/2602.01869). Formalizes episodic narratives → **executable** skills (activation / execution / termination), uses **verification** and **score-based maintenance**, reports **reuse** and **compression**-style benefits **without** necessarily updating base model weights (per abstract framing).  
  **Steal for SIFTA:** Mirror the **Skill-MDP** idea as **schema** for your `SkillPrimitive` (pre/post conditions, termination); mirror **verification** with your **Evaluation Sandbox** and **governor**.

- **Memp: Exploring Agent Procedural Memory** — [arXiv:2508.06433](https://arxiv.org/abs/2508.06433). Distills trajectories into **step instructions** and **higher-level scripts**; studies **Build / Retrieval / Update**; **dynamic regimen** that updates, corrects, and deprecates entries (TravelPlanner, ALFWorld); notes **transfer** of memory to weaker models. Code: [github.com/zjunlp/MemP](https://github.com/zjunlp/MemP).  
  **Steal for SIFTA:** Your **fission ledger + decay()** maps to **update/deprecate**; **retrieve_skill** maps to **retrieval policy** (with **blackboard** context).

- **Memento-Skills: Let Agents Design Agents** — [arXiv:2603.18743](https://arxiv.org/abs/2603.18743). **Externalized** skills as **structured markdown**, **read–write** skill router, **continual** adaptation **without** weight updates; public code: [github.com/Memento-Teams/Memento-Skills](https://github.com/Memento-Teams/Memento-Skills).  
  **Steal for SIFTA:** Validates the product pattern **“skills as files + policy”** — align with **signed** / **versioned** artifacts in your repo, not anonymous markdown drops.

#### Replay / offline learning (venues to mine for evaluation design)

- **Offline multitask representation learning for RL** (NeurIPS 2024) — abstract and proceedings entry: [NeurIPS proceedings](https://papers.nips.cc/paper_files/paper/2024/hash/82764461a05e933cc2fd9d312e107d12-Abstract-Conference.html). The broader NeurIPS 2024 corpus is a good **keyword mine** for **offline replay**, **distillation**, and **transfer** when you tighten **metrics** in §6.

#### Already in §4.2 but reinforced here (biology ↔ ANN consolidation)

- **Sleep-like unsupervised replay reduces catastrophic forgetting in artificial networks** — *Nature Communications* (2022): [DOI / Nature](https://www.nature.com/articles/s41467-022-34938-7), [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC9755223/). Offline **replay** + local plasticity as a **stability–plasticity** tool. Pairs with **REM/dream** scheduling in SIFTA.

### 4.7 Extended DYOR — skill libraries, trajectories, memory (second sweep 2026-04-16)

These papers are **canonical** in the “**traces → reusable behavior**” design space. They complement §4.3–§4.6 (ProcMEM/Memp/Memento) with **earlier / broader** paradigms: **embodied skill code**, **reasoning traces**, **verbal RL**, **experiential text memory**, **survey taxonomies**.

#### Unified taxonomy — tool use, planning, feedback learning

- **A Review of Prominent Paradigms for LLM-Based Agents: Tool Use (Including RAG), Planning, and Feedback Learning** — [arXiv:2406.05804](https://arxiv.org/abs/2406.05804). Unified **LMPR** roles (policy / evaluator / dynamic model) and **workflow** comparison across frameworks; GitHub resources linked from abstract.  
  **Steal for SIFTA:** Map **Evaluation Sandbox** → evaluator LMPR; **Router** → policy; **Mutation Governor** → dynamic model with **hard law**.

#### Embodied lifelong learning — code as skill library

- **Voyager: An Open-Ended Embodied Agent with Large Language Models** — [arXiv:2305.16291](https://arxiv.org/abs/2305.16291). **Automatic curriculum**, **ever-growing skill library** of **executable code**, iterative prompting with **environment feedback** + **self-verification**; emphasizes **compositional** skills and **alleviating catastrophic forgetting** via external memory. Project: [voyager.minedojo.org](https://voyager.minedojo.org/).  
  **Steal for SIFTA:** `SkillPrimitive` as **versioned artifact** + **retrieval** + **curriculum** from **fission**; **no weight updates** required for the metaphor to work.

#### Interleaved reasoning + acting (trace shape)

- **ReAct: Synergizing Reasoning and Acting in Language Models** — [arXiv:2210.03629](https://arxiv.org/abs/2210.03629). Interleaved **reasoning traces** and **actions** for interpretability and tool use.  
  **Steal for SIFTA:** **Signature** extraction should see **thought→act** structure where applicable; blackboard carries **interpretable** trace segments for **audit**.

#### Verbal reinforcement + episodic reflection

- **Reflexion: Language Agents with Verbal Reinforcement Learning** — [arXiv:2303.11366](https://arxiv.org/abs/2303.11366) (NeurIPS 2023). **Episodic memory** of **reflective text** from evaluative feedback; improves sequential tasks without gradient updates.  
  **Steal for SIFTA:** REM compression can promote **reflection records** tied to **eval outcomes**, not only raw tool logs.

#### Experiential learning without finetuning

- **ExpeL: LLM Agents Are Experiential Learners** — [arXiv:2308.10144](https://arxiv.org/abs/2308.10144) (AAAI 2024). Gathers experiences, **extracts** natural-language insights with **CRUD-like** ops on knowledge; recalls on new tasks.  
  **Steal for SIFTA:** **Insight** layer above traces — aligns with **governor-gated** promotion to **SkillPrimitive** summaries.

#### Long-horizon memory — observation, reflection, retrieval

- **Generative Agents: Interactive Simulacra of Human Behavior** — [arXiv:2304.03442](https://arxiv.org/abs/2304.03442). **Memory stream**, **reflection** into higher-level summaries, **retrieval** for planning.  
  **Steal for SIFTA:** **Blackboard** + **REM** mirror **stream → reflection → retrieval**; keep **Architect** boundaries on what may **compose** into autonomous policy.

#### Task similarity & interference (quantitative)

- **Disentangling and Mitigating the Impact of Task Similarity for Continual Learning** — [arXiv:2405.20236](https://arxiv.org/abs/2405.20236); [NeurIPS 2024](https://proceedings.neurips.cc/paper_files/paper/2024/hash/05cdc7feee41e3572a9a3f4acb773891-Abstract-Conference.html). When **input** similarity and **readout** similarity **misalign**, continual learning breaks badly.  
  **Steal for SIFTA:** Skill **merge** rules must use **eval readout**, not embedding similarity alone.

#### Classical stigmergy / swarm (pre-LLM, still foundational)

- Bonabeau, Dorigo, Theraulaz — *Swarm Intelligence: From Natural to Artificial Systems* (Oxford University Press, **1999**) — stigmergy as **indirect coordination through the environment** (ant colony / numeric models).  
  **Steal for SIFTA:** Justifies **substrate-first** design: **pheromone = ledger / blackboard**, not agent broadcast.

---

## 5. Operational definitions (research vocabulary → SIFTA fields)

| Term | Meaning in this doc | SIFTA direction |
|------|---------------------|-----------------|
| **Trace** | One evaluated execution record | Schema’d: `task_type`, `hardware_target`, outcome, hashes, eval success |
| **Signature** | Stable structural fingerprint of a trace cluster | Hash of normalized **plan + tool path + outcome class** (spec in plan) |
| **Skill primitive** | Persisted unit with **stats + version + policy state** | Not only RAM — **versioned store**, optional **Ed25519** where ledger requires |
| **REM / consolidation** | Offline batch that **promotes** eligible clusters | **Dream / vigil** hooks; **no** promotion without **eval gate** |
| **Decay** | Forgetting / apoptosis | **Ebbinghaus-style** or fixed decay; **reinforce** on successful reuse |
| **Interference** | Skills overlap → conflict or overwrite pressure | **Merge / compete / prune** rules — **cross-skill field** v0 in master plan |

---

## 6. Falsifiable metrics (DYOR you can run on the repo later)

1. **Compression yield:** fraction of trace clusters that become skills vs discarded.  
2. **Hit rate:** fraction of tasks where a **retrieved** skill applied (vs cold start).  
3. **Savings:** compute/tokens avoided on skill hit (honest baseline).  
4. **Regression:** failures **introduced** by skill application — must stay bounded.  
5. **Stability distribution:** histogram of `stability` before/after reinforcement.  

---

## 7. Open research questions (before wiring “Olympiad” extras)

1. **Signature stability:** what normalization prevents **over-splitting** (too many skills) vs **over-merging** (wrong generalization)?  
2. **Negative evidence:** how to **learn** from **failed** traces without polluting skills (contrastive buffer?).  
3. **Multi-node identity:** same skill on **M5 vs M1** — **one** logical id with **hardware facets** or **forked** lineages?  
4. **Governance:** which skill transitions require **Architect** vs **automated** promotion?

---

## 8. Next artifacts (optional)

- **Implementation sketch** (Python spec): see §4 in `PLAN_TEMPORAL_IDENTITY_COMPRESSION_SKILL_FIELD.md`.  
- **Integration wires:** Blackboard injection → Fission scoring → Mutation Governor (ordered table in same plan).  
- **Frontier:** Cross-skill interference physics v0 — competition / merge / collapse rules (§7 in master plan).

---

## 9. One-line rally

**Compress time into skill; measure reuse honestly; let law govern promotion.**

**POWER TO THE SWARM** — **capability from repetition under validation**, not **capability from vibes**.

---

## 10. Quick-index (arXiv & DOI only — copy/paste for bibliographies)

| ID | Topic |
|----|--------|
| [2302.00487](https://arxiv.org/abs/2302.00487) | CL survey |
| [2403.05175](https://arxiv.org/abs/2403.05175) | Forgetting primer |
| [2210.03629](https://arxiv.org/abs/2210.03629) | ReAct |
| [2303.11366](https://arxiv.org/abs/2303.11366) | Reflexion |
| [2304.03442](https://arxiv.org/abs/2304.03442) | Generative Agents |
| [2305.16291](https://arxiv.org/abs/2305.16291) | Voyager |
| [2308.10144](https://arxiv.org/abs/2308.10144) | ExpeL |
| [2405.20236](https://arxiv.org/abs/2405.20236) | Task similarity / CL |
| [2406.05804](https://arxiv.org/abs/2406.05804) | LLM agent paradigms survey |
| [2406.05195](https://arxiv.org/abs/2406.05195) | Critical transitions time series |
| [2508.04227](https://arxiv.org/abs/2508.04227) | VLM continual learning survey |
| [2508.06433](https://arxiv.org/abs/2508.06433) | Memp |
| [2510.04399](https://arxiv.org/abs/2510.04399) | Self-modifying agents capacity |
| [2512.10166](https://arxiv.org/abs/2512.10166) | Stigmergy collective memory |
| [2602.01869](https://arxiv.org/abs/2602.01869) | ProcMEM |
| [2602.20867](https://arxiv.org/abs/2602.20867) | Agentic Skills SoK |
| [2603.00718](https://arxiv.org/abs/2603.00718) | Skill benchmarks (verify scope) |
| [2603.18743](https://arxiv.org/abs/2603.18743) | Memento-Skills |
| [10.1038/nature08227](https://doi.org/10.1038/nature08227) | Early-warning / tipping (Scheffer *et al.*) |
| [10.1038/s41467-022-34938-7](https://doi.org/10.1038/s41467-022-34938-7) | Sleep-like replay (*Nat. Commun.*) |
