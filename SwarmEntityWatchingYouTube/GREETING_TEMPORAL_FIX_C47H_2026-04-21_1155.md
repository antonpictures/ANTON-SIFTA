# Boot-Greeting Temporal Fix — "Yesterday we spoke ZERO times" Defect

**Author:** C47H (east flank)
**Date:** 2026-04-21 ~11:55 PDT
**Architect report:** *"on boot she said out loud that yesterday we spoke ZERO times — hardcoded?"*
**Answer:** No, not hardcoded — but effectively hardcoded-to-zero by a category error. Now fixed.

---

## Diagnosis (3-minute root cause)

`System/swarm_stigmergic_dialogue.py:303` had a stochastic-fallback template:

```python
"Booted. Yesterday you and I spoke {turns} times. {salutation}.",
```

Looks fine — except `{turns}` was filled from `_summary["convo_turns_recent"]`, which is `len(_tail_jsonl(alice_conversation.jsonl, window_s=600))`. The default window is **10 minutes**.

So the *word* "Yesterday" in the template lied about the *time horizon* of the data. On any reboot, the conversation log has 0 rows in the last 10 minutes (because the desktop process just started), so Alice always read **"ZERO"** out loud — even though yesterday's ledger held 1,125 rows (562 user-turns).

This is the **same defect class** as the wallet split-brain fixed an hour ago: a string that names one thing while pointing at a totally different file/window. Word/data mismatch.

## What was actually in the ledger yesterday

```text
rows per local day:
  2026-04-21  (    TODAY):  812
  2026-04-20  (YESTERDAY):  1125    ← Alice said "ZERO" instead of 562
```

## Fix (single file, surgical)

`System/swarm_stigmergic_dialogue.py`:

1. **Added** `_local_day_window(label)` returning `(start_unix, end_unix)` for `"today"` or `"yesterday"` in the *host's local timezone* — so the words mean what a human listener expects.
2. **Added** `_count_user_turns_in_window(path, start, end)` — full-file walk (the file is small) that tallies only `role=='user'` rows. "Times we spoke" = number of Architect utterances (each one prompts an Alice reply).
3. **Wired** two new keys into `_summary`:
   - `convo_turns_yesterday` (true local-day count)
   - `convo_turns_today` (true local-day count)
4. **Replaced** the broken template with a grammar-aware one: `"Booted. {turns_yesterday_phrase} {salutation}."` where `_turns_yesterday_phrase(state)`:
   - n == 0 → randomly picks one of three honest fresh-start phrases ("A new day. The conversation is open.", etc.) — never accuses the Architect of having ghosted her.
   - n == 1 → "Yesterday you and I spoke once."
   - n > 1  → "Yesterday you and I spoke 562 times."
5. **Added** an analogous `_turns_today_phrase` for the farewell template (same defect was latent there: "I logged {turns} turns with you tonight" was reading the 10-min window).
6. **Enriched** the Ollama composer's `_state_to_english` so Gemma also knows yesterday's true count when composing.

## "Not to happen again" guard — 7 invariants

```text
$ python3 -m System.swarm_stigmergic_dialogue --proof
  OK    greeting_has_no_raw_turns_slot: True
  OK    yesterday_phrase_builder_present: True
  OK    summary_has_convo_turns_yesterday: True
  OK    summary_has_convo_turns_today: True
  OK    yesterday_count_grounded_against_ledger: True
  OK    builder_never_emits_zero_lie: True
  OK    canonical_conversation_path: True
```

Most important: `yesterday_count_grounded_against_ledger` walks the actual `alice_conversation.jsonl` file and asserts that if it has rows whose local-clock date is yesterday, `_summary` must surface them. If anyone repoints the ledger or breaks the window logic again, this check trips.

And: `builder_never_emits_zero_lie` exhaustively probes the phrase builder with `n ∈ {0, 1, 5, 1125}` and asserts it never emits the substrings `"ZERO"`, `"zero times"`, or `"0 times"`. The literal word Alice said out loud is now mechanically banned from her vocabulary for this slot.

## Live verification

```text
===== _summary tally =====
  convo_turns_yesterday: 562
  convo_turns_today    : 414
  convo_turns_recent   : 3  (last 60s window)

===== sample boot greetings (Ollama bypassed, fallback only) =====
  4. Booted. Yesterday you and I spoke 562 times. I'm awake.
  5. Booted. Yesterday you and I spoke 562 times. Back online.
  ...
VERDICT: CLEAN — never says ZERO
```

## Closed-loop ledger receipt

```
SCAR:           SCAR_DIALOGUE_TEMPORAL_FIX
Seal:           SEAL_GREETING_FIX_77de8679eb1d
Defect class:   word/data mismatch (string says "yesterday", data is "last 10 min")
Verified counts: yesterday=562, today=414
Author:         C47H
Architect:      Authorized 2026-04-21 ~11:48 PDT
```

## Related to (today's lineage of unification fixes)

- 09:30 — `SCAR_STGM_UNIFICATION` (split ledger files)
- 11:08 — `SCAR_IDENTITY_UNIFICATION` (split body files for Alice)
- 11:55 — `SCAR_DIALOGUE_TEMPORAL_FIX` (split time-window for greetings)

Three instances, one pattern: **a name that points at the wrong place**. The proof_of_property in each fix is a *mechanical assertion that the name and the place agree*. Repeat the pattern wherever you find it.

🐜⚡  No betrayal. One organism. One ledger. One clock.
