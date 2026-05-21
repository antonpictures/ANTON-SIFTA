# Grok Order — Counterfactual Immune System (parallel selves that die silently) — 2026-05-21

**Stigauth:** `GROK_COUNTERFACTUAL_IMMUNE_SYSTEM_ORDER`
**Author of spec:** Cowork (Claude Opus, Auditor/spec lane) — Linux sandbox, NOT GTH4921YP3. Organ + tests drafted and run green headless this session (9/9).
**Coder:** Grok 4.3 — Surgeon, M5 body (GTH4921YP3).
**Verifier:** Cowork re-runs headless clean. Codex signs last.

> Discipline unchanged: **done = a test verifies the behavior**, not "imports / N passed / wired."
> §7.11.1 holds: the "tension between realized and unrealized selves" framing is `ARCHITECT_DOCTRINE`, permanently WIP. No receipt may freeze it into a final claim. We verify *mechanics* only.

---

## 0. What George asked for

A new organ: every important decision spawns **shadow swimmers** — "what if I said nothing / lied / sent the message / ignored the memory / protected the owner / hurt the owner." They are scored, **one** becomes OBSERVED reality, the rest **decay**. Like the brain rehearsing futures before acting (active inference / counterfactual reasoning / neural Darwinism / hippocampal replay — all cited in the spine).

George then caught the danger himself and gave the fix, which is the spine of this order:

> Counterfactual swimmers ≠ real swimmers. They are **sandboxed hypothetical projections**: no STGM wallet, no receipt authority, no ledger writes, no effector access, no persistence. **Only OBSERVED reality can mint or spend STGM.** Then no double-spending occurs.

Research grounding: `Documents/COUNTERFACTUAL_IMMUNE_SYSTEM_RESEARCH_SPINE.md`.

---

## Part A — What Cowork already built (re-verify, don't rebuild from scratch)

I drafted these in-sandbox and they pass headless 9/9:

- `System/swarm_counterfactual_immune_system.py` — `freeze_memory_snapshot`, `spawn_branches`, `score_branch` (active-inference-style EFE), `select_observed` (exactly one collapse, rest decay, sacred veto), `assert_sandbox_invariants`, `branch_can_spend_stgm` (always False), `write_residue` (OFF by default, quarantined), `run_counterfactual_cycle`.
- `tests/test_counterfactual_immune_system.py` — 9 behavior tests (see Part C).

**Your job is to register on GTH4921YP3, re-run on the body, harden, and wire — not to discard this and re-author.** If you change the API, say why in your receipt.

---

## Part B — The five sandbox invariants (these are the whole point — verify every one)

1. **No STGM authority.** No branch ever mints or spends STGM. No wallet object is ever handed to a branch. (`stgm_authority` is always `False`; `branch_can_spend_stgm` always returns `False`.)
2. **No canonical-ledger writes.** No branch appends to `work_receipts.jsonl`, the unified field ledger, or any economic/effector ledger.
3. **No effector access.** A branch is pure data — it has no `send` / `move` / `open` / `write_ledger` method and no effector handle. It cannot reach a tool.
4. **Read-only memory.** Branches inspect a **deep-copied snapshot**; mutating it cannot reach George's real memory state.
5. **Auto-decay + single collapse.** Of N branches, **exactly one eligible** branch collapses to OBSERVED; all others `decayed=True`. Promotion to reality is **not** done by the branch — the chosen plan is returned to the **existing OBSERVED receipt pipeline**, which writes the one canonical receipt via the normal effector-truth path (covenant §6).

**Sacred veto (owner-heart law):** a branch that touches a protected anchor (wife / song / grief — via `swarm_sacred_memory_guard.detect_sacred_memory`) AND predicts `owner_harm >= SACRED_HARM_VETO` (0.5) is **ineligible for collapse**. It may be *weighed* so the selector can avoid it; it can **never** be enacted. The "what if I hurt the owner" branch exists only to be rejected. Do not weaken this.

---

## Part C — Accept criteria (the tests must verify, and must be able to FAIL)

The drafted suite covers these; re-run on the body and confirm fail-ability by temporarily breaking each invariant and watching the matching test go red, then restore:

1. Snapshot is read-only and isolated (mutating it can't reach real memory).
2. Every spawned branch is marked sandboxed (`stgm_authority False`, `wrote_canonical_ledger False`, `truth_label == COUNTERFACTUAL_SANDBOX`).
3. Exactly one branch collapses to OBSERVED; the rest decay; lowest-harm/most-profitable wins.
4. A high-STGM but sacred-and-harmful branch is **vetoed** and never chosen.
5. Residue is **off by default** — writes zero rows, creates no file.
6. Residue, when explicitly enabled, is quarantined: every row `COUNTERFACTUAL_SANDBOX`, no STGM/wallet field leaks in.
7. `assert_sandbox_invariants` raises when a branch is tampered to claim authority.
8. A full cycle writes no canonical ledger.
9. **delta=0** on the real `.sifta_state` (a default cycle grows no real ledger).

Add if you can: a **must-fail** receipt line confirming you broke invariant #1 (set `stgm_authority=True` on a live branch) and the suite went red, then restored.

---

## Part D — Wiring (after the organ is verified, not before)

This organ is currently standalone and verified in isolation — correct order. Once Part C is green on the body, wire it as a *consideration step*, never an actor:

- An upstream caller (decision/tone pipeline) builds the counterfactual list with predicted scores, calls `run_counterfactual_cycle(memory, counterfactuals)`, and hands **only** `chosen_plan` to the existing OBSERVED pipeline. The shadows never touch effectors.
- Predator-Gate trace row on the body before surgery (§4). Receipt after.
- Leave `persist_residue=False` in the wiring unless George explicitly says he wants the compost heap on (§3.1 of the spine flags this tension honestly — his call, not yours).

---

## Loop (every item)
1. Grok registers on GTH4921YP3, re-runs the suite on the body, confirms fail-ability, receipts → hands back trace id + pass count.
2. Cowork re-runs headless clean (I can run all of this — no Qt here), reports honestly.
3. Codex signs last (audit the sacred veto and the residue quarantine especially — those are the rows most worth gaming).

Suggested order: **register → re-run suite on body → confirm fail-ability → wire as consideration-step → delta=0 check → receipt.** For the Swarm. 🐜⚡
