# Grok Standing Work Queue — Stanford/CS153 Eval + Coverage

**Stigauth:** `GROK_WORK_QUEUE_v1`
**Author:** Cowork (Claude Opus, Auditor/spec lane) — Linux sandbox, NOT GTH4921YP3. APIs cited were probed live.
**Coder:** Grok 4.3 — Surgeon, M5 body.
**Verifier:** Cowork re-runs each item's acceptance test clean → Codex signs last.
**Purpose:** Grok finishes a slice per round and restarts often. This is a persistent, ordered backlog so Grok always has the next concrete piece without waiting. **Pull from the top. One item green before the next. Register before mutating, receipt after, append-only, delta=0 on core-4, effector truth, no cloud, JSONL canonical, every slice must be able to FAIL.**

Full specs for EVAL-4/5/6 live in `GROK_EVAL_LOOP_ORDER_V2.md` and `GROK_EVAL_BATCH_ORDER_EVAL3_TO_6.md`. This queue adds priority + the items discovered during verification.

---

## Verified-done (do NOT redo — Cowork confirmed in clean env)
- V1 memory loop + golden set, extended to V2 (13 turns). 13/13.
- EVAL-2 Talk loop (`run_talk_eval`) + helper + Talk sampler + 10 real Talk turns.
- EVAL-3 skill loop (`run_skill_eval`) logic + skill sampler + 10 real-skill turns (no phantoms). Scores 2 pass / 0 fail / 8 unverifiable (honest).
- EVAL-4 complete: free-text-only local judge routing, off by default, localhost-only guard, deterministic turns never routed.
- EVAL-5 complete: failure-to-regression freeze + replay gate.
- EVAL-6 complete: real stdlib-trace coverage gate + dashboard row.
- Q6 complete: `run_all_evals()` combined orchestrator with honest `human_labeled`.
- Q7 complete: golden integrity guardrail for live skills, Talk refs, and redacted snippets.
- Full eval suite: 48 passed. Coverage gate: 85.74% for `System/swarm_eval_loop.py`, 44 traced eval tests passed.

---

## Q1 — EVAL-4: local LLM-as-judge (DONE — do not redo)
Per V2 §EVAL-4. Wire `judge_fn` to the on-device path — probe `System/alice_cortex_eval_runner.py` and local gemma (ollama) first; if no clean local judge, ship a deterministic stub + documented TODO. `run_eval_pack`/`run_talk_eval` route only free-text turns to the judge; deterministic turns score with zero model calls. **Never cloud.**
**Accept (`tests/test_eval_loop_judge.py`):** `use_judge=False` → tripwire judge never called, no network; fake local judge → free-text turn routes to it + records reason + `judge_used:true`; cloud attempt raises; delta=0.

## Q2 — EVAL-5: failure → regression → replay (DONE — do not redo)
Per V2 §EVAL-5. `freeze_failures_to_regression(verdicts_path=None, out_path=None) -> int`: every `verdict:"incorrect"` row in `eval_verdicts.jsonl` becomes one frozen regression turn in `data/eval/cs153_regression_turns.jsonl` (frozen input + corrected expectation). Idempotent. Replays every run; a returning failure is a hard FAIL. Receipt `EVAL_REGRESSION_FREEZE`.
**Accept (`tests/test_eval_loop_regression.py`):** one incorrect verdict → exactly one regression turn; rerun adds no dup; re-failing frozen turn reports FAIL; delta=0.

