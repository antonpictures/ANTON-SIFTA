# r1733 — Alice hears Romanian again

**Status:** REPAIRED (2026-07-25). Receipt `r1733-stt-language-unlock`.

## George's question

> "she does not understand romanian anylonger from the speech? only english?"

He had already written the answer into her own room ledger at 19:18, in his own
words:

> "now speaking in romanian on speaker w my mom.. translation stt englidsh
> qwrong"

## What was actually wrong

Two cages, not one. Either alone was enough to make Romanian impossible.

1. **The parameter.** Both live ears called faster-whisper with a hardcoded
   `language="en"`:
   - `Applications/sifta_talk_to_alice_widget.py` — the Talk ear
   - `System/swarm_ambient_consciousness.py` — the room ear
2. **The weights.** Her live setting in `.sifta_state/alice_audio_settings.json`
   was `whisper_model: "tiny.en"`. The `.en` suffix means an English-only
   checkpoint. Romanian is not in that model at all, so removing the parameter
   would have changed nothing on its own. Only `faster-whisper-tiny.en` was in
   the model cache; the multilingual `small` the ambient organ asked for had
   never been downloaded.

Result in her ledger, 2026-07-25 19:02, confidence 0.263:

> "the kumos ronati shipo esa as tafo estudat"

That is Romanian forced through English phonetics.

## A correction to the record

An earlier reply in this session claimed "Romanian IS being transcribed
correctly," citing two clean Romanian lines from July 20. That was wrong. Both
rows carry `stt_confidence: 1.0`, which is the typed-text marker in this ledger
— the same value as "Hey Alice, pls defecate the dups in Alice Journal app".
Real STT rows sit between 0.09 and 0.78.

Across 14,921 genuine STT rows there is **no evidence Alice ever transcribed
Romanian speech**. She did not lose the language. The ear she was speaking
through never had it.

## The repair

`System/swarm_stt_language.py` — one place that decides what Alice's ears are
allowed to hear.

- Default is auto-detect. `SIFTA_STT_LANGUAGE` pins a language when the owner
  wants one; `auto`, `none`, `detect` and empty all mean detect.
- An `.en` checkpoint is swapped for its multilingual sibling whenever the owner
  has not pinned English, because no parameter can make it speak Romanian.
- If the multilingual model cannot load, the ear falls back to the configured
  model and says so, rather than trading a working English ear for silence.
- If an English-only checkpoint ends up live anyway, `"en"` is passed honestly
  instead of asking it to auto-detect.
- Every transcription receipts the language Whisper actually detected, with its
  probability, to `.sifta_state/stt_language.jsonl`. The cage cannot return
  quietly.

The multilingual `small` model (464 MB) was downloaded into the venv's cache, so
the fix does not depend on network at the moment George speaks.

## Proof on real audio

Romanian speech synthesised with the macOS `Ioana` voice, run through both paths:

| Path | Output |
| --- | --- |
| Before — `tiny.en`, `language="en"` | `Boonalis, Sunpajorje, Vobeskromoneshtakutinakum, Maemoriata krebui Reparata.` |
| After — resolved to `small`, auto-detect | `Bună Alice, sunt George, vorbesc românește cu tine acum. Memoria ta trebuie reparată.` |

Detected language `ro`, probability 1.00, diacritics intact. The "before" line is
the same failure shape as the live 19:02 row.

Tests: `12 passed` in `tests/test_swarm_stt_language.py`.

## What this does not fix

- The running SIFTA GUI holds the old modules. **Restart SIFTA** before speaking
  Romanian, or the old English lock is still in memory.
- `small` is slower than `tiny.en` on CPU. If the Talk ear feels sluggish, set
  `SIFTA_STT_LANGUAGE=en` to go back to the fast English-only path, or pick a
  different model in the audio settings.
- Voice and television contamination in the ambient lane remains an open defect
  from r1732. Auto-detect does not separate George's voice from a TV; it only
  stops mangling whichever language is being spoken.

For the Swarm. 🐜⚡
