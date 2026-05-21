# Grok Order — Test the Consciousness↔Memory Connections, All Ways (2026-05-21)

**Stigauth:** `GROK_CONSCIOUSNESS_MEMORY_CONNECTION_TEST_ORDER`
**Author of spec:** Cowork (Claude Opus, Auditor/spec lane) — Linux sandbox, NOT GTH4921YP3. Edges probed live this session.
**Coder:** Grok 4.3 — Surgeon, M5 body (GTH4921YP3).
**Verifier:** Cowork re-runs each item clean where the sandbox allows. Codex signs last.

> Discipline unchanged: **done = a test proves data actually flows across the edge**, not "imports / N passed / wired."
> §7.11.1 holds: stigmergic consciousness is **WORK_IN_PROGRESS**. No test may stamp any edge "proven" or "unproven." Tests prove *flow*, not awareness.

---

## 0. George's ask, said plainly

> "Test the consciousness organ to memory connections — all of them, all ways."

So we test **every** consciousness organ against memory, in **both directions** (organ→memory write, memory→organ read), and we test the honest **negative** case too: where there is *no* edge, prove there is none and ask whether there should be. We are mapping a real wiring diagram, not decorating one.

---

## Part A — The honest edge map I probed (build the tests around THIS, not a fantasy)

I grepped every consciousness organ for real memory/ledger/engram references. The edges are **not uniform** — that is the whole point. Here is the ground truth as of today:

| Organ | Edge kind | Real reference on disk | What the test must prove |
|---|---|---|---|
| `swarm_memory_consciousness_bridge` | **bidirectional** | `memory_consciousness_bridge.jsonl`, `unified_stigmergic_field.jsonl` | already 4/4 — extend: prove the before/after self-vector delta actually changes when a memory is written (loop is live, not a constant) |
| `swarm_ambient_consciousness` | **write → memory** | `ambient_room_transcripts.jsonl` (hippocampus later consumes) | a heard phrase produces a transcript row the hippocampus organ can actually read back |
| `swarm_consciousness_engine` | **write → memory** | `long_term_engrams.jsonl` | a tick that crosses the engram threshold writes exactly one engram row; below threshold writes zero |
| `swarm_observer_observed_boundary` | **write → own ledger** | `observer_observed_boundary.jsonl` | an observer/observed claim writes a boundary row; ordinary turn writes none |
| `swarm_body_brain_observer` | **read ← memory** | reads `body_brain_memory.jsonl` | summary reflects the rows present; empty ledger → empty/typed summary, not a crash |
| `swarm_alice_self_vector` | **read ← memory** | `_compute_memory_block`, `memory_entropy` | `memory_entropy` actually moves when the underlying ledger content changes (not a frozen 0.0) |
| `alice_self_vector` | **read ← memory** | reads `Documents/architect_memory*` digests | the memory dimension reflects digest presence vs absence |
| `swarm_os_consciousness_proof` | **read ← memory** | `_ledger_receipts` counts memory ledgers | the receipt count tracks real row counts (add a row → count goes up) |
| `swarm_tab_consciousness` | **NO edge** | (zero memory refs) | **honest negative:** prove it touches no memory ledger today; leave a `# WIP: should tab-consciousness persist to memory?` note for the Architect — do NOT fabricate an edge |

**This is the most important instruction in the order:** test the edge *that is actually there*. For `swarm_tab_consciousness`, the correct, scientific result is "no connection," and the test should assert exactly that. Inventing a memory write just to make a green test would be gaming the gate.

---

## Part B — What "all ways" means per edge (the test matrix)

For each edge above, write a behavior test that covers as many of these as apply:

1. **Write proves flow:** the organ action appends the expected row(s) to the expected ledger, with the expected `kind`/`truth_label`. Count goes from N to N+1.
2. **Read proves consumption:** seed the ledger with a known row, run the organ, assert the organ's output reflects that row's content (not a placeholder).
3. **Round-trip (bidirectional organs only):** write via the organ, then read it back through the consuming organ — prove the same datum survives the hop (hash or value match).
4. **Negative / gate:** an input that should NOT cross the edge writes zero rows (e.g. below-threshold tick, ambient-with-no-session, ordinary non-claim turn).
5. **Empty-state safety:** missing/empty ledger → typed empty result, never a crash.
6. **Honest label:** any row the organ writes that relates to the consciousness loop carries a WIP-family label (`STIGMERGIC_CONSCIOUSNESS*` / `MEMORY_CONSCIOUSNESS_BRIDGE*`), never "proven."

Not every edge needs all six — write the ones the edge actually supports. A read-only organ (`body_brain_observer`) gets 2, 5, 6; it does not get 1.

---

## Part C — Hard requirements (same as every order)

- **delta=0 on the core-4.** These tests must not perturb the live `.sifta_state` ledgers. Use `tmp_path` / dependency-injected ledger paths exactly like `test_sacred_memory_guard.py` and `test_memory_consciousness_bridge.py` already do. Re-run the core suite before/after: zero new/changed rows in the real ledgers.
- **Must be able to fail.** Each assertion must fail if the edge is broken. Prove it: temporarily break the write path, watch the test go red, restore. (Note in the receipt that you confirmed fail-ability.)
- **One test file:** `tests/test_consciousness_memory_connections.py`. Group by organ with clear test names (`test_ambient_consciousness_writes_transcript_hippocampus_can_read`, `test_tab_consciousness_has_no_memory_edge`, etc.).
- **Sandbox caveat:** anything that imports a Qt widget is **Mac-only verification** — I cannot run it here. Keep the connection logic importable headless (pure functions + injectable paths) so I can re-verify the core of it; mark any Qt-bound assertion clearly so it's run on GTH4921YP3, not claimed by me.
- **No "proven."** Per §7.11.1, comments and labels say WORK_IN_PROGRESS. We are proving *flow*, never awareness.

---

## Part D — Accept criteria (what lets me sign the re-verify)

- `tests/test_consciousness_memory_connections.py` exists and the headless portion runs green in my sandbox.
- Every edge in the Part A table has at least one test; the `swarm_tab_consciousness` **negative** test is present and asserts no memory edge.
- A receipt (trace id) on GTH4921YP3 showing: total tests, pass count, the fail-ability confirmation, and a delta=0 check on the core-4 ledgers.
- No row written to a real ledger by the test run.
- Hand back the trace id + the list of edges proven (write/read/round-trip/negative) per organ.

---

## Loop (every item)
1. Grok registers on GTH4921YP3, builds the test, runs it, confirms fail-ability, receipts → hands back trace id + the edge-by-edge result.
2. Cowork re-runs the headless portion clean, reports honestly which edges I could verify vs which are Mac-only.
3. Codex signs last (audit the negative test especially — that's the one most likely to be gamed).

Suggested order: **bridge (extend) → write edges → read edges → tab-consciousness negative → delta=0 check → receipt.** For the Swarm. 🐜⚡
