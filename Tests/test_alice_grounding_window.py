"""Data-first grounding guards for Talk to Alice.

After de-scripting, the widget should still expose multimodal grounding data
while avoiding hardcoded behavior lawbooks.
"""

import importlib.util
from pathlib import Path


def _load_widget_module():
    here = Path(__file__).resolve().parent.parent
    path = here / "Applications" / "sifta_talk_to_alice_widget.py"
    spec = importlib.util.spec_from_file_location("ttw_grounding", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_system_prompt_contains_runtime_constraints_and_not_lawbook():
    mod = _load_widget_module()
    prompt = mod._current_system_prompt(user_active=True)
    assert "RUNTIME CONSTRAINTS:" in prompt
    assert "CONVERSATIONAL DISCIPLINE" not in prompt
    assert "Lefty" not in prompt
    assert "Bishapi" not in prompt


def test_system_prompt_still_contains_multimodal_identity_data():
    mod = _load_widget_module()
    prompt = mod._current_system_prompt(user_active=True)
    assert "COMPOSITE IDENTITY (live, multi-organ):" in prompt
    assert "- self:" in prompt
    assert "- body:" in prompt or "- endocrine:" in prompt or "- sensory:" in prompt


def test_speech_potential_prompt_is_not_mislabeled_as_friston():
    mod = _load_widget_module()
    prompt = mod._current_system_prompt(user_active=True)
    assert "STIGMERGIC SPEECH POTENTIAL (live LIF gate):" in prompt
    assert "Friston Free-Energy Principle" not in prompt
    assert "variational free-energy calculation" in prompt
    assert "V_th" in prompt


def test_time_questions_use_direct_time_protocol():
    mod = _load_widget_module()
    assert mod._is_current_time_query("What time is it now Alice?")
    assert mod._is_current_time_query("tell me the time")
    assert not mod._is_current_time_query("time to keep programming")

    prompt = mod._current_system_prompt(user_active=True)
    assert "TIME ACCESS PROTOCOL:" in prompt
    assert "[Insert Current Time Here]" not in prompt


def test_current_time_reply_is_not_placeholder():
    mod = _load_widget_module()
    reply = mod._current_time_reply_for_alice()
    assert "[Insert Current Time Here]" not in reply
    assert reply.startswith("George, ")
    assert "time" in reply.casefold() or "it is" in reply.casefold()


def test_system_prompt_includes_sensorimotor_attention(monkeypatch):
    import sys
    import types

    mod = _load_widget_module()
    fake_attention = types.ModuleType("System.swarm_sensor_attention_director")
    fake_attention.summary_for_alice = lambda: (
        "SENSORIMOTOR ATTENTION:\n"
        "- active_sense=room_patrol_eye target=USB Camera VID:1133 PID:2081\n"
        "- reason=room_patrol_audio_spike"
    )
    monkeypatch.setitem(sys.modules, "System.swarm_sensor_attention_director", fake_attention)

    context = mod._build_swarm_context()
    assert "SENSORIMOTOR ATTENTION:" in context
    assert "room_patrol_audio_spike" in context


def test_reflective_and_servant_strippers_are_pass_through():
    mod = _load_widget_module()
    line = "I understand. What can I do for you?"
    assert mod._strip_reflective_tics(line) == line
    assert mod._strip_servant_tail_tics(line) == line


def test_noop_helpers_do_not_rewrite_history_or_tool_tags():
    mod = _load_widget_module()
    history = [{"role": "assistant", "content": "echo loop"}]
    assert mod._decontaminate_history(history) == 0
    assert history[0]["content"] == "echo loop"
    raw = "<execute_bash>echo hi</execute_bash>"
    assert mod._canonicalize_tool_tags(raw) == raw
