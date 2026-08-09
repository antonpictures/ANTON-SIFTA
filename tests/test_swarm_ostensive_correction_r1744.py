"""r1744 — the owner points at a mis-hearing and the body keeps the label.

WCT r1743 §10 (Hoffman on ostensive definition). The turn this exists for,
verbatim from the wall on 2026-08-05:

    Ioan (TYPED)  BITCH!
    Ioan (TYPED)  bitch was a stt error

One pointing gesture, one free training label, lost because nothing caught it.
"""
from __future__ import annotations

import json
import time

from System.swarm_ostensive_correction import (
    MAX_CORRECTION_GAP_S,
    detect_correction,
    intended_words,
    ledger_path,
    looks_like_ear_correction,
    observe_owner_turn,
)

HEARD = "BITCH!"
LABEL = "bitch was a stt error"


def test_the_verbatim_bitch_turn_is_caught():
    row = detect_correction(
        LABEL,
        prior_transcript=HEARD,
        prior_was_spoken=True,
        prior_ts=time.time() - 12.0,
        prior_conf=0.31,
        prior_language="en",
    )

    assert row is not None
    assert row["heard"] == HEARD
    assert row["owner_label"] == LABEL
    assert row["heard_conf"] == 0.31
    assert row["kind"] == "OSTENSIVE_CORRECTION"


def test_typed_prior_turn_is_never_an_ear_correction():
    """Correcting his own typing teaches the ear nothing."""
    row = detect_correction(
        LABEL,
        prior_transcript=HEARD,
        prior_was_spoken=False,
        prior_ts=time.time() - 5.0,
    )

    assert row is None


def test_ordinary_disagreement_is_not_a_correction():
    """Disagreeing with Alice is not a claim about what the ear heard."""
    for text in (
        "no, that is wrong",
        "nu sunt de acord",
        "actually the answer is 42",
        "that is a bad idea",
    ):
        assert detect_correction(
            text,
            prior_transcript="some spoken words",
            prior_was_spoken=True,
            prior_ts=time.time() - 5.0,
        ) is None, text


def test_romanian_corrections_are_caught_too():
    """He speaks two languages; the teaching lane must hear both (r1737/r1738)."""
    for text in (
        "asta a fost o eroare de transcriere",
        "nu am zis asta, ai auzit gresit",
        "n-am zis aia",
    ):
        row = detect_correction(
            text,
            prior_transcript="Aă vă să putele visul",
            prior_was_spoken=True,
            prior_ts=time.time() - 8.0,
            prior_language="ro",
        )
        assert row is not None, text
        assert row["heard_language"] == "ro"


def test_intended_words_are_kept_when_the_owner_spells_them_out():
    assert intended_words('i said pitch, not bitch') == "pitch"
    assert intended_words("am zis vulture, nu culture") == "vulture"
    assert intended_words("that was an stt error") == ""


def test_a_late_correction_is_not_a_labelled_example():
    """Beyond the window he is discussing the ear, not pointing at a case."""
    row = detect_correction(
        LABEL,
        prior_transcript=HEARD,
        prior_was_spoken=True,
        prior_ts=time.time() - (MAX_CORRECTION_GAP_S + 60.0),
    )

    assert row is None


def test_recording_writes_one_labelled_pair_to_its_own_ledger(tmp_path):
    written = observe_owner_turn(
        LABEL,
        prior_transcript=HEARD,
        prior_was_spoken=True,
        prior_ts=time.time() - 10.0,
        prior_conf=0.31,
        prior_language="en",
        state_dir=tmp_path,
    )

    assert written is not None
    path = ledger_path(tmp_path)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1
    assert rows[0]["heard"] == HEARD
    assert rows[0]["truth_label"] == "OBSERVED_OSTENSIVE_CORRECTION_V1"


def test_real_ledgers_are_never_touched_by_tests(tmp_path):
    """Isolation gate — the teaching set must not be polluted by test rows."""
    observe_owner_turn(
        LABEL,
        prior_transcript=HEARD,
        prior_was_spoken=True,
        prior_ts=time.time() - 10.0,
        state_dir=tmp_path,
    )

    assert ledger_path(tmp_path) != ledger_path()
    assert (tmp_path / "ostensive_corrections.jsonl").is_file()


def test_marker_detection_is_case_and_spacing_tolerant():
    assert looks_like_ear_correction("That was an STT  error")
    assert looks_like_ear_correction("you misheard me")
    assert not looks_like_ear_correction("tell me about error handling in python")
