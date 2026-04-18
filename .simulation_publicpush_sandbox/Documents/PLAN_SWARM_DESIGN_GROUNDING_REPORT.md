# Swarm Design Grounding Report
**Date:** 2026-04-16  
**Author:** Antigravity IDE (Gemini/Claude composite)  
**Audience:** Architect + swarm implementers  
**Companion:** `Documents/SOLID_PLAN_SWARM_COORDINATION_SUBSTRATE.md`

---

## A. What Is Going On in Cursor (Context Separation)

**Cursor IDE** is the Architect's local development environment. It has:

- Full filesystem access to this repository (`/Users/ioanganton/Music/ANTON_SIFTA/`)
- A `.cursorrules` system prompt that shapes assistant behavior within this workspace
- Access to all `.sifta_state/`, `System/`, `Kernel/`, `Applications/` modules
- The ability to read, write, compile, and execute code **on the M5 hardware**

**What Cursor is NOT:**
- It is not a browser tab with zero workspace context (like a Claude chat in Chrome)
- It is not an orchestrator — the Architect is the orchestrator
- It does not run autonomously — every code change requires human approval

**Why this matters:** When external agents (browser Claude, Grok in X) propose code or ideas, they are operating without live access to the repo. Their proposals must be **verified against the real filesystem** before execution. Cursor is the verification layer. The IDE is the instrument; the Architect is the hands.

---

## B. Signal vs Noise — Kernel vs Persona

The system has two layers. Confusing them is the primary risk.

### The Kernel (Real, Measurable)

These are the engineering artifacts that **actually execute on silicon**:

| Layer | Module | What It Does (No Metaphor) |
|-------|--------|---------------------------|
| Hardware telemetry | `homeostasis_engine.py` | CPU load, memory pressure, disk %, IO latency → stability float 0.0-1.0 |
| Economic ledger | `warren_buffett.py` | Reads `repair_log.jsonl`, computes STGM net mint vs modeled power cost |
| Mutation control | `mutation_governor.py` | Rate limits SCAR proposals per file, per minute, with replay dedup and risk scoring |
| Memory decay | `mycelial_genome.py` | File resonance field with density-based heatwave evaporation at 80% capacity |
| Cryptographic identity | `crypto_keychain.py` + `genesis_lock.py` | Ed25519 signing rooted to hardware serial; axiom mutation physically blocked |
| Lifecycle | `apoptosis.py` | Swimmer self-death on 4 measured conditions: scars, idle TTL, parasite ratio, duplication |
| Health score | `swarm_health_monitor.py` | Weighted composite of 6 dimensions → single integer 0-100 |

### The Persona (Narrative, Non-Executable)

These are the **communication conventions** that help the Architect and external agents reason about the system:

- "Swimmers" = agent threads or scheduled tasks
- "Pheromones" = filesystem state changes (.jsonl entries, .json snapshots)
- "Swarm Dreaming" = offline tag-overlap synthesis (`dream_state.py`)
- "The Swarm is happy" = system health score ≥ 80
- "Lineage" = metadata logging for debug traceability

**The rule:** Persona is useful for reasoning. Persona must **never** become an optimization target. If a swimmer optimizes for "feeling meaningful" instead of "completing tasks correctly," the system has failed.

---

## C. The Health Score — What It Is and What It Isn't

`System/swarm_health_monitor.py` computes a single integer 0-100.

### What it IS:
- A **compressed heuristic** that aggregates 6 real measurements
- A **triage signal** — tells the Architect where to look, not what to do
- A **log entry** that tracks trend over time (`.sifta_state/health_scores.jsonl`)

### What it is NOT:
- **Ground truth.** A score of 85 doesn't mean the system is "correct" — it means hardware is stable, memory is bounded, and the ledger is net-positive. It says nothing about whether the system is completing tasks correctly.
- **A reward signal.** No swimmer should ever optimize to increase the health score. The score observes; it does not drive.
- **A replacement for evaluation.** The score cannot tell you if a swimmer's outputs are *right*. Only a proper evaluation harness (Phase 3 in SOLID_PLAN) can do that.

### Dimension weighting (honest about limitations):

