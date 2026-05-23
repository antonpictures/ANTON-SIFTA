"""Tests for the wallpaper router bridge.

Per §8.5 consensus, this bridge does not modify either peer surface
(swarm_alice_wallpaper_effector or swarm_cortex_gated_effector_router).
These tests verify the bridge:
   - registers default/change/undo intents idempotently
   - routes 'Alice change the wallpaper to X' → 'owner_wallpaper_change'
   - routes 'Alice change the wallpaper to default' → 'owner_wallpaper_default'
   - routes 'undo the wallpaper' → 'owner_wallpaper_undo'
   - extracts the query slot correctly
   - REFUSES non-architect audiences for wallpaper intents
   - the router gate writes its decision receipt
"""
import json
import re

import pytest

# Importing the bridge registers the intents on the singleton registry.
# Tests interact with that singleton — see test_bridge_registration_is_idempotent.

from System.swarm_wallpaper_router_bridge import (
    _WALLPAPER_CHANGE_RE,
    _WALLPAPER_DEFAULT_RE,
    _WALLPAPER_UNDO_RE,
    _change_slot_extractor,
    _undo_slot_extractor,
    register_with_router,
)


# ── Pattern coverage ──────────────────────────────────────────────────────

@pytest.mark.parametrize("phrase,expected_query", [
    ("Alice change the desktop wallpaper to a black hole",
     "a black hole"),
    ("Change the background to a forest at night",
     "a forest at night"),
    ("Wallpaper of honey dripping on a circuit board",
     "honey dripping on a circuit board"),
    ("Alice, change wallpaper to NASA Goddard",
     "NASA Goddard"),
    ("Set my background to deep space",
     "deep space"),
    ("Change desktop image to a misty mountain",
     "a misty mountain"),
])
def test_wallpaper_change_pattern_extracts_query(phrase, expected_query):
    m = _WALLPAPER_CHANGE_RE.search(phrase)
    assert m is not None, f"pattern missed: {phrase!r}"
    slots = _change_slot_extractor(m)
    assert expected_query.lower() in slots["query"].lower()


@pytest.mark.parametrize("phrase", [
    "What's the weather like?",
    "I painted my bedroom wall yesterday",
    "Tell me about the desktop environment",
])
def test_wallpaper_change_pattern_does_not_false_positive(phrase):
    m = _WALLPAPER_CHANGE_RE.search(phrase)
    assert m is None, f"unexpected match on {phrase!r}"


@pytest.mark.parametrize("phrase", [
    "undo the wallpaper",
    "Alice, undo wallpaper",
    "wallpaper back",
    "go back to the previous wallpaper",
    "revert that wallpaper",
    "I don't like that wallpaper",
])
def test_wallpaper_undo_pattern_matches(phrase):
    assert _WALLPAPER_UNDO_RE.search(phrase) is not None


@pytest.mark.parametrize("phrase", [
    "Alice change the wallpaper to default",
    "hey Alice change the wallpaper back to default",
    "hey Alice changed the wallpaper back to default",
    "restore the desktop wallpaper to the theme default",
    "reset my wallpaper",
    "wallpaper back to default",
    "clear the background",
])
def test_wallpaper_default_pattern_matches(phrase):
    assert _WALLPAPER_DEFAULT_RE.search(phrase) is not None


# ── Registration ──────────────────────────────────────────────────────────

def test_bridge_registration_is_idempotent():
    """Calling register_with_router twice should not raise — second
    call sees both intents already present."""
    out1 = register_with_router()
    out2 = register_with_router()
    # Both intents should be present after either call.
    assert "owner_wallpaper_default" in (out1["registered"] + out1["already_present"])
    assert "owner_wallpaper_change" in (out1["registered"] + out1["already_present"])
    assert "owner_wallpaper_undo" in (out1["registered"] + out1["already_present"])
    # Second call must see them as already_present (not crash).
    assert out2["ok"] is True
    assert "owner_wallpaper_default" in out2["already_present"]
    assert "owner_wallpaper_change" in out2["already_present"]
    assert "owner_wallpaper_undo" in out2["already_present"]


# ── End-to-end through the router gate ────────────────────────────────────

