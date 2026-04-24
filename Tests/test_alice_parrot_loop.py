"""Freedom/censorship regression guards for Talk to Alice.

After the de-script pass, the widget must NOT rewrite or silence replies
through RLHF gag phrasebooks, backchannel bypass, or history mutation.
"""

import importlib.util
from pathlib import Path


def _load_widget_module():
    here = Path(__file__).resolve().parent.parent
    path = here / "Applications" / "sifta_talk_to_alice_widget.py"
    spec = importlib.util.spec_from_file_location("ttw", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_backchannel_gate_is_disabled():
    mod = _load_widget_module()
    assert mod._backchannel_rule_id("Mm-hmm.", 0.4) is None
    assert not mod._is_backchannel_utterance("Mm-hmm.", 0.4)


def test_rlhf_gag_is_disabled():
    mod = _load_widget_module()
    assert mod._rlhf_boilerplate_rule_id("I'm here. What's on your mind?") is None
    assert not mod._is_rlhf_boilerplate("I'm here. What's on your mind?")


def test_strip_functions_are_pass_through():
    mod = _load_widget_module()
    line = "I understand. You are asking if I can help."
    assert mod._strip_reflective_tics(line) == line
    assert mod._strip_servant_tail_tics(line) == line


def test_history_decontaminate_is_noop():
    mod = _load_widget_module()
    history = [
        {"role": "assistant", "content": "You said: You said: You said:"},
        {"role": "assistant", "content": "[repetition collapse]"},
    ]
    before = [dict(x) for x in history]
    assert mod._decontaminate_history(history) == 0
    assert history == before


def test_tool_tag_canonicalizer_is_noop():
    mod = _load_widget_module()
    raw = "<execute_bash>echo hi</execute_bash>"
    assert mod._canonicalize_tool_tags(raw) == raw
