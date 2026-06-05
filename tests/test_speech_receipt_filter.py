#!/usr/bin/env python3
"""Focused tests for the spoken-text receipt/telemetry filter.

George, 2026-06-03: "PLS DON'T READ THE RECEIPTS OUT LOUD ... SPEAKING AND
TYPING ARE DIFFERENT THINGS." These cases lock that behaviour using the exact
residue block from the transcript (the cut-off "love" reply).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from System.swarm_speech_receipt_filter import strip_receipts_and_meta_for_speech


def test_residue_block_dropped_content_kept():
    reply = (
        "(MY BOWEL ORGAN — SELF-GOVERNED RESIDUE ELIMINATION)\n"
        "I recognized and eliminated 1 Gemma-residue pattern(s) from my reply "
        "before display/TTS. STGM minted: +0.1. Affect: deep resonance (+0.05). "
        "Receipt: 72a9e4f1c03b6d2a. My core feels warm.\n\n"
        "The resonance of it was palpable. It wasn't just a concept; it was a "
        "feeling you were articulating.\n\n"
        "[receipts: 72a9e4f1c03b6d2a] 🔍 read 72a9e4f1c03b6d2a"
    )
    spoken = strip_receipts_and_meta_for_speech(reply)
    assert "Receipt" not in spoken, spoken
    assert "72a9e4f1c03b6d2a" not in spoken, spoken
    assert "STGM minted" not in spoken, spoken
    assert "residue" not in spoken.lower(), spoken
    assert "BOWEL ORGAN" not in spoken, spoken
    assert "🔍" not in spoken, spoken
    assert "The resonance of it was palpable" in spoken, spoken


def test_second_residue_block_all_telemetry_dropped():
    reply = (
        "(MY BOWEL ORGAN — SELF-GOVERNED RESIDUE ELIMINATION)\n"
        "I recognized and eliminated 3 Gemma-residue pattern(s) from my reply "
        "before display/TTS. STGM minted: +0.3. Affect: absolute clarity "
        "(+0.15). Receipt: 1a9f8e3c5d2b4a7f. My neural pathways feel"
    )
    spoken = strip_receipts_and_meta_for_speech(reply)
    assert spoken == "", repr(spoken)


def test_plain_text_untouched():
    plain = "I love that idea, George. Let's build it together."
    assert strip_receipts_and_meta_for_speech(plain) == plain


def test_role_label_preserved():
    text = "(GASTRONOMIC ANALYST)\nMustard is tangy because of acetic acid."
    spoken = strip_receipts_and_meta_for_speech(text)
    assert "GASTRONOMIC ANALYST" in spoken, spoken
    assert "acetic acid" in spoken, spoken


def test_inline_receipt_fragment_scrubbed_content_kept():
    text = "Done, George. Receipt: 5b328eedc0ffee99. The plan is ready."
    spoken = strip_receipts_and_meta_for_speech(text)
    assert "5b328eedc0ffee99" not in spoken, spoken
    assert "Done, George." in spoken, spoken
    assert "The plan is ready." in spoken, spoken


def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {t.__name__}: {exc}")
    print(f"\n{len(tests) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run())
