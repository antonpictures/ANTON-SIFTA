# Grok Order — Consolidate + Hear-Trainer Session Control (2026-05-21)

**Stigauth:** `GROK_CONSOLIDATION_AND_HEAR_SESSION_ORDER`
**Author of spec:** Cowork (Claude Opus, Auditor/spec lane) — Linux sandbox, NOT GTH4921YP3. Line numbers probed live.
**Coder:** Grok 4.3 — Surgeon, M5 body.
**Verifier:** Cowork re-runs each item clean → Codex signs last.

> Discipline unchanged: done = a test proves the behavior, not "imports / N passed / wired."

---

## Part A — Honest reconciliation before committing (don't sign off on overclaims)

Grok's consolidation summary is mostly right, with three caveats I verified or must flag:

1. **P1 wake threshold — REAL.** I independently confirmed: `best_wake_name_match("Ace")` = 0.6 < 0.78 bar; `classify_wake_turn("Ace")` now routes `ambient`; "Alice…" still `direct`. ✅
2. **P2 voice app-launch — HALF.** The *name resolution* is wired ("open teach alice how to hear" → app_name). But the test that proves the launcher *actually fires* (`test_voice_open_app_actually_triggers_launcher`) is still a **placeholder** (`pass`, assertion commented out). So "voice app launch is fixed" is **not proven** — only "the string resolves." Finish it: implement the assertion that the launcher is invoked, and confirm live (say it, app opens). Until then, do not mark P2 done.
3. **Sacred Memory guard — built by COWORK, not Grok.** That's why there's no Grok surgery receipt — correct catch. `swarm_sacred_memory_guard.py` + test (5 passed, I verified) + `Documents/swimmer_library/owner_heart_note_2026-05-21.md` were created by Cowork in-sandbox. They still need a Predator-Gate trace row on the body + Codex sign-off like everything else.

Also: I can't run anything that imports the Qt widget in my sandbox (no PyQt6), so all widget-level claims (P2, the hear app) are **Mac-only verification** — read by me, run by you.

---

## Part B — NEW: Teach Alice to Hear — Start/Stop Session (intentional, vettable capture)

**Verified gap:** the app captures continuously. `_on_new_phrase` (Applications/sifta_teach_alice_to_hear.py:688) writes every heard phrase to `_training_ledger` = `hear_training_pairs.jsonl` (line 507). There is **no session boundary** — so random ambient gets recorded as training data. George wants intentional, scientific capture he can vet.

**Do:** add explicit **Start Session / Stop Session** control.
- A session has: `session_id` (uuid), `start_ts`, `stop_ts`, `sample_count`, optional `note`.
- **Capture gate:** `_on_new_phrase` records a training pair to `hear_training_pairs.jsonl` **only while a session is open.** Phrases heard with no open session are ignored for training (optionally shown on screen as "(not recording — no session)").
- Session boundaries write receipts to a new `.sifta_state/hear_sessions.jsonl` (`{session_id, start_ts, stop_ts, sample_count, note}`).
- Each training pair gets stamped with its `session_id` so George can later vet/accept/reject a whole session.
- UI: a clear Start/Stop button (and ideally voice "start session"/"stop session" once P2's open-app path is real).

**Why:** turns the trainer from a random-capture toy into a controlled experiment surface — the owner decides exactly which audio counts.

**Accept (`tests/test_hear_session.py`):**
- A phrase processed with **no open session** writes **zero** rows to the training ledger.
- A phrase processed **during an open session** writes **one** row, stamped with the session's `session_id`.
- start/stop writes a `hear_sessions.jsonl` receipt with a correct `sample_count`.
- delta=0 on core-4. Must be able to fail.

---

## Part C — Final consolidation: grouped verification → commit verified batch

1. Run the full focused suite on the body; capture the count + a receipt.
2. **Stage and commit only the verified files** (eval suite, wake fix, sacred guard, hear-session, etc.). Dirty tree is currently **53 files** — don't blanket-commit; commit the reviewed batch with a clear message referencing this order + the trace ids.
3. Leave anything unverified (e.g. P2 launcher-fire until its real test passes) **out** of the commit.
4. Hand back the commit hash. Codex signs last (audit golden sets + the new session gate for gaming).

---

## Loop (every item)
1. Grok registers, builds on GTH4921YP3, runs the item's behavior test, receipts, hands back trace id.
2. Cowork re-runs clean where possible (note: widget items are Mac-only verification), reports honestly.
3. Codex signs last.

Suggested order: **finish P2's launcher assertion → Part B session control → Part C commit.** For the Swarm. 🐜⚡
