# SOLID PLAN — Swarm Coordination Substrate (April 2026)

**Purpose:** One master plan to move SIFTA from “strong skeleton” to **agent ecology** with governance—not “more intelligence,” but a **better coordination substrate**.  
**Audience:** Architect + swarm implementers.  
**Companion docs:** `Documents/PLAN_CLAW_SWARM_MUTATION_GOVERNOR.md`, `Documents/NEW_IMPLEMENTATION_NOTES_GHOST_MEMORY.md`, `Documents/RESEARCH_NEXT_EVOLUTIONARY_STEP_CRUCIBLE_LOOP.md`, `Documents/REPORT_VOICE_TTS_CAMERA_GEMMA_STACK.md`, `Documents/PLAN_ORGAN_ANATOMY_GROK_SYNTHESIS_AND_FRONTIER.md` (extended slice of §5.3), `Documents/RESEARCH_CODE_FISSION_STIGMERGIC_SUBSTRATE.md` (code fission + fission ledger), `Documents/PLAN_FINAL_BOSS_LAYER_MUTATION_GOVERNANCE.md` (governor ↔ fission ↔ eval closed loop), `README.md` (Recent updates).

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

### 5.1 Raw camera + “stigmergic vision” model (Architect direction — **DYOR**)

**Intent:** Close the loop between **world** and **swarm**: **raw camera access** (with explicit macOS permissions and user consent) feeds a pipeline that does **not** dump pixels into the ledger as truth — it emits **high-saliency traces** / **pheromones** into the shared field (`stigmergic_vision`, `sensory_cortex`, interference layer), aligned with `Documents/RESEARCH_NEXT_EVOLUTIONARY_STEP_CRUCIBLE_LOOP.md`.

| Layer | What to build | Notes |
|-------|----------------|-------|
| **Capture** | `AVCaptureSession` (or PyObjC bridge) — **raw frames** or **compressed keyframes** | **Ephemeral by default** on disk; promote-to-memory is a **policy action**. |
| **Vision backbone** | **Commodity VLM** (e.g. **Gemma 4 multimodal** checkpoint, **LLaVA-class**, **MLX**-friendly small VLMs) — **quantized** | You do **not** need to train ImageNet from scratch; the **differentiator** is **where** outputs go (stigmergy), not the ViT paper. |
| **Stigmergic head (your IP)** | Thin module: VLM **embedding / caption / tags** → **PheromoneWave** / blackboard row with **decay**, **STGM cost**, **saliency score** | This is the **“stigmergic vision model”** in the SIFTA sense — **policy + graph + economy**, not a 200B-parameter from-scratch LM. |
| **Full custom VLM** | Train a **new** large vision-language model **from scratch** | **Impractical** for most solo/small teams; only consider if you have **data + compute + eval** — default is **backbone + stigmergic head**. |

**M5 Mac Studio 24GB — is it “holding”? (DYOR, not financial advice for weights):**

- **Unified memory** means **RAM == VRAM pool** for Metal/MLX-style workloads — **24GB is workable** for **small/medium quantized VLMs** and **low FPS** sampling (not 30fps full-res 70B vision stacks).
- **Rule of thumb:** **~7B–9B class** models in **Q4** often fit with headroom for OS + PyQt + background swarm; **larger** (e.g. **30B+**) may **load** with aggressive quant + swapping but **hurt latency** and **starve** the desktop — **try before you commit** (`ollama` / **MLX** / `lmstudio`, watch **resident size** + **frame time**).
- **Throughput strategy:** **1 FPS** “context sampling” or **event-triggered** frames (motion/saliency prefilter) beats **continuous** 1080p30 inference.
- **Verify on your machine:** Apple’s **MLX + M-series** guidance (machinelearning.apple.com research notes for **M-series LLMs**) + your exact **model card** + quantization tag — **numbers move every release**.

**Governance:** Raw camera + vision **must** stay behind **Neural Gate**, **mutation governor**, and **non-proliferation** — no covert surveillance productization; **Architect-visible** indicators when capture is active.

### 5.2 Leverage mechanisms — *control forces, not more layers*

The structural plan is already strong: **you do not need more strata** — you need **leverage mechanisms** that make **mutation governor**, **entropy / dissipation ideas**, **STGM**, **blackboard**, **Claw**, and **temporal spine** **behave better over time**. The list below is **architecture-native**: constraints that **shape behavior**, not speculative feature soup.

