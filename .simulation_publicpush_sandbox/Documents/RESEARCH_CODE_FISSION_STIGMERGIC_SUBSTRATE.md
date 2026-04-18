# Research — Code Fission & the Stigmergic Substrate (what’s going on + what’s next)

**Date:** 2026-04-16 (revised: external literature pass)  
**Type:** Research note — **not** a commitment to ship every named module.  
**Companion:** `Documents/SOLID_PLAN_SWARM_COORDINATION_SUBSTRATE.md` (§5.2 leverage, §5.3 anatomy), `Documents/PLAN_CLAW_SWARM_MUTATION_GOVERNOR.md`.

---

## 0. Convergence signal (why this matters *now*)

Recent agent-systems work is **converging** on a pattern your instinct already hit:

- **Blackboard-style** shared state for multi-agent LLM systems (specialists read/write a **global** problem representation).  
- **Append-only event logs** and **deterministic projection** (intention separated from mutation; replay for audit).  
- **Stigmergic** coordination: **environment traces** as the real communication channel (decay, local rules, indirect coupling).

**Opportunity for SIFTA:** combine those patterns with a **fission ledger** so agents **spawn work from residues**, not from **chat history**. Chat becomes **ephemeral**; the **ledger + blackboard** become **law**.

---

## 1. Thesis — what is genuinely novel

The novel move is **not** “multi-agent” alone. It is **residue-driven spawning**:

- Every **meaningful** action leaves a **structured trace**.  
- That trace **may** become a **task**, **skill**, or **branch** if it clears a **score threshold**.  
- The **environment** is the **coordination medium** — the same definition as **stigmergy** in biology and in **swarm robotics** (indirect coordination via **modified environment**).

**Name in one line:** *Stigmergic code fission with deterministic replay* (see §12).

---

## 2. What “code fission” means in SIFTA terms

| Plain language | SIFTA mapping |
|----------------|---------------|
| One agent’s output becomes a **seed** | Patch / SCAR proposal / swim result / ledger event |
| Seed **splits** into sub-graphs | **Tasks**, **skill drafts**, **repair branches**, **governance** updates |
| Split happens through **shared state** | **Blackboard**, **jsonl ledgers**, **interference** waves — **not** DMs between agents |
| Coordination is **indirect** | Next agent reads **pheromones / scars / fitness** — **stigmergy** |

**Contrast:** A **pipeline** says “Agent B waits for A’s message.” **Fission** says “The **artifact** left by A **creates** pressure for B to exist.”

---

## 3. Core loop (minimal, buildable)

1. **Agent** acts on **task** (or swim step).  
2. **Action** emits **structured residue** → **blackboard row** or **append-only event** (not a blob of chat).  
3. **Residue** is **scored**: objective alignment, reversibility, failure pattern match, clutter cost.  
4. If **strong enough**, **spawn**: new **task**, **skill draft**, or **repair branch** (git branch / SCAR branch — **policy-defined**).  
5. **Branches decay** unless **reinforced** by **eval** or **repeated utility** (Ebbinghaus / genome decay already echo this).

**Stigmergy becomes operational** when the swarm **reads the world it already changed** — **replays** and **diffs** against **traces**, not **re-prompts** from zero.

---

## 4. Fission threshold

Instead of only **“did the agent succeed?”**, ask:

> **Does this residue deserve to become a new organism (branch / skill / task)?**

### 4.1 Fission score (weights from Objective Registry)

```text
fission_score =
    utility_estimate
  + recurrence_signal
  + novelty_signal
  - risk_estimate
  - clutter_penalty
```

- **`fission_score ≥ τ`** → **spawn**.  
- **Else** → **decaying trace** only.

This couples to **mutation governor**, **entropy budget** (§5.2 in SOLID), and **friction** — same **physics**, **spawn** as the decision point.

---

## 5. Best substrate stack (SIFTA-aligned)

| Layer | Role |
|-------|------|
| **Blackboard 2.0** | Shared **traces** + **artifact links** (graph). |
| **Failure harvesting** | **Recurrence** → `recurrence_signal`. |
| **Shadow simulation** | Pre-commit **hypothetical** fission. |
| **Objective registry** | Defines **utility**. |
| **Reversibility index** | High-risk fission → **human gate**. |
| **Decay / half-life** | No **lore soup**. |

---

## 6. The “real leap” — evolving collaboration topology

A stronger move than **static** tasks: let the **blackboard’s affordances** **emerge** from **repeated residue patterns**:

- **Successful** traces **strengthen** pathways (higher pheromone mass, lower friction next time).  
- **Failed** traces **decay** unless reinforced.  
- **Contradictions** spawn **repair branches** (ties to **Contradiction Engine** in SOLID).