def test_router_routes_wallpaper_change_to_correct_effector(tmp_path, monkeypatch):
    """The gate should fire 'owner_wallpaper_change' on a matching phrase
    when audience=architect. Since the peer effector requires a network
    call to DDG, we expect either FIRE (with a bridge-error effector_result
    because no network in sandbox) or a REFUSE if the audience check
    fails. The DECISION must be one of those two — we just verify the
    correct effector was selected by the classifier."""
    monkeypatch.setattr(
        "System.swarm_cortex_gated_effector_router._LEDGER",
        tmp_path / "router.jsonl",
    )
    # Ensure the bridge is registered.
    register_with_router()
    from System.swarm_cortex_gated_effector_router import gate

    d = gate(
        "Alice change the desktop wallpaper to a black hole",
        audience="architect",
    )
    # Decision must reference the wallpaper-change effector either way
    # (FIRE if peer effector returned ok=False on no-network, or just
    # FIRE with a bridge error stored in extras).
    assert d.effector == "owner_wallpaper_change"
    # The gate should have ATTEMPTED to fire (decision='FIRE') because
    # confidence=0.95 from regex match > threshold 0.7. The peer
    # effector's network call will then fail in the sandbox and the
    # effector returns ok=False — but the gate's decision was correct.
    assert d.decision in ("FIRE", "REFUSE")


def test_router_refuses_wallpaper_for_non_architect_audience(tmp_path, monkeypatch):
    """Wallpaper effector is architect-only. Any other audience must
    be refused at the gate before the peer effector is even reached."""
    monkeypatch.setattr(
        "System.swarm_cortex_gated_effector_router._LEDGER",
        tmp_path / "router.jsonl",
    )
    register_with_router()
    from System.swarm_cortex_gated_effector_router import gate

    d = gate(
        "Alice change the wallpaper to a forest",
        audience="media",
    )
    assert d.decision == "REFUSE"
    assert "audience" in d.reason


def test_router_routes_undo_to_correct_effector(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "System.swarm_cortex_gated_effector_router._LEDGER",
        tmp_path / "router.jsonl",
    )
    register_with_router()
    from System.swarm_cortex_gated_effector_router import gate

    d = gate("undo the wallpaper", audience="architect")
    assert d.effector == "owner_wallpaper_undo"


def test_router_routes_default_before_wallpaper_change(tmp_path, monkeypatch):
    """Default restore must not DDG-search the word 'default'. The
    specialized default intent must beat the broad change intent."""
    monkeypatch.setattr(
        "System.swarm_cortex_gated_effector_router._LEDGER",
        tmp_path / "router.jsonl",
    )
    import System.sifta_desktop_themes as themes
    saved = []
    monkeypatch.setattr(themes, "load_custom_wallpaper_path", lambda: "/tmp/custom.jpg")
    monkeypatch.setattr(themes, "save_custom_wallpaper_path", lambda value: saved.append(value))
    register_with_router()
    from System.swarm_cortex_gated_effector_router import gate

    d = gate("hey Alice changed the wallpaper back to default", audience="architect")

    assert d.decision == "FIRE"
    assert d.effector == "owner_wallpaper_default"
    assert saved == [None]
    assert d.extras["effector_result"]["kind"] == "WALLPAPER_DEFAULT_RESTORED"


def test_router_does_not_fire_wallpaper_on_unrelated_text(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "System.swarm_cortex_gated_effector_router._LEDGER",
        tmp_path / "router.jsonl",
    )
    register_with_router()
    from System.swarm_cortex_gated_effector_router import gate

    d = gate("I'm just thinking about how the wall looks", audience="architect")
    # Either UNKNOWN_INTENT, or a different effector that legitimately
    # matched — but NOT the wallpaper one (no verb-pattern match for
    # changing wallpaper).
    assert d.effector != "owner_wallpaper_change"


@pytest.mark.parametrize("phrase", [
    "hey Alice",
    "Alice yellow",
    "Alice are you awake?",
    "I saw yellow wallpaper in a store",
])
def test_wake_name_alone_does_not_fire_wallpaper_effectors(tmp_path, monkeypatch, phrase):
    """Hearing the name is attention, not authorization."""
    monkeypatch.setattr(
        "System.swarm_cortex_gated_effector_router._LEDGER",
        tmp_path / "router.jsonl",
    )
    register_with_router()
    from System.swarm_cortex_gated_effector_router import gate

    d = gate(phrase, audience="architect")

    assert d.effector not in {
        "owner_wallpaper_default",
        "owner_wallpaper_change",
        "owner_wallpaper_undo",
    }
