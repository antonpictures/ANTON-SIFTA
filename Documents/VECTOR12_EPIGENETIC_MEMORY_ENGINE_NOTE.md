# Vector 12 — Epigenetic Memory Engine (design note)

**Stigmergic deposit:** intent → durable substrate → downstream behavior. This note tightens the idea so it stays **measurable, stable, RL-compatible**, and does not depend on brittle keyword “resonance.”

**Status:** bus + consumer are **wired**; scoring is on a **migration path** (see below).

### Implementation status (ground truth)

- **`StigmergicMemoryBus.remember(text, app_context, decay_modifier=1.0)`** — real. `PheromoneTrace.decay_modifier` feeds **`retention()`** as `effective_age = age_hours * decay_modifier` (values below 1.0 slow decay).
- **`System/ide_trace_consumer.py`** — real. Ingests `ide_stigmergic_trace.jsonl` kinds `handoff` / `response` / `swimmer_dispatch`, maps **lexical** `_calculate_resonance()` (marker list) → `decay_modifier` via `_resonance_to_decay_modifier()`. That is **v1 trophallaxis**: quick to ship, same fragility class as any keyword layer.
- **Structural resonance** (impact, novelty, length — earlier sections of this doc) is **not** fully implemented in the consumer yet; it is the **intended upgrade** when traces carry `meta.files_touched` (or similar) and we add a cheap novelty pass over recent ledger lines.
- **ACMF fitness overlay (Vector 12 v1):** **`System/memory_fitness_overlay.py`** + **`.sifta_state/memory_fitness.json`** (gitignored like other `*.json` state). Fitness **never** mutates `PheromoneTrace` rows in `memory_ledger.jsonl`. Writes use **`read_write_json_locked()`** in **`System/jsonl_file_lock.py`** (one `LOCK_EX` for load→merge→save). **`MemoryForager`** applies **`fitness_multiplier`** to confidence; **`recall()`** calls **`bump_after_recall`** after ledger reinforcement. **`apply_outcome(trace_id, reward)`** is the hook for future gatekeeper / RL feedback.
- **Do not use** in new code: fake helpers from earlier drafts (`get_memory_bus()`, `debit_stgm()` as a free function, `remember(memory_id=...)`). Use **`StigmergicMemoryBus(architect_id)`** and the real **`remember`** signature above.

See also: `Documents/PLAN_IDE_STIGMERGIC_TROPHALLAXIS.md`.

---

## Core idea (formal)

Build a **persistent high-weight memory channel** that injects **design intent** into the learning stack as **long-timescale priors** for agent behavior. That is legitimate and uncommon in many RL setups when the channel is grounded.

---

## Problem with naive resonance

Keyword-style scoring (e.g. counting marker hits) is:

- arbitrary and easy to game  
- weakly tied to real system impact  

**Replace with structural resonance** — signals derived from trace shape and history, not vibes.

---

## Structural resonance (proposed)

Given an IDE trace record (e.g. a line from `.sifta_state/ide_stigmergic_trace.jsonl` plus optional enrichment):

### 1. Structural impact

How much of the repo/system the change touches:

```text
impact_score = min(len(trace.get("files_touched", [])) / 10.0, 1.0)
```

(`files_touched` must be supplied by the producer or a git-aware hook — not invented by the consumer.)

### 2. Novelty (anti-duplication)

```text
novelty_score = 1 - max_j similarity(payload, existing_memory_j)
```

Start with a simple overlap or embedding similarity; keep the interface swappable.

### 3. Persistence relevance (density)

```text
length_score = min(len(payload) / 500.0, 1.0)
```

### 4. Combined resonance

```text
resonance = 0.4 * impact_score + 0.4 * novelty_score + 0.2 * length_score
resonance = min(resonance, 1.0)
```

Properties: bounded, interpretable weights, no keyword table.

---

## Consumer sketch: `ide_trace_consumer` → memory

**Role:** tail or poll `ide_stigmergic_trace.jsonl`, score lines with the above, optionally write into **`StigmergicMemoryBus`** with cost scaled by resonance (e.g. STGM debit proportional to `resonance` if economics stay consistent with `System/stigmergic_memory_bus.py`).

**Integration reality check:** today `StigmergicMemoryBus.remember(text, app_context)` stores text and derives tags internally. A production Vector 12 path either:

- extends the bus with explicit **weight / decay** on traces, or  
- stores a structured JSON line in `app_context` / payload conventions and keeps “weight” in a sidecar ledger.

The pseudocode in the original brief used a richer `remember(...)` — treat that as **target API**, not current API.

**Trace fields:** prefer existing bridge schema (`trace_id`, `ts`, `source_ide`, `kind`, `payload`, optional `meta`). Use `meta` for `files_touched` until a schema bump is justified.

---

## What this is (real terms)

- **Hierarchical memory prioritization** with structure-aware weighting — adjacent to meta-learning priors, lifelong-learning buffers, and architecture-aware knowledge injection.  
- **Not** literal “DNA” or “instinct encoding” — functionally it behaves like **long-horizon priors** if bias injection is added later.

---

## Vector 13 (next leap, research-grade)

Use scored memories to **bias policy**, e.g. add a retrieved bias term to logits or gatekeeper features:

```text
policy_logit += memory_bus.retrieve_bias(state)   # sketch only
```

That ties architecture and intent to behavior without semantic magic — **if** retrieval and bias are regularized and measured.

---

## Verdict

The direction is strong if:

- keyword resonance is removed  
- resonance is **structural + measurable**  
- integration into RL/policy is explicit and testable  

Next implementation choices (when the Architect approves): wire consumer → `StigmergicMemoryBus`, or extend the bus API for weighted traces, then connect to **`System/gatekeeper_policy.py`** as bias injection (Vector 13).

---

## References in-repo

- Cross-IDE substrate: `System/ide_stigmergic_bridge.py`, `.sifta_state/ide_stigmergic_trace.jsonl`  
- Memory ledger: `System/stigmergic_memory_bus.py`, `.sifta_state/memory_ledger.jsonl`  
- Policy hook surface: `System/gatekeeper_policy.py`
