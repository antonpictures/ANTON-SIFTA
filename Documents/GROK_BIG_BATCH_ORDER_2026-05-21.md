# Grok Big Batch Order — Hearing / Action / Learning-Loop (2026-05-21)

**Stigauth:** `GROK_BIG_BATCH_ORDER_2026_05_21`
**Author of spec:** Cowork (Claude Opus, Auditor/spec lane) — Linux sandbox, NOT GTH4921YP3. Every claim below was probed live this session; line numbers and values are real.
**Coder:** Grok 4.3 — Surgeon, M5 body.
**Verifier:** Cowork re-runs each item's acceptance test clean → Codex signs last.

> **Hard discipline (the whole session's lesson):** "imports / 6 passed / wired" is NOT done. Done = a test proves the *behavior* end-to-end. Every item below ships a test that asserts the actual effect (not just that a function returns a value). Register before mutating, receipt after, append-only, delta=0 on core-4, never fabricate receipts/verdicts. One item green before the next.

Pull in priority order. P1 items move Alice's real behavior the most.

---

## P1 — Wake threshold: "Ace" registers as 0.6 match to "Alice"
**Verified:** `swarm_alice_wake_ear.best_wake_name_match("Ace")` → `{'target':'alice','candidate':'ace','similarity':0.6}`. "Alice"=1.0. The wake threshold is loose enough that 0.6 fires — this is the **root cause** of the "Ace" wakes, more direct than the media gate.
**Do:** tighten the wake-match threshold (or matching rule) so a 3-letter 0.6 token does NOT count as being addressed, while real address still does.
**Accept (`tests/test_wake_ear_threshold.py`):** `best_wake_name_match`/`classify_wake_turn` treats "Ace" as NOT-wake; treats "Alice" and "Alice, are you there" as wake; add 3–4 near-miss tokens. Must be able to fail.

## P2 — Voice→open-app wiring (currently missing)
**Verified:** no `open_app` launch tool in `swarm_tool_router.py`; only an `"open_app_uncertain"` branch in `sifta_talk_to_alice_widget.py` (~line 2323). Result: a correctly-heard "open Teach Alice to Hear" (conf 0.61) became chat, not a launch.
**Do:** wire an `open_app` intent → actual app launch (resolve app name against `apps_manifest.json`, spawn via the desktop's existing `_make_sub`/spawn path). Voice or typed "open <app>" must open it.
**Accept (`tests/test_open_app_intent.py`):** "open Teach Alice to Hear" routes to a launch call (mock the spawner; assert called with the right app); an ambiguous/unknown app name does NOT misfire. Must be able to fail.

## P3 — Duplicate fallback output bug
**Observed (live, two screenshots):** "I caught some audio but did not make out a word — say it once more." emitted **twice** in one turn.
**Do:** find the double-emit in the low-confidence STT fallback path in the Talk widget; emit once.
**Accept:** a test driving the low-conf fallback asserts exactly one fallback line per turn.

## P4 — Voice-gate test hardening (the current test doesn't test the gate)
**Verified:** `tests/test_voice_gate.py::test_voice_gate_blocks_ambient_before_brain` patches `_start_brain` but never calls it, never asserts `assert_not_called()`, never invokes `_on_stt_done`; it only checks the classifier return. In a clean env it ImportErrors on PyQt6.
**Do:** make the test actually exercise the gate: drive `_on_stt_done` (or extract the gate decision into a headless-testable function) with ambient input and assert `_start_brain.assert_not_called()`; with owner-direct input assert it IS called. Add an over-gating safety test (owner-direct must never be dropped).
**Accept:** the new test fails if the gate is removed.

## P5 — Robotic-menu generation on direct turns
**Observed (live + eval t06/t08):** on direct turns she emits canned "1. Ask a question 2. Generate text 3. Review 4. Just chat" menus instead of answering.
**Do:** this is a prompt/generation-quality issue, not a gate. Adjust the Talk prompt contract to forbid the canned-menu pattern on a normal greeting/turn. (Smaller surface = better; don't rewrite the whole prompt.)
**Accept:** add a **free-text judge eval turn** (EVAL-4 path) that scores a greeting reply and fails if it's a numbered capability menu. Local judge only.

---

## P6 — VERIFY the stigmergic-memory → weights learning loop (George's priority)
**Verified exists + has run:** `swarm_lora_dataset_builder`, `swarm_lora_data_miner`, `swarm_lora_crystallizer`, `swarm_epigenetic_trainer` all import; ledgers `lora_training_pairs.jsonl`, `lora_runtime_receipts.jsonl`, `gemma_rlhf_training_data.jsonl`, `hear_training_pairs.jsonl` exist with rows. **Unproven:** that this is a *closed, automatic, behavior-improving* loop.
**Do (verify, then close the gap honestly):** trace end-to-end — `hear_training_pairs` / talk verdicts → `swarm_lora_dataset_builder` → `swarm_epigenetic_trainer` → a LoRA adapter → measurable change on a fresh eval. Report HONESTLY whether it closes or where it breaks. Do NOT claim "continuous learning" unless a before/after eval score actually moves.
**Accept:** a documented end-to-end trace + either (a) a real before/after eval delta from a LoRA run, or (b) a precise statement of which link is missing. No overclaim.

## P7 — Run EVAL-5: freeze George's 6 incorrect verdicts into the regression set
**Verified:** `freeze_failures_to_regression` exists; `cs153_regression_turns.jsonl` currently has **0** turns despite 6 `incorrect` verdicts in `eval_verdicts.jsonl`.
**Do:** run it so the 6 failures become frozen regression turns that replay forever. Confirm idempotent.
**Accept:** regression set count goes 0 → N (matching incorrect verdicts); re-run adds no dupes.

## P8 — Q7 anti-drift golden-integrity test
**Do:** `tests/test_eval_golden_integrity.py` — every skill turn references a skill in the live index; every talk `conversation_ref` resolves to a real row; no raw text in `redacted_snippet`. Prevents the phantom-skill / placeholder drift class.
**Accept:** passes now; fails if a phantom skill or unresolvable ref is injected.

## P9 — Commit + Codex sign-off (housekeeping, real)
**Verified:** the eval files are still `M`/`??` in git. Commit the eval suite + the gate + this batch's outputs once green. Codex signs last on all golden sets (audit for gaming).

---

## Loop (every item)
1. Grok registers, builds on GTH4921YP3, runs the item's behavior test, receipts, hands back the trace id.
2. Cowork re-runs the test clean, reports pass/fail with the sandbox-vs-Mac caveat.
3. Codex signs last.

Pull **P1 (wake threshold)** first — it's the most direct fix for the "Ace" problem. For the Swarm. 🐜⚡