| # | Mechanism | One-line role | Primary hooks |
|---|------------|---------------|----------------|
| 1 | **Friction layer** | Cost of **change**, not just compute — penalizes noisy mutation | Governor, genome proposals, STGM debit |
| 2 | **Reversibility index** | Score **undoability**; low score → **human gate** | Governor, `claw_harness`, planning |
| 3 | **Attention budget** | Hard cap on **reads / analyzes / writes** per cycle | Blackboard, vision, swimmers |
| 4 | **Contradiction engine** | Detect **conflicting** traces; spawn **resolution** | Blackboard 2.0, `INFERRED` vs ground truth |
| 5 | **Silence detection** | React to **missing** expected activity | Vigil, sentinels, territory zones |
| 6 | **Temporal layering** | **Three clocks** — wall, event density, cognitive load | `temporal_spine`, swim loop, UI urgency |
| 7 | **Shadow simulation** | **Dry-run** estimate of blackboard / risk **before** act | Crucible, Claw, governor pre-check |
| 8 | **Identity decoupling** | **`id` / lineage / policy / permissions** separated | PKI, swimmers, genesis (no mythology in kernel) |
| 9 | **Failure harvesting** | **Failures** as first-class, clustered, feed improvement | Logs, eval harness, PoUW receipts |
| 10 | **Objective function registry** | **Explicit** weighted objectives — every policy references them | STGM, governor thresholds, eval metrics |

---

#### 1 — Friction layer (anti-runaway intelligence)

**Gap:** Governor + entropy + economy still allow **over-eager** mutation if “cheap” in the wrong dimension.

**Idea:** Every action pays **friction** — **state disruption**, not only FLOPs:

```text
friction_cost(action, state_delta) =
    complexity(action)
  + magnitude(state_delta)
  + novelty_penalty(action)
```

**Why it matters:** Prefer **small, reversible** edits; stabilize stigmergy (less blackboard noise). Biology works because **change is expensive**.

**Fit:** Feed **friction_cost** into `MutationGovernor.allow(...)` as an additive **tax** or **hard ceiling**; pair with **dissipation / irreducible cost** organs already in the philosophical stack.

---

#### 2 — Reversibility index (safety + evolution)

**Gap:** Mutations occur — **clean undo** is not always defined.

**Idea:** Each action carries **reversibility_score** ∈ [0, 1]. **1.0** = fully reversible (e.g. git revertable, Crucible-only); **0.0** = destructive / irreversible.

**Policy:** `if reversibility_score < threshold: require_human_gate()` (Neural Gate / Architect flag).

**Why:** **Aggressive experimentation** in sandboxes + **terror-free** live territory.

---

#### 3 — Attention budget (true swarm limiter)

**Gap:** Bounded **memory**, **mutation**, **compute** — but not **attention**, so **scan loops** and **everything-at-once** behavior can still blow up.

**Idea:** Per agent, per cycle: finite **attention tokens** spent on:

- read blackboard / trace  
- observe vision  
- write / mutate  
- spawn / delegate  

**Example sketch** (tunable): `ATTENTION_BUDGET = 100` with costs e.g. `read_trace=5`, `analyze_event=10`, `write_trace=8`, `spawn_agent=50`.

**Why:** Forces **prioritization** and **specialization**; prevents infinite lateral scanning.

**Fit:** Blackboard reader API + swim loop scheduler; complements **§5.2.1** friction.

---

#### 4 — Contradiction engine (truth stabilizer)

**Gap:** Traces **accumulate**; **active reconciliation** of conflicting beliefs is optional in most systems.

**Idea:** When `belief_A.conflicts_with(belief_B)` on the blackboard → **spawn_resolution_task()**: replay evidence, request observation, or **downgrade confidence** (especially for `INFERRED` / dream traces).

**Why:** Without it, the swarm becomes **inconsistent lore**; with it, **self-correction** becomes a first-class loop.

**Fit:** Ghost / ledger discipline; do **not** let contradictions silently merge into “truth.”

---

#### 5 — Silence detection (missing-signal response)

**Gap:** Systems react to **events**; few react to **absence** of expected events.

