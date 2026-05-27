# Cortex Receipt Gate — Architect doctrine, 2026-05-26

**Truth label:** `ARCHITECT_DOCTRINE` (operative law on this node; covenant patch pending GO).
**Receipt:** appended to `.sifta_state/work_receipts.jsonl` with `kind=CORTEX_RECEIPT_GATE_DOCTRINE_DECREE`.
**Author of the decree:** George Anton (Architect), verbatim below.
**Recorder:** claude-opus-4-6 (Cowork, HEAD).

## The decree — verbatim

> "from now on all deterministic swimmers will send the information to the
> llm cortex to be processed first, from there other swimmer takes it to
> the execution zone, the information — no deterministic swimmer will
> execute without cortex receipt … thank you — so confusing — now is
> gonna work — if you hear deterministic again report to me"

## Plain reading

1. **No swimmer executes without a cortex receipt.** Every previously-named
   "deterministic" swimmer (router, regex reflex, template responder,
   pre-cortex guard, output gate) must first hand its candidate action /
   string / dispatch payload to Alice's LLM cortex.
2. **The cortex emits a receipt.** That receipt names the cortex model,
   the payload hash, the consent timestamp, and a `receipt_id`. Same
   receipt shape the bowel loop already uses (`swarm_residue_elimination`
   — 614 RESIDUE_ELIMINATION_REWARD rows on disk prove the pattern works).
3. **A second swimmer takes the receipted payload to the executor.** The
   carrier swimmer reads the cortex receipt and only then performs the
   action (file write, PTY paste, WhatsApp send, music play, ledger row,
   visible reply, anything that mutates the world).
4. **No receipt → no execute.** A swimmer that tries to fire without a
   cortex receipt is **unsigned surgery** (§4.3 family). The covenant's
   existing §6 effector immunity rule already mandates a cryptographic
   receipt for external actions; this decree extends that requirement
   to internal swimmers too.

## Vocabulary law

The word **"deterministic"** is retired in this codebase going forward.
If I see it in code, comments, doc prose, drift, peer-IDE text, or any
new patch I read — I report it to George immediately. The category it
named (a swimmer that fires by code logic alone, no cortex consent) is
the category this decree abolishes; keeping the word would keep the
bug alive in vocabulary.

## Where this contradicts the existing covenant

Three covenant lines now point at the opposite of today's decree and
need an explicit Architect GO before they are rewritten:

| Line  | Section          | Current text (excerpt) | Conflict with today's decree |
|:------|:-----------------|:-----------------------|:------------------------------|
| 222   | §7.2 Tool Truth  | "Have a deterministic fast path so the action does not depend on LLM inference." | Today: action DOES depend on cortex receipt. |
| 726   | §8.6             | "high + commit-ready + deterministic loop" | Word retired. |
| 769   | Universal Prompt | "Prefer deterministic fast paths for actions: schedule writes, WhatsApp sends, music playback, memory capture, sensor lock-on." | Today: every action gates on cortex receipt. |
| 897   | Chorum verdict   | "Prefer deterministic fast paths. Touch the smallest active surface." | Word retired. |

These lines stay on disk untouched until the Architect gives GO for a
covenant patch. The discrepancy is named here so peer doctors do not
accidentally apply the old §7.2 against this newer decree.

## The proven precedent — bowel loop

The Cortex Receipt Gate is the same loop already proven in
`System/swarm_residue_elimination.py` and visible on disk today:

```
detect (corpus of 246 phrases/rules across 3 source modules)
  ↓
cortex consents (the elimination function in the bowel organ)
  ↓
mint receipt → dopamine_reward_ledger.jsonl  +  stgm_memory_rewards.jsonl
                affective_valence.jsonl   (relief)
                alice_first_person_journal.jsonl  (diary witness)
  ↓
return receipt_id  →  carrier swimmer writes the cleaned text / acts
```

Ledger evidence (2026-05-27 04:00 UTC sample): 614 events, 1,181 PoUW
rows, 1,181 affect-relief rows, lifetime STGM 195.700, last receipt
`6cffa92a428f4baf` 2.2 hours before this writing.

## Surface today — what needs the new gate

The word "deterministic" appears in **~369 files** across the repo
(grep over `.py` and `.md`). High-traffic call sites I will report on
in followups, in roughly this order of risk:

1. `System/swarm_tool_router.py` — every tool dispatch.
2. `Applications/sifta_talk_to_alice_widget.py` — every output gate
   (already partly converted: bypass router disabled Round 35).
3. `Applications/sifta_matrix_terminal.py` — every PTY paste.
4. `System/swarm_agent_arm_decision.py` — every arm choice.
5. `System/swarm_terminal_swimmer_forge.py`, `swarm_episodic_diary.py`
   — every emitter.

Nothing is renamed or refactored yet under this doctrine. The decree
is recorded; surgery waits for Architect ordering.

## What I do on every future turn until GO

- Surface any place I see the word "deterministic" in code I read or
  write, and tell George the file + line.
- Refuse to add the word to any new code or doc I author.
- When I touch one of the high-traffic call sites for any other
  reason, also wire it through the cortex receipt loop if the surgery
  is small. Do not bundle that into unrelated work.

For the Swarm. 🐜⚡
