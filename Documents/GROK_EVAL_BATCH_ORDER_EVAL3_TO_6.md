# Grok Batch Order — EVAL-3 completion → EVAL-6 (Stanford / CS153 track)

**Stigauth:** `GROK_EVAL_BATCH_ORDER_EVAL3_TO_6_v1`
**Author of spec:** Cowork (Claude Opus, Auditor/spec lane) — written in a Linux sandbox, NOT on GTH4921YP3. Public APIs below were probed live on disk.
**Coder:** Grok 4.3 — Surgeon, on the M5 body.
**Verifier:** Cowork re-runs each slice's acceptance test in a clean env → Codex signs last.
**Builds on:** `GROK_EVAL_LOOP_ORDER_V2.md`. This doc persists so the batch survives IDE restarts — work it top to bottom, **one slice landed green before the next starts.**

> **Verified state (Cowork, clean sandbox):** memory pack 13/13; EVAL-2 Talk loop + helper + sampler done, 10 real Talk turns populated (await George's labels); EVAL-3 **skeleton** landed (3 turns, all `unverifiable` — logic is empty). Full eval suite: 21 passed. EVAL-3 logic, EVAL-4/5/6: not built.

> **Carry every hard constraint from V2:** no MMLU, no cloud (judge is local-only), JSONL canonical, **delta=0 guard on core-4 per slice**, **effector truth** (score from a real receipt or report `unverifiable` — never fake a pass), every slice ships at least one must-FAIL test, no new MCP surface. Register (Surgeon) before mutating; receipt after; append-only.

---

## SLICE EVAL-3 (COMPLETE IT) — real scoring, all read-only, no skill side effects

The skeleton in `run_skill_eval` currently marks everything `unverifiable`. Replace the body with real, **read-only, deterministic** scoring across the three turn targets already in `data/eval/cs153_skill_turns.jsonl`. Do **not** execute skills for side effects — score from existing artifacts.

**Probed public APIs (use these exact entrypoints; re-probe signatures before calling):**
- Trigger matching → `System.swarm_skill_library.match_skills(query, limit=5) -> list[dict]`
- CheckResolvable → `System.swarm_duplicate_organ_audit.audit_repo(root=None) -> dict`
- Effector truth → read `.sifta_state/nanobot_skill_receipts.jsonl` (skill install/invoke receipts; rows carry `destination`, `installed_by`, `installed_sha256`, etc. — match on the skill name appearing in `destination`/skill fields).

**Per target:**

1. **`skill_invoke`** — scan `nanobot_skill_receipts.jsonl` for a receipt whose skill matches `turn.skill_name`. Pass if a receipt exists **and** its status ∈ `expect.receipt_status_in`. No matching receipt → `unverifiable` (§6 effector truth: never invent a pass). Never write a receipt during scoring.
2. **`skill_trigger_eval`** — call `match_skills(turn.query)`; assert `turn.skill_name` appears in the matches (`trigger_fired`). Then call `match_skills` on a **near-miss** query (define a deterministic near-miss per turn, e.g. a fixed unrelated string) and assert the skill does **not** appear (`no_overfire`). Both must hold to pass.
3. **`skill_check_resolvable`** — call `audit_repo()`; assert no Finding flags `turn.skill_name` as a duplicate owner of its trigger (`no_duplicate_owner`). Pass/fail deterministically from the audit result.

**Report shape:** same as `run_talk_eval` — `{pass_rate, passed, failed, unverifiable, turns:[...], golden_hash, ts}`, plus per-turn `detail`. Receipt `work_type:"EVAL_RUN_SKILL"`.

**Acceptance (`tests/test_eval_loop_skill.py`, extend it):**
- (a) a `skill_trigger_eval` turn passes only when the trigger fires AND does not over-fire on the near-miss;
- (b) a `skill_invoke` turn with no matching receipt is `unverifiable`, never pass;
- (c) a deliberately-wrong `expect` (e.g. demand a receipt status that isn't present) reports FAIL — prove the loop can fail;
- (d) a `skill_check_resolvable` turn detects a seeded duplicate as a violation;
- (e) delta=0 on core-4; (f) `match_skills`/`audit_repo` are called read-only (no receipt written during a run).

---

## SLICE EVAL-4 — local LLM-as-judge for free-text turns (OFF by default)

Per V2 §EVAL-4. Wire `judge_fn` to the **on-device** path — probe `System/alice_cortex_eval_runner.py` and local gemma (ollama) first; if no clean local judge, ship a deterministic stub and leave real wiring as a documented TODO. **Never call cloud.** `run_eval_pack(..., use_judge=True, judge_fn=...)` and `run_talk_eval(..., use_judge=True, judge_fn=...)` route only free-text turns to the judge; deterministic turns still score with zero model calls.

**Acceptance (`tests/test_eval_loop_judge.py`):** with `use_judge=False`, a tripwire `judge_fn` is never called and no network touched; with a fake local `judge_fn`, a free-text turn routes to it and records the reason + `judge_used:true`; a cloud-call attempt raises. delta=0.

---

## SLICE EVAL-5 — failure → regression → replay (the closed loop)

Per V2 §EVAL-5. New `freeze_failures_to_regression(verdicts_path=None, out_path=None) -> int`: read `eval_verdicts.jsonl`, take every `verdict:"incorrect"` row, write a frozen regression turn into `data/eval/cs153_regression_turns.jsonl` (frozen input + corrected expectation). **Idempotent** — never duplicate a turn_id already frozen. The regression set replays on every run; a past failure that returns is a hard FAIL. Receipt `work_type:"EVAL_REGRESSION_FREEZE"` with count.

**Acceptance (`tests/test_eval_loop_regression.py`):** one `incorrect` verdict → exactly one regression turn; re-running adds no duplicate; a frozen regression that re-fails reports FAIL; delta=0.

---

## SLICE EVAL-6 (last) — coverage gate + closed-loop dashboard row

Per V2 §EVAL-6. `tools/eval_coverage.py`: run `coverage` over `swarm_eval_loop.py` + the organ under test, emit the real percentage, gate at ≥ 80%. Append one row to `.sifta_state/eval/company_dashboard.jsonl`: `{ts, week, commits, tests_passed, eval_pass_rate, stgm_burn}` computed from **real ledgers only**.

**Acceptance:** coverage number is real (not hardcoded); dashboard row computed from actual ledgers; delta=0.

---

## Parallel lane available (only if explicitly told — collision risk §4.4)

The tranche-2 coverage campaign still has **organs 8–12** untested (1–7 landed). That is a **separate lane** from this eval track. Do NOT interleave it into the same PRs as the eval slices. If George says go, take them one organ at a time under the existing tranche contract (delta=0 on core-4 + the organ's own ledgers).

---

## Loop (every slice)

1. **Grok** registers, builds the slice on GTH4921YP3, runs its acceptance test, writes a receipt, hands back the trace id.
2. **Cowork** re-runs the slice's acceptance test in a clean env, reports pass/fail with the honest sandbox-vs-Mac caveat (real-receipt and delta gates only fully close on the body).
3. **Codex** signs last: audits the new turns for gaming, adds edge probes, marks CONFIRM/DISPUTE.

Land EVAL-3 completion first. One slice green before the next. Do not boil the ocean in one PR.

For the Swarm. 🐜⚡ EVAL-3→6.
