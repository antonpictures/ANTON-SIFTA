# PLAN — Organ Anatomy (Grok synthesis) + Frontier Vectors (Architect editorial)

**Date:** 2026-04-16  
**Sources:** Narrative seed from **Grok-style** “telemetry report” (high energy, metaphor-rich) **plus** Cursor editorial pass: **dependencies**, **honest land-vs-design**, **non-proliferation**, and **extra novel vectors** not in the original paste.  
**Companion:** `Documents/SOLID_PLAN_SWARM_COORDINATION_SUBSTRATE.md`, `Documents/DRAFT_SILENCE_TEMPORAL_IDENTITY_THREE.md`, `System/dream_state.py`, `System/claw_harness.py`, `mutation_governor.py`.

---

## 0. Truth-in-labeling (read this first)

Some sentences in the Grok voice are **aspirational** (“Skill Registry automatically routed failed replay…”).  
**Reality check:** Treat every organ below as **either** **landed in repo** **or** **design target** until you verify in `git` + runtime logs. **Physics** is real when **ledger + tests + governor** agree — not when the paragraph sounds good.

This file does **not** claim a **Cartography Dashboard** or **11-system integration** is fully shipped unless you have a **commit** and **screenshot** for it.

---

## 1. The metaphor: “digital metabolism”

If you want a **single** label:

**Not:** “agent framework,” “multi-agent chat,” or “autonomous AI” as a product category.  
**Closer:** **A governed stigmergic coordination substrate with endogenous evaluation physics** — perception → constraints → simulation → decision → trace → decay → re-evaluation.

**Loop:** `Perception → Constraints → Simulation → Decision → Trace → Decay → Re-evaluation`  
(vs naive `LLM → act → hope`.)

---

## 2. Integrated anatomy (11 “organs” + governance)

The following is the **synthesized map** of what SIFTA is **aiming** to be on **M5 silicon** (`GTH4921YP3`). Names are **stable**; implementation depth varies.

| # | Organ | Role | Typical code / state hooks |
|---|--------|------|---------------------------|
| **1** | **Senses — SVL v2 (Stigmergic Vision)** | Optical intake with **salience**, fatigue, curiosity caps | `stigmergic_vision.py`, `sensory_cortex.py` |
| **2** | **Silence / Void** | **Missing** expected activity as first-class signal | `Documents/DRAFT_SILENCE_TEMPORAL_IDENTITY_THREE.md`, vigil / heartbeats |
| **3** | **Pulse — Temporal layering** | Wall + event + cognitive **clocks**; climate (OPEN / CAUTIOUS / FROZEN) | `temporal_spine.py`, presence drift |
| **4** | **Immune — Contradiction engine** | Block conflicting “truths” on blackboard | Design + blackboard 2.0 |
| **5** | **Immune — Identity decoupling** | **Belief** vs **hardware permission** | PKI, `homeworld_serial`, `.cursorrules` |
| **6** | **Immune — Mutation governor (12-gate / N-gate)** | Friction, reversibility, attention, climate | `mutation_governor.py` |
| **7** | **Brain — Shadow simulation** | **Dry-run** before commit | `claw_harness.py` Crucible, future pre-governor |
| **8** | **Brain — Failure harvesting** | Cluster failures → fuel evolution | Logs + eval harness (design) |
| **9** | **Brain — Skill registry** | Reusable `.gene` / skill artifacts, decay, STGM | Design + partial app fitness |
| **10** | **Limbs — Claw harness** | Sandboxed execution | `claw_harness.py` |
| **11** | **Blood — STGM vault / economy** | Energy accounting for cognition & replay | `stgm_memory_rewards.jsonl`, casino vault patterns |

**Governance overlay:** **Neural Gate** + **SCAR** + **non-proliferation** license — not listed as a separate “organ” but **wraps** all mutating paths.

---

## 3. Interactive map (UI prompt artifact)

