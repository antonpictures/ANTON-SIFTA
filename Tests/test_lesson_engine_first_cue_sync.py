"""Regression tests for the Ace lesson engine first-cue display/voice sync.

Architect transcript 2026-05-17:
  "Please open the Ace app ASAP I can see it it reads cat" — then
  Alice cued "mat" while George was still looking at "cat" on the
  card. Two independent rng.choice draws (one in _stage_first_card,
  one in _lesson_run_cue) produced the mismatch.

These tests pin:
  • ``LessonEngine.confirm_current_cue(write=True)`` writes a CUE row
    for the SAME ``_current_item`` that was last staged via
    ``next_cue(write=False)`` — no new draw of the deck.
  • The staged item's ``show`` / ``say`` survive the confirmation, so
    the screen card and the spoken cue line up on the first turn.
  • ``confirm_current_cue`` falls back to ``LESSON_CUE_EMPTY`` when no
    item is staged.

StigAuth: SIFTA_LESSON_ENGINE_FIRST_CUE_SYNC_V0 (Cowork CW47 / Claude,
surgery cw47-0517-0007, 2026-05-17).
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.swarm_alice_lesson_mode import LessonEngine, LessonItem  # noqa: E402


# A tiny in-memory lesson pack — three deterministic items so we can
# control which one rng would draw.
_PACK_BODY = {
    "name": "test_pack",
    "version": "test",
    "levels": [
        {
            "id": "L1",
            "name": "test_words",
            "kind": "word",
            "items": [
                {"id": "i_cat", "show": "cat", "say": "cat"},
                {"id": "i_mat", "show": "mat", "say": "mat"},
                {"id": "i_bat", "show": "bat", "say": "bat"},
            ],
        }
    ],
}


@pytest.fixture
def engine(tmp_path: Path) -> LessonEngine:
    pack = tmp_path / "pack.json"
    pack.write_text(json.dumps(_PACK_BODY), encoding="utf-8")
    state = tmp_path / "state"
    state.mkdir()
    # Seeded rng so draws are deterministic.
    return LessonEngine(
        pack_path=pack,
        state_dir=state,
        rng=random.Random(1234),
    )


def test_confirm_current_cue_reuses_staged_item(engine: LessonEngine) -> None:
    # Stage — write=False, no trace row, but _current_item is set.
    staged = engine.next_cue(write=False)
    staged_show = staged["show"]
    staged_say = staged["expected_say"]
    staged_item_id = staged["item_id"]

    # Confirm — should reuse the SAME item (no new draw).
    confirmed = engine.confirm_current_cue(write=True)
    assert confirmed["show"] == staged_show
    assert confirmed["expected_say"] == staged_say
    assert confirmed["item_id"] == staged_item_id
    assert confirmed.get("staged_card_confirmed") is True
    # confirm_current_cue must NOT have rolled the rng again.
    assert engine.current_item is not None
    assert engine.current_item.item_id == staged_item_id


def test_confirm_current_cue_returns_empty_when_nothing_staged(tmp_path: Path) -> None:
    # Empty pack engine — no items staged.
    empty_pack = tmp_path / "empty.json"
    empty_pack.write_text(json.dumps({"levels": []}), encoding="utf-8")
    engine = LessonEngine(pack_path=empty_pack, rng=random.Random(0))
    out = engine.confirm_current_cue(write=True)
    assert out.get("kind") == "LESSON_CUE_EMPTY"


def test_subsequent_next_cue_after_confirm_still_draws_fresh(engine: LessonEngine) -> None:
    # Stage → confirm → run next_cue. The second cue is a fresh draw.
    engine.next_cue(write=False)            # stage
    first = engine.confirm_current_cue(write=True)  # first cue = staged
    second = engine.next_cue(write=True)    # second cue = fresh draw

    # Both must be valid items.
    assert first.get("kind") == "LESSON_CUE"
    assert second.get("kind") == "LESSON_CUE"
    # next_cue must NOT set the staged_card_confirmed flag.
    assert second.get("staged_card_confirmed") is not True


def test_display_word_matches_spoken_prompt_after_confirm(engine: LessonEngine) -> None:
    """The screen ``show`` and the prompt ``say`` must come from the same item.

    This is the contract the Architect's transcript broke: "I can see it
    it reads cat" + Alice cued "mat".
    """
    engine.next_cue(write=False)
    confirmed = engine.confirm_current_cue(write=True)
    prompt = engine.cue_prompt_for_alice(owner_name="Ace")
    # The displayed word from the cue must appear in the spoken prompt.
    assert confirmed["show"] in prompt, (
        f"Spoken prompt {prompt!r} must mention displayed word "
        f"{confirmed['show']!r}"
    )
    # And the expected_say must also be in the prompt (since show == say
    # for these test items, "Say: <word>" form applies).
    assert confirmed["expected_say"] in prompt


def test_confirm_writes_a_lesson_cue_trace_when_write_true(engine: LessonEngine, tmp_path: Path) -> None:
    # The trace ledger should grow by exactly one row.
    engine.next_cue(write=False)
    ledger = (engine.state_dir or tmp_path) / "alice_lesson_trace.jsonl"
    pre = ledger.read_text(encoding="utf-8").splitlines() if ledger.exists() else []
    engine.confirm_current_cue(write=True)
    post = ledger.read_text(encoding="utf-8").splitlines() if ledger.exists() else []
    assert len(post) == len(pre) + 1, (
        f"Expected 1 new trace row; pre={len(pre)} post={len(post)}"
    )
    last = json.loads(post[-1])
    assert last["kind"] == "LESSON_CUE"
    assert last.get("staged_card_confirmed") is True


def test_confirm_does_not_write_when_write_false(engine: LessonEngine, tmp_path: Path) -> None:
    engine.next_cue(write=False)
    ledger = (engine.state_dir or tmp_path) / "alice_lesson_trace.jsonl"
    pre = ledger.read_text(encoding="utf-8").splitlines() if ledger.exists() else []
    engine.confirm_current_cue(write=False)
    post = ledger.read_text(encoding="utf-8").splitlines() if ledger.exists() else []
    assert len(post) == len(pre)


def test_stage_then_confirm_keeps_rng_in_sync(engine: LessonEngine) -> None:
    """Confirm should not consume rng entropy — the next draw should be
    identical to what would have happened without the confirm call."""
    rng_state = engine.rng.getstate()
    engine.next_cue(write=False)
    engine.confirm_current_cue(write=True)
    # Now draw the next_cue and compare to a parallel engine that did
    # only the original stage+next.
    after_confirm_next = engine.next_cue(write=False)["item_id"]

    # Parallel engine — same seed, same stage, then next_cue right away.
    import json as _json
    engine2 = LessonEngine(
        pack_path=engine.pack_path,
        state_dir=engine.state_dir,
        rng=random.Random(1234),  # same seed as fixture
    )
    engine2.next_cue(write=False)
    parallel_next = engine2.next_cue(write=False)["item_id"]

    # confirm_current_cue should have left rng untouched, so the next
    # draw matches the parallel engine that skipped the confirm step.
    assert after_confirm_next == parallel_next
