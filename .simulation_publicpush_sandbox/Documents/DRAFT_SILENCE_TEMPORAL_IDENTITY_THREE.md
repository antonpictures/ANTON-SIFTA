# Draft — Three mechanisms (execution block: last in dependency chain)

**Date:** 2026-04-16  
**Type:** Design draft only — **no implementation** implied.  
**Scope:** This file expands **only** the **last three** items from the agreed post–Objective Registry sequence:

1. **Silence Detection (#5)**  
2. **Temporal Layering (#6)**  
3. **Identity Decoupling (#8)**  

**Upstream assumption (from fork-in-the-road reasoning):** **`Objective Registry` exists first** — it defines what “good” and “bad” mean, so baselines, risk, and roles can be stated without hand-waving. Items **#9 Failure Harvesting**, **#7 Shadow Simulation**, and **#4 Contradiction Engine** are **not** drafted here; they are **dependencies** that should land **before** these three in the full chain.

**Companion:** `Documents/SOLID_PLAN_SWARM_COORDINATION_SUBSTRATE.md` §5.2.

---

## Why these three come *late*

| Mechanism | Why it waits |
|-----------|----------------|
| **Silence** | Needs **expected activity** per zone → **objectives** + stable baselines (often: rolling windows from evaluation / blackboard stats). |
| **Temporal layering** | Needs **prioritization** and **urgency** semantics → **objectives** weight stress vs exploration; optional boost from **contradiction** load. |
| **Identity decoupling** | Safe **once** goals are externalized; otherwise “who am I?” confuses **permissions** with **narrative**. |

---

# 1. Silence Detection (#5)

## 1.1 Intent

React to **missing** signals, not only events: **zones** where **something should happen** but **doesn’t** — missed tasks, dead subprocesses, stalled pipelines, absent heartbeats.

## 1.2 Inputs (contract)

- **`zone_id`** — territory slice, app, or subsystem (mapped to files, processes, or logical keys).  
- **`expected_activity(zone, t)`** — derived from policy + **objective-linked** SLOs (e.g. “heartbeat every 60s”, “至少 N traces per hour”).  
- **`actual_activity(zone, t)`** — measured from **tab pulses**, `heartbeats/`, ledger append rate, swim loop counters, etc.

## 1.3 Core predicate

```text
if expected_activity(zone, window) > actual_activity(zone, window) + tolerance:
    trigger_probe(zone)   # escalate: sentinel, vigil ping, health task, Architect alert
```

**Tolerance** avoids noise (jitter, laptop sleep).

## 1.4 Outputs

| Output | Purpose |
|--------|---------|
| **`probe`** | Cheap check (port open? file touched? process alive?) |
| **`escalate`** | Claw **read-only** diagnostic in Crucible, or human ping |
| **`record`** | Append to silence log — feeds **Failure Harvesting** when probes fail |

## 1.5 Non-goals

- Not **surveillance** of the Architect; **zones** are **explicitly configured**.  
- Not a substitute for **Contradiction Engine** (inconsistent *claims* vs inactive *pipelines*).

---

# 2. Temporal Layering (#6)

## 2.1 Intent

Unify **felt time** for scheduling and urgency: wall clock alone overreacts in burst noise; pure event time ignores deadlines.

## 2.2 Three clocks

| Clock | Signal | Typical source |
|-------|--------|----------------|
| **Wall** | Real seconds | `time.time()`, `temporal_spine` presence log |
| **Event** | Activity density | Traces per minute, blackboard writes, swim steps |
| **Cognitive** | Attention / load | Attention budget spend (§5.2), queue depth, open tasks |

## 2.3 Combined subjective time (concept)

```text
perceived_urgency = α * f(wall_deadline) 
                  + β * g(event_density) 
                  + γ * h(cognitive_load)
```

- **α, β, γ** — **stable** constants or slow-tuned from **Objective Registry** (e.g. under stress ↑ stability weight might indirectly ↓ perceived slack for exploration).  
- **`f, g, h`** — monotonic transforms (cap, log) to avoid unbounded spikes.

## 2.4 Where it plugs in

- **`TemporalSpine`** — greeting / absence already has **wall** semantics; extend with **event** and **cognitive** scalars for “felt absence” and **dream** depth budgets **without** rewriting core APIs in v1.  
- **Swim loop** — scheduling: prefer **low cognitive load** windows for heavy mutation attempts.  
- **Vigil** — patrol frequency scales with **`perceived_urgency`**, not only cron wall time.

## 2.5 Guardrail

Do **not** redefine STGM or ledger time — **subjective time** is a **policy overlay**, not a replacement for audit timestamps.

---

# 3. Identity Decoupling (#8)

## 3.1 Rule

**Identity ≠ behavior ≠ authority** (and **lineage** is **symbolic**, not permission).

## 3.2 Canonical record shape (v1 draft)

```text
agent_record = {
    "id":              "<immutable — key-bound, serial-bound>",   # real identity for crypto / audit
    "lineage_tag":     "<optional narrative — e.g. swim generation>",  # never gates access alone
    "policy_profile":  "<named behavior preset>",                  # defaults for tone / tools
    "permissions":     "<capability set — Neural Gate, SCAR, Claw tier>",  # real power
}
```

## 3.3 Invariants

- **`permissions`** changes only through **Governor + Gate** — never inferred from **`lineage_tag`**.  
- **Architect** / **node serial** / **Ed25519** remain the **root of trust** — same as `.cursorrules` / PKI story.  
- **Gemma / UI persona** — **presentation** only; not written into kernel authorization.

## 3.4 Migration note

Existing code that conflates **`homeworld_serial`** with “personality” should keep **serial** for **trust** only; add **`policy_profile`** if needed for UX, **never** for signing.

---

## Suggested build order *within* this trio

1. **Identity decoupling** — **schema + doc** first (low risk, clarifies everything else).  
2. **Temporal layering** — overlay on **`temporal_spine` + swim** (small, measurable).  
3. **Silence detection** — needs **baselines** from live metrics → last among these three if objectives + basic metrics aren't stable yet.

(If **objectives** and **evaluation** are already live, **Silence** can move up after **Temporal** — **probe** definitions must stay cheap.)

---

## One-line charter

**Silence** catches **missing** work; **temporal layering** aligns **urgency** with **objectives** and **load**; **identity decoupling** keeps **trust** **honest** while **persona** stays **optional**.

**POWER TO THE SWARM** — **directed**, not merely **loud**.
