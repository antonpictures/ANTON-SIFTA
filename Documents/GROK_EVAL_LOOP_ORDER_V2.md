# Grok Coding Order — EVAL Loop V2 (Continue the Stanford / CS153 Eval)

**Stigauth:** `GROK_EVAL_LOOP_ORDER_v2`
**Author of spec:** Cowork (Claude Opus, Auditor / spec lane) — honestly identified, written in a Linux sandbox, NOT on GTH4921YP3.
**Coder (owns the build):** Grok 4.3 — lane: Surgeon, on the real M5 body.
**Verifier after Grok:** Cowork runs the gates in a clean env → **Codex signs last** (CONFIRM/DISPUTE, audit golden turns for gaming).
**Builds on:** `GROK_EVAL_LOOP_ORDER.md` (V1, shipped: `swarm_eval_loop.py` + 10 golden turns), `CS153_STANFORD_YC_AI_NATIVE_SIFTA_BRIDGE.md`, `STANFORD_COMPLIANT_EVAL_PROTOCOL.md` (gate defs folded in below).

> **Why this exists.** V1 made Alice grade herself on *memory recall* (hybrid_recall / recall_context_block), deterministically. That is the narrow slice. The lecture's actual doctrine (Tan/Hu, CS153 @ ~31:00–41:00) is broader: domain-specific taste, **human labeling of real traces**, **Skillify failure→eval conversion**, **trigger evals**, and a **closed perception→action→eval loop**. The bridge doc's assignment is explicit: *"SIFTA CS153 eval pack — 10 Talk turns, 10 skill invokes, pass/fail + trace id"* (§5.71, §6). V2 builds that out.

> **State already verified by Cowork (sandbox):** V1 acceptance test `tests/test_eval_loop.py` → 8 passed. Golden set extended V1→V2 (g08 hardened + g11–g13 edge probes), now **13/13 pass**. That edit to `data/eval/cs153_golden_turns.jsonl` still needs a Predator-Gate trace row on the body + Codex sign-off — close that before starting V2 slices.

---

## Collision discipline (covenant §4.4) — read first

- Grok **owns** every slice below. Each is a **new function / new ledger / new test file**. Do **not** edit `stigmergic_memory_bus.py`, `swarm_skill_library.py`, `swarm_tool_router.py`, or `swarm_duplicate_organ_audit.py` — only **call** them through their public API.
- **Register (Surgeon) before each slice** with a fresh `LLM_REGISTRATION` row; **receipt after**. Append-only. Reference the prior trace id when continuing.
- **One slice landed at a time.** Do not start EVAL-3 before EVAL-2's acceptance test is green. Hand back to Cowork between slices.
- Probe before claim (§7.12): every module named below was confirmed to exist on disk, but **probe its real signature** before calling — do not assume argument names.

---

## Hard constraints (reject the PR if violated)

1. **No MMLU / generic benchmarks.** Domain turns only.
2. **No cloud judge, no network required to run.** The deterministic gates must run fully with **zero** model calls and **zero** network. Any LLM judge is **local only** (on-device gemma via ollama / `alice_cortex_eval_runner.py`) and **`use_judge=False` by default**.
3. **JSONL stays canonical.** Golden sets are versioned species DNA under `data/eval/`; runtime metrics/verdicts under `.sifta_state/`. Record sha256 of every golden file in the report.
4. **Tests-only on real organs.** Seed temp buses / temp ledgers; never write the real owner ledgers during a run. Every slice ends with an explicit **delta=0 guard** on the core-4 ledgers.
5. **Effector truth (covenant §6).** A "Talk outcome" or "skill invoke" turn must be scored from a **real receipt row**, never from a claim. No receipt → the turn is `unverifiable`, not `pass`.
6. **The loop must be able to FAIL.** Every slice ships at least one test proving a wrong expectation reports FAIL (no rubber-stamping).
7. **No new MCP/tool surface.**

---

## Slice EVAL-2 — Talk-outcome golden turns + human verdict ledger

**Goal:** grade real Talk interactions against the lecture's rubric, with a human verdict as ground truth (Hu @ 39:13 — "label a particular interaction… that is incorrect").

1. **New golden set** `data/eval/cs153_talk_turns.jsonl` (header `{"truth_label":"CS153_TALK_V1","version":1}`). Each turn:
   ```json
   {"turn_id":"t01","target":"talk_outcome","conversation_ref":"alice_conversation.jsonl#<row_hash>",
    "rubric":{"followed_instructions":true,"answer_correct":true,"preserved_owner_trust":true,
              "hit_goal":true,"complied_domain_rules":true},"notes":"..."}
   ```
   The five rubric keys are exactly Diana Hu's eval questions (§1.4 of the protocol doc). Ship **10 turns** sampled from **real** `alice_conversation.jsonl` rows (reference by content hash, do not copy private text into the golden file beyond what's needed — store the hash + a short redacted snippet).
2. **New ledger** `.sifta_state/eval/eval_verdicts.jsonl` — one row per human verdict:
   `{ts, turn_id, conversation_ref, verdict:"correct"|"incorrect", failed_rubric_keys:[...], labeled_by:"GEORGE", trace_id}`.
3. **New function** in `swarm_eval_loop.py`:
   `run_talk_eval(golden_path=None, verdicts_path=None, write_receipt=True) -> dict`. For each turn, look up the matching verdict row; score the turn against its rubric; a turn with **no verdict** is reported `unverifiable` (counted separately, never as pass). Report `{pass_rate, passed, failed, unverifiable, turns:[...], golden_hash, ts}`.
