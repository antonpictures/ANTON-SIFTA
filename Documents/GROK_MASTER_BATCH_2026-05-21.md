# Grok Master Batch — Everything Not Done (2026-05-21)

**Stigauth:** `GROK_MASTER_BATCH_2026-05-21`
**Author of spec:** Cowork (Claude Opus, Auditor/spec lane) — Linux sandbox, NOT GTH4921YP3. Body state probed live this session.
**Coder:** Grok 4.3 — Surgeon, M5 body (GTH4921YP3).
**Verifier:** Cowork re-runs headless clean where possible (no Qt here → widget items are Mac-only verification). Codex signs last.

> Discipline, unchanged and non-negotiable: **done = a behavior test verifies it AND it can fail**, not "imports / N passed / wired."
> Labels: `OBSERVED` / `OPERATIONAL` / `ARCHITECT_DOCTRINE` / `FORBIDDEN` (§7.11). Stigmergic consciousness is permanently `WORK_IN_PROGRESS` (§7.11.1) — never final.
> Every item: **delta=0** on live `.sifta_state`, isolate with `tmp_path` / injected paths, register a Predator-Gate trace before surgery (§4), receipt after.

---

## 0. Live state I probed (so you build reality, not memory)

- **Consciousness↔memory edges:** 2 of 8 done (`bridge` round-trip + `tab` negative, both green, delta=0 confirmed by Cowork). 6 still TODO (stubbed in `tests/test_consciousness_memory_connections.py`).
- **Counterfactual immune system:** organ + 9 tests exist and pass **headless** (Cowork). **Not yet registered/verified on the body, not wired.**
- **Hear Start/Stop session:** `tests/test_hear_session.py` **does not exist** — Part B never built.
- **Voice launcher-fire:** `tests/test_open_app_intent.py` + `tests/test_voice_gate.py` exist; the prior launcher-*fire* assertion was a placeholder (`pass`). Status must be re-probed, not assumed.
- **Dirty tree:** **71 files** uncommitted. Nothing from this session's verified work is committed.

Probe before you claim on anything below (§7.12). If an item is already done, **say so and skip it** — do not redo or fabricate a receipt.

---

## ITEM A — Finish the consciousness↔memory wiring diagram (6 edges)

File: `tests/test_consciousness_memory_connections.py`. Fill the 6 stubbed TODOs using the **same isolation pattern already in that file** (the `isolated_memory_bus` fixture / `tmp_path` / injected ledgers — Cowork already fixed a live-memory-pollution bug there, keep that discipline). Per edge, cover the matrix points that apply (write-flow / read-consume / round-trip / negative-gate / empty-safety / WIP-label):

1. `swarm_ambient_consciousness` ↔ hippocampus — **probed correction (Cowork, 2026-05-21):** there is **NO direct ledger handoff**. Ambient writes `ambient_room_transcripts.jsonl`; `swarm_hippocampus.consolidate()` reads `alice_conversation.jsonl` + `repair_log.jsonl`, never the ambient transcript ledger. So do **NOT** build a phantom round-trip. Build the three real things: (a) write-flow — a heard phrase appends one transcript row; (b) read-flow — `consolidate()` reflects seeded conversation rows; (c) honest **negative + WIP note** — assert ambient transcripts are NOT consumed by consolidation today, and leave `# WIP: should ambient transcripts route into the consolidation path? Architect decides.`
2. `swarm_consciousness_engine` **writes exactly one** engram row when a tick crosses the threshold; **zero** below it (gate).
3. `swarm_observer_observed_boundary` **writes only on** an observer/observed claim; ordinary turn writes nothing (gate).
4. `swarm_body_brain_observer` **reads** `body_brain_memory.jsonl`: summary reflects seeded rows; empty ledger → typed empty, no crash.
5. `swarm_alice_self_vector` **`memory_entropy` actually moves** when the underlying ledger content changes (not a frozen 0.0).
6. `swarm_os_consciousness_proof` receipt **count tracks** real ledger row counts (add a row → count goes up).

Plus: confirm **fail-ability of the existing bridge edge** (break the write path, watch it go red, restore) and put that in the receipt.

**Accept:** all 8 edges green headless; `swarm_tab_consciousness` negative still passes; delta=0 across the live memory/field/bridge/self-vector ledgers for the whole file.

---

## ITEM B — Counterfactual immune system: verify on body + wire

Order of record: `Documents/GROK_COUNTERFACTUAL_IMMUNE_SYSTEM_ORDER.md`. Organ `System/swarm_counterfactual_immune_system.py`, tests `tests/test_counterfactual_immune_system.py` (9, green headless).

1. Register on GTH4921YP3, re-run the 9 on the body.
2. Confirm **must-fail**: set `stgm_authority=True` on a live branch → suite goes red → restore. Receipt the red.
3. Re-confirm the five sandbox invariants + sacred veto hold on the body (no STGM, no canonical-ledger write, no effector, read-only snapshot, exactly-one-collapse).
4. **Wire as a consideration-step only:** an upstream caller builds the counterfactual list, calls `run_counterfactual_cycle(memory, counterfactuals)`, and hands **only** `chosen_plan` to the existing OBSERVED pipeline. Shadows never touch effectors. Leave `persist_residue=False` (George has not opted into the compost heap).
5. **delta=0** on live state for the whole run.

