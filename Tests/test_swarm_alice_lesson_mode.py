"""Tests for the deterministic lesson engine.

These pin:
  - The pack loads + exposes all 6 levels.
  - next_cue picks an item and writes a LESSON_CUE row.
  - score_attempt CORRECT on exact + confident heard text.
  - score_attempt CLOSE on near-miss within DL distance 2.
  - score_attempt CLOSE on exact text but low confidence.
  - score_attempt MISS on wrong word.
  - Empty heard text → MISS.
  - Alternates ("kat" for "cat") are accepted as CORRECT.
  - First-person Alice prompts open with the kid's first name.
  - Session stats aggregate verdicts per level.
  - Mocked audio path: feed the engine a string heard_text without
    touching STT.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_alice_lesson_mode import (  # noqa: E402
    CLOSE_DISTANCE_THRESHOLD,
    LESSON_LEDGER,
    LessonEngine,
    LessonItem,
    MIN_CONFIDENCE_CORRECT,
    TRUTH_LABEL,
    _damerau_levenshtein,
    _normalise,
    _score,
    is_lesson_attempt_candidate,
    score_heard_against_expected,
    score_attempt_pure,
)


# ── distance + normalisation ──────────────────────────────────────────────


def test_normalise_strips_punctuation_and_case():
    assert _normalise("Cat!") == "cat"
    assert _normalise("  The   DOG  ") == "the dog"


def test_damerau_levenshtein_basic():
    assert _damerau_levenshtein("cat", "cat") == 0
    assert _damerau_levenshtein("cat", "kat") == 1   # substitution
    assert _damerau_levenshtein("cat", "act") == 1   # transposition
    assert _damerau_levenshtein("cat", "dog") == 3


# ── scorer ────────────────────────────────────────────────────────────────


def test_scorer_correct_on_exact_confident():
    v = score_attempt_pure("cat", "cat", stt_confidence=0.95)
    assert v.label == "CORRECT"
    assert v.distance == 0
    assert v.sticker == "🐝"


def test_scorer_close_on_low_confidence_exact():
    v = score_attempt_pure("cat", "cat", stt_confidence=0.40)
    assert v.label == "CLOSE"
    assert v.distance == 0


def test_scorer_close_on_near_miss():
    v = score_attempt_pure("cat", "kat", stt_confidence=0.90)
    assert v.label == "CLOSE"
    assert 1 <= v.distance <= CLOSE_DISTANCE_THRESHOLD


def test_scorer_miss_on_wrong_word():
    v = score_attempt_pure("cat", "dog", stt_confidence=0.95)
    assert v.label == "MISS"
    assert v.distance > CLOSE_DISTANCE_THRESHOLD


def test_scorer_miss_on_empty_heard():
    v = score_attempt_pure("cat", "", stt_confidence=0.0)
    assert v.label == "MISS"


def test_scorer_alternates_accepted_as_correct():
    v = score_attempt_pure("cat", "kat", stt_confidence=0.90, alternates=["kat"])
    assert v.label == "CORRECT"
    assert v.distance == 0


def test_wordace_bridge_scorer_rejects_letter_inside_noise():
    v = score_heard_against_expected("S", "SABCD", cue_kind="letter", stt_confidence=0.95)
    assert v.label == "MISS"


def test_wordace_bridge_scorer_accepts_letter_sequence_exact():
    v = score_heard_against_expected("ABC", "A B C", cue_kind="letter_sequence", stt_confidence=0.95)
    assert v.label == "CORRECT"


def test_wordace_bridge_scorer_accepts_word_in_phrase():
    v = score_heard_against_expected("cat", "I say cat", cue_kind="word", stt_confidence=0.95)
    assert v.label == "CORRECT"

def test_wordace_bridge_scorer_rejects_wrong_word_in_phrase():
    v = score_heard_against_expected("man", "the cat", cue_kind="word", stt_confidence=0.95)
    assert v.label == "MISS"


def test_wordace_attempt_gate_allows_story_answer():
    assert is_lesson_attempt_candidate(
        "man",
        "the man was thirsty",
        cue_kind="word",
    )


def test_wordace_attempt_gate_releases_doctor_instructions():
    assert not is_lesson_attempt_candidate(
        "man",
        "hey man how are you doing sorry I was just giving instructions to the doctor",
        cue_kind="word",
    )
    assert not is_lesson_attempt_candidate(
        "S",
        "I am talking to Dr Codex about this app",
        cue_kind="letter",
    )


# ── engine round-trip ────────────────────────────────────────────────────


def test_engine_loads_pack_and_lists_levels(tmp_path):
    eng = LessonEngine(state_dir=tmp_path)
    levels = eng.levels()
    assert len(levels) == 6
    assert any(L["id"] == "L1_letters" for L in levels)
    assert next(L for L in levels if L["id"] == "L1_letters")["kind"] == "letter_sequence"
    assert any(L["id"] == "L6_sentences" for L in levels)


def test_engine_next_cue_writes_lesson_cue_row(tmp_path):
    eng = LessonEngine(state_dir=tmp_path, rng=random.Random(0))
    eng.set_level("L2_cvc_short_a")
    cue = eng.next_cue(write=True)
    assert cue["kind"] == "LESSON_CUE"
    assert cue["level_id"] == "L2_cvc_short_a"
    assert cue["expected_say"] in {"cat", "bat", "hat", "mat", "ran", "man", "tan", "can"}
    rows = (tmp_path / LESSON_LEDGER).read_text().splitlines()
    assert any(json.loads(r)["kind"] == "LESSON_CUE" for r in rows)


def test_engine_full_round_trip_correct(tmp_path):
    eng = LessonEngine(state_dir=tmp_path, rng=random.Random(1))
    eng.set_level("L2_cvc_short_a")
    cue = eng.next_cue(write=True)
    expected = cue["expected_say"]
    result = eng.score_attempt(expected, stt_confidence=0.95, write=True)
    assert result["label"] == "CORRECT"
    rows = [json.loads(r) for r in (tmp_path / LESSON_LEDGER).read_text().splitlines() if r.strip()]
    kinds = [r["kind"] for r in rows]
    assert kinds == ["LESSON_CUE", "LESSON_ATTEMPT", "LESSON_VERDICT"]
    # Parent linkage
    cue_trace = next(r["trace_id"] for r in rows if r["kind"] == "LESSON_CUE")
    assert all(r.get("parent_trace_id") == cue_trace
               for r in rows if r["kind"] in {"LESSON_ATTEMPT", "LESSON_VERDICT"})


def test_engine_full_round_trip_miss(tmp_path):
    eng = LessonEngine(state_dir=tmp_path, rng=random.Random(2))
    eng.set_level("L2_cvc_short_a")
    eng.next_cue(write=True)
    result = eng.score_attempt("banana", stt_confidence=0.95, write=True)
    assert result["label"] == "MISS"
    assert result["sticker"] == "🦋"


def test_engine_score_without_cue_returns_no_cue(tmp_path):
    eng = LessonEngine(state_dir=tmp_path)
    eng._current_item = None
    out = eng.score_attempt("cat", stt_confidence=0.95, write=False)
    assert out.get("kind") == "LESSON_VERDICT_NO_CUE"


# ── prompt phrasing ──────────────────────────────────────────────────────


def test_cue_prompt_uses_first_name_and_first_person(tmp_path):
    eng = LessonEngine(state_dir=tmp_path, rng=random.Random(3))
    eng.set_level("L1_letters")
    eng.next_cue(write=False)
    text = eng.cue_prompt_for_alice(owner_name="Acer")
    assert text.startswith("Acer,")
    assert "letters" in text
    # No servant-voice
    for forbidden in ("What's on your mind", "What can I help",
                      "Since you have presented", "as an AI", "the system"):
        assert forbidden not in text


def test_word_cue_uses_meaning_story_not_bare_command(tmp_path):
    eng = LessonEngine(state_dir=tmp_path)
    eng._current_item = LessonItem(
        item_id="man",
        show="man",
        say="man",
        level_id="L2_cvc_short_a",
        level_kind="word",
    )

    text = eng.cue_prompt_for_alice(owner_name="Ace")

    assert text.startswith("Ace,")
    assert "man was walking" in text
    assert "Who was thirsty?" in text
    assert "Read the word on the card: man." in text


def test_verdict_prompt_correct_acknowledges_kid(tmp_path):
    eng = LessonEngine(state_dir=tmp_path, rng=random.Random(4))
    eng.set_level("L2_cvc_short_a")
    cue = eng.next_cue(write=False)
    result = eng.score_attempt(cue["expected_say"], stt_confidence=0.95, write=False)
    text = eng.verdict_prompt_for_alice(result, owner_name="Acer")
    assert "Acer" in text or "perfect" in text.lower() or "exactly" in text.lower()


def test_verdict_prompt_miss_offers_target_to_repeat(tmp_path):
    eng = LessonEngine(state_dir=tmp_path, rng=random.Random(5))
    eng.set_level("L2_cvc_short_a")
    cue = eng.next_cue(write=False)
    result = eng.score_attempt("banana", stt_confidence=0.95, write=False)
    text = eng.verdict_prompt_for_alice(result, owner_name="Acer")
    assert cue["expected_say"] in text


# ── session aggregator ───────────────────────────────────────────────────


def test_session_stats_counts_three_verdict_types(tmp_path):
    eng = LessonEngine(state_dir=tmp_path, rng=random.Random(6))
    eng.set_level("L2_cvc_short_a")

    cue = eng.next_cue(write=True)
    eng.score_attempt(cue["expected_say"], stt_confidence=0.95, write=True)

    cue = eng.next_cue(write=True)
    typo = "k" + cue["expected_say"][1:]
    eng.score_attempt(typo, stt_confidence=0.90, write=True)

    cue = eng.next_cue(write=True)
    eng.score_attempt("totally wrong", stt_confidence=0.95, write=True)

    stats = eng.session_stats()
    assert stats["total_attempts"] == 3
    assert stats["correct"] >= 1
    assert stats["miss"] >= 1
    assert "L2_cvc_short_a" in stats["per_level"]


# ── mocked-audio integration sketch ──────────────────────────────────────


def test_mocked_audio_path_round_trip(tmp_path):
    """Simulate the Talk widget flow without touching the mic.

    Steps:
      1. Engine picks a cue (Decide).
      2. Caller feeds a fake STT transcript + confidence (Execute).
      3. Engine scores + writes both rows (Receipt).
    """
    eng = LessonEngine(state_dir=tmp_path, rng=random.Random(7))
    eng.set_level("L5_sight_words")
    cue = eng.next_cue(write=True)

    # Simulate the STT layer returning the heard text directly.
    fake_stt_text = cue["expected_say"]
    fake_stt_conf = 0.88

    result = eng.score_attempt(fake_stt_text, stt_confidence=fake_stt_conf, write=True)
    assert result["label"] == "CORRECT"

    # Trace ledger has three rows in order
    rows = [json.loads(r) for r in (tmp_path / LESSON_LEDGER).read_text().splitlines() if r.strip()]
    assert [r["kind"] for r in rows] == ["LESSON_CUE", "LESSON_ATTEMPT", "LESSON_VERDICT"]
    # Every row carries the truth label
    for r in rows:
        assert r["truth_label"] == TRUTH_LABEL
