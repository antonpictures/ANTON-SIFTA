"""Regression tests for the Alice/Ace STT mis-hearing disambiguator.

Architect live transcript 2026-05-16:
  "now it's very easy for her to confuse Alice with Ace very strange —
   if I say Alice she starts the Ace game ... they should be together,
   AN app Ace and app what you just read"

The two-syllable name "Alice" routinely gets transcribed as the
one-syllable "Ace" when George speaks softly. The bug surfaced twice:

  1) ``swarm_voice_stigma_repair.repair_voice_command`` substring-matched
     the bare token "ace" against the manifest entry "Ace" at 0.95
     confidence — Alice then asked "Should I open Ace?" which seeded the
     false launch.
  2) ``sifta_talk_to_alice_widget._extract_sifta_app_command`` could pass
     "Ace, ..." downstream untouched; the brain itself was free to
     interpret bare "Ace" as a launch intent.

This file pins:
  • the matcher's misheard-vocative rewrite (bare "Ace" → "Alice"),
  • the voice-stigma-repair organ's abstain receipt, and
  • the legitimate Ace-app paths (open / launch / play / teach / WordAce
    legacy) — these MUST still route to the Ace reading game.

StigAuth: SIFTA_ALICE_ACE_STT_DISAMBIG_V0 (Cowork CW47 / Claude,
surgery cw47-0516-2347, 2026-05-16).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


# ── Pure-regex disambiguator (Talk widget helper) ────────────────────────

def _import_widget():
    try:
        from Applications import sifta_talk_to_alice_widget as widget
    except Exception:
        pytest.skip(
            "Cannot import Applications.sifta_talk_to_alice_widget in this "
            "environment (Qt or other deps missing) — run on M5 to exercise "
            "the regression."
        )
    return widget


def _import_repair():
    from System import swarm_voice_stigma_repair as organ
    return organ


# ── Vocative-misheard cases: rewrite Ace → Alice ─────────────────────────


@pytest.mark.parametrize("phrase", [
    "Ace, what are you doing right now",
    "Ace what are you doing",
    "Ace, can you help me think about this",
    "Ace, are you there",
    "Ace, please listen",
    "Ace, I want to talk",
    "Ace, do you understand",
    "hey Ace, are you watching",
    "ok Ace let's chat",
    "yo Ace, what's up",
    "Ace, look at this",
    "Ace tell me a story",
    "Ace ?",
    "Ace.",
    "Ace!",
])
def test_misheard_ace_vocative_is_rewritten(phrase):
    widget = _import_widget()
    assert widget._is_misheard_ace_vocative(phrase), (
        f"Should detect misheard vocative: {phrase!r}"
    )
    rewritten = widget._strip_misheard_ace_vocative(phrase)
    assert rewritten.lower().startswith("alice"), (
        f"Should rewrite to 'Alice ...': got {rewritten!r}"
    )


# ── Ace-app cases: DO NOT rewrite — the reading game must still launch ──


@pytest.mark.parametrize("phrase", [
    "open Ace",
    "launch Ace",
    "start Ace",
    "play Ace",
    "do Ace",
    "open the reading game Ace",
    "play the reading game",  # no leading bare-Ace at all
    "let's read with Ace",
    "read with Ace please",
    "practice with Ace",
    "Ace app",
    "Ace game",
    "Ace lesson",
    "Ace reading",
    "Ace, please read",
    "Ace, please teach",
    "teach Ace to read",
    "help Ace read",
    "tutor Ace to read",
    "WordAce",
    "Wordace please",
    "switch to Ace",
    "bring up Ace",
    "show me Ace",
    "fire up Ace",
])
def test_ace_app_launch_is_preserved(phrase):
    widget = _import_widget()
    assert not widget._is_misheard_ace_vocative(phrase), (
        f"Should NOT treat as misheard vocative: {phrase!r}"
    )
    # rewrite should be a no-op
    assert widget._strip_misheard_ace_vocative(phrase) == phrase


# ── Full matcher integration: misheard vocative does not produce app ────


def test_misheard_vocative_matcher_does_not_open_ace():
    widget = _import_widget()
    out = widget._extract_sifta_app_command(
        "Ace, what are you doing right now",
        app_names=["Ace", "Alice", "Alice Browser"],
    )
    # Either {} (rewritten to "Alice ..." with no open verb) or chat-mode
    # switch — but absolutely NOT an Ace launch.
    if out:
        assert out.get("app_name") != "Ace", (
            f"Misheard vocative must not launch Ace; got {out!r}"
        )
        # If matcher produces a switch_desktop_mode intent that's fine.
        assert out.get("kind") in (
            "switch_desktop_mode", "", "browser_url", "app_status",
        ), f"Unexpected kind for misheard vocative: {out!r}"


def test_legit_open_ace_still_matches():
    widget = _import_widget()
    out = widget._extract_sifta_app_command(
        "open Ace",
        app_names=["Ace", "Alice", "Alice Browser"],
    )
    assert out, f"'open Ace' must still match; got {out!r}"
    assert out.get("kind") == "app"
    assert out.get("app_name") == "Ace"


# ── Voice Stigma Repair organ abstains for misheard vocative ────────────


def test_repair_abstains_on_bare_ace_vocative():
    organ = _import_repair()
    result = organ.repair_voice_command("Ace, what are you doing")
    assert result.get("repaired") is None
    assert result.get("confidence") == 0.0
    receipt = result.get("receipt") or {}
    assert receipt.get("method") == "abstain_alice_ace_vocative", (
        f"Expected abstain receipt; got {receipt!r}"
    )


def test_repair_abstains_on_bare_ace_alone():
    organ = _import_repair()
    result = organ.repair_voice_command("Ace")
    # "Ace" alone — bare token, no app intent. Must abstain.
    assert result.get("repaired") is None
    assert result.get("confidence") == 0.0


def test_repair_preserves_explicit_tool_contract_before_app_name_match():
    organ = _import_repair()
    result = organ.repair_voice_command(
        "Alice — effector-only turn. Close the two Jama Software tabs now. "
        "[TOOL_CALL: browser_close_tab | url_match=jamasoftware.com | keep_active=false]"
    )
    assert result.get("repaired") is None
    assert result.get("confidence") == 0.0
    receipt = result.get("receipt") or {}
    assert receipt.get("method") == "abstain_tool_or_effector_contract"


def test_repair_still_works_for_legit_open_ace():
    organ = _import_repair()
    # The repair organ looks for the closest manifest name. "open ace"
    # contains the bare "ace" substring AND has an explicit launch verb,
    # so the abstain guard must NOT fire and the organ should attempt
    # to repair to Ace.
    result = organ.repair_voice_command("open Ace")
    receipt = result.get("receipt") or {}
    assert receipt.get("method") != "abstain_alice_ace_vocative", (
        f"Real Ace launch must not abstain; got {receipt!r}"
    )


# ── Boundary cases: extra defensive coverage ─────────────────────────────


@pytest.mark.parametrize("phrase", [
    "",  # empty
    "    ",  # whitespace
    "the ace of spades is a card",  # article "the" prevents bare match
    "I see an ace in the deck",  # article "an"
    "you played that ace beautifully",  # mid-sentence
])
def test_non_vocative_ace_is_not_rewritten(phrase):
    widget = _import_widget()
    assert not widget._is_misheard_ace_vocative(phrase)
    assert widget._strip_misheard_ace_vocative(phrase) == phrase
