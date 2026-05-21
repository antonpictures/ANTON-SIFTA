# Grok Coding Order — Memory Epistemology, Slice 1

**Stigauth:** `GROK_MEMORY_EPISTEMOLOGY_SPEC_v1`
**Author of spec:** Cowork (Claude Opus 4.7), Auditor lane
**Coder (owns the edit):** Grok
**Verifier after Grok:** Cowork runs the acceptance tests below → then Codex (OpenAI) verifies Cowork.
**Target organ:** `System/stigmergic_memory_bus.py` (654 lines; schema in `PheromoneTrace`, write path in `remember()`)
**Companion:** `Documents/CS153_STANFORD_YC_AI_NATIVE_SIFTA_BRIDGE.md` §5, `Documents/IDE_BOOT_COVENANT.md` §6.

> Collision discipline (covenant §4.4): **Grok owns this scalpel.** Cowork will NOT edit
> `stigmergic_memory_bus.py` in parallel — Cowork only writes this spec + the tests and verifies.
> Grok: append your `LLM_REGISTRATION` row to `.sifta_state/ide_stigmergic_trace.jsonl` (lane: Surgeon)
> before mutating, and a `work_receipt` after. No anonymous surgery.

---

## Why this slice

Memory rows today carry no epistemic status. A line George *said*, a thing Alice *inferred*, a fact
that was *verified*, and a *TV/cowatch fiction* all land in the same ledger and can be recalled as if
equally real. The fix is **typed epistemic status + backlinks** so recall knows the difference. Per
the Architect's expert call, the rejected paths are: Postgres-only memory, pgvector as required infra,
a second markdown brain competing with `.sifta_state`, and LLM "belief promotion" without receipt
rules. **JSONL stays canonical.** This slice ships the schema only — embeddings/BM25 are slice 2.

**Correction baked in:** `epistemic_label` alone is not enough. The field MUST ship together with
`links[]`. Label + backlink is the unit; a bare label is just an adjective.

---

## 1. Schema change — `PheromoneTrace`

Add two fields to the dataclass (keep all existing fields and their order; append the new ones with
safe defaults so old rows and old callers keep working):

```python
from dataclasses import dataclass, field  # `field` import is required

epistemic_label: str  = "HYPOTHESIS"        # see allowed set below; conservative default
links:           list = field(default_factory=list)   # backlinks / evidence_refs (strings)
```

**Allowed labels** (define as a module-level frozenset `EPISTEMIC_LABELS`):

| Label | Meaning | Recall-as-fact? |
|-------|---------|-----------------|
| `OBSERVED` | Directly stated by George, or a tool result with a receipt | yes |
| `WORLD` | Verified real-world fact, evidence-backed | yes |
| `BELIEF` | Alice holds it, evidence-supported but not proven | qualified |
| `HYPOTHESIS` | Alice's guess / inference, unverified | no (mark as guess) |
| `ARCHITECT_DOCTRINE` | Covenant / doctrine / standing order | yes (as doctrine) |
| `FICTION` | TV, cowatch, media, story, roleplay | **never as real-world fact** |

**Link grammar** — each entry in `links` is a string with one of these prefixes (validate; reject
unknown prefixes by dropping them and logging, do not raise inside `remember`):

- `trace_id:<id>` → a row in `.sifta_state/ide_stigmergic_trace.jsonl`
- `receipt:<ledger>.jsonl#<receipt_id>` → e.g. `receipt:work_receipts.jsonl#95c7686a4e7b4d4b`
- `doc:Documents/<path>` → a canonical document
- `memory:<trace_id>` → another memory row (link between memories)

---

## 2. The label↔evidence rule (the correction, enforced)

A claim that asserts reality must carry evidence. Enforce in `remember()`:

- If `epistemic_label` in {`OBSERVED`, `WORLD`} **and** `links` is empty → **auto-downgrade to
  `HYPOTHESIS`** and append a `links` entry `note:downgraded_no_evidence`, and log one line to
  `.sifta_state/memory_epistemology_audit.jsonl` `{ts, trace_id, requested_label, final_label, reason}`.
  Do **not** raise — degrade honestly rather than crash the write path.
- `ARCHITECT_DOCTRINE`, `BELIEF`, `HYPOTHESIS`, `FICTION` may have empty `links`.
- Unknown label string → coerce to `HYPOTHESIS` + audit row.

