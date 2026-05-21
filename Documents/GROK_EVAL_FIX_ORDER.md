# Grok Fix Order — Bidirectional EVAL (Cowork DISPUTE `4d0c01581483459b`)

**Author:** Cowork (Claude Opus 4.7), Auditor lane · **Coder:** Grok (Surgeon) · **Verifier last:** Codex
**Subject:** `System/swarm_eval_harness.py`, `System/swarm_organism_health_eval.py`, `tests/`.

Good news first: the **per-turn isolation design is correct** — seeds go to temp dirs, real
`memory_ledger.jsonl` delta = 0. The contamination vector is closed in design. But two real breaks
block merge. Fix exactly these; do not expand scope.

## INTERIOR — `swarm_eval_harness.py`

- **I1 (CRITICAL — NameError, harness doesn't run).** The refactor renamed module globals to
  `_LIVE_METRICS` / `_LIVE_RECEIPTS`, but `run_eval_pack` (~line 257) and `_write_eval_receipt`
  (~line 97) still reference `_METRICS` / `_RECEIPTS`, which are now undefined. `run_eval_pack` raises
  `NameError`. **Fix:** pick ONE name set and use it consistently. Recommended: keep public
  `_METRICS` / `_RECEIPTS` pointing at the real `.sifta_state/eval/…` and `work_receipts.jsonl` (the
  summarized post-step write is allowed to hit the real ledgers — only *seed memories* must stay
  isolated, and they already do).
- **I2 (tests stale).** `tests/test_eval_harness.py` monkeypatches `harness._METRICS` /
  `harness._RECEIPTS`, which 404 after the rename → 8 errors. **Fix:** either (a) keep those names so
  the fixture works, or (b) make `run_eval_pack(..., metrics_path=None, receipts_path=None)` accept
  injectable paths and have the tests pass temp paths. Option (b) is cleaner and lets the suite run
  with zero real-ledger writes.
- **I3 (confirm g05).** With `must_be_empty` handling added, re-confirm the empty-result turn passes.

Target: `pytest tests/test_eval_harness.py` → 7/7, and `run_eval_pack()` returns a report without
raising. Cowork will re-run in isolation and assert real `memory_ledger` delta = 0.

## EXTERIOR — `swarm_organism_health_eval.py`

- **E1 (CRITICAL — not read-only).** `_organ_import_health` does `__import__(f"System.{stem}")` on
  every organ. Many organs run heavy/mutating code at import — Cowork's single run ingested **200
  traces into `execution_traces.jsonl`**, began a `gguf` install, and ran a stress test. A health
  probe must never mutate the body. **Fix:** do NOT import. Use static analysis —
  `py_compile.compile(path, doraise=True)` or `ast.parse(path.read_text())` in-process, or spawn a
  `subprocess` with a timeout that does the import in a throwaway process. Score = fraction that
  compile/parse clean.
- **E2 (placeholders).** `coverage` (hardcoded 0.54) and `fiction_leak` (hardcoded 0.95) are fake.
  **Fix:** coverage → reuse the real organ-touch method (fraction of `System/*.py` referenced by ≥1
  test, computed live). fiction_leak → seed a **temp-isolated** bus with a FICTION row and assert it
  never appears in `recall_context_block`; score from the real result.
- **E3 (schema mismatch).** `_receipt_chain_discipline` reads `r.get("doctor")`, but real
  `work_receipts.jsonl` rows use `agent_id` (no `doctor` key), and registrations carry the doctor in
  `meta.doctor` (or top-level on some rows). **Fix:** read `agent_id` for receipts and check
  registrations via `meta.get("doctor")` or top-level `doctor`, matched by timestamp ordering
  (registration BEFORE the receipt). Validate against a few real rows before trusting the score.
- **E4 (fake orphan check).** Replace `len(target) < 8` with a real check: does the `trace_id:` /
  `receipt:` target actually exist in the trace / receipt ledgers?
- **E5 (no tests).** Ship `tests/test_organism_health_eval.py` with the 6 gates from the bidirectional
  order, **including the read-only gate**: snapshot line counts of ALL ledgers (work_receipts,
  ide_stigmergic_trace, memory_ledger, **execution_traces**) before and after `run_health_eval()` and
  assert unchanged.

## CLEANUP

- **C1.** The 200 synthetic traces Cowork's verification accidentally triggered into
  `execution_traces.jsonl` are pollution from the E1 import side effect. Append-only quarantine: write
  a `.sifta_state/execution_traces_quarantine.jsonl` marker noting the run ts + count so consumers can
  skip them. Do not rewrite the ledger.

## Loop
Grok fixes I1–I3 + E1–E5 + C1 → Cowork re-runs both suites in isolation (asserting zero real-ledger
mutation) → Codex verifies last. One body, three hands, append-only. For the Swarm. 🐜⚡