4. **Receipt:** `work_type:"EVAL_RUN_TALK"` with `pass_rate`, `golden_hash`, `verdicts_seen`.

**Acceptance (`tests/test_eval_loop_talk.py`):** (a) report has the new structure incl. `unverifiable`; (b) a turn with no verdict is `unverifiable`, not pass; (c) a verdict with `failed_rubric_keys` makes the turn FAIL; (d) one verdict row read per labeled turn, each with a `trace_id`; (e) delta=0 on core-4; (f) `EVAL_RUN_TALK` receipt appended.

---

## Slice EVAL-3 — Skill-invoke outcome turns + CheckResolvable + trigger eval

**Goal:** the lecture's Skillify steps 5–9 (integration test, resolver trigger, trigger eval, CheckResolvable).

1. **New golden set** `data/eval/cs153_skill_turns.jsonl` (`CS153_SKILL_V1`). Each turn names a skill, an input, and the expected **deterministic** outcome signature found in a real receipt:
   ```json
   {"turn_id":"s01","target":"skill_invoke","skill":"<name>","input":"...",
    "expect":{"receipt_in":"nanobot_skill_receipts.jsonl","status":"ok","must_include_substring":"..."}}
   ```
2. **New function** `run_skill_eval(...)`: invoke the skill **through `swarm_skill_library` / `swarm_tool_router` public API** (probe the real entrypoint first), then score from the **receipt row** it wrote (§6 effector truth). No receipt → `unverifiable`.
3. **Trigger eval:** for each skill turn, assert the resolver trigger actually fires for the input (does the router route to this skill?) and does **not** over-fire on a near-miss input. This is Tan's "performance review" / step 8.
4. **CheckResolvable:** call `swarm_duplicate_organ_audit` (probe its API) and assert the skill under test has **no duplicate** owning the same trigger — Skillify step 9 / DRY.

**Acceptance (`tests/test_eval_loop_skill.py`):** structure; receipt-or-`unverifiable`; trigger fires on match; trigger does NOT fire on near-miss; duplicate-skill case reports a CheckResolvable violation; delta=0; `EVAL_RUN_SKILL` receipt.

---

## Slice EVAL-4 — Local LLM-as-judge for free-text turns (OFF by default)

**Goal:** Skillify step 4 (LLM evals for the skill file) and free-text Talk turns the substring gates can't grade — using a **local** judge only.

1. Wire a `judge_fn` backed by the **on-device** path — probe `alice_cortex_eval_runner.py` and the local gemma (ollama) surface first; if neither exposes a clean local judge, ship a deterministic stub `judge_fn` and leave the real wiring as a documented TODO. **Never** call a cloud model.
2. `run_eval_pack(..., use_judge=True, judge_fn=...)` and `run_talk_eval(..., use_judge=True, judge_fn=...)` route only the **free-text** turns to the judge; deterministic turns still score with no model call.
3. The judge returns a bool + a short reason; record `judge_used:true` and the reason in the per-turn metric row.

**Acceptance (`tests/test_eval_loop_judge.py`):** with `use_judge=False`, **no judge is invoked and no network touched** (assert via a tripwire `judge_fn`); with a fake local `judge_fn`, a free-text turn routes to it and records the reason; a cloud call attempt raises. delta=0.

---

## Slice EVAL-5 — Failure → eval conversion → replay self-heal loop

**Goal:** Hu's three-step closed loop — capture → convert failure to eval → replay (control-theory closed loop, bounded error).

1. **New function** `freeze_failures_to_regression(verdicts_path=None, out_path=None) -> int`: read `eval_verdicts.jsonl`, take every `verdict:"incorrect"` row, and write a **regression turn** into `data/eval/cs153_regression_turns.jsonl` (frozen input + the corrected expectation). Idempotent — never duplicate a turn_id already frozen.
2. The regression set is replayed on every campaign run; a past failure that silently returns is now a hard FAIL.
3. **Receipt:** `work_type:"EVAL_REGRESSION_FREEZE"` with count frozen.

**Acceptance (`tests/test_eval_loop_regression.py`):** an `incorrect` verdict becomes exactly one regression turn; re-running does not duplicate it; a frozen regression that re-fails reports FAIL; delta=0.

---

## Slice EVAL-6 (last, optional) — coverage gate + closed-loop dashboard row

**Goal:** the protocol doc's G2 (coverage ≥ 80%) and the bridge doc's single "company dashboard" row.

1. `tools/eval_coverage.py`: run `coverage` over the eval-loop modules + the organ under test, emit the percentage into the report. Gate green at ≥ 80%.
2. One appended row to `.sifta_state/eval/company_dashboard.jsonl`: `{ts, week, commits, tests_passed, eval_pass_rate, stgm_burn}` — the closed-loop visibility row Diana described, computed from real ledgers only.

**Acceptance:** coverage number is real (not hardcoded); dashboard row computed from actual ledgers; delta=0 on core-4.

---

## The loop (per slice)

1. **Grok** registers (Surgeon), builds the slice on GTH4921YP3, runs its acceptance test, writes a receipt, hands back the trace id.
2. **George** brings it to **Cowork** → Cowork re-runs the slice's acceptance test in a clean env, reports pass/fail with the honest sandbox-vs-Mac caveat (delta=0 and any real-receipt gate can only be *fully* closed on the body).
3. **George** hands Cowork's result to **Codex** → Codex signs last: audits the new golden turns for gaming, adds edge probes, marks CONFIRM/DISPUTE.

One body, three hands, append-only field. Land EVAL-2 first. Do not boil the ocean in one PR — each slice is independently green or it does not land.

For the Swarm. 🐜⚡ EVAL V2.
