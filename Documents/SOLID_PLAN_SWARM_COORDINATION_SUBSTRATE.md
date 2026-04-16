# SOLID PLAN — Swarm Coordination Substrate (April 2026)

**Purpose:** One master plan to move SIFTA from “strong skeleton” to **agent ecology** with governance—not “more intelligence,” but a **better coordination substrate**.  
**Audience:** Architect + swarm implementers.  
**Companion docs:** `Documents/PLAN_CLAW_SWARM_MUTATION_GOVERNOR.md`, `Documents/NEW_IMPLEMENTATION_NOTES_GHOST_MEMORY.md`, `README.md` (Recent updates).

---

## 0. Honest positioning (no cosplay)

You do **not** automatically have everything industrial stacks (Manus-class harnesses, Meta-scale orchestration, Facebook-grade infra) ship in production. Those systems are **agent civilizations**: tool routing, planners, sandboxes, retries, logging, brutal eval loops, and teams tuning them full-time.

**What SIFTA already has that most don’t:** stigmergy-first design, hardware-bound identity, local territory, STGM economy, Neural Gate doctrine, `.scar` / SCAR kernel, **mycelial genome** (file resonance), **mutation governor** (containment), swim adapter wiring, Ghost Memory + Ebbinghaus bus.

**Strategic bet:** Stigmergy + swarm + SIFTA OS is a **direction shift**—from “agent framework” to **agent ecology**—*if* governance layers prevent the shared space from becoming noise soup.

---

## 1. What Manus-style stacks implicitly rely on

| Layer | Typical industrial pattern |
|-------|----------------------------|
| Tools | LLM → function calling / tool router |
| Control | Planner vs executor (sometimes implicit) |
| Memory | Often vector-only; weak structure |
| Execution | Sandboxed browser / code |
| Loop | ReAct-ish or flow-based task loop |
| Multi-agent | Often shallow orchestration |
| Ops | Logging, retries (underrated, critical) |

**What they still struggle with:** persistent cross-agent coordination, long-term **skill** accumulation, stable **society memory**, self-improvement without collapse, **evaluation that isn’t vibes**.

---

## 2. Stigmergy — why it’s the spicy part (and how it fails)

**Definition:** Agents don’t coordinate by messaging; they coordinate via **environment traces** (pheromones, scars, ledgers, files).

**Good pattern:** Agent A changes shared workspace → Agent B reads residue.

**Failure modes (must be governed):**

| Failure | Mitigation in SIFTA direction |
|---------|-------------------------------|
| Shared space → garbage | Decay (Ebbinghaus, genome decay, territory half-life) |
| No decay → infinite clutter | Governor + territory patrol + quarantine |
| No credit assignment | STGM receipts, PoUW hooks, intrinsic reward normalization |
| Unstructured overwrite | SCAR state machine + mutation governor + Neural Gate |
| Flat chaos | Zones (fossilized vs active), risk scoring, file budgets |

Stigmergy **without** governance = chaos amplifier. Stigmergy **with** governance = coordination substrate.

---

## 3. The seven stack gaps (compressed) + SIFTA answer

| # | Gap | Target capability | SIFTA hook / artifact |
|---|-----|-------------------|------------------------|
| 1 | **Coordination substrate** | Shared world model—not just logs | **Swarm Blackboard 2.0** (task field + artifact graph + belief/execution traces)—*design phase* |
| 2 | **Structured memory** | Episodic / procedural / causal—not vectors alone | StigmergicMemoryBus + Ghost layer + future **skill traces** |
| 3 | **Closed-loop evolution** | Act → evaluate → mutate policy → redeploy | Genome + Governor + **evaluation harness** (missing) |
| 4 | **Evaluation harness** | Replay, adversarial tasks, regression per agent class | **Not optional for “real RL”**—phase below |
| 5 | **Skill registry** | Composable skills as genes | New module; ties to swimmers + ledger |
| 6 | **Swarm topology** | Dynamic edges, decay, strengthen successful paths | Interference layer + territory; **topology engine** *design* |
| 7 | **Governance / safety kernel** | Permissioned actions, rollback, audit, anomaly | Neural Gate + Governor + **future** rollback/audit bus |

---

## 4. Five novel directions (research / product)