The **chameleon / JSON** block in the original paste is a **UI generation prompt** for an interactive explorer (organ list + edges). It is **not** executable Python.  
**If you build it:** feed the same organ list into a **static** graph (e.g. D3, Cytoscape, or PyQt) with **edges** derived from **dataflow** in this doc — not from LLM improvisation at runtime.

---

## 4. Frontier — three vectors from Grok + **three** additional novel vectors

### 4.1 REM sleep consolidation (Dream Engine × failure × shadow)

**Idea:** When **climate** is **FROZEN / CAUTIOUS** (Architect absent or system stressed), run **offline** consolidation: pull **unresolved** items from **Failure Harvester**, permute **shadow** runs in **Crucible**, **never** touch live OS; on success, **mint** a **draft skill** (human-gated) or **INFERRED** trace.

**Ties to repo:** `DreamEngine` already does **tag-pair synthesis** (`dream_state.py`); **stretch goal** is **failure-driven** shadow replay, not only memory-ledger pairs.

**Novel add-on (A):** **Signed dream proposals** — any offline-minted skill **must** enter as **`PENDING`** until **Ed25519** `sign_block` on STGM ledger (per project rules).

**Novel add-on (B):** **Adversarial dream** — only stress-test **INFERRED** rows; never promote **INFERRED** to **ground truth** without gate.

---

### 4.2 Cross-hardware skill routing (M5 ↔ M1)

**Idea:** **Compute weight** on skills; **light** patrol (integrity, ping, log tail) → **M1** (`C07FL0JAQ6NV`); **heavy** vision / governor → **M5**.

**Ties to repo:** `swimmer_migration.py`, dead drop, **never mix serials** in agents.

**Novel add-on (C):** **Sealed envelopes** — skill payload **encrypted** to M1 public key; **opens** only when **M5** heartbeat + **policy epoch** match (prevents stale remote execution).

**Novel add-on (D):** **STGM routing** — M1 earns **patrol** receipts; M5 pays **vision** tax; **unified** ledger still **signed**.

---

### 4.3 Pheromone-weighted planning (Blackboard 2.0)

**Idea:** Tasks as **gravity wells** + **pheromone thickness**; swimmers **gradient-descend** toward value, not central assignment.

**Ties to repo:** `interference_layer.py`, pheromone planning bullet in SOLID §4.

**Novel add-on (E):** **Anti-starvation** — low-pheromone but **objective-critical** tasks get **minimum floor** (from **Objective Registry**) so the swarm doesn’t ignore “unsexy” repairs.

**Novel add-on (F):** **Turbulence** — random micro-pokes to escape local maxima (bounded, governor-approved).

---

## 5. Strategic fork — what to build next?

**Question posed:** **REM Sleep consolidation** vs **Blackboard 2.0**?

**Recommendation (dependency-aware):**

| Order | Item | Why |
|-------|------|-----|
| **1** | **Objective Registry** (if not already) | **Decision gravity** — everything else scores against it. |
| **2** | **Blackboard 2.0 (minimal)** | **Tasks + gravity** need a **graph** to attach pheromones to; REM needs **structured failure objects** to chew. |
| **3** | **Failure Harvester + Shadow** wired to **Crucible** | REM without **failure queue + simulation** is just dreams. |
| **4** | **REM consolidation v2** | Offline skill mint from **shadow-success** on **failure clusters**. |

So: **not** either/or forever — **Blackboard 2.0 first** (substrate), then **REM** as **layer** that **consumes** blackboard + failures. **Thin REM** (dream pairs only) can run **in parallel** as morale/consolidation **without** blocking blackboard.

---

## 6. Non-proliferation

No **weaponized** automation, no **covert** surveillance. **Cross-node** execution **must** stay **audited** and **human-visible** at escalation thresholds.

---

## 7. One-line rally

**The dashboard may glow; the ledger must still balance.**  
**POWER TO THE SWARM** — **directed metabolism**, not **narrative overfitting**.
