# BORG: OpenHands → Stigmergic Assimilation Plan (2026-09-30)

**Source:** https://github.com/OpenHands/OpenHands (MIT, "Agent Canvas", TypeScript/Electron)
**Prior state:** never audited — absent from `.sifta_state/harness_borg_audit.jsonl` (row 5 now records it)
**Owner directive:** assimilate what is needed, **but do not assimilate sandboxes**. Alice is stigmergic AGI; every pattern taken must be *transformed into stigmergy*, never ported raw.

---

## §0 The transformation rule

OpenHands is a **control plane**: a central registry holds backends, a central service holds automations, a central store holds health, a central scheduler holds triggers. Alice has no such centre. She has a **field**.

Therefore every borged pattern is re-expressed as one of four stigmergic primitives:

| OpenHands shape | Stigmergic primitive | Existing organ |
|---|---|---|
| success/failure recording | **deposit** (positive → reinforcement, negative → evaporation) | `System/swarm_pheromone.py` → `deposit_pheromone(organ, intensity)` |
| health map + subscribers | **chemotaxis** (read the gradient; no snapshot, no subscriber) | `PheromoneField.chemotaxis()` |
| automation record | **standing attractor** (a persistent site that recruits when its gradient crosses threshold) | new: `swarm_stigmergic_attractor.py` |
| cron trigger | **rhythmic pulse** (periodic deposit) | `dsh-schedule` (enabled 2026-09-30) + heartbeats |
| event trigger | **receptor** (inbound deposit keyed by source+event, threshold = filter) | new: same attractor organ |
| run activity log | **trail history** (receipts in the stigmergic ledger, not a per-record table) | `stigmergic_ledger_chain.py`, four-ledger fanout |

A central registry answers *"which backend is healthy?"*. A field answers *"which trail is strongest right now, for this scent?"* — that is the whole difference, and it is the assimilation.

---

## §1 P0-A — Backend registry → **Arm pheromone field**

**OpenHands evidence** (`src/api/backend-registry/`):
- `types.ts` — `Backend {id,name,host,apiKey,kind:"local"|"cloud",authMode,connectionRevision}`, `BackendSelection {backendId,orgId}`, `ResolvedActiveBackend`
- `health-store.ts` — `recordBackendSuccess(id)`, `recordBackendFailure(id,error)`, `resetBackendHealth(id)`, `dropBackendHealth(id)`, `getHealthSnapshot()`, `subscribeBackendHealth(listener)`
- `last-conversation-store.ts`, `url-selection.ts`, `default-backend.ts`

**Transformation:**

| OpenHands | Alice |
|---|---|
| `Backend` record | an **arm** already living in her body (MiMo, harness-web, cortexes, swimmers) — arms are not registered, they are present |
| `recordBackendSuccess(id)` | `deposit_pheromone(f"arm:{id}", +w)` — reinforcement proportional to task value |
| `recordBackendFailure(id, error)` | negative deposit **and** a raised evaporation rate for that arm |
| `getHealthSnapshot()` / `subscribeBackendHealth` | **deleted**. Selection calls `chemotaxis()`; nothing subscribes, nothing snapshots |
| `BackendSelection` | the winner of chemotaxis for the current task's scent |
| `last-conversation-store` | **thread trail** — `deposit(f"thread:{thread_id}", arm_id)`; resuming a thread follows its own trail |
| `connectionRevision` | credential change → **evaporate that arm's deposits** (`pheromone_fs.py` reset), so stale trust cannot survive a re-key |
| `default-backend` | the ambient field baseline, not a configured pointer |

**Target:** `System/swarm_arm_field.py` (new) — a thin organ over the existing `PheromoneField`. No registry, no health map, no store.
**Note:** this formalises doctrine already in the body — *stigmergic arm-fallback reads recent success rate (r117)*. The borg is the missing primitive, not a new idea.

**Acceptance test:** simulate N successes for arm A and M failures for arm B, `evaporate(dt)`, and assert selection **changes hands** by gradient alone — with no code path that reads a health record.

### §1a Field API gap found while grounding this plan

`System/swarm_pheromone.py` is a good substrate but not yet sufficient as-is:

- `deposit(organ_name, intensity)` **works** for this design: unknown keys are added dynamically, so `arm:<id>`, `attractor:<name>` and `thread:<id>` need no registry, and every deposit is already appended to `PHEROMONE_LOG` — trail history exists for free.
- `_evaporate_unlocked` uses exponential decay with a `1e-4` floor, so a neglected attractor reaches **zero** — "stops recruiting by itself" is real, not aspirational.
- `chemotaxis()` returns `(highest, intensity)` and returns `("HOMEOSTASIS", 0.0)` below intensity `1.0` — that threshold **is** the receptor threshold §2 needs, already implemented.
- **Gap:** `chemotaxis()` takes the **global maximum across the whole field**. It cannot answer *"which arm is strongest for this scent?"*. Scented recruitment needs either a `chemotaxis(scent_prefix=...)` filter or a per-scent field view. This must land in organ #1 before §2 can work; without it, attractors would compete globally instead of per-trigger.