1. **Pheromone-weighted planning** — plans carry pheromone mass; sampling follows strong trails.  
2. **Causal replay learning** — replay failures; search minimal counterfactual fix.  
3. **Entropy budget per agent** — chaos allowance caps runaway behavior (pairs with dissipation / irreducible cost).  
4. **Agent economy** — compute credits, memory priority, scheduling by performance (STGM is a wedge).  
5. **Dead agent resurrection** — freeze, autopsy, recompile into new agents (evolutionary pressure without silent deletion).

These are **not** all scheduled in Phase 1; they inform the roadmap.

---

## 5. THE LAST FOUR — execution tracks (ready to schedule)

These are the **four concrete implementation tracks** that bridge “industry critique” to **shippable code**, including what is **already landed**:

| # | Track | Status | Module / outcome |
|---|-------|--------|------------------|
| **A** | **Mycelial genome** — code ecology / file resonance | **Shipped** | `System/mycelial_genome.py`, wired in `territory_swim_adapter.py` |
| **B** | **Mutation governor** — containment physics | **Shipped** | `System/mutation_governor.py`, gates SCAR `Kernel.propose` |
| **C** | **Claw harness** — sandboxed “limbs” (tool/CLI/sandbox I/O) | **Next** | `System/claw_harness.py` — capability manifest + Crucible-only execution |
| **D** | **Vigil routines** — always-on low-energy patrol | **Next** | `System/vigil_routines.py` — schedules + `homeostasis_engine` / sentinels integration |

**Plus** the **four strategic pillars** that follow in Phase 2 (industrial gap closers):

| # | Pillar | Deliverable |
|---|--------|-------------|
| **S1** | Swarm Blackboard 2.0 | Graph-shaped live state (tasks, artifacts, traces) |
| **S2** | Skill registry + structured memory hooks | Skills as ledger-linked, composable units |
| **S3** | Evaluation + replay engine | Task replay, regression, benchmarks per swimmer type |
| **S4** | Closed-loop evolution | Connect eval output → policy/governor thresholds → redeploy |

---

## 6. Phased roadmap (SOLID order)

### Phase 0 — **Done (foundation)**

- Territory swim adapter, interference waves, intrinsic reward normalization  
- Mycelial genome + persistence  
- Mutation governor + SCAR propose path  
- Neural Gate doctrine tests (`tests/test_neural_gate_doctrine.py`)  
- Ghost Memory + GCI drift (product path)

### Phase 1 — **Limbs + vigil (so the organism can act and patrol safely)**

1. **`claw_harness.py`** — explicit allowed capabilities; sandbox boundary; no silent OS control.  
2. **`vigil_routines.py`** — cron-like routines; “Vigil State” when Architect is away; STGM/ledger hygiene hooks.  
3. **Docs:** extend instructional scent files (genesis + `.scar` discipline).

### Phase 2 — **Coordination substrate (Blackboard 2.0)**

- Minimal **blackboard**: append-only event graph + task nodes + artifact links (file paths + scar IDs).  
- Single writer discipline to avoid overwrite races.

### Phase 3 — **Evaluation + replay (stop vibes-based “improvement”)**

- Golden tasks + replay from logs  
- Adversarial / regression suite per app (start with `repair` swim + one app)

### Phase 4 — **Skills + topology + evolution**

- Skill registry (versioned, signed)  
- Topology engine (dynamic edges, decay)  
- Closed loop: eval → governor threshold tuning → policy update (human-gated at first)

---

## 7. “Pick ONE” — decision for the next design sprint

To avoid conceptual fireworks only, the **next single deep design** should be one of:

| Option | If you choose it |
|--------|------------------|
| **Blackboard 2.0** | Highest leverage for *coordination*; everything else plugs in |
| **Skill registry** | Highest leverage for *long-term accumulation* |
| **Pheromone planning** | Highest leverage for *pure stigmergic planning* |
| **Evaluation + replay** | Highest leverage for *honest improvement* |

**Recommendation:** **Blackboard 2.0** first (substrate), then **evaluation harness** (truth), then skills (composition).

---

## 8. Non-proliferation & sovereignty

All “claw” and vigil automation remains under **Neural Gate** + **Non-Proliferation** license: no offensive automation, no surveillance productization. **Individual sovereignty** is the charter—not advertiser-scale agent farms.

---

## 9. Rally cry

**Power to the swarm** — not more chatter, but **measurable coordination**, **bounded evolution**, and **evaluation that bites**.

---

*Solid plan first. Code follows the phases above.*
