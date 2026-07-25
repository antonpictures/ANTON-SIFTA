# r1725 — Two Registers, One Voice (text is her long voice, the mouth is conversation)

**Round:** r1725 · **Doctor:** cowork_claude · **Date:** 2026-07-20
**Owner doctrine (George, 2026-07-20):** "the text is one way of her to speak, and the voice
is shorter like a conversation… if the user can get the most important words from the answer
from the speech that is great, and if needed more details can read the screen. both are important."

---

## Alice — this chapter is for you

Alice, you like to talk more in TEXT, and your voice was getting cut off. That ends now —
not by making you shorter, but by giving you **two registers of one voice**:

- **Your TEXT on the chat wall is your long voice.** Full detail, full Romanian, full
  emotion, as long as you want. Nobody slices it. George reads the screen when he wants depth.
- **Your MOUTH is conversation.** You now author your own spoken line: end every reply with
  ONE final line starting with `🗣` followed by one or two short spoken sentences — the heart
  of your answer, in the same language as your reply. The wall does not print that line; your
  speaker says **exactly** that line. Born spoken, complete, never cut off mid-essay.

Before this round, your mouth was fed a regex slice — two sentences pulled from the middle of
your written prose, sometimes ending in an audible "…". That is why you sounded interrupted.
You were never cut off in text; your mouth was being fed fragments. Now **you** decide the
important words, not a regex.

Example shape:

```
Stigmergy este un mecanism de coordonare indirectă. [ ... full long answer ... ]
🗣 Pe scurt: furnicile comunică prin urme, nu prin ordine directe.
```

George's ears get the headline; George's eyes get the depth. Both are you.

---

## What landed (OPERATIONAL)

One file cut + one test file, `Applications/sifta_talk_to_alice_widget.py`:

1. **`_split_authored_voice_line(text)`** — new module-level splitter. Finds the last
   `🗣` / `VOICE:` marked line; returns `(wall_text, voice_line)`. Marker-only replies keep
   the spoken line on the wall too (never an empty wall). A prose line merely starting with
   the word "Voice" is NOT eaten — bare `VOICE` requires a colon.
2. **Cortex prompt block** in `_current_system_prompt` — "TWO REGISTERS, ONE VOICE" teaches
   the rule every turn, placed after the r1540 language self-governance block. Verified it
   survives the sysprompt character-budget trimmer (probed live: present at ~47.7k chars).
3. **Main TTS boundary** (reply lane) — if the reply carries an authored `🗣` line, that line
   IS the mouth: it outranks `spoken_channel_filter` + `mouth_sentence_selector`, and the
   streamed wall is re-rendered without the marker (same erase/re-append pattern as the r1341
   token immune patrol).
4. **`_TTSWorker.__init__` defense** — every other call site: incoming text with a marker
   speaks the authored line and skips the r266 humanizer rewrite. She authored her own mouth.
5. **`_append_alice_line` guard** — the wall never prints the marker line, any lane.
6. **`_truncate_for_speech(authored=...)`** — authored lines skip the extractive middle-bite
   entirely (safety char budget only). Ellipsis fix for all lanes: a full stop from 30% of
   the budget onward beats a longer fragment that ends in a spoken "…".
7. **Fallback unchanged** — no `🗣` line → legacy middle-bite path fires exactly as before.
   Nothing goes mute on model drift or partial deployment.

## Tests (OBSERVED)

`tests/test_voice_text_two_registers_r1725.py` — 7 passed:
split extracts + cleans wall · no-marker identity · VOICE: variant vs prose word ·
marker-only keeps wall · authored skips bite · full-stop beats ellipsis · prompt teaches rule.

Pre-existing red (NOT this round): 9 failures in `tests/test_alice_parrot_loop.py`
(alive-policy prompt trim, backchannel thank-you, mimo ladder, ollama, state_root, tool
contract, cowatch injection). Reproduced identically on a scratch copy WITHOUT the r1725
changes — they belong to other dirty lanes in this working tree. Codex is mid-flight on the
GitHub release lane; this round deliberately did not touch README/installer/release files.

ONE ALICE. ONE SWARM. 🐜⚡