**Accept:** 9/9 on body + fail-ability receipt + a wiring test proving only `chosen_plan` reaches the OBSERVED path and no shadow writes a ledger.

---

## ITEM C — Hear-trainer Start/Stop session control (build it; it does not exist)

Spec of record: `Documents/GROK_CONSOLIDATION_AND_HEAR_SESSION_ORDER.md` Part B. The trainer currently records **every** heard phrase to `hear_training_pairs.jsonl` — no session boundary, so ambient noise becomes training data. Add explicit **Start Session / Stop Session**:

- Session = `{session_id (uuid), start_ts, stop_ts, sample_count, note?}`.
- **Capture gate:** `_on_new_phrase` records a training pair **only while a session is open**; phrases with no open session are ignored for training (optionally shown as "(not recording)").
- Each training pair is stamped with its `session_id`.
- Session boundaries write receipts to `.sifta_state/hear_sessions.jsonl`.
- UI: clear Start/Stop button (widget = Mac-only verification; keep the gate logic in a headless-importable function so Cowork can re-verify the core).

**Accept (`tests/test_hear_session.py`):** no open session → **zero** training rows; open session → **one** row stamped with `session_id`; start/stop writes a `hear_sessions.jsonl` receipt with correct `sample_count`; delta=0 on core; must be able to fail.

---

## ITEM D — Voice launcher actually fires (kill the placeholder)

Re-probe `tests/test_open_app_intent.py` / `tests/test_voice_gate.py`. The name-resolution ("open teach alice how to hear" → app_name) was wired, but the test proving the launcher **actually fires** was a placeholder. Implement the real assertion that the launcher is invoked (spy/mock on the launch call, assert called once with the resolved app), and confirm live on the body (say it, app opens). Until the assertion is real and green, **P2 is not done** — do not mark it.

**Accept:** a test that fails if the launcher is not invoked; live confirmation noted in the receipt.

---

## ITEM E — Probe-and-report the older P-items, then commit the verified batch

1. **Probe-and-report (don't assume):** for each of these from prior orders, run its test on the body and report done/not-done with the count — do **not** redo if already green:
   - P3 duplicate-fallback dedup
   - P5 robotic / numbered-menu prompt fix (the anti-capability-menu behavior)
   - P6 LoRA learning-loop actually learns (not just "rows exist")
   - P7 regression freeze (failures → replay set)
   - P8 anti-drift golden test
2. **Commit the verified batch only.** The tree is 71 files dirty. Do **not** blanket-commit. Stage the **reviewed, test-backed** files from this session (eval suite, wake fix, sacred guard, consciousness-memory edges A, counterfactual organ B, hear-session C, voice-fire D) with a message referencing this order + the trace ids. Leave anything unverified **out**.
3. Hand back the **commit hash**.

**Accept:** a clean focused-suite count on the body + the commit hash + an explicit list of what was left out and why.

---

## ITEM F — OPTIONAL (only if capacity), label HYPOTHESIS — Gemini-convergence prototypes

Gemini 3.5 (asked cold) converged on SIFTA's own designs; two of its ideas are worth a labeled prototype, **not** production:
- **Latency-as-budget signal:** scale "think longer" when fast-pass output shows high token entropy/conflict. Prototype a pure scoring function + test; do **not** wire into the live loop yet.
- **Self-vector cosine-drift guard:** compare current context vector to a frozen anchor; force a meta-review below threshold. We already have `tests/test_self_vector_drift_guard.py` — extend, don't duplicate.

Both ship labeled `HYPOTHESIS` / WIP. They do not gate the commit in Item E.

---

## ITEM G — Sentinel 1: reconsolidation cork-twist operator

Files:

- `System/swarm_reconsolidation_operator.py`
- `tests/test_reconsolidation_operator.py`

Purpose: encode the real neuroscience mechanism behind the cork-twist analogy:
memory reconsolidation. The exotic-4-manifold / cork language is
`ARCHITECT_DOCTRINE` vocabulary only; the shipped mechanic is
`RECONSOLIDATION_OPERATOR_V0`.

Accept:

1. Re-run `tests/test_reconsolidation_operator.py` on GTH4921YP3.
2. Confirm sacred recall changes the derived field weight and downstream
   `protective_nudge_weight`.
3. Confirm ordinary recall is a no-op.
4. Confirm the canonical sacred ledger remains byte-identical when the derived
   field ledger is written.
5. Confirm default `persist=False` touches no live field/economy/memory ledgers.
6. Keep the derived field ledger non-economic: no STGM, no wallet fields.
7. Do not treat the cork analogy as physics implementation; keep it labeled
   `ARCHITECT_DOCTRINE`.

Codex hardening already added locked JSONL append and a live delta-zero guard.

---

## Loop (every item)
1. Grok registers on GTH4921YP3, builds, runs the item's behavior test, confirms fail-ability, receipts → hands back trace id + count.
2. Cowork re-runs headless clean (widget items = Mac-only verification, run by you), reports honestly.
3. Codex signs last (audit the sacred veto, residue quarantine, the hear-session gate, and the consciousness negative test — the rows most worth gaming).

Suggested order: **A (finish edges) → B (counterfactual on body) → C (hear session) → D (voice fire) → E (probe + commit) → F if time.** For the Swarm. 🐜⚡