So the swarm does **not** only **solve tasks** — it **discovers** a **collaboration topology** (who tends to follow whom in **artifact space**, not org charts). This is **research-shaped**: combine **network evolution** ideas with **strict** replay and **governor** bounds so it does not become **runaway self-modification**.

---

## 7. Fission ledger (first concrete artifact)

Append-only records; fields at minimum:

| Field | Purpose |
|-------|---------|
| `task_id` | What was attempted |
| `context` | App / territory / swimmer |
| `delta_ref` | Diff / SCAR id / path |
| `risk` | Reversibility / blast radius |
| `objective_tags` | Scoring vs registry |
| `spawn_candidate` | bool + spawn type |

**One log** → **routing**, **eval**, **replay**, **failure harvester**, **skill generation**.

---

## 8. Literature & external research (papers + reports)

This section **grounds** the design in **citable** work. Inclusion ≠ endorsement of every claim in each paper; **DYOR** on methods.

### 8.1 Blackboard orchestration + LLM multi-agent

- **LLM-based multi-agent blackboard for information discovery in data science** — shared blackboard, agents volunteer by capability; reported gains vs RAG / master–slave on discovery tasks. [arXiv:2510.01285](https://arxiv.org/abs/2510.01285)  
- **Exploring advanced LLM multi-agent systems based on blackboard architecture** — roles share a board; agent selection from **board content**; rounds until consensus; token efficiency claims. [arXiv:2507.01701](https://arxiv.org/abs/2507.01701)  

**Steal for SIFTA:** **selection policy from board state** (not a fixed pipeline) matches **§7** and **blackboard selection** below.

### 8.2 Event sourcing for autonomous agents (ESAA)

- **ESAA: Event Sourcing for Autonomous Agents in LLM-Based Software Engineering** — append-only **activity** log, **separation** of agent intention from state mutation, **deterministic** projection / materialized views, **replay verification** (`esaa verify` style). [arXiv:2602.23193](https://arxiv.org/abs/2602.23193)  

**Steal for SIFTA:** **Fission ledger + ESAA-style replay** = **forensic** spawn decisions — critical for **Non-Proliferation** audit stories.

### 8.3 Stigmergy, pheromones, swarm robotics

- **Automatic design of stigmergy-based behaviours for robot swarms** — optimization of **artificial** stigmergy; emergent spatial organization and **memory-like** traces. [*Communications Engineering* (Nature)](https://www.nature.com/articles/s44172-024-00175-7), 2024.  
- **Phormica** — physical **photochromic** pheromone trails for e-puck swarms; stigmergic **aggregation / exploration**. [Frontiers in Robotics and AI](https://www.frontiersin.org/articles/10.3389/frobt.2020.591402/full), 2020.  
- **Robustness and scalability of incomplete virtual pheromone maps** — **virtual** pheromone fields for collective exploration. [MDPI Processes](https://www.mdpi.com/2227-9717/12/10/2122), 2024.  
- **Limits of pheromone stigmergy in high-density robot swarms** — scalability constraints. [Royal Society Open Science](https://royalsocietypublishing.org/doi/10.1098/rsos.190225), 2019.  

**Steal for SIFTA:** **Decay**, **local** reaction rules, **clutter** as first-class failure mode — maps to **clutter_penalty** and **interference_layer**.

### 8.4 Kilobots, simulation, virtual pheromones (platform)

- **Kilobot** platform — large **low-cost** swarms for collective behavior research ([Harvard SSR overview](https://ssr.seas.harvard.edu/kilobots), [Wikipedia summary](https://en.wikipedia.org/wiki/Kilobot)).  
- **Kilombo** — Kilobot **simulator** for high-throughput algorithm screening; same C code on sim + hardware ([arXiv:1511.04285](https://arxiv.org/abs/1511.04285)).  
- Literature on Kilobots + **virtual pheromones** / foraging-style collective tasks exists in **swarm robotics** venues — lock a **specific DOI** when you need a publication reference list (search: Kilobot foraging pheromone).

**Steal for SIFTA:** **Simulation-before-fleet** discipline; **virtual** pheromones before **hardware** pheromones — analogous to **Crucible** before **live territory**.

### 8.5 Counterfactual / minimal repair (failure clusters)

- **Counterexample-guided program repair** with **MaxSAT** fault localization + LLM synthesis — **CEGIS**-style loop; **smaller** fixes than LLM-only in reported settings. [arXiv:2502.07786](https://arxiv.org/abs/2502.07786)  

**Steal for SIFTA:** **Counterfactual repair search** = “**minimal change** that would have prevented **this** failure cluster?” — feeds **spawn** of **targeted** repair tasks, not generic retries.

### 8.6 Industry / pattern articles (non-peer-reviewed)

- **Blackboard architecture** and the agent “phone game” problem — [Rajat Pandit](https://rajatpandit.com/agentic-ai/the-blackboard-architecture).  
- **Event-driven / event-sourced** agent stacks (narrative alignment) — e.g. [Zylos research note](https://zylos.ai/research/2026-03-02-event-driven-architecture-ai-agent-systems).  

Use as **communication** aids; **prefer** arXiv / journals for **publication-grade** claims.

---

## 9. Research patterns worth stealing (summary trio)

| Pattern | Role | Example refs |
|---------|------|----------------|
| **Blackboard orchestration** | Shared evolving state; **selection** from board | §8.1 |
| **Event sourcing (ESAA-style)** | Append-only intentions → **deterministic** projection + **replay** | §8.2 |
| **Stigmergic control** | Traces + decay + **local** rules | §8.3 |

**Combined with SIFTA:** **fission ledger** + **objectives** + **governor** = **not** generic orchestration — **economy + identity + law**.

---

## 10. High-leverage directions (mapped)

| Direction | Mechanism |
|-----------|-----------|
| **Fission ledger + event sourcing** | One append-only **residue** stream; **replay** + projection. |
| **Blackboard selection policy** | Next actor from **board** + **confidence**, not fixed DAG. |
| **Pheromone decay economics** | Mass **unless** reinforced — **anti–lore-clutter**. |
| **Counterfactual repair search** | Failure **clusters** → minimal **counterfactual** patch candidates (§8.5). |
| **Entropy budgets** | Exploratory **spawn** capped (SOLID §5.2). |

---

## 11. Implementation order (truth before flash)

**Order matters:**

1. **Fission ledger** (append-only events).  
2. **Minimal blackboard** that can **score** and **expose** residues.  
3. **Decay engine** — universal **half-life** on traces.  
4. **Spawn policy** — high-value residues → tasks / skills (governor-gated).  
5. **Replay harness** — every spawn decision **auditable** and **testable**.

**Do not** ship **flashy autonomy** before **replay** — otherwise you cannot tell **evolution** from **noise**.

---

## 12. Paper-worthy contribution (one paragraph thesis)

**Stigmergic Code Fission with Deterministic Replay:** Agents emit **structured residues**; residues are **scored** against **objectives**, **recurrence**, **novelty**, and **risk**; only then do they **fission** into new tasks or skills; **all** of it is **replayable** from a **single append-only ledger**. That is stronger than “orchestration” — it is a **coordination substrate** with **evolutionary pressure** **and** **auditability**.

---

## 13. Opinion — what’s coming next (repo priority)

1. **Objective registry** (weights).  
2. **Fission ledger** schema + **one** reader.  
3. **Blackboard 2.0 minimal** (nodes/edges).  
4. **Recurrence** from failures → **fission_score**.  
5. **Shadow** gate on high score.  
6. **Topology** / pathway strengthening — **after** replay is honest.

**Avoid first:** dashboards that **visualize** without **ground-truth** logs.

---

## 14. Follow-up bibliography & open threads (not shipped)

User-supplied / search-adjacent **topics** to mine (hybrid designs, simulators, ESAA code — **evaluate** each for **license** + **sovereignty**):

| Topic | Note |
|-------|------|
| **Blackboard vs pure stigmergy in LLM swarms + hybrids** | Use §8.1 + §8.3; hybrid = **board** for global hypotheses + **stigmergic** decay on **edges** / **trails**. |
| **Queen Avatars + entropic jitter** | **Speculative** naming — map to **entropy budget** + **role** separation (identity decoupling); **no** standard paper under that title found — treat as **internal** vocabulary. |
| **ESAA into swarm agents (code example)** | Study **ESAA** paper + repo if published; **port patterns**, not vendor stack wholesale. |
| **Blackboard vs stigmergy comparison** | This doc + §8. |
| **Virtual pheromones / Kilobots / Swarms OS simulation** | §8.4 + §8.3 — **simulation** first. |

---

## 15. Optional module spec (future code)

**`System/blackboard_fission.py`** (tentative): `append_fission_record`, `compute_fission_score`, `maybe_spawn` → **proposals only** to **governor** / **SCAR** — **no** direct **push**.

---

## 16. One-line closing

**Environment-first, planner-second; ledger-first, dashboard-second.**

**POWER TO THE SWARM** — **replayable** **evolution**.