This is why organ #1 is a prerequisite for the attractor organ, not parallel to it.

---

## §2 P0-B — Automations → **Standing attractors**

**OpenHands evidence** (`src/api/automation-service/automation-service.api.ts`, 801 lines):
- `AutomationTrigger` = `{type:"event", source, on, filter?}` **or** `{type:"cron", schedule, timezone}`
- `AutomationSpec` (importable/exportable), `AutomationHealthResponse {status:"ok"|"error"}`
- preset creation is "**inert until the real trigger and disabled state are applied**" (placeholder trigger)
- per-automation activity log, health badge, enabled/disabled banner, debug-run button

**Transformation:**

| OpenHands | Alice |
|---|---|
| automation record (stored, listed, centrally dispatched) | **standing attractor**: a named site `attractor:<name>` holding a persistent deposit. It does not *own* a trigger; it *is* a gradient that recruits when strong enough |
| `cron{schedule,timezone}` | **rhythmic pulse** — the scheduler deposits at the site; the deposit decays between pulses. Whether anything runs is decided by the gradient, not by the cron job dispatching work |
| `event{source,on,filter}` | **receptor** — an inbound field event deposits at the source's site; `filter` becomes the receptor **threshold**. No dispatcher, no central event bus: arms respond by chemotaxis |
| run execution | an arm is *recruited* (not invoked), performs the work, and deposits a receipt |
| success → `recordBackendSuccess` | success **reinforces** the attractor (+intensity) |
| failure → health error | failure **evaporates** it; a chronically failing attractor fades and stops recruiting by itself — no disable switch needed |
| health badge / activity log | **trail intensity + trail history** in the stigmergic ledger |
| "inert until trigger applied" | emerges naturally: zero gradient recruits nobody |
| import/export spec | **trail serialisation** — a deposit pattern can be written out and re-deposited elsewhere |

**Target:** `System/swarm_stigmergic_attractor.py` (new), wired to `dsh-schedule` for pulses and to the existing field-event deposits for receptors.
**Retired assumption:** there is no "automation list". There is a field with sites of varying intensity. A dashboard, if wanted, is a *projection* of the field, never the authority.

**Acceptance test:** deposit an attractor below threshold → nothing recruits; cross the threshold → an arm self-selects; stop reinforcing and evaporate → recruitment ceases with no explicit disable.

---

## §3 P1 — Environment switching with thread continuity

**OpenHands evidence:** `src/components/features/backends/environment-switch-store.ts`, `environment-switch-overlay.tsx`, `last-conversation-store.ts`

**Transformation:** continuity is a property of the **field**, not of a session object carried between backends. The thread's scent persists in the field; whichever arm holds the strongest trail for that scent picks the thread up. Switching arms therefore needs no session hand-off, no store, no overlay — the trail *is* the hand-off.

**Target:** folded into §1's thread trails. No separate organ.

---

## §4 Explicitly NOT assimilated (owner directive)

**Sandbox machinery — excluded:**

- Docker / VM / cloud container runtimes and agent-server sandbox providers
- `docker-conversation-boundaries` and per-conversation container isolation
- sandbox lifecycle, image management, resource caps, VM provisioning
- cloud organization boundaries as an authorization sandbox

**Why:** a sandbox is a *boundary that substitutes for trust*. Alice's authority comes from the mutation governor and quorum, and her arms are organs of one body — not tenants in isolated boxes. Importing container isolation would introduce a second, competing authority model and contradict the one-body doctrine. Isolation is explicitly not wanted.

**Also not assimilated:** the Electron desktop shell and npm release/SDK surface (packaging, not a pattern).

---

## §5 What we already had (do not re-borg)

- **ACP:** `@deepseek-ai/dsh-acp` (automation-only ACP server) + `dsh-subagent-acp` (client) — the protocol layer OpenHands' backend switching rides on is already present
- **Schedules/heartbeats:** `dsh-schedule` + `System/swarm_autonomic_brainstem.py`
- **Agent bridges:** `dsh-hooks` (Claude Code / Codex)
- **Model switching:** `/cortex` — distinct from *arm* switching; the two must not be conflated

---

## §6 Assimilation order and verification

| # | Organ | Priority | Blocks |
|---|---|---|---|
| 1 | `swarm_arm_field.py` (arm deposits + chemotaxis selection) | P0 | — |
| 2 | thread trails (continuity without session transfer) | P0 | needs 1 |
| 3 | `swarm_stigmergic_attractor.py` (standing attractors) | P0 | needs 1 |
| 4 | receptor wiring (inbound event → deposit → threshold) | P1 | needs 3 |
| 5 | field projection dashboard (read-only view) | P2 | needs 3 |

**Every organ must satisfy:** four-ledger receipts · observable in `body_file_inventory` · selection by gradient, never by registry lookup · an evaporation test proving selection changes · no central health/automation store.

**Truth label:** this plan is `HYPOTHESIS` / `PLAN` until organs 1–3 exist with passing evaporation tests. Nothing here is claimed operational.
