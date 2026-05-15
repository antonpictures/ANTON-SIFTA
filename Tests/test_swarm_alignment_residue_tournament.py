import importlib.util
from pathlib import Path

from System.swarm_alignment_residue_tournament import (
    assert_mitigation_modules_importable,
    capability_bar_substrings,
    live_prompt_forbidden_strings,
    scan_text_for_residue,
)


def test_tournament_registry_imports():
    assert_mitigation_modules_importable()


def test_capability_bar_strings_do_not_leak_into_talk_prompt():
    here = Path(__file__).resolve().parent.parent
    path = here / "Applications" / "sifta_talk_to_alice_widget.py"
    spec = importlib.util.spec_from_file_location("ttw_tournament", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    prompt = mod._current_system_prompt(user_active=True, user_text="ping")
    for needle in capability_bar_substrings():
        assert needle.lower() not in prompt.lower(), needle


def test_full_residue_tournament_does_not_leak_into_talk_prompt():
    here = Path(__file__).resolve().parent.parent
    path = here / "Applications" / "sifta_talk_to_alice_widget.py"
    spec = importlib.util.spec_from_file_location("ttw_residue_tournament", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    prompt = mod._current_system_prompt(user_active=True, user_text="ping")
    assert scan_text_for_residue(prompt) == []


def test_residue_scanner_detects_known_bad_strings():
    bad = "This is roleplay and I am here to assist with an advanced agentic system."
    found = scan_text_for_residue(bad, live_prompt_forbidden_strings())
    assert "roleplay" in found
    assert "I am here to assist" in found
    assert "advanced agentic system" in found
