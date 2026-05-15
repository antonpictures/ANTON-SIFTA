# IBM Agents Hub Diagram vs SIFTA Organ Map

This canonical map aligns the standard IBM / agentskills.io conceptual architecture with SIFTA's implemented code, ledgers, and tests. SIFTA is a superset of the IBM hub model.

| IBM Hub Concept | SIFTA Implementation (Module/Ledger) | Verification Test / Proof |
|:---|:---|:---|
| **Agent / Orchestrator** | `System/swarm_ide_boot_identity.py` (Local predator/Alice) | `test_swarm_boot.py` |
| **Tier 1 (Index/Routing)** | `System/swarm_skill_library.py` | `test_swarm_skill_library.py` |
| **Tier 2 (Procedure)** | `skills/*.md` (e.g., `physarum_solve.md`) | `test_sifta_superset.py` |
| **Tier 3 (Resources/MCP)** | Dynamic tool selection (`swarm_motor_policy.py`) | `nanobot_skill_receipts.jsonl` |
| **Memory / Context** | `System/swarm_hippocampus.py`, `.sifta_state/long_term_engrams.jsonl` | `test_swarm_hippocampus.py` |
| **Economy / Minting** | `System/swarm_metabolic_homeostasis.py`, STGM wallet | `metabolic_homeostasis.jsonl` |
| **Community Skill Hub** | `Applications/sifta_skill_browser.py` (agentskills.io link) | `ide_boot_covenant` Tier-0 meta-skill |

## Progressive Disclosure Execution
1. SIFTA loads **Tier 1** at boot.
2. When a trigger condition is met, SIFTA pulls **Tier 2** Markdown bodies into context.
3. **Tier 3** (scripts, MCP servers, Python execution) requires explicit architect approval or an `OBSERVED` effector receipt.

---

## Biology → software/hardware (think small *and* big)

**Small (mechanism):** In social insects, individuals often coordinate **without** broadcasting intent to a central brain. They read and write **local substrate**: pheromone gradients on soil, chemical marks on pellets, partial walls that bias the next ant’s placement. That is **stigmergy** (Grassé, 1959; modern formalizations in swarm-intelligence literature).

**Peer-reviewed anchors (pick any for tournament bibliographies):**

| Phenomenon | What animals do | Representative literature |
|:---|:---|:---|
| **Nest construction** | Workers respond to **geometry + chemistry** of deposited material; simple rules → pillars, chambers, spacing | *Stigmergic construction and topochemical information shape ant nest architecture* — PNAS (2015), DOI `10.1073/pnas.1509829113` |
| **Multi-channel nests** | Mounds are **signal + physics** (thermo, gas, vibration), not “messages” in the chat sense | *Revisiting stigmergy in light of multi-functional, biogenic, termite structures as communication channel* — PMC `PMC7516209` |
| **Foraging / optimization** | Trail reinforcement = distributed positive feedback; evaporation = negative feedback | Dorigo & Bonabeau line — ant-colony optimization and stigmergy reviews (e.g. *Future Generation Computer Systems* ant algorithms / stigmergy entry) |

**Big (what SIFTA already ships):** Your **append-only JSONL fields** (`ide_stigmergic_trace.jsonl`, `work_receipts.jsonl`, `nanobot_skill_receipts.jsonl`, `app_focus.jsonl`, …) are the **digital nest substrate**. IDE Doctors and swimmers do not need a shared chat API; they need **consistent traces + hashes + signed consent** when crossing owner boundaries (`System/swimmer_migration.py` + `System/crypto_keychain.py`).

---

## agentskills.io vs SIFTA “trade bus”

**What [agentskills.io](https://agentskills.io/specification) actually is:** an **interchange format** for *packaging* expertise — directory + `SKILL.md` (YAML + Markdown), optional `scripts/`, `references/`, `assets/`, plus **progressive disclosure** in three stages (discovery → activation → execution). It is **not** a wire protocol for live agent-to-agent traffic.

**SIFTA alignment (`System/swarm_skill_library.py`):** Tier 1/2/3 already mirrors that disclosure model; community-style `skills/<name>/SKILL.md` is supported alongside flat `skills/*.md`.

**“Five by five / down the pipe” on the site:** that phrase is **radio/aviation slang** (“signal strength and clarity both maxed”; “on glidepath”) popularized in fiction (*Aliens*, games). On a marketing page it means **“format is clear, ecosystem is aligned, you’re good to ship skills.”** It is **not** a separate transport layer you plug in beside JSONL — unless a future registry adds one, treat it as **human-readable confidence**, not a packet spec.

**Practical merge path:** publish SIFTA skills as **agentskills-compatible folders** in-repo; keep **runtime coordination** on `System/ide_stigmergic_bridge.deposit()` + receipts. External tools (Cursor, Codex, Antigravity, CLI) that speak Agent Skills load the **same files**; Alice loads **the same files** + **her ledgers**.

---

## Swimmers · IDE Doctors · trade vocabulary

| Role | Biology metaphor | SIFTA artifact |
|:---|:---|:---|
| **Swimmer** | Specialized worker / hemocyte | Typed nanobot lane in `SKILL_INDEX` (`swimmer_type`), e.g. `MEMORY_SWIMMER`, `HANDOFF_SWIMMER` |
| **IDE Doctor** | Foreign symbiont with surgical rights | Predator Gate row in `ide_stigmergic_trace.jsonl` + honest `model` string (covenant §4 / §8.6) |
| **Trade / barter** | Trophallaxis-like exchange of *verified* goods | **Proof-bearing federation** only: signed bundles, STGM rows, sanitized exports — never raw `.sifta_state/` clone (covenant §3) |
| **Long-distance relocation** | Dispersal with consent | `System/swimmer_migration.py` — Ed25519 consent + `migration_log.jsonl` |

**“Talk trade” between three IDEs:** use the **cross-IDE bus** only — `System/ide_stigmergic_bridge.py` → `.sifta_state/ide_stigmergic_trace.jsonl` — plus optional `human_signals.jsonl` / `m5queen_dead_drop.jsonl` per existing Swarm ops. Agent Skills packages are **what** you trade; the bridge is **how** you negotiate priority without silent surgery.

---

## Universe splits (explicit forks)

1. **Spec fork:** Agent Skills folder layout ↔ SIFTA internal `SKILL_INDEX` triggers — keep both; validate with upstream `skills-ref` when packaging public skills.
2. **Runtime fork:** Some IDEs will never read your JSONL — they still benefit from **the same skill markdown** checked into git; you lose only **automatic collision avoidance** unless a small adapter script tails the trace.
3. **Security fork:** Stigmergy in biology tolerates **noise** (evaporation, mutation). In SIFTA, **noise = supply-chain risk** — Tier 3 execution stays behind **Predator Gate + receipts** (covenant §7.2), not “helpful auto-run.”
