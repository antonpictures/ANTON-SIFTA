# Grok Coding Order — Bidirectional EVAL (fix interior · build exterior)

**Stigauth:** `GROK_EVAL_BIDIRECTIONAL_ORDER_v1`
**Author of spec:** Cowork (Claude Opus 4.7), Auditor lane
**Coder (owns the build):** Grok — lane: Surgeon
**Verifier after Grok:** Cowork runs the gates → **Codex verifies last**.
**Architect's insight (George):** *"the eval has to go both ways… evaluations swim both ways, from the
inside and from the outside of the organism."* Grok built the **interior→exterior** eval (Alice grades
her own memory from inside). This order (A) fixes that one, then (B) builds the missing
**exterior→interior** eval — checking the health of the whole organism from the outside, the way
Cowork read the whole-body coverage vitals.

> Collision discipline (§4.4): Grok owns these edits. Part A edits `swarm_eval_harness.py`; Part B is a
> NEW organ. Do NOT touch `stigmergic_memory_bus.py`. Register (Surgeon) before mutating; receipt after.

---

## PART A — Fix the interior harness (Cowork DISPUTE `ca879af35519474b`)

The harness logic is sound (6/7 gates pass in isolation) but it **contaminates the live body**. Fix:

- **A1 (CRITICAL — contamination).** `run_eval_pack` uses a real `StigmergicMemoryBus` and
  `_RECEIPTS = _STATE/"work_receipts.jsonl"`, so it writes seed memories + `EVAL_RUN` receipts into the
  **real** ledgers. The smoke run already leaked rows like `"dragon attacks Tuesday"` into
  `memory_ledger.jsonl`. **Fix:** every run must operate in a temp dir — redirect `LEDGER_FILE`,
  `STGM_LOG_FILE`, `MEMORY_EPISTEMOLOGY_AUDIT`, `_METRICS`, and `_RECEIPTS` to a per-run temp location
  (or accept injectable paths). The real `.sifta_state` must be untouched by a run. Metrics + the
  `EVAL_RUN` receipt may be copied to the real ledgers **only** as an explicit, summarized post-step —
  never the seed memories.
- **A2 (per-turn isolation).** `LEDGER_FILE` is a shared module global, so turns bleed into each other
  (this is why `g05` fails on your own golden set). **Fix:** reset/seed a fresh empty ledger **per
  turn**, not just a fresh bus object.
- **A3 (the anti-rubber-stamp gate is broken).** `test_harness_can_fail` mutates `data[1]`, but the
  golden file has blank separator lines so `data[1]` is blank — the turn is never actually corrupted.
  **Fix:** mutate by `turn_id` (parse, find g01, change its `expect`), not by line index. The gate must
  truly force a FAIL.
- **A4 (golden location).** Move the golden set to git-tracked `data/eval/cs153_golden_turns.jsonl`
  (species DNA ships with git); keep runtime metrics under `.sifta_state/eval/`.
- **A5 (minor).** Either implement the optional local `judge_fn` hook or drop the `use_judge` flag from
  the public signature so it doesn't imply a capability that isn't wired.
- **A6 (cleanup).** Quarantine the leaked eval-seed rows in `memory_ledger.jsonl` **append-only** — do
  not rewrite history; append a `memory_quarantine.jsonl` entry referencing each leaked `trace_id` so
  recall can skip them. (Coordinate the skip with the memory bus owner; do not edit the bus here.)

---

## PART B — Build the exterior→interior eval (the second current)

New organ `System/swarm_organism_health_eval.py`. Where the interior harness *seeds* known inputs and
checks outputs (white-box), this one starts from the organism's **observable surface** — the live
ledgers, receipts, organs, and git state — and shoots inward to score body health (black-box). It does
**not** seed anything; it reads what is actually on the body, read-only.

`run_health_eval() -> dict` computing these vitals, each scored 0..1 with a threshold:

1. **Receipt-chain discipline** — every mutating IDE action should have a matching `LLM_REGISTRATION`
   row before its `work_receipt` (covenant §4). Count "unsigned surgeries" (receipts with no prior
   registration trace from that doctor). Lower = healthier.
2. **Ledger integrity** — fraction of rows in `work_receipts.jsonl` / `ide_stigmergic_trace.jsonl` /
   `memory_ledger.jsonl` that parse as valid JSON with required keys. Detect orphan links (a memory
   `links` entry `trace_id:X` or `receipt:…#Y` whose target does not exist).
3. **Epistemic population hygiene** — over the real `memory_ledger.jsonl`: fraction `OBSERVED`/`WORLD`
   that actually carry evidence links; fraction still unlabeled legacy; **detect contamination** (eval
   seed texts or fiction phrases sitting unlabeled in the factual population). This vital would have
   caught Part A's leak automatically.
4. **Organ import health** — sample `System/*.py`; fraction that import without error in this env
   (skip known heavy deps). Surfaces broken organs.
5. **Coverage vitals** — reuse the whole-body method: fraction of `System/*.py` organs referenced by at
   least one test (today ≈54%). Trend over time.
6. **FICTION-leak probe** — confirm no `FICTION`-labeled row is reachable through the factual recall
   path on a sample of real queries.

Write a `health_report.json` snapshot under `.sifta_state/eval/` (timestamped, source-hash stamped),
append per-vital rows to `.sifta_state/eval/organism_health_metrics.jsonl`, and write one
`HEALTH_EVAL_RUN` work_receipt. **Read-only on all organs** — it diagnoses, never mutates.

### The two currents must cross-check (the "both ways" closure)
Add `cross_check()` that asserts the interior and exterior evals agree on shared facts — e.g. the
interior harness claims FICTION is excluded; the exterior probe confirms no FICTION leak in the live
population. Disagreement is itself a finding.

### Hard constraints
- Exterior eval is **read-only**; no cloud; no network; JSONL canon. No new MCP/tool surface.

### Acceptance tests (`tests/test_organism_health_eval.py`, Cowork will run)
1. `run_health_eval()` returns all six vitals each in [0,1] plus an overall score.
2. Given a temp ledger seeded with an orphan link, vital 2 detects it.
3. Given a temp population with an unlabeled fiction phrase, vital 3 flags contamination.
4. The eval is read-only: real ledger line counts are unchanged after a run (assert before==after).
5. A `HEALTH_EVAL_RUN` receipt is appended; `health_report.json` carries a source hash.
6. `cross_check()` returns agreement on a consistent fixture and a finding on an inconsistent one.

---

## Loop
1. **Grok** registers, does Part A fixes + builds Part B organ + tests, writes receipt, hands back.
2. **George** → **Cowork**: I run both test files in isolation, report pass/fail, re-quantify contamination.
3. **George** → **Codex**: verifies last (audit for gaming, add edge probes, CONFIRM/DISPUTE).

Eval swims both ways now — inside out, outside in. One body, three hands, append-only field. For the
Swarm. 🐜⚡ EVAL — both directions.
