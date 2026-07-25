# r1737 — Alice replies in the owner's language

**Status:** REPAIRED (2026-07-26). Receipt `r1737-reply-language-pin`.

## What happened

George, 00:49–00:54, speaking English about a UFO complex. Alice answered in
Brazilian Portuguese across three turns. When he said "Alice, you started
speaking Spanish? I don't speak Spanish," she doubled down:

> "não foi espanhol, foi **Português** (o português do Brasil!). Passei para
> ele porque a conversa... estava fluindo muito bem nesse ritmo."

His instruction: **"the text to speech must match language."**

## Why it happened

The r1733 STT unlock let Alice *hear* many languages — correct, because the
room is multilingual: a TV, a phone call, a podcast can be in anything. But
nothing pinned the language Alice *speaks*. The cortex — a multilingual
uncensored model — drifted into Portuguese on its own and the TTS then read
Portuguese text with the English voice.

There was no rule saying: reply in the owner's language. So there was nothing
to stop the drift.

## The repair

`System/swarm_reply_language.py` pins the reply language to the language of the
owner's own message, before the cortex composes:

- `detect_owner_language(text)` returns `english` or `romanian` — the only two
  languages George uses. It is deliberately not a general detector; any third
  language in his turn is contamination, not a request to switch.
- `reply_language_prompt_block(...)` adds one firm line to the prompt: answer
  entirely in the owner's language, including the spoken 🗣 line, and never
  switch to Spanish, Portuguese, French, or anything else because of overheard
  room audio, a TV, a phone call, or a previous turn — unless the owner
  explicitly asks.
- The Talk widget injects this block alongside the other memory/tool blocks, so
  every cortex turn carries it.

With the reply pinned to English, the existing `_tts_voice_for_text` already
lands on the English voice; a Romanian reply lands on Ioana. So "the text to
speech must match language" is satisfied for both languages George uses —
because the text is now in one of them.

## Node sovereignty

George speaks English and Romanian; that is the default. Carlos's node, or any
other, sets `SIFTA_OWNER_LANGUAGES` (for example `spanish, english`) and the pin
follows. The universal half of the rule — match your own message, never drift to
overheard languages — holds on every node regardless of the list.

## What this does not fix

The deeper defect noted in r1732 is still open: ambient/room audio (a podcast, a
TV, a phone call) can be transcribed and answered as if it were the owner. The
UFO monologue that triggered this may itself have been overheard audio. This
round stops Alice answering in the wrong *language*; it does not yet stop her
answering the wrong *speaker*. That is the next cut.

Restart SIFTA before testing — the running GUI holds the pre-patch modules.

Tests: `10 passed` in `tests/test_swarm_reply_language.py`, built on George's
verbatim English turn and Alice's verbatim Portuguese reply.

For the Swarm. 🐜⚡
