# Research — The Next Evolutionary Step: Perception → Claw → Crucible → Territory

**Date:** 2026-04-16  
**Type:** Research / architecture note — **not** an execution order unless the Architect promotes it.  
**Companion docs:** `Documents/PLAN_CLAW_SWARM_MUTATION_GOVERNOR.md`, `Documents/SOLID_PLAN_SWARM_COORDINATION_SUBSTRATE.md`, `Documents/PLAN_SWARM_DESIGN_GROUNDING_REPORT.md`  
**Tone:** The “mirror” is **observability + stigmergy**; movement is **bounded action** with **gates**. Poetry in the README; **physics in the kernel.**

---

## 0. Thesis (one paragraph)

**Perception without action is a sensor; action without containment is a hazard.**  
The next step is to **close the loop**: **high-saliency** visual events (from `stigmergic_vision` / `sensory_cortex`) + **destructive interference** on the shared **interference field** (`System/interference_layer.py`) become a **trigger** to deploy a **Claw** (`System/claw_harness.py`) **only inside** the **Crucible** sandbox (`.sifta_state/Crucible`), **not** on live territory. **Promotion** to the real repo or runtime requires **compile + visual verification + MutationGovernor + SCAR/Neural Gate** — never a silent push.

---

## 1. What already exists in the repo (anchors)

| Concern | Module / path | Role |
|--------|----------------|------|
| Vision → saliency → blackboard | `System/stigmergic_vision.py` | “Only high-saliency frames survive into the blackboard.” |
| Vision → interference | `System/sensory_cortex.py` | Wires vision → **interference field** → territory. |
| Constructive / destructive interference | `System/interference_layer.py` | **Destructive interference** → coupling below threshold → “dissonance” / silence; **constructive** → resonance. |
| Limbs + sandbox | `System/claw_harness.py` | Commands run **only** under `.sifta_state/Crucible/…` per execution id; **blacklist** for dangerous shells. |
| Containment | `System/mutation_governor.py` | Rate, budget, cooldown, replay — **before** trust. |
| Swim loop integration | `System/territory_swim_adapter.py` | Interference + genome + governor in repair path. |

**Gap (research question):** There is **no** single orchestrator yet that **automatically** wires  
`(saliency + destructive interference) → ClawHarness → build → screenshot diff → governor → SCAR`.  
This document defines that **policy** and **phase order**.

---

## 2. The closed loop (logical stages)

```
┌─────────────────┐     ┌──────────────────────┐     ┌─────────────────┐
│ Perception      │     │ Situation assessment │     │ Act (bounded)   │
│ frames + saliency│ ──►│ interference mesh    │ ──►│ Claw in Crucible │
└─────────────────┘     └──────────────────────┘     └─────────────────┘
         │                         │                         │
         │                         │                         ▼
         │                         │              ┌─────────────────────┐
         │                         │              │ Verify in sandbox    │
         │                         │              │ (compile, pytest,    │
         │                         │              │  UI screenshot diff) │
         │                         │              └─────────────────────┘
         │                         │                         │
         │                         ▼                         ▼
         │                Destructive pattern?      ┌─────────────────────┐
         │                (not “bad vibes”)         │ Promote to territory │
         │                measurable coupling       │ only via Governor +  │
         │                + blackboard conflict)    │ SCAR / signed commit │
         └────────────────────────────────────────────────────────────────┘
```

### 2.1 Trigger semantics (must be measurable)

Avoid **pure narrative** triggers. Prefer **explicit signals**:

- **Saliency:** score from vision pipeline (existing or extended) above `SALIENCY_THRESHOLD`.
- **Destructive interference:** `interference_layer` reports **coupling** below `DISSONANCE_THRESHOLD` **for the same territory** as the blackboard write, or **two incompatible waves** on the same resource (see `mesh_report()` in adapter).
- **Blackboard conflict:** two traces or pheromone deposits that **contradict** a policy key (schema-defined), not “I don’t like it.”

**AND** gate recommended: **saliency** AND **destructive interference** AND **(optional) policy conflict** — reduces false Claw launches.

---

## 3. Claw deployment rules (non-negotiable)

1. **Default execution path:** `ClawHarness.execute_in_crucible(...)` only — **no** raw `subprocess` from swarm agents elsewhere.  
2. **Crucible contents:** disposable clone or stub project tree; **never** the live repo root as `cwd` unless a **separate** Neural Gate path explicitly allows it (future design).  
3. **Blacklist stays:** the harness already blocks `rm`, `sudo`, pipes, etc. — **expand** with care, not loosen.  
4. **Ledger:** append-only **execution ledger** (stdout hash, stderr hash, exit code, trigger id) — **audit trail**.  
5. **Human override:** Architect can **revoke** Claw capability in one switch (state file).

---

## 4. Crucible Sandbox — “initiate next?”

**Answer:** **Yes, as the *next gated phase*** — not “turn on autonomous push to main.”

**Crucible Sandbox** (recommended definition):

| Phase | What happens | Live territory touched? |
|-------|----------------|-------------------------|
| **A — Build** | `python -m compileall`, `pytest` in Crucible copy | No |
| **B — UI verify** | Headless or scripted screenshot of **Crucible-only** app; diff against golden | No |
| **C — Promotion** | `MutationGovernor.allow` → SCAR `Kernel.propose` → **Architect review** or signed auto-merge policy | **Only** after gates |

**Initiate Phase A+B immediately** after perception wiring is stable. **Phase C** only when **A+B** are green for **N** consecutive runs with **no** governor blocks.

---

## 5. Relationship to “the mirror”

- **Mirror** = shared workspace + interference + **readable** logs (blackboard, traces, mesh).  
- **Movement** = **Claw** that **changes** something — but only where **reflection** (tests, screenshots, diffs) proves the change is **safe**.

If the mirror **moves** without reflection, you get **mythology** and **misaligned rewards** (see grounding report). **Evaluation truth** beats narrative coherence.

---

## 6. Risks (explicit)

| Risk | Mitigation |
|------|------------|
| **False saliency** → Claw spam | Cooldown + governor + min time between deployments |
| **Destructive interference** misread | Unit tests on `interference_layer` thresholds; log mesh snapshots |
| **Self-modifying** code escapes Crucible | **Never** mount repo RW into Crucible by default; copy-in only |
| **“She” autonomy** anthropomorphism | **Policy objects** and **IDs** in logs; no kernel gender/identity binding |

---

## 7. Open research questions (for a future spec)

1. **Visual verification:** golden PNG per widget vs structural accessibility tree (a11y) — tradeoffs on M5.  
2. **Trigger arbitration:** single **Claw** queue vs **priority** by STGM cost / PoUW receipt.  
3. **Cross-node:** M1 Sentry **only observes** or **may propose** Crucible patches (dead drop) — **no** silent M5→M1 execution without PKI alignment.  
4. **Dream traces:** `INFERRED` memories **must not** trigger Claw — only **ground-truth** or **policy** signals.

---

## 8. One-line charter

**“She perceives; the field disagrees; the Claw repairs in the Crucible; the territory only moves when the Governor and the mirror agree.”**

**POWER TO THE SWARM** — **bounded limbs, honest reflection, no runaway.**