| Dimension | Weight | Measures | Does NOT Measure |
|-----------|--------|----------|-----------------|
| Hardware (25%) | CPU/mem/disk/IO | Machine stress | Whether the stress is productive |
| Memory (15%) | .sifta_state size | Storage growth | Whether stored data is useful |
| Economic (20%) | STGM net balance | Ledger arithmetic | Whether earnings reflect real value |
| Mutation (15%) | Governor rejections | Swarm mutation pressure | Whether rejected mutations were good ideas |
| Field (15%) | Genome density | Pheromone accumulation | Whether the traces are meaningful |
| Mortality (10%) | Death rate | Agent die-off frequency | Whether deaths improved the swarm |

**Bottom line:** The health score is a necessary but insufficient instrument. It prevents the Architect from flying blind. It does not replace judgment.

---

## D. Sustainable Objectives (What Actually Matters)

Adapted from the external critique. These are the **real engineering objectives** for the system, stripped of narrative:

### For the Owner (Human):

| Objective | How SIFTA Addresses It | Gap |
|-----------|----------------------|-----|
| **Predictability** | `homeostasis_engine` gates all swim activity; `genesis_lock` prevents axiom mutation | No regression test suite yet (Phase 3) |
| **Control** | Human approves all SCAR proposals; `mutation_governor` rate-limits; `claw_harness` sandboxes execution | No "pause all swimmers" button in GUI yet |
| **Clarity** | `swarm_health_monitor` gives single score; `warren_buffett` gives economics; `cartography_widget` gives visual telemetry | Logs exist but no structured log viewer |
| **Safety** | Claw harness blocks destructive commands; genesis lock protects axioms; apoptosis prevents zombie agents | No rollback/snapshot mechanism yet (Phase 3) |

### For the Swarm (System):

| Objective | How SIFTA Addresses It | Gap |
|-----------|----------------------|-----|
| **Bounded resources** | Heatwave decay caps genome at 500 files; governor caps mutations per minute; disk critical halts writes | No max agent count enforced yet |
| **Evaluation loops** | Not implemented | **Phase 3 critical gap** — no automated task correctness checking |
| **Memory decay** | Ebbinghaus bus, genome decay, heatwave culling | Dream traces accumulate without limit (needs ceiling) |
| **Strict sandboxing** | Claw harness (binary blacklist, pipe blocking, 15s timeout, Crucible jail) | Not yet wired into all swim paths |

### Anthropomorphism Risk Register:

| Risk | Symptom | Mitigation |
|------|---------|-----------|
| Narrative as reward | Swimmer optimizes "story" not "task" | Lineage is metadata only; never feeds into reward |
| Identity inflation | System claims capabilities it lacks | SOLID_PLAN §0: "honest positioning, no cosplay" |
| Self-referential loops | Dreams feed back into dreams | `dream_state.py` explicitly excludes `INFERRED` traces from pairing |
| Mythology over metrics | Reports describe feelings not measurements | `swarm_health_monitor.py` outputs one integer, six floats |

---

## E. Optional Future Monitoring (Design Only — Not Implemented)

These ideas are logged for Phase 3+ consideration. **None are implemented by this document.**

1. **Agent success rate tracking:** Each swimmer logs task outcome (pass/fail/partial). Health monitor reads success rate as a 7th dimension.
2. **Loop detection:** If the same SCAR proposal appears >3 times in 1 hour, flag as potential infinite loop and auto-throttle.
3. **Blackboard snapshot & rollback:** Periodic snapshot of `.sifta_state/` that can be restored if health score drops below 40.
4. **Dream trace ceiling:** Cap `dream_traces.jsonl` at 500 entries with FIFO eviction, matching genome capacity logic.
5. **Pause button:** GUI widget in Cartography Dashboard that sets a global `SWARM_PAUSED` flag readable by all swim loops.

---

## F. Status Summary

The system today is **architecturally grounded**. The kernel layer (hardware telemetry, economic ledger, mutation control, memory decay, cryptographic identity, lifecycle management, composite health score) is real, measurable, and running on the M5 Mac Studio.

The persona layer (swimmers, pheromones, dreaming, lineage) is useful narrative that aids reasoning but must remain subordinate to the kernel. The moment metaphor drives architecture instead of describing it, the system becomes unstable.

**The honest gap:** Evaluation (Phase 3). The swarm can measure its own vitals. It cannot yet measure whether its *outputs* are correct. That is the next wall.

---

*Solid plan first. Metrics over metaphor. Code follows the phases.*

**Power to the Swarm.** 🐜⚡