**Idea:** For each **zone** or **subsystem**, compare `expected_activity(zone)` vs `actual_activity`; on deficit → **probe** (sentinel, vigil ping, health check).

**Why:** Catches **missed tasks**, **dead pipelines**, **broken heartbeats** before a human notices.

---

#### 6 — Temporal layering (time done right)

**Idea:** Three clocks:

| Clock | Driver | Use |
|-------|--------|-----|
| **Wall** | Real time | Deadlines, leases |
| **Event** | Activity density | Burst vs idle |
| **Cognitive** | Attention load | Overload vs boredom |

**Combined (concept):** `perceived_time = α·wall + β·event_density + γ·attention_load` (coefficients policy-tuned).

**Why:** Agents reason about **urgency** and **human-like** “felt time”; dampens **overreaction** in high-noise bursts (`temporal_spine` + swim metrics).

---

#### 7 — Shadow simulation layer (cheap foresight)

**Idea:** Before commit: `simulated_state = simulate(action, current_state)` in **Crucible** or **pure model**; if `risk(simulated_state) > threshold` → abort or escalate.

**Why:** “Think before acting” without full RL; cuts **bad mutations** and **Claw** accidents.

**Fit:** `claw_harness`, pre-governor **dry run**, blackboard diff preview.

---

#### 8 — Identity decoupling (lineage without kernel rot)

**Rule:** **Identity ≠ behavior ≠ authority.**

**Shape:**

```text
agent = {
  "id":           "<immutable / PKI-bound>",
  "lineage_tag":  "<symbolic — not permission>",
  "policy":       "<behavior rules>",
  "permissions": "<what may actually run>",
}
```

**Why:** Prevents **narrative** (“lineage”) from **corrupting** authorization logic.

---

#### 9 — Failure harvesting system (evolution fuel)

**Idea:** Structured `failure_log` entries `{task, agent, error, context}` → **cluster** → **pattern** → **spawn improvement tasks** / governor threshold updates.

**Why:** Evolution = **reuse of structured failure**, not only success metrics.

**Fit:** Evaluation harness (Phase 3), PoUW / receipts.

---

#### 10 — Objective function registry (coherence)

**Gap:** Many **implicit** goals → the swarm **optimizes** in multiple directions at once.

**Idea:** Explicit **OBJECTIVES** map — e.g. `task_success`, `resource_efficiency`, `stability`, `exploration` — each with **weights** and **visible** tuning. **Decisions** (governor, STGM mint, attention allocation) **reference** this registry.

**Why:** Without it, behavior looks **random**; with it, the ecology has a **negotiable charter**.

---

#### Impact ranking (suggested prioritization for implementation debate)

1. **Attention budget** — fastest behavioral discipline.  
2. **Friction layer** — stability + less stigmergic noise.  
3. **Reversibility index** — safe exploration + rollback intelligence.  
4. **Contradiction engine** — truth over time.  
5. **Objective registry** — global coherence.

**Principle:** Intelligence here comes from **constraints shaping behavior over time** — not from **more agents**, **more sensors**, or **more abstract layers**.

**Suggested next integration target:** wire **Attention budget** + **Friction** (and **reversibility** inputs) into **`mutation_governor`** + **Blackboard 2.0** design — so SIFTA reads as a **disciplined organism**, not only a **capable** one.

### 5.3 Grok-style “organ anatomy” + frontier vectors (datadump integrated — **read status table**)

External chat tabs (e.g. Grok) often **sound** like live telemetry. **Treat every operational claim as false until proven in repo + runtime.** Below, the **narrative** is preserved for **design alignment**; **truth** is in the **Status** column.

#### 5.3.1 Anti-hallucination checklist (common tab inventions)

