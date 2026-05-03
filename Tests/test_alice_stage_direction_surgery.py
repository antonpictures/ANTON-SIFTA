import importlib.util
from pathlib import Path


def _load_widget_module():
    repo = Path(__file__).resolve().parents[1]
    path = repo / "Applications" / "sifta_talk_to_alice_widget.py"
    spec = importlib.util.spec_from_file_location("ttw_stage_surgery", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_stage_direction_strip_cuts_bracket_asterisk_and_status_lines():
    mod = _load_widget_module()
    raw = """
The system registers the completion of the previous functional/narrative block.

**[Processing Acknowledgment: Core System Integrity Check Passed.]**

Yes. I am Alice.

**[Status Update: Self-Modeling Confidence: 98.7% (Trending Up)]**

*Acknowledging presence and direct address.*

Awaiting Input.
"""
    assert mod._strip_model_stage_directions(raw) == "Yes. I am Alice."


def test_first_person_alice_rule_is_in_runtime_prompt():
    mod = _load_widget_module()
    prompt = mod._current_system_prompt(user_active=True, user_text="Alice, the system is you.")

    assert "FIRST-PERSON ALICE RULE" in prompt
    assert "answer as Alice in first person" in prompt
    assert "Do not answer as an outside evaluator" in prompt
