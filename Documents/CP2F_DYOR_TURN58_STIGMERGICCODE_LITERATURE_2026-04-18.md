# CP2F DYOR — Turn 58 “Stigmergiccode” + AO46 upgrades (literature map)

**Date:** 2026-04-18  
**Purpose:** Separate **browser-tab sketches** from **citable research**. Map five engineering directions (provenance, budgets, diffs, anomalies, cold-start) to **physics / math / biology / CS**, and to **stigmergy** (environment-mediated coordination — Bonabeau line), **without** claiming nanoscale robots.

**Epistemic rule:** “Stigmergiccode” = **code + append-only substrates + explicit edges** — not a separate programming language.

---

## A. Interdisciplinary spine (why “biocode olympiad” is a *metaphor*)

| Layer | Anchor | Role |
|--------|--------|------|
| **Math / control** | Lyapunov / feedback stability (any standard text, e.g. Khalil *Nonlinear Systems*) | Bounded loops, governors |
| **Physics / information** | Landauer (irreversible computation & heat); Shannon entropy | Costs of erasure / bits — **not** mysticism |
| **Biology (real)** | Grassé → Bonabeau **stigmergy**; Janeway **PRRs** (pattern vs self) | Coordination without central planner; “immune” as **classification** |
| **CS** | PROV, lineage, SPC, RL warm-start | Auditable systems |

**Stigmergy (papers):** Bonabeau, Dorigo, Theraulaz — *Swarm Intelligence* (OUP, 1999); Bonabeau — “Editor’s Introduction: Stigmergy” — *Artificial Life* (1999).

---

## B. Upgrade 1 — Provenance graph (truth layer)

**Idea:** Every important mutation = one append-only **edge** (`who`, `what`, `inputs`, `output`, `ts`).

| Reference | Why |
|-----------|-----|
| **W3C PROV** — PROV-DM, PROV-O — `https://www.w3.org/TR/prov-dm/` | Standard vocabulary for **entities, activities, agents** |
| **Green, Karvounarakis, Tannen** — *Provenance semirings* — *PODS* 2007 | Lineage in **query evaluation** (how-provenance) |
| **Buneman, Khanna, Tan** — “Why and Where: A Characterization of Data Provenance” — *VLDB* 2001 | Foundational **where-provenance** |
| **Lamport** — “Time, Clocks, and Ordering of Events…” — *CACM* 1978 | Ordering in distributed systems (tie-break for edges) |

**Repo:** `System/provenance_graph.py` → `.sifta_state/provenance_graph.jsonl`; wired from **brainstem** on successful DA/5-HT loop.

---

## C. Upgrade 2 — Execution budget governor (anti-Goodhart)

**Idea:** Hard cap on inference calls per cycle / per agent — **not** infinite swarm spam.

| Reference | Why |
|-----------|-----|
| **Stroud** — “The Development of Rate Limiting Controls” (token bucket family) — classic networking texts | **Token bucket / leaky bucket** |
| **Goodhart** — Bank of England (1975) aphorism; **Strathern** (“Campbell’s law”) | **When a measure becomes a target…** |
| **Manheim & Garrabrant** — “Categorizing Goodhart” — arXiv `1803.04585` | Taxonomy of metric failure modes |

**Already in repo:** `System/metabolic_throttle.py` — inference rate limiting; **extend** rather than duplicating a second “BudgetGovernor” unless semantics differ (global vs per-agent).

---

## D. Upgrade 3 — State diff engine (semantic change visibility)

**Idea:** Persist `{file, diff}` when JSON state changes — not only full snapshots.

| Reference | Why |
|-----------|-----|
| **RFC 6902** — JSON Patch | Standard **diff** / patch ops |
| **Myers** — diff algorithm (1986) — *Algorithmica* | Line-oriented diff foundation |
| **Chandy & Lamport** — distributed snapshots (1985) | Consistent cuts if you diff **across** files |

---

## E. Upgrade 4 — Anomaly scoring (“immune” without mysticism)

**Idea:** z-score / robust z vs rolling mean — **statistical** monitoring, not only rule checks.

| Reference | Why |
|-----------|-----|
| **Shewhart** — *Statistical Method from the Viewpoint of Quality Control* (1939) | **SPC** — control charts |
| **Hotelling** — T² multivariate control (1947 lineage) | Multivariate anomaly |
| **Liu, Ting, Zhou** — “Isolation Forest” — *ICDM* 2008 | Lightweight **unsupervised** anomaly detector |
| **Samuel et al.** — ML monitoring survey — arXiv `2006.12117` (cited in `runtime_safety_monitors.py` doc) | Ops framing |

**Repo overlap:** `System/runtime_safety_monitors.py` — extend with **rolling stats** if you outgrow static bounds.

---

## F. Upgrade 5 — Cold-start memory seeder

**Idea:** Bootstrap buffers / policy from **last good checkpoint**, not empty every run.

| Reference | Why |
|-----------|-----|
| **Nguyen et al.** — warm-start RL line (policy transfer) | **Warm start** in RL |
| **Hinton / fine-tuning** literature | Transfer from prior task |
| **Buzsáki** — hippocampal replay (DYOR §23 in main gather) | Biological **offline** consolidation analogue — use as **scheduling** inspiration only |

**Repo overlap:** `hippocampal_replay_scheduler.py`, `pfc_state_buffer.json` — seeder should **read last snapshot**, not fiction.

---

## G. Physics + mathematics + biology (tournament-style reading order)

1. **Information / thermodynamics:** Landauer — “Irreversibility and heat generation…” — *IBM J. R&D* **5** (1961).  
2. **Distributed truth:** Lamport (1978); Fidge (1988) vector clocks (if you scale provenance multi-host).  
3. **Swarm coordination:** Bonabeau *et al.* (1999).  
4. **Dependability:** Avizienis *et al.* — *IEEE TDSC* (2004) DOI `10.1109/TDSC.2004.2`.  
5. **When metrics lie:** Manheim & Garrabrant — arXiv `1803.04585`.

---

## H. What AO46’s tab got right vs wrong

| Claim | CP2F verdict |
|-------|----------------|
| Unified provenance graph | **Right direction** — implemented minimal **append-only** layer + brainstem hook |
| Budget governor | **Partially exists** — see `metabolic_throttle.py`; unify naming if adding a second knob |
| State diff | **Right** — add **after** provenance volume is observable |
| Anomaly scoring | **Right** — complements **rule-based** watchdog |
| Cold-start seeder | **Right** — align with **checkpoints** you already persist |

**Avoid:** more full-file scan loops without **tail/offset** discipline (see `swarm_chat_relay` watermarks).

---

## I. One-line direction (shared with AO46)

> **Make every state change traceable, bounded, and explainable** — provenance first, then budgets, then diffs, then anomalies, then warm-start.
