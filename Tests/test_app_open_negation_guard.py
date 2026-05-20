"""Regression test for the app-open matcher's negation guard.

Architect live transcript 2026-05-16 — the matcher latched on:
  * "I'm gonna start the YouTube video soon" → Stigmergic Video Poker (fuzzy)
  * "Alice, I don't want to open any app right now" → Alice Shell (fuzzy)

These tests pin the verbatim transcript phrases so future Doctors
cannot regress the bug. The guard at the top of
``_extract_sifta_app_command`` returns ``{}`` for explicit-refusal
patterns so the brain receives the conversational text intact.

StigAuth: SIFTA_NEGATION_GUARD_V0 (Cowork CW47 / Claude, surgery
cw47-0516-2335, 2026-05-16).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def _import_matcher():
    """Helper: pull the matcher functions out of the big Talk widget."""
    # The widget pulls in Qt and a lot of organs. For pure regex testing
    # we only need the two module-level helpers; import the module and
    # access them via attribute lookup. If Qt is missing in CI we still
    # get the helpers because they live at module top level.
    try:
        from Applications import sifta_talk_to_alice_widget as widget
    except Exception:
        pytest.skip(
            "Cannot import Applications.sifta_talk_to_alice_widget in this "
            "environment (Qt or other deps missing) — run on M5 to exercise "
            "the regression."
        )
    return widget


# ── Negation guard primitive (_is_explicit_open_refusal) ─────────────────


@pytest.mark.parametrize("phrase", [
    # Verbatim Architect transcript 2026-05-16
    "Alice, I don't want to open any app right now.",
    "I don't want to open any app right now",
    "I do not want to open any app",
    "I would not open any app right now",
    "i didn't want to open an app",
    # Strong refusal variants
    "no app please",
    "not any app",
    "no apps",
    "no application",
    # Verb-level negation
    "do not open it",
    "don't open it",
    "won't open it",
    "never open that",
    "do not launch it",
    "don't show it",
    # Cancellation
    "stop opening that",
    "cancel opening",
    "skip opening any app",
    "abort opening the app",
])
def test_explicit_refusal_returns_empty_dict(phrase):
    widget = _import_matcher()
    out = widget._extract_sifta_app_command(phrase)
    assert out == {}, (
        f"Explicit refusal {phrase!r} should NOT trigger app-open matcher; "
        f"got {out!r}"
    )


# ── Whole-pipeline behaviour: the exact George transcript phrases ────────


def test_youtube_video_soon_phrase_does_not_match_app():
    widget = _import_matcher()
    # "I'm gonna start the YouTube video soon" — contains "start" verb
    # + noun phrase, but "the YouTube video soon" is ambient media, not
    # a manifest app. Should NOT fuzz-match to Stigmergic Video Poker.
    out = widget._extract_sifta_app_command(
        "I'm gonna start the YouTube video soon"
    )
    # The matcher might return {} OR a browser-intent shape — but it
    # must NOT return open_app_uncertain matching to Stigmergic Video
    # Poker against the live manifest.
    if out:
        kind = out.get("kind", "")
        app_name = out.get("app_name", "")
        assert kind != "open_app_uncertain" or "Stigmergic Video Poker" not in (out.get("candidates") or ""), (
            f"YouTube-video phrase should not fuzz-match Stigmergic Video Poker; "
            f"got {out!r}"
        )


def test_long_youtube_transcript_start_with_i_read_does_not_match_app():
    widget = _import_matcher()
    out = widget._extract_sifta_app_command(
        "Discuss consciousness with you, just a very brief introduction, "
        "but you are a professor of cognitive and computational neuroscience "
        "and I would love to hear about what you consider that new science "
        "to be and start with I read."
    )
    assert out == {}, f"Media transcript phrase should not become app repair; got {out!r}"


def test_long_youtube_transcript_start_arguing_does_not_match_app():
    widget = _import_matcher()
    out = widget._extract_sifta_app_command(
        "The dress was powerful because the experiences were so different "
        "people use different words and they could start arguing. Do you see "
        "it as white and gold? How can you see that? And it is crazy."
    )
    assert out == {}, f"Nested media quote should not become app repair; got {out!r}"


def test_pending_app_repair_does_not_treat_right_now_as_yes():
    widget = _import_matcher()
    assert widget._voice_repair_confirmation_action(
        "Alice, listen to me very carefully. I'm going to sleep right now "
        "and watching TV, so be quiet and listen."
    ) == ""


def test_dont_want_any_app_phrase_does_not_match_app():
    widget = _import_matcher()
    out = widget._extract_sifta_app_command(
        "Alice, I don't want to open any app right now."
    )
    # Must return {} — the negation guard catches "I don't want to open"
    assert out == {}


def test_no_was_talking_about_youtube_does_not_match_app():
    widget = _import_matcher()
    # "No, I was talking about the YouTube video on consciousness that we are
    # gonna be listening together" — leads with "No,"; should not fuzz.
    out = widget._extract_sifta_app_command(
        "No, I was talking about the YouTube video on consciousness "
        "that we are gonna be listening together"
    )
    # If this triggers ANY app-open intent it's still a regression. The
    # leading "No," and the topic-shift verbs ("talking about") should
    # route to the brain, not the matcher.
    if out:
        kind = out.get("kind", "")
        assert kind not in ("open_app_uncertain", "app"), (
            f"Topic-shift sentence routed to {kind!r}: {out!r}"
        )


def test_any_app_right_now_continuation_phrase_returns_empty():
    widget = _import_matcher()
    # If somehow the regex captures "any app right now" as a noun
    # phrase, the continuation-phrases set rejects it.
    out = widget._extract_sifta_app_command("show any app right now")
    # Either guard catches it. Result must not be an app-open intent.
    if out:
        assert out.get("kind") not in ("app", "open_app_uncertain"), (
            f"Continuation phrase should not match app-open; got {out!r}"
        )


# ── Regression: legitimate open commands still work ─────────────────────


def test_open_wordace_still_matches():
    widget = _import_matcher()
    # Mock the manifest with a known app
    out = widget._extract_sifta_app_command(
        "open Ace", app_names=["Ace", "WordAce", "Pheromone Symphony"],
    )
    # Must produce an app intent (kind=app or switch_desktop_mode for chat aliases)
    assert out, f"Open command should match; got {out!r}"
    assert out.get("kind") in ("app", "switch_desktop_mode"), (
        f"Legit open should produce app-kind intent; got {out!r}"
    )


def test_launch_pheromone_symphony_still_matches():
    widget = _import_matcher()
    out = widget._extract_sifta_app_command(
        "launch Pheromone Symphony",
        app_names=["Pheromone Symphony", "Ace"],
    )
    assert out, f"Legit launch should match; got {out!r}"
    assert out.get("kind") == "app"
    assert out.get("app_name") == "Pheromone Symphony"


def test_explicit_refusal_does_not_block_pure_chat():
    widget = _import_matcher()
    # Pure conversation — no verbs, no negation, no app names
    out = widget._extract_sifta_app_command(
        "I'm listening to a YouTube video about consciousness."
    )
    # This sentence has no leading open-verb, so the matcher should
    # return {} regardless of the negation guard.
    assert out == {} or out.get("kind") not in ("app", "open_app_uncertain")
