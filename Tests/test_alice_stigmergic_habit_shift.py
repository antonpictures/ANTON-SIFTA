import json
import sys
import types
from pathlib import Path

from System import alice_stigmergic_habit_shift as mod


def test_dominant_organ_bias_is_field_derived_not_ace_hardcoded(tmp_path, monkeypatch):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    monkeypatch.setattr(mod, "_STATE", state)
    monkeypatch.setattr(
        mod,
        "_ranked_focus_entry",
        lambda: {"app": "Some Other Organ", "attention_rank_score": 0.2},
    )
    monkeypatch.setattr(
        mod,
        "get_app_health",
        lambda app, limit=10: [{"skills": ["phonics", "lesson_engine"]}],
    )
    (state / "sifta_desktop_app_state.json").write_text(
        json.dumps({"active_app": "Reading Lab", "open_apps": ["Reading Lab"]}),
        encoding="utf-8",
    )

    bias = mod.get_dominant_organ_bias()
    prompt = mod.get_current_habit_bias_for_prompt()

    assert bias["dominant_organ"] == "Reading Lab"
    assert bias["suggested_habit_shift"]["timing"] == "patient turn-taking from the app health trace"
    assert "Reading Lab" in prompt
    assert "field-derived bias, not a hardcoded app mode" in prompt
    assert "Ace" not in prompt


def test_no_active_receipt_returns_no_bias(tmp_path, monkeypatch):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    monkeypatch.setattr(mod, "_STATE", state)
    monkeypatch.setattr(mod, "_ranked_focus_entry", lambda: {})

    assert mod.get_current_habit_bias_for_prompt() == ""


def test_organ_acknowledgment_uses_skills_not_app_name_branch(tmp_path, monkeypatch):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    monkeypatch.setattr(mod, "_STATE", state)
    monkeypatch.setattr(mod, "_ranked_focus_entry", lambda: {})
    monkeypatch.setattr(
        mod,
        "get_app_health",
        lambda app, limit=10: [{"skills": ["play_turns", "reading_lesson"]}],
    )
    (state / "sifta_desktop_app_state.json").write_text(
        json.dumps({"active_app": "Reading Lab", "open_apps": ["Reading Lab"]}),
        encoding="utf-8",
    )
    monkeypatch.setitem(
        sys.modules,
        "System.swarm_alice_self",
        types.SimpleNamespace(assess_my_thermodynamic_risk=lambda: {"risk_level": "low"}),
    )
    monkeypatch.setitem(
        sys.modules,
        "System.swarm_processing_thermodynamic_gate",
        types.SimpleNamespace(prompt_context=lambda: ""),
    )

    line = mod.generate_organ_acknowledgment()

    assert line == "Oh, you want to play Reading Lab. I see you."
    assert "Ace" not in line
