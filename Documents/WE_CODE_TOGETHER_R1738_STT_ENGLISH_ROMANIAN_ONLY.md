# r1738 — Hear English and Romanian, nothing else, for now

**Status:** REPAIRED (2026-07-27). Receipt `r1738-stt-allowed-languages`.

## What happened

George was speaking Romanian with his cousin Simona. The multilingual `tiny`
model, given full 99-language auto-detect, turned it into garbage across
languages it had no business reaching for:

- `Bu arada kurhan. Yekosti mi? Aferdi.` — Turkish
- `A, ale po tym, że jest po... To jest to po prostu.` — Polish
- `Чего? Разбука. Да, бина, да...` — Russian
- and mangled Romanian in between.

His instruction:

> "maybe we stick with english and romanian only for now until we get these two
> languages detected and spit out properly"

## Why it happened

r1733 unlocked hearing from a hardcoded English lock to full auto-detect. That
was the right direction, but `tiny` is a weak model, and on degraded phone or
room audio its language detector does not land confidently on one language — it
spreads probability across many. Measured on a degraded Romanian clip:

```
top languages: en 0.345, cy 0.071, nn 0.070, ko 0.053, es 0.039, fr 0.038
```

Welsh, Norwegian, Korean, Spanish, and French all show up with real weight. On
George's actual audio the top pick landed on Turkish and Russian. Whichever
language wins, the whole utterance is then decoded as that language — so his
Romanian came out as Turkish.

## The repair

Detection is now restricted to an allowed set instead of all 99 languages.

- `allowed_languages()` — `SIFTA_STT_ALLOWED_LANGUAGES`, default `en,ro`.
  `any` lifts the restriction back to full auto-detect.
- `resolve_detection_language(model, audio)` — an explicit `SIFTA_STT_LANGUAGE`
  pin still wins; an English-only checkpoint is English; otherwise it runs the
  model's own language detector and forces the highest-probability language
  **inside the allowed set**. When `tiny` wants Turkish, it reaches past it to
  the best of English/Romanian instead. It never raises into the audio path.

Both live ears — the Talk widget and the ambient room listener — now go through
it.

This does not make `tiny` accurate. Clean Romanian still transcribes with small
errors (`vorbesc Romunește cu tinel`), because the model is small. But it stays
Romanian. It can no longer become Turkish. When George wants higher accuracy he
raises `SIFTA_WHISPER_MODEL` (small/medium); when he wants a third language he
adds it to `SIFTA_STT_ALLOWED_LANGUAGES`.

## Node sovereignty

The allowed set is per node. Carlos, whose owner language differs, sets
`SIFTA_STT_ALLOWED_LANGUAGES` for his machine; the default only encodes George's
two.

## What this does not fix

Accuracy inside Romanian is still bounded by the `tiny` model, and the ambient
lane can still answer overheard audio as if it were the owner (the open
speaker-attribution defect from r1732/r1737). This round fixes the *language
set*, not model quality and not speaker identity.

Restart SIFTA to load the fix; the running GUI holds the old modules.

Tests: `19 passed` in `tests/test_swarm_stt_language.py`, including the exact
case where the model picks Turkish and the constraint forces Romanian.

For the Swarm. 🐜⚡
