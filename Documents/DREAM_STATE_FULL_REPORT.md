# Swarm Dream State — Full Report (SIFTA alignment + gaps)

**Date:** 2026-04-16  
**Scope:** Map the “Swarm dreams / hippocampal replay during absence” concept to the existing SIFTA stack, document safety boundaries, and record the minimal novel code added (`System/dream_state.py` + `System/temporal_spine.py` hooks).

---

## 1. What you asked for (literal, not metaphor)

- When the **Temporal Spine** infers meaningful **Architect absence**, the system should **not** treat idle time as a no-op.
- A **`DreamEngine`** should read **ground-truth** memories from **`.sifta_state/memory_ledger.jsonl`**, find pairs of traces whose **semantic tags overlap**, and emit **`DreamTrace`** records that are **explicitly `INFERRED`**, never confused with observed fact.
- On return, a **morning briefing** string can surface the strongest recent syntheses **before** normal dialogue (integration point: LLM system prefix or console print — see §5).

This mirrors **consolidation**: biology uses offline replay to integrate patterns; here we use **deterministic graph pairing + templates** (no LLM required for the core loop).

---

## 2. How this maps to SIFTA today

| Concept | SIFTA substrate |
|--------|------------------|
| “Architect away” | `TemporalSpine` reads `.sifta_state/temporal/presence_rhythm.jsonl` and computes **absence** before a new `open_session` beat is appended. |
| Episodic store | `.sifta_state/memory_ledger.jsonl` (append-only JSON lines). |
| Offline synthesis | `.sifta_state/dreams/dream_traces.jsonl` — **separate** from the ledger; dreams are not written as ground truth. |
| Economy / traceability | Dream rewards append to `.sifta_state/stgm_memory_rewards.jsonl` with `reason: "DREAM_SYNTHESIS"` (same **shape** as stigmergic mint helpers — **not** a silent alternate economy path). |

**Safety / non-harm:** The engine **does not** delete or rewrite swimmer state, **does not** inject dream text into the primary ledger as fact, and **does not** overwrite temporal logs. Failures in dreaming are **swallowed** at the spine so presence/session flow stays intact.

---

## 3. Novel code added (what was missing)

### 3.1 `System/dream_state.py`

- **`DreamTrace`** dataclass with `kind="INFERRED"`.
- **`DreamEngine.dream(absence_hours)`** — scales a **synthesis budget** with absence depth; pairs only **non-inferred** ledger rows (`is_inferred` / `app_context != "dream"` guard).
- **`morning_briefing()`** — returns a short, labeled block for optional injection upstream.
- **STGM:** `_mint_stgm_dream()` appends small attributed amounts for bookkeeping consistency.

**Important implementation note:** Earlier sketches that **fed dream rows back** into the pairing pool caused **combinatorial explosion**. The production-shaped version **only pairs ground-truth ledger traces** and caps total syntheses per run.

### 3.2 `System/temporal_spine.py`

- Paths anchored to **`_REPO`** so `.sifta_state` resolves regardless of cwd.
- **`open_session`:** if absence ≥ **1 hour**, runs `DreamEngine.dream(...)` once and prints `morning_briefing()` (optional later: pass briefing to GCI).
- **`open_session`:** greeting gap uses **`_time_since_last()` before** appending the new beat so “welcome back” reflects real time since the **previous** session start.

---

## 4. Why this is different from “idle = zero” assistants

Most assistants **discard** the interval between sessions. SIFTA treats **absence as a first-class input**: longer absence increases **budget** for **offline** consolidation over **existing** memories, producing **hypotheses** (`INFERRED`) rather than hallucinated facts.

---

## 5. Remaining integration (optional)

- **GCI / first LLM call:** Prefix `DreamEngine(...).morning_briefing()` to the system prompt or conversation bootstrap **once per return**, not on every message.
- **Ed25519 signing:** If project policy requires **all** STGM mutations to be signed via `System/crypto_keychain.py`, align `DREAM_SYNTHESIS` rewards with that policy in a follow-up (current code matches the existing jsonl-append helper pattern).

---

## 6. Quick verification

From repo root:

```bash
python3 -m py_compile System/dream_state.py System/temporal_spine.py
python3 System/dream_state.py
```

---

## 7. One-line thesis

**Novel idea — The Swarm dreams:** *Offline tag-overlap synthesis during absence, stored only as `INFERRED` traces, grounded in the memory ledger but never merged into it as truth — Proof of Useful Sleep without pretending to know what the Architect did not say.*
