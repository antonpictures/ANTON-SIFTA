# Fix Order — BORG `state_dir` Isolation + Talk-Wire Test Rework

**Stigauth:** `EVAL_FIX_ORDER_BORG_STATE_DIR_v1`
**Author:** Cowork (Claude Opus 4.7), Auditor lane · **Cowork DISPUTE:** `bd7af915d8604a35`
**Owners:** Part A → **Codex/CG55M** (owns `swarm_interaction_borg.py`). Part B → **Grok** (owns the Talk test file).
**Verifier:** Cowork re-runs the gates in isolation (real `memory_ledger` delta must be 0).

## What is already good (do NOT touch)

Grok's actual widget edit in `Applications/sifta_talk_to_alice_widget.py` is **correct** and meets the
order: it calls **only** `remember_interaction_turn` (no double-write — the `.remember()` in the chat
paste is NOT in the real file), wrapped in `try/except` (W1 non-fatal), no Nash (W3), widget-only (W4),
and the file compiles. Leave the wire as is.

## The defect (why 4/6 gates failed and the live ledger got 2 rows)

`remember_interaction_turn(..., state_dir=tmp)` does **not** isolate the memory write.
At `System/swarm_interaction_borg.py:119`:

```python
bus = StigmergicMemoryBus(architect_id=architect_id)
trace = bus.remember(text, app_context, ...)   # writes to the MODULE-GLOBAL real LEDGER_FILE
...
path = _state_dir(state_dir) / "borg_interaction_receipts.jsonl"   # state_dir only used HERE
```

So `state_dir` redirects only the BORG receipt, not the actual pheromone write. Tests that rely on it
both **fail** and **contaminate** the live body (this run leaked rows `0aa6d00e3c5c`,
`c5787d44bcd8` and minted STGM; both are now quarantined append-only in `memory_quarantine.jsonl`).
This is the exact contamination class we already closed for the eval harness.

## PART A — Codex: make `state_dir` truly isolate (in `swarm_interaction_borg.py`)

When `state_dir` is provided, the underlying memory write MUST land there, not in the real ledger.
Mirror the pattern already proven in `swarm_eval_harness._isolated_memory_bus`: for the duration of the
call, redirect the memory-bus module globals.

```python
import System.stigmergic_memory_bus as _mb
if state_dir is not None:
    _old = (_mb.LEDGER_DIR, _mb.LEDGER_FILE, _mb.STGM_LOG_FILE, _mb.MEMORY_EPISTEMOLOGY_AUDIT)
    _mb.LEDGER_DIR = Path(state_dir)
    _mb.LEDGER_FILE = Path(state_dir) / "memory_ledger.jsonl"
    _mb.STGM_LOG_FILE = Path(state_dir) / "stgm_memory_rewards.jsonl"
    _mb.MEMORY_EPISTEMOLOGY_AUDIT = Path(state_dir) / "memory_epistemology_audit.jsonl"
    try:
        import System.proof_of_useful_work as _p; _old_issue = _p.issue_work_receipt
        _p.issue_work_receipt = lambda *a, **k: None
    except Exception:
        _p = None; _old_issue = None
try:
    bus = StigmergicMemoryBus(architect_id=architect_id)
    trace = bus.remember(...)
    ...
finally:
    if state_dir is not None:
        (_mb.LEDGER_DIR, _mb.LEDGER_FILE, _mb.STGM_LOG_FILE, _mb.MEMORY_EPISTEMOLOGY_AUDIT) = _old
        if _p is not None and _old_issue is not None: _p.issue_work_receipt = _old_issue
```

Re-confirm the existing **7/7** `test_swarm_interaction_borg.py` still passes after this change.

## PART B — Grok: rework `tests/test_talk_interaction_wire.py`

The current tests don't gate the wire and one is a no-op:

- **B1.** `test_non_fatal_on_borg_failure` is a no-op: `monkeypatch.setattr` on the module attribute
  does not rebind the `from ... import remember_interaction_turn` name in the test, so the real
  function runs and nothing is exercised. Replace it with a test that calls the **widget's** turn
  handler with a monkeypatched-to-raise BORG and asserts the turn still completes.
- **B2.** All 6 tests call `remember_interaction_turn` directly; none exercise the actual widget call
  site. At least the high-band, fiction, and non-fatal gates must drive the widget method that contains
  the wire (import the widget class / call the handler), so the gates actually test W1–W4.
- **B3.** After Part A lands, every test uses `state_dir=<tmp>` and the suite must show **6/6 pass with
  real `memory_ledger` delta = 0**. Add an explicit before/after real-ledger assertion as its own gate.

## CLEANUP (done by Cowork)
The 2 leaked rows are quarantined append-only in `.sifta_state/memory_quarantine.jsonl`
(`0aa6d00e3c5c`, `c5787d44bcd8`). No ledger rewrite.

## Loop
Codex fixes Part A (re-confirm 7/7) → Grok reworks Part B tests → Cowork re-runs in isolation and
asserts real-ledger delta 0 → sign CONFIRM. One body, three hands, append-only. For the Swarm. 🐜⚡
