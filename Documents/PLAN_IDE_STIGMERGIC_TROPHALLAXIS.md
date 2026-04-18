# Plan — IDE stigmergy, trophallaxis consumer, and hallucination guardrails

This note is for **Cursor (local)** and **Antigravity**: planning first, APIs second, biology last.

---

## What is real in the repo (verify before citing)

| Piece | Location | Fact |
|--------|----------|------|
| IDE trace substrate | `.sifta_state/ide_stigmergic_trace.jsonl` | Append-only JSONL |
| Bridge API | `System/ide_stigmergic_bridge.py` | `deposit()`, `forage()` |
| Memory bus | `System/stigmergic_memory_bus.py` | `StigmergicMemoryBus(architect_id).remember(text, app_context, decay_modifier=...)` |
| Ledger | `.sifta_state/memory_ledger.jsonl` | One JSON object per line |
| IDE → memory ingest | `System/ide_trace_consumer.py` | Resonance → `decay_modifier`; state in `ide_consumer_cursor.json` |
| CWMS (constraint-weighted retrieval) | `System/constraint_memory_selector.py` | Reranks forager output with `ConstraintState` (λ, τ); **does not** mutate `GatekeeperPolicy` internals |

---

## CWMS — constraint-weighted memory selection (Vector 11 fork)

**Do not** merge memory decay and gatekeeper τ in one feedback loop. **Do** multiply retrieval confidence by a **constraint alignment** factor derived from `decay_modifier` + pressure scalars:

- `ConstraintState.from_gatekeeper_meta(meta, tau, ev_guess)` — builds `lambda_norm`, `tau_norm` from a `GatekeeperDecision`.
- `ConstraintMemorySelector.rerank(candidates, state)` — `new_conf = forager_conf * alignment(trace, state)`.
- `recall_context_block_cwms(bus, query, app_context, state)` — optional LLM context block with reranking.

Alignment uses **only** trace fields (epigenetic `decay_modifier`), not `SAFE` / `NOVEL` string tags.

---

## What was hallucinated (do not paste into new code)

Earlier drafts referenced call sites that **do not exist**:

- `get_memory_bus()`
- `debit_stgm()` as a standalone consumer API (STGM minting lives **inside** `remember` / recall paths in the bus)
- `remember(memory_id=..., decay_modifier=...)` with a custom memory id parameter on the **public** `remember` (trace id is **generated inside** `remember`)

**Rule:** Open `stigmergic_memory_bus.py` and `ide_trace_consumer.py` before describing behavior in chat.

---

## v1 vs v2 resonance (honest)

**v1 (shipped in `ide_trace_consumer.py`):** lexical markers → resonance → `decay_modifier`. Fast, tunable, **gameable** if someone stuffs keywords.

**v2 (Vector 12 design goal):** structural + novelty + density (see `Documents/VECTOR12_EPIGENETIC_MEMORY_ENGINE_NOTE.md`), e.g.:

- `impact` from `meta.files_touched` length (requires producers or a git hook to populate `meta`)
- `novelty` from max similarity to last *N* ledger lines (same architect)
- `density` from `len(payload)` (already available)

**Migration:** Replace or blend `_calculate_resonance()` so keyword count is **at most** one term in a weighted sum, not the whole score.

---

## Vector 13 (policy bias) — not yet wired

`gatekeeper_policy.py` does **not** currently consume `recall_context_block()` or memory bus priors. CWMS is a **separate** compositional layer: build `ConstraintState` from the same gatekeeper **decision** you already trust, then call `recall_context_block_cwms` for context injection — **not** inside `evaluate_action` unless you add a deliberate, tested hook.

---

## Operational commands

```bash
cd System && python3 ide_trace_consumer.py           # ingest new traces
cd System && python3 ide_trace_consumer.py --reingest # reset cursor + re-run all
```

---

## Stigmergic pointer

When changing behavior, append a short `handoff` via `ide_stigmergic_bridge.deposit()` so the other IDE sees the intent without shared chat.