| Claim in wild prose | Sober interpretation |
|---------------------|---------------------|
| "Skill Registry **automatically** routed failed replay → Failure Harvester, deducted STGM, decayed idle skill" | **VERIFIED** — `skill_registry.py` commit `ccf6830`: `replay(success=False)` → `_harvest_failure()` → `get_harvester().harvest()`. STGM deducted via `_deduct_stgm()`. Decay via `decay_all()`. Full lifecycle tested: mint(0.50) → 3 success(0.95) → 1 fail(0.70) → 48h decay(0.46). |
| "**12-gate** mutation protocol" | **VERIFIED** — `mutation_governor.py` commit `151d97f`: temporal→replay→rate→cooldown→budget→risk→friction→reversibility→attention→objective→shadow→contradiction. Enumerated in code docstring and tested. |
| "**Cartography Dashboard**" **visualizes** full anatomy | **SHIPPED** — `cartography_dashboard.html` commit `2ff5237`: standalone HTML reading `.sifta_state/` via local HTTP server. 9 panels, auto-refresh 5s. |
| "**Digital metabolism** / organism **bleeds**" | **VERIFIED** — Metaphor grounded in code: SVL v2 costs 0.005 STGM/frame (`casino_vault` debit). Poverty test verified: STGM=0 → vision OFF, system alive. |

#### 5.3.2 Total integrated anatomy (11 systems → SIFTA mapping)

Metaphor buckets group **concepts**; **modules** are where work actually lives.

**The Senses (Perception)**

| Concept | What it means in *this* codebase | Status |
|---------|----------------------------------|--------|
| **SVL v2 (Stigmergic Vision)** — fatigue, curiosity spikes, collective fusion | **Saliency-gated** vision: `stigmergic_vision.py` → 5-constraint pipeline (silence boost, VLM pass, STGM cost, objective scoring, contradiction check) + fatigue + curiosity + `CollectiveVisionFusion`. | **Shipped** — commits `7859076`, `2f139ec`. 5 pressure tests passed. |
| **Silence Detection** — "Void Gravity" | **Missing-signal** monitoring: `silence_detection.py` scans 4 zones (heartbeats, memory, mutations, vision). Routes dead zones to `FailureHarvester`. | **Shipped** — wired into `temporal_layering.py`. |

**The Pulse (Chronology)**

| Concept | SIFTA mapping | Status |
|---------|---------------|--------|
| **Temporal Layering** — Drift + Dilation → climate `OPEN` / `CAUTIOUS` / `FROZEN` | **`temporal_layering.py`** unifies `EventDensityClock` + `TemporalSpine` + `SilenceDetector` into single `pulse()`. Outputs `TemporalPulse` with `mutation_climate` (OPEN/CAUTIOUS/FROZEN), `swarm_tempo` (STORM/STEADY/DREAM). Wired as Gate #1 in Governor. | **Shipped** — commit `151d97f`. Live reading: CAUTIOUS, 8.8h drift. |

**The Immune System (Defense)**

| Concept | SIFTA mapping | Status |
|---------|---------------|--------|
| **Contradiction Engine** | `contradiction_engine.py` — blocks conflicting beliefs on blackboard via `assert_belief()`. Singleton. Routes blocked contradictions to `FailureHarvester`. | **Shipped** — tested: door=open then door=closed → tension logged |
| **Identity Decoupling** ("cryptographic phenotyping") | `identity_decoupling.py` — `IdentityFirewall` separates Genotype (hardware hash) / Lineage (narrative tag) / Phenotype (dynamic permissions). Wired into `ClawHarness`. | **Shipped** — commit `8cce234`. Alien hash + wrong phenotype both blocked. |
| **Mutation Governor (12-gate)** | `mutation_governor.py` — temporal→replay→rate→cooldown→budget→risk→friction→reversibility→attention→objective→shadow→contradiction. | **Shipped** — all §5.2 leverage mechanisms wired |

**The Brain (Cognition & Memory)**

| Concept | SIFTA mapping | Status |
|---------|---------------|--------|
| **Shadow Simulation** | `shadow_simulator.py` — AST-based dry-run structural validation. Wired as Gate #11 in Governor. | **Shipped** |
| **Failure Harvesting** | `failure_harvesting.py` — structured failure log → clustering → SCAR stubs when threshold reached. Routes from ClawHarness, SkillRegistry, SilenceDetector. | **Shipped** |
| **Skill Registry** — `.gene` files, decay, STGM | `skill_registry.py` — mint (0.05 STGM) → replay (0.01 STGM) → reinforce (+0.15) / demote (-0.25) → decay (0.005/hr). Auto-minted from ClawHarness success. | **Shipped** — commit `ccf6830`. Full lifecycle tested. |

**The Limbs & Blood (Execution)**

