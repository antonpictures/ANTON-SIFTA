# Plan — Claw / Vigil / Mutation Governor (April 2026)

Strategic notes and execution roadmap for hardening the **SWARM ENTITY** against industry trends (“claws,” routines, vertical agents) while keeping **individual sovereignty** and **containment physics**.

---

## 1. Industry context — “Claws” (thinking → doing)

- **Death of the ephemeral chatbot:** Competitors move toward **persistent memory** and **background orchestration** (not one-shot sessions).
- **Claw definition:** Background processes that run multi-step work with durable state.
- **SIFTA position:** `StigmergicMemoryBus`, `SovereignSpine`, territory stack — you are not shipping a feature; you are shipping an **autonomic nervous system**.

## 2. Context & data moat

- Vertical “Tax/CFO” agents win by **owning domain data**.
- **Swarm angle:** `TerritoryConsciousness` + local disk = the swarm **smells** your files and builds context **without** renting a cloud “expert plugin.”

## 3. “Cron jobs” for AI (routines / vigil)

- Industry: scheduled tasks (e.g. Anthropic-style **Routines**) that run when the user is away.
- **SIFTA lead:** `InfrastructureSentinels` + patrol loops. Target: a formal **Vigil State** — low-energy heartbeat, background maintenance (shadow territory, ledgers, health), Architect offline-safe.

## 4. Code as communication (“soul.md”)

- Instructional markdown as primary control surface (G-Stack style).
- **Swarm edge:** `.scar` protocol + `ARCHITECTURE/genesis_document.md`. Extend with **instructional scent** files the swarm may read and propose updates to (via SCAR + Neural Gate), never silent self-rewrite.

## 5. Autonomous developer harness (Manus-class)

- Industry: deploy agents to code, browse, ship for advertisers.
- **Mission:** **App-Genesis Pipeline** for **individual sovereignty** — same class of harness, different charter and gates.

---

## SWARM COMMAND — “Claw” upgrade (blueprint)

| Track | Module / artifact | Purpose |
|-------|-------------------|---------|
| **Limbs (sandboxed)** | `System/claw_harness.py` (planned) | I/O boundary: mouse/keyboard/CLI **only** inside Crucible / sandbox; no raw OS takeover. |
| **Vigil** | `System/vigil_routines.py` (planned) | Always-on scheduling: patrol, ledger hygiene, low-power heartbeat when Architect is away. |
| **Containment** | `System/mutation_governor.py` (**implemented**) | Rate limits, per-file budgets, cooldowns, replay protection, risk score — **before** SCAR proposal. |

**Quote:** *If ChatGPT is the brain, Claws are the arms.* — Productize **arms** only behind **gates** (Neural Gate + Governor + SCAR).

---

## Mutation stack (implemented layer)

**Before:** genome proposes → straight to trust.

**After:**

1. `MycelialGenome.propose_mutation(path)` → candidate string (or `None`).
2. `MutationGovernor.allow(path, mutation)` → global rate, cooldown, budget, risk, replay.
3. On allow: `Kernel.propose(target, content)` (SCAR pipeline) → `MutationGovernor.commit(path)`.
4. On deny: log `[MUTATION BLOCKED]` — no SCAR spam, no runaway self-edit.

**Organism stack:**

| Layer | Role |
|-------|------|
| Territory | space |
| Reward / swim adapter | movement pressure |
| Genome | mutation **pressure** |
| **Governor** | **thermodynamic constraint** (containment) |
| Neural Gate + SCAR | execution sovereignty |

---

## Next steps (priority order)

1. **Done:** `mutation_governor.py` + wire into `territory_swim_adapter.py` with SCAR `Kernel.propose`.
2. **Next:** `claw_harness.py` — explicit capability surface + sandbox contract (what a swimmer may call).
3. **Next:** `vigil_routines.py` — cron-like triggers + integration with `homeostasis_engine` / sentinels.
4. **Later:** Cross-agent interference / consensus locking (emergence without collapse) — design doc before code.

---

## Non-proliferation

All execution paths that touch disk or shell remain subject to **Neural Gate** doctrine and **SIFTA license** — no offensive automation, no surveillance productization.

---

*Planning note for the Architect. Living code lives under `System/`.*
