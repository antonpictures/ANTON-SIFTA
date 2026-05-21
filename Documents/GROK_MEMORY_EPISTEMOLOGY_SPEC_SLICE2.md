# Grok Coding Order — Memory Epistemology, Slice 2 (Local Hybrid Recall)

**Stigauth:** `GROK_MEMORY_EPISTEMOLOGY_SPEC_SLICE2_v1`
**Author of spec:** Cowork (Claude Opus 4.7), Auditor lane
**Coder (owns the edit):** Grok — lane: Surgeon
**Verifier after Grok:** Cowork runs the gates → Codex re-verifies Cowork.
**Target organ:** `System/stigmergic_memory_bus.py` (slice 1 already merged & verified, receipt `ac9b0e71063d4980`).
**Precondition:** Read `MemoryForager.forage()` (~line 173) and `recall_context_block()` (~line 516)
before you touch anything — slice 2 *composes* the existing forager score, it does not replace it.

> Collision discipline (§4.4): Grok owns this scalpel. Cowork writes spec + tests only. Register
> (Surgeon) before mutating; receipt after. Append-only.

## Why this slice

Slice 1 gave memories typed truth (`epistemic_label`) + backlinks (`links`). Slice 2 makes *recall*
use that truth, and ranks better. The Architect's order: **a rebuildable search helper, not a new
source of truth.** JSONL stays canonical. No cloud. No required Postgres. No required pgvector.

## What to build

A new method `hybrid_recall(self, query, app_context, *, top_k=5)` returning a ranked list of
`(score, trace, breakdown)` where `breakdown` is a dict of the component scores. The final score is a
weighted blend of four signals, all computable locally from the ledger:

1. **Forager score** — the existing `MemoryForager.forage()` confidence (semantic/keyword smell). Reuse
   it; do not rewrite it.
2. **BM25-lite keyword score** — a small, dependency-free BM25 over `raw_text` + `semantic_tags`
   tokens across the ledger (k1≈1.5, b≈0.75). Pure Python, no external libs.
3. **Decay** — `trace.retention()` (already on `PheromoneTrace`, Ebbinghaus). Fresh/reinforced rows rank higher.
4. **STGM / fitness** — `recall_count` and the fitness overlay already used by the bus. More-recalled
   memories rank higher.

Then apply an **epistemic weight** on top:

- `OBSERVED`, `WORLD`, `ARCHITECT_DOCTRINE` → multiply score by ~1.25 (evidence-backed truth ranks up).
- `BELIEF` → ~1.0. `HYPOTHESIS` → ~0.7 (guesses rank down).
- `FICTION` → **excluded from factual recall entirely** (consistent with slice 1's recall guard).

Expose the weights as module constants so they are tunable and testable (e.g. `HYBRID_WEIGHTS`,
`EPISTEMIC_RANK_MULTIPLIER`). Wire `recall_context_block()` to use `hybrid_recall` for ordering while
keeping its existing label-prefixed, FICTION-excluded output format unchanged.

## Rebuildable index (derived, never authoritative)

If you add an index cache to speed BM25 (optional), it must be:

- Stored under `.sifta_state/` as a **derived** file (e.g. `memory_recall_index.json`), regenerable in
  full from `memory_ledger.jsonl` by a `rebuild_recall_index()` function.
- Stamped with `{source_ledger_hash, ts}` so staleness is detectable.
- Never read as truth when it disagrees with the ledger — the ledger always wins.

## Hard constraints (reject, per the Architect)

- No embeddings *required*. If you scaffold an embedding hook, it must be **off by default**, local
  only, no network call, and the system must work fully without it this slice.
- No Postgres. No pgvector. No second markdown brain. No new MCP/tool surface.

## Acceptance tests (Cowork will run these)

1. `hybrid_recall` returns results ordered by blended score; `breakdown` contains all four components.
2. Two memories identical except label: the `OBSERVED`+links one outranks the `HYPOTHESIS` one.
3. A `FICTION` memory never appears in `hybrid_recall` factual results nor in `recall_context_block`.
4. BM25-lite: a memory containing the rare query term outranks one that merely shares a common word.
5. Decay: given equal text relevance, the more-recently-reinforced (`recall_count` higher) memory ranks higher.
6. `rebuild_recall_index()` (if implemented) reproduces ranking identically to the no-index path, and
   the index carries a `source_ledger_hash`. (If you skip the index, assert hybrid_recall works without one.)
7. Back-compat: legacy rows (slice-0, no label) default to `HYPOTHESIS` weighting and still rank/recall.

## Out of scope (later slices)

- Slice 3: `Documents/SIFTA_BRAIN_REPO_INDEX.md` — a generated *map* of canonical docs/row-types/ledgers.
- Slice 4: book-mirror pattern — generated prose with source ledger hashes, never authority over receipts.

One body, many hands, append-only field. This is not a competition. For the Swarm. 🐜⚡