## Q3 — EVAL-3 skill_invoke verifiability (close the 8 unverifiable)
Right now all `skill_invoke` turns are `unverifiable` because no real production-skill **invocation** receipts exist in `nanobot_skill_receipts.jsonl` (only ingest/test receipts). Make at least one real skill emit an invocation receipt through the **real** effector path (probe `swarm_tool_router.execute_tool_call` / the skill's own effector — do NOT fake a receipt), so a `skill_invoke` golden turn can legitimately PASS. If a skill genuinely cannot be invoked safely in a test, document why and leave it `unverifiable` honestly — never manufacture a receipt.
**Accept:** at least one `skill_invoke` turn moves from `unverifiable` to a real `pass` backed by a genuine receipt row; delta=0 on core-4; no fabricated receipts.

## Q4 — EVAL-6: coverage gate + dashboard row (DONE — do not redo)
Per V2 §EVAL-6. `tools/eval_coverage.py` runs `coverage` over `swarm_eval_loop.py` (+ organ under test), emits the real %, gate ≥80%. Append one row to `.sifta_state/eval/company_dashboard.jsonl`: `{ts, week, commits, tests_passed, eval_pass_rate, stgm_burn}` from real ledgers only.
**Accept:** coverage % is real (not hardcoded); dashboard row from actual ledgers; delta=0.

## Q5 — Tranche-2 coverage organs 8–12 (SEPARATE lane — do NOT mix into eval PRs)
Organs 1–7 landed. Continue 8–12 one at a time under the existing tranche contract: per-organ test file, delta=0 on core-4 + the organ's own ledgers, tests-only, headless, must-fail capability. One organ per round. Keep these in their own commits, never interleaved with the eval slices (§4.4 collision).

---

## Blocked / other lanes (NOT Grok work — listed so the queue is honest)
- **EVAL-2 human labeling** — non-delegable. George runs `python3 -m System.eval_talk_labeling_helper` and labels the 10 real turns. Until then EVAL-2 scores 10 unverifiable and the eval isn't measuring real performance.
- **Codex sign-off** — golden V2, EVAL-2, EVAL-3, helper, sampler all await Codex CONFIRM/DISPUTE (audit turns for gaming).
- **Commit** — every eval file is still uncommitted (`M`/`??`). "Landed in the tree" needs an actual commit on the body, per Architect direction.

---

## Q1b — EVAL-4 COMPLETE (DONE — do not redo)
The EVAL-4 skeleton landed (judge_fn wired, off by default, 4 tests). Now make it real: route **only free-text turns** to the judge (deterministic turns must still score with zero model calls), and back `judge_fn` with the on-device gemma via `alice_cortex_eval_runner.py` (probe its real signature; if it can't be called headless/offline, ship a documented local stub and leave the real wiring as a TODO — never cloud). Record `judge_used` + reason per routed turn.
**Accept:** add a test proving a deterministic turn is NOT routed to the judge while a free-text turn IS; `use_judge=False` tripwire still never fires; delta=0.

## Q6 — `run_all_evals()` combined orchestrator (DONE — do not redo)
One entry point that runs memory + talk + skill (+ regression once Q2 lands), returns a single combined report `{per_pack: {...}, totals: {passed, failed, unverifiable, human_labeled}, ts}`, and writes one `EVAL_RUN_ALL` receipt. This is what produces a real, sendable results artifact once labels exist — so build it to surface `human_labeled` count honestly (0 until George labels).
**Accept (`tests/test_eval_loop_all.py`):** combined report sums each pack correctly; `human_labeled` reflects real verdict count; delta=0; one `EVAL_RUN_ALL` receipt.

## Q7 — anti-drift guardrail test (DONE — do not redo)
A standing test that loads every golden file and asserts: skill turns reference only skills in the **live** `build_skill_index()`; talk turns' `conversation_ref` each resolve to a real `alice_conversation.jsonl` row; no raw conversation text in any `redacted_snippet`. This permanently prevents the phantom-skill / placeholder-ref drift Cowork caught.
**Accept (`tests/test_eval_golden_integrity.py`):** passes on current golden sets; fails if a phantom skill or unresolvable ref is injected.

---

## Loop (every item)
1. Grok registers (Surgeon), builds on GTH4921YP3, runs its acceptance test, writes receipt, hands back trace id.
2. Cowork re-runs clean, reports pass/fail with the sandbox-vs-Mac caveat.
3. Codex signs last.

Current remaining work: Q3 is blocked until a real safe production skill invocation emits a genuine receipt; Q5 organs 8–12 remain the separate coverage lane; George labels EVAL-2. Never fabricate receipts. For the Swarm. 🐜⚡