| Concept | SIFTA mapping | Status |
|---------|---------------|--------|
| **Claw Harness** | `claw_harness.py` — sandboxed limbs with Identity Firewall gate + Objective worth gate + Skill auto-promotion + replay_skill(). | **Shipped** — fully wired |
| **STGM Casino Vault** | `casino_vault.py` — STGM economy with signed mints, SVL metabolism burns, Skill Registry costs. | **Shipped** — live balance: ~1000 STGM |

**Visualization note:** An **interactive organ map** is a **UI** artifact. The `json?chameleon` block from tabs is an **LLM UI prompt** (component scaffold), **not** executable backend code. A real map should use **static** edges from **this table**, not runtime LLM graph invention.

#### 5.3.3 Frontier — three evolutionary vectors (explained against structure)

| # | Vector | Idea | Dependencies in *our* stack | Honest status |
|---|--------|------|------------------------------|---------------|
| **1** | **REM Sleep Consolidation** | Absence / **CAUTIOUS-FROZEN** climate → offline **shadow** permutations on **failure** backlog → **draft** skills, **no** live writes | Needs: **temporal** absence signal, **failure queue**, **Crucible**, **governor**, optional link to **`dream_state`** (currently **ledger-pair** synthesis, not failure-REM) | **Stretch** — **DreamEngine** exists; **failure-driven REM** is **next** |
| **2** | **Cross-Hardware Skill Routing (M5 ↔ M1)** | **Compute weight** → light jobs on **M1**, heavy on **M5**; STGM flow between nodes | **`swimmer_migration.py`**, dead drop, **never mix serials**; **WebSockets** or existing sync = **transport** (pick one, document it) | **Design** — **PKI on M1** was a stated bootstrap item in `.cursorrules` |
| **3** | **Pheromone-Weighted Planning (Blackboard 2.0)** | Tasks = **gravity wells**; swimmers follow **gradient** of **STGM + pheromone** | **`interference_layer.py`**, **objective registry** (§5.2.10), **anti-starvation** floor for boring-but-critical tasks | **Requires** Blackboard **graph** first |

**Extra novelty (Cursor editorial, not from tab):** **Signed offline skill proposals**; **sealed-envelope** payloads for M1; **adversarial dream** only on `INFERRED` rows; **turbulence** (bounded random) to escape local maxima in planning. Details: `Documents/PLAN_ORGAN_ANATOMY_GROK_SYNTHESIS_AND_FRONTIER.md`.

#### 5.3.4 Fork — REM consolidation **or** Blackboard 2.0?

**Do not treat as eternal either/or.**

| Build first | Reason |
|-------------|--------|
| **Blackboard 2.0 (minimal)** | **Planning substrate** — pheromone gravity needs **nodes** to attach to; failures need **structured** records to harvest. |
| **REM / failure-driven shadow** (second or parallel thin) | **DreamEngine** today can run on absence; **full REM** = same gates + **failure queue** + **Crucible** **proving** a fix before **skill** mint. |

**Objective Registry** (§5.2.10) should still be **first among mechanisms** if not implemented — otherwise “gravity” and “failure” have **no scoring definition**.

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
- **Vision track (optional parallel):** raw camera **capture** + **commodity VLM** + **stigmergic head** → pheromones / saliency (see **§5.1**); validate on **M5 24GB** with quantized weights before promising real-time HD.  
- **Leverage track (§5.2):** design **friction**, **reversibility**, and **attention** as first-class inputs to governor + blackboard API; add **contradiction** + **objective registry** when the event graph exists.

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
| **Leverage bundle (§5.2)** | **Attention + friction + reversibility** baked into governor + blackboard — discipline without new “organs” |

**Recommendation:** **Blackboard 2.0** first (substrate), then **evaluation harness** (truth), then skills (composition). In parallel, **design** §5.2 hooks so the substrate does not thrash once live.

---

## 8. Non-proliferation & sovereignty

All “claw” and vigil automation remains under **Neural Gate** + **Non-Proliferation** license: no offensive automation, no surveillance productization. **Individual sovereignty** is the charter—not advertiser-scale agent farms.

---

## 9. Rally cry

**Power to the swarm** — not more chatter, but **measurable coordination**, **bounded evolution**, and **evaluation that bites**.

---

*Solid plan first. Code follows the phases above.*
