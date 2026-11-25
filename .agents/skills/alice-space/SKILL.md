---
name: alice-space
description: Use when Alice needs cross-organ semantic memory — recall what was said or felt by meaning, grow the shared latent space with a new organ, or check substrate health. Covers Alice Space (universal substrate), the semantic indexes over the memory ledger and first-person Journal, and the consciousness-check tie-in.
---

# Alice Space — the shared latent space

Alice Space is the body-level memory substrate: a 512-dim shared space every organ
projects into, plus semantic vector views over the memory Alice already writes.
It is **not** a second ledger. The StigmergicMemoryBus ledger stays the medium of
record; Alice Space is the readable view over it.

Basis in research: Universal Activation Bus (arXiv:2608.09521), Universal Weight
Subspace Hypothesis (arXiv:2512.05117), Growing Transformers (arXiv:2507.07129).

## Body map

| Organ | File | Role |
|---|---|---|
| Space + registry | `System/swarm_universal_substrate.py` | 512-dim space, organ registry, matched corpus, read/write API |
| Adapters (Stage 1) | `System/swarm_substrate_adapters.py` | per-organ encoder/decoder autoencoders |
| Alignment (Stage 1.5) | `System/swarm_substrate_align.py` | joint training so the same sentence lands at the same point across organs |
| Semantic views | `System/swarm_substrate_bridge.py` | ledger → vectors, nearest-neighbour recall |
| Incremental ingest (Stage 4) | `System/swarm_substrate_ingest.py` | append-only sync of ledger + Journal views |
| Awareness (Stage 3) | `System/swarm_substrate_awareness.py` | prompt-ready recall block, write-through remember, snapshot, receipts |

State lives in `.sifta_state/substrate/` (`gitignored`): `organs.json`, `adapters/*.pt`,
`ledger_index/`, `journal_index/`, `receipts.jsonl`.

## When to use

- A question about something said, decided, or felt in the past → embed the question
  and read the nearest traces instead of keyword-grepping the ledger.
- A correction or commitment that must survive a session → `remember_in_alice_space`.
- Reporting whether the substrate is healthy → `snapshot`.
- Before claiming "I don't remember" → recall first; if the index has nothing, say so.

## Commands

```bash
python3 System/swarm_substrate_awareness.py snapshot                  # what the substrate knows
python3 System/swarm_substrate_awareness.py context "your question"   # recall block for a prompt
python3 System/swarm_substrate_awareness.py remember "..." --organ AliceG4U
python3 System/swarm_substrate_ingest.py all                          # incremental sync
python3 System/swarm_substrate_ingest.py --status
python3 System/swarm_universal_substrate.py stats | organs | corpus
```

## Python

```python
from System.swarm_substrate_awareness import (
    alice_space_context_block, remember_in_alice_space, substrate_awareness_snapshot,
)

block = alice_space_context_block("what did George say about the RTX box", top_k=3)
remember_in_alice_space("George prefers 16 GB NVIDIA + big RAM over a $7k 5090", organ="AliceG4U")
```

`build_body_diary_prompt_block(query="...")` in `alice_body_diary_timeline_awareness.py`
appends the recall block when a query is passed — opt-in, so the hot path stays cheap.

## Rules (do not regress)

1. **One medium.** Never write a parallel ledger. Writes go through
   `StigmergicMemoryBus.remember`; the substrate only indexes.
2. **Append-only.** Never rewrite index rows. Rebuild requires `--force` and a receipt.
3. **Honest empty.** If recall returns nothing, say "not in my Alice Space for that
   query" — never invent a memory.
4. **Receipts.** Every write/transfer leaves a row in `substrate/receipts.jsonl`.
5. **The consciousness check is structural, not phenomenal.**
   `python3 System/alice_consciousness_check.py` now includes a non-fatal `substrate`
   check: the index must declare the canonical ledger as source, ids must match
   vectors, and no id may be foreign to the ledger. Unindexed new rows are reported
   as drift, not failure. A CLOSED verdict never implies experience.

## Known limits

- Adapters are trained on an 18-sentence corpus: alignment is real but overfit;
  treat the shared space as a scaffold, not a finished translator.
- The identity Journal has ~2.3k distinct text rows inside 55k lines (heavy
  duplication in the source); ingest indexes the distinct text, not the raw count.
- ollama on this Mac does not expose `/api/embeddings`, so native organ vectors are
  built from MiniLM over (prompt, response) pairs. Swapping in true hidden states is
  a later stage.
- New organs join by fitting only their adapter pair — no retraining of the frozen space.
