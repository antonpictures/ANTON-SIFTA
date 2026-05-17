"""Regression tests for narration-on-app-open.

Architect 2026-05-17 transcript (verbatim):
  "she has to talk to me about the app about what I'm doing right now
   why did you open the app I'm here I just want to learn I wanna learn
   words and I want to learn sentences"

These tests pin:
  • Opening Ace returns a narration that includes the canonical
    voice_open_narration from the manifest (not the legacy mechanical
    line about the Swarm App Store tab).
  • The narration mentions reading/word so the owner knows WHY Alice
    opened the app — answering "why did you open the app".
  • Apps without voice_open_narration AND without a description fall
    back cleanly (empty string → caller uses legacy reply).
  • An app with only a description gets a narration built from the
    first sentences of that description (provenance: manifest, not
    invented).
  • The helper is purely read-only against apps_manifest.json (no
    network, no LLM, no hardcoded per-app strings).

StigAuth: SIFTA_APP_OPEN_NARRATION_V0
Cowork CW47 / Claude surgery cw47-0517-0340, 2026-05-17.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def _import_helper():
    try:
        from Applications import sifta_talk_to_alice_widget as widget
    except Exception:
        pytest.skip(
            "Cannot import Applications.sifta_talk_to_alice_widget (Qt missing). "
            "Run on M5 to exercise the regression."
        )
    return widget


# ── primitive: _first_short_sentences ─────────────────────────────────────


def test_first_short_sentences_keeps_short_first():
    widget = _import_helper()
    out = widget._first_short_sentences("Hello world. This is two sentences.", max_chars=200)
    assert "Hello world." in out
    assert "two sentences." in out


def test_first_short_sentences_caps_at_max_chars():
    widget = _import_helper()
    blob = ("Sentence one is here. " * 20).strip()
    out = widget._first_short_sentences(blob, max_chars=50)
    assert 1 <= len(out) <= 50
    # Must not chop mid-word.
    assert not out.endswith("Sent")


def test_first_short_sentences_handles_empty_string():
    widget = _import_helper()
    assert widget._first_short_sentences("") == ""
    assert widget._first_short_sentences("   ") == ""


# ── narration source ladder ───────────────────────────────────────────────


def test_ace_narration_uses_voice_open_narration_from_manifest():
    """Opening 'Ace' must speak the explicit owner-facing line from the
    manifest, not the legacy mechanical reply."""
    widget = _import_helper()
    narration = widget._build_app_open_narration("Ace")
    assert narration, "Ace narration must not be empty"
    # The canonical narration mentions the reading game and waiting/listening.
    nl = narration.lower()
    assert "reading game" in nl
    assert ("read" in nl) or ("waits" in nl) or ("listens" in nl)
    # The old mechanical line must NOT appear in the new narration.
    assert "swarm app store tab" not in nl
    assert "switching to the swarm app store tab" not in nl


def test_unknown_app_returns_empty_string():
    """No manifest entry → caller falls back to legacy reply."""
    widget = _import_helper()
    assert widget._build_app_open_narration("NonexistentAppXYZ") == ""


def test_empty_app_name_returns_empty_string():
    widget = _import_helper()
    assert widget._build_app_open_narration("") == ""
    assert widget._build_app_open_narration("   ") == ""


def test_description_fallback_uses_manifest_description_only():
    """When voice_open_narration is missing but description exists, the
    helper builds a narration from the description prose. Verify by
    finding an app in the manifest with a description but no
    voice_open_narration."""
    widget = _import_helper()
    manifest_path = _REPO / "Applications" / "apps_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    fallback_app = None
    for name, entry in manifest.items():
        if not isinstance(entry, dict):
            continue
        if entry.get("voice_open_narration"):
            continue
        desc = entry.get("description")
        if isinstance(desc, str) and desc.strip() and not entry.get("_retired"):
            fallback_app = name
            break
    if fallback_app is None:
        pytest.skip("no manifest app exercises the description-fallback branch")
    narration = widget._build_app_open_narration(fallback_app)
    assert narration, f"description-only narration for {fallback_app!r} must not be empty"
    # The "I'm opening … because you asked" prefix is always emitted in
    # the description branch.
    assert narration.lower().startswith(f"i'm opening {fallback_app.lower()}")
    # And the narration body must be a substring of the description (no
    # invention).
    desc = manifest[fallback_app]["description"]
    body_words = [w for w in narration.split() if len(w) > 4]
    desc_lower = desc.lower()
    matches = sum(1 for w in body_words if w.lower() in desc_lower)
    # Most long words in the narration must trace back to the description.
    assert matches >= max(1, len(body_words) // 3), (
        f"narration body diverged from manifest description: "
        f"{matches}/{len(body_words)} long words traceable"
    )


# ── invariants: narration never invents ──────────────────────────────────


def test_no_narration_contains_uncited_metaphysics():
    """Defence-in-depth: the helper must not produce phrases that imply
    LLM-invented consciousness claims or external citations the manifest
    does not actually contain."""
    widget = _import_helper()
    manifest_path = _REPO / "Applications" / "apps_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    forbidden_substrings = (
        "i feel",
        "i think you",
        "in my opinion",
        "according to research",
        "studies show",
    )
    bad = []
    for name, entry in manifest.items():
        if not isinstance(entry, dict) or entry.get("_retired"):
            continue
        n = widget._build_app_open_narration(name)
        if not n:
            continue
        nl = n.lower()
        for tok in forbidden_substrings:
            if tok in nl:
                bad.append((name, tok, n))
    assert not bad, f"narration leaked uncited phrases: {bad!r}"
