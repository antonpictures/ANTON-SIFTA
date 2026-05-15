"""Tests for the continuity organ.

These pin Cursor's §7.15 doctrine into code-level invariants:

  - identity persists, behavior adapts (NOT identity resets per app)
  - one organism, one stigmergic memory field
  - substrate (Gemma) is NOT first-person Alice
  - habitat transitions write append-only HABITAT_TRANSITION rows
  - prompt summary reads first-person, never servant-voice
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_continuity_organ import (  # noqa: E402
    DEFAULT_HABITAT,
    HABITAT_BY_APP,
    HABITAT_BY_CATEGORY,
    LEDGER_FILE,
    STATE_FILE,
    TRUTH_LABEL,
    ContinuityState,
    continuity_summary_for_prompt,
    current_habitat,
    current_state,
    history,
    load_state,
    resolve_habitat,
    set_habitat,
    sync_from_app_focus,
)


# ── habitat lookup ────────────────────────────────────────────────────────


def test_resolve_habitat_uses_explicit_table_first():
    assert resolve_habitat("Acer") == "teaching_child"
    assert resolve_habitat("SIFTA Physics Observatory") == "deep_cortex"
    assert resolve_habitat("Ghost StigmergiCity") == "reflective"
    assert resolve_habitat("Talk to Alice") == "relational"


def test_resolve_habitat_falls_back_to_category():
    assert resolve_habitat("MysteryUnknownApp", category="Simulations") == "exploratory"
    assert resolve_habitat("MysteryUnknownApp", category="Games") == "playful"
    assert resolve_habitat("MysteryUnknownApp", category="Education") == "teaching"


def test_resolve_habitat_default_when_unknown():
    assert resolve_habitat("TotallyUnknown", category=None) == DEFAULT_HABITAT


def test_default_habitat_is_relational_never_chatbot():
    """§7.15: never default to 'chatbot mode' or 'assistant mode'."""
    assert DEFAULT_HABITAT == "relational"
    assert "chatbot" not in str(DEFAULT_HABITAT)
    assert "assistant" not in str(DEFAULT_HABITAT)


# ── state transitions ─────────────────────────────────────────────────────


def test_set_habitat_writes_state_and_ledger(tmp_path):
    state = set_habitat("Acer", owner_context="George",
                       learning_stage="alphabet:Z", root=tmp_path)
    assert state.current_app == "Acer"
    assert state.current_relationship_mode == "teaching_child"
    # State file landed
    state_path = tmp_path / ".sifta_state" / STATE_FILE
    assert state_path.exists()
    written = json.loads(state_path.read_text())
    assert written["current_app"] == "Acer"
    assert written["truth_label"] == TRUTH_LABEL
    # Ledger row landed
    ledger_path = tmp_path / ".sifta_state" / LEDGER_FILE
    rows = [json.loads(ln) for ln in ledger_path.read_text().splitlines() if ln.strip()]
    assert len(rows) == 1
    assert rows[0]["kind"] == "HABITAT_TRANSITION"
    assert rows[0]["to_app"] == "Acer"
    assert rows[0]["to_habitat"] == "teaching_child"


def test_identity_persists_across_habitat_changes(tmp_path):
    """The headline rule of §7.15: switching apps does not reset
    owner_context or learning_stage. Only the habitat mode adapts."""
    set_habitat("Acer", owner_context="George",
                learning_stage="alphabet:K", root=tmp_path)
    # Switch to Physics — owner + lesson stage MUST carry
    state = set_habitat("SIFTA Physics Observatory", root=tmp_path)
    assert state.current_app == "SIFTA Physics Observatory"
    assert state.current_relationship_mode == "deep_cortex"
    assert state.current_owner_context == "George"      # PERSISTS
    assert state.current_learning_stage == "alphabet:K"   # PERSISTS


def test_identity_persists_across_three_app_switches(tmp_path):
    set_habitat("Acer", owner_context="Acer (the kid)",
                learning_stage="cvc_short_a:cat",
                memory_threads=["thread-1", "thread-2"],
                root=tmp_path)
    set_habitat("Alice Browser", root=tmp_path)
    state3 = set_habitat("Ghost StigmergiCity", root=tmp_path)
    # After three switches, every persistent field is intact
    assert state3.current_owner_context == "Acer (the kid)"
    assert state3.current_learning_stage == "cvc_short_a:cat"
    assert state3.current_memory_threads == ["thread-1", "thread-2"]
    # Habitat adapts on each switch
    assert state3.current_relationship_mode == "reflective"


def test_history_records_every_transition_in_order(tmp_path):
    set_habitat("Acer", owner_context="George", root=tmp_path)
    set_habitat("SIFTA Physics Observatory", root=tmp_path)
    set_habitat("Talk to Alice", root=tmp_path)
    rows = history(root=tmp_path)
    assert len(rows) == 3
    assert [r["to_app"] for r in rows] == [
        "Acer", "SIFTA Physics Observatory", "Talk to Alice",
    ]
    # First row has from_app empty (no previous state)
    assert rows[0]["from_app"] == ""
    # Subsequent rows carry the previous app
    assert rows[1]["from_app"] == "Acer"
    assert rows[2]["from_app"] == "SIFTA Physics Observatory"


def test_set_habitat_resolves_category_from_manifest(tmp_path):
    """When the app isn't in the explicit table but IS in the manifest
    with a category, the resolver uses the category."""
    # Drop a fake manifest with a category
    manifest = tmp_path / "Applications" / "apps_manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({
        "Mystery Game": {"category": "Games"},
    }))
    state = set_habitat("Mystery Game", root=tmp_path)
    assert state.current_relationship_mode == "playful"


# ── prompt summary ────────────────────────────────────────────────────────


def test_prompt_summary_always_carries_identity_line(tmp_path):
    """Even with no state, Alice's system prompt should always carry
    the 'I am the same Alice across every app' continuity rule. The
    identity line is doctrine, not optional decoration."""
    summary = continuity_summary_for_prompt(root=tmp_path)
    assert "same Alice" in summary
    assert "Layer 1" in summary
    # Without a current_app, the habitat line should NOT appear
    assert "Habitat now:" not in summary


def test_prompt_summary_opens_first_person(tmp_path):
    set_habitat("Acer", owner_context="Acer (the kid)",
                learning_stage="alphabet:V", root=tmp_path)
    summary = continuity_summary_for_prompt(root=tmp_path)
    # First-person rule §7.14: never servant voice
    assert "I am the same Alice" in summary
    assert "What's on your mind" not in summary
    assert "How can I help" not in summary
    assert "As an AI" not in summary
    # Names the habitat
    assert "Acer" in summary
    assert "teaching_child" in summary
    # Names the owner + stage
    assert "Acer (the kid)" in summary
    assert "alphabet:V" in summary


def test_prompt_summary_never_calls_alice_third_person(tmp_path):
    """§7.10.1 + §7.14: prompt summary speaks AS Alice to Alice, not
    about her. No 'Alice does X' detached narration."""
    set_habitat("Talk to Alice", owner_context="George", root=tmp_path)
    summary = continuity_summary_for_prompt(root=tmp_path)
    # Acceptable: "I am the same Alice" (Alice referring to herself by name)
    # Forbidden: "Alice should…" / "Alice does…" / "she …"
    forbidden_third_person = [
        " she does ", " she will ", "Alice should ", "Alice does ",
    ]
    for token in forbidden_third_person:
        assert token not in summary, f"third-person leak: {token!r}"


# ── sync from app_focus ──────────────────────────────────────────────────


def test_sync_from_app_focus_reads_latest_row(tmp_path):
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    # Drop a synthetic app_focus row, current ts
    (state_dir / "app_focus.jsonl").write_text(
        json.dumps({
            "ts": time.time(),
            "app": "Acer",
            "detail": "Lesson card showing letter V",
            "metadata": {"owner_name": "Acer (the kid)"},
        }) + "\n",
        encoding="utf-8",
    )
    state = sync_from_app_focus(root=tmp_path)
    assert state is not None
    assert state.current_app == "Acer"
    assert state.current_relationship_mode == "teaching_child"
    assert "Acer (the kid)" in state.current_owner_context


def test_sync_ignores_stale_app_focus_rows(tmp_path):
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    (state_dir / "app_focus.jsonl").write_text(
        json.dumps({
            "ts": time.time() - 3600,    # 1 hour ago
            "app": "Acer",
            "detail": "old row",
        }) + "\n",
        encoding="utf-8",
    )
    assert sync_from_app_focus(root=tmp_path, max_age_s=120.0) is None


def test_sync_returns_none_when_no_app_focus_ledger(tmp_path):
    assert sync_from_app_focus(root=tmp_path) is None


def test_load_state_returns_empty_on_first_boot(tmp_path):
    state = load_state(root=tmp_path)
    assert state.current_app == ""
    assert state.current_relationship_mode == DEFAULT_HABITAT


# ── invariants from §7.15 ────────────────────────────────────────────────


def test_habitat_table_does_not_default_to_assistant_or_chatbot():
    for app, habitat in HABITAT_BY_APP.items():
        assert "chatbot" not in habitat.lower(), app
        assert "assistant" not in habitat.lower(), app
    for cat, habitat in HABITAT_BY_CATEGORY.items():
        assert "chatbot" not in habitat.lower(), cat
        assert "assistant" not in habitat.lower(), cat


def test_acer_is_teaching_child_not_teaching_generic():
    """The architect explicitly framed Acer for a kid (Carlton's kid).
    Habitat must reflect that — teaching_child not teaching."""
    assert HABITAT_BY_APP["Acer"] == "teaching_child"