This is the operational form of "no belief promotion without receipt rules."

---

## 3. `remember()` signature + default inference

```python
def remember(self, text, app_context, *, decay_modifier=1.0,
             epistemic_label=None, links=None):
```

- `links=None` → `[]`.
- `epistemic_label=None` → infer via a new helper `_infer_label(app_context, text)`:
  - `app_context` matching any of `fiction`, `cowatch`, `media`, `tv`, `movie`, `story`, `roleplay`
    (case-insensitive substring) → `FICTION`.
  - otherwise → `HYPOTHESIS` (conservative; the caller must explicitly assert `OBSERVED` *with* links
    to make something count as real). Document this clearly.
- Then apply the §2 rule. Write the resulting label + links into the `PheromoneTrace` and hence the
  JSONL row (still via `append_line_locked(LEDGER_FILE, json.dumps(asdict(trace)) + "\n")`).

---

## 4. Recall guard (so fiction is never surfaced as fact)

In `recall_context_block()` (and anywhere recall builds a "facts" block):

- Exclude `FICTION` rows from the factual block entirely (they may still be recalled in an explicitly
  fiction-aware path later — out of scope here).
- Prefix each surfaced line with its label, e.g. `- [OBSERVED] (app, 3h ago): "..."`,
  `- [HYPOTHESIS·guess] (...)`. This keeps the latent layer honest about what is fact vs guess.
- Do not change the forager's scoring math in this slice (that's slice 2).

---

## 5. Backward compatibility (hard requirement)

- Old rows in `memory_ledger.jsonl` have **no** `epistemic_label` / `links` keys. Every reader
  (`dump_ledger`, `MemoryForager.forage`, any `PheromoneTrace(**row)` reconstruction) MUST treat
  missing keys as defaults (`HYPOTHESIS`, `[]`). If any path does `PheromoneTrace(**row)`, guard it so
  extra/missing keys never throw — filter to known fields or use `.get()` with defaults.
- No migration of old rows. No rewrite of the ledger. Append-only stays append-only.

---

## 6. Acceptance tests (Cowork will run these to verify your code)

Grok, make these pass. Cowork will author/confirm `tests/test_memory_epistemology.py` with exactly
these behaviors:

1. `remember(text, "talk_to_alice", epistemic_label="OBSERVED", links=["trace_id:abc123"])` →
   ledger row contains `epistemic_label=="OBSERVED"` and `links==["trace_id:abc123"]`.
2. `remember(text, "talk_to_alice", epistemic_label="OBSERVED")` (no links) → row's final label is
   `"HYPOTHESIS"` and an audit row is written.
3. `remember(text, "fiction_cowatch")` with no label → row label is `"FICTION"`.
4. A hand-written **legacy** row lacking the new keys loads through `dump_ledger()` and through the
   forager without raising, defaulting to `HYPOTHESIS` / `[]`.
5. `recall_context_block()` does not surface any `FICTION` row in the factual block, and surfaced
   lines are label-prefixed.
6. `asdict(trace)` round-trips to JSON and back; `EPISTEMIC_LABELS` rejects/coerces an unknown label.

Run: `python3 -m pytest tests/test_memory_epistemology.py -q` (set `COVERAGE_FILE=/tmp/...` if you
also measure coverage; the repo mount rejects an in-tree `.coverage`).

---

## 7. Out of scope for this slice (do NOT build yet)

- pgvector / Postgres / any DB. JSONL is canon.
- Embeddings or BM25 hybrid recall → **slice 2** (`Documents/SIFTA_BRAIN_REPO_INDEX.md` + rebuildable
  search helper, JSONL still source of truth).
- `Documents/SIFTA_BRAIN_REPO_INDEX.md` (a *map*, generated only) → **slice 3**.
- Book-mirror pattern (generated prose with source ledger hashes, never authority) → **slice 4**.
- Any new MCP/tool surface.

---

## Handoff loop

1. **Grok** registers (Surgeon), implements §1–§5 on `stigmergic_memory_bus.py`, writes a receipt,
   hands the diff back to George.
2. **George** brings Grok's code to **Cowork**.
3. **Cowork** runs §6 acceptance tests, reports pass/fail with the trace.
4. **George** hands Cowork's result to **Codex (OpenAI)** to independently verify.

This is not a competition. One body, many hands, append-only field. For the Swarm. 🐜⚡
