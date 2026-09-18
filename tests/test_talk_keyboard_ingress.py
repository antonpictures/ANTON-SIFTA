import ast
import copy
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


ROOT = Path(__file__).parents[1]


def test_keyboard_gate_is_wired_before_dialogue_promotion():
    source = (ROOT / "Applications/sifta_talk_to_alice_widget.py").read_text()
    tree = ast.parse(source)
    function = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                    and node.name == "_on_stt_done")
    calls = [node for node in ast.walk(function) if isinstance(node, ast.Call)]
    names = [node.func.id for node in calls if isinstance(node.func, ast.Name)]
    assert "classify_keyboard_audio" in names
    append_lines = [node for node in ast.walk(function) if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "_append_user_line"]
    classify_line = next(node.lineno for node in calls
                         if isinstance(node.func, ast.Name)
                         and node.func.id == "classify_keyboard_audio")
    assert append_lines
    assert all(node.lineno > classify_line for node in append_lines)


def test_keyboard_gate_is_never_used_for_typed_turns():
    source = (ROOT / "Applications/sifta_talk_to_alice_widget.py").read_text()
    tree = ast.parse(source)
    function = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                    and node.name == "_on_stt_done")
    gate_call = next(node for node in ast.walk(function) if isinstance(node, ast.Call)
                     and isinstance(node.func, ast.Name)
                     and node.func.id == "classify_keyboard_audio")
    guard = next(node for node in ast.walk(function) if isinstance(node, ast.If)
                 and any(isinstance(child, ast.Call)
                         and isinstance(child.func, ast.Name)
                         and child.func.id == "classify_keyboard_audio"
                         for child in ast.walk(node)))
    assert isinstance(guard.test, ast.BoolOp)
    assert isinstance(guard.test.values[0], ast.UnaryOp)
    assert isinstance(guard.test.values[0].op, ast.Not)
    assert isinstance(guard.test.values[0].operand, ast.Name)
    assert guard.test.values[0].operand.id == "_typed_turn"
    assert gate_call.lineno > guard.lineno


def function_node(name):
    tree = ast.parse((ROOT / "Applications/sifta_talk_to_alice_widget.py").read_text())
    return copy.deepcopy(next(node for node in ast.walk(tree)
                              if isinstance(node, ast.FunctionDef) and node.name == name))


def compile_method(node, namespace):
    # Execute the real source without importing/booting the entire Qt desktop.
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), node], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), "<talk-source-fixture>", "exec"), namespace)
    return namespace[node.name]


@pytest.mark.parametrize("typed,route,admitted", [(True, "ambient_keyboard", True),
    (False, "ambient_keyboard", False), (False, "uncertain", True)])
def test_executed_callback_admission(monkeypatch, typed, route, admitted):
    node = function_node("_on_stt_done")
    # Stop at the first downstream branch; exercise the entire admission prefix.
    cut = next(i for i, child in enumerate(node.body) if isinstance(child, ast.If)
               and isinstance(child.test, ast.UnaryOp)
               and isinstance(child.test.operand, ast.Name)
               and child.test.operand.id == "typed_turn")
    node.body = node.body[:cut] + [ast.Return(value=ast.Constant("admitted"))]
    classify = Mock(return_value={"route": route})
    monkeypatch.setitem(sys.modules, "System.swarm_keyboard_acoustic_gate", SimpleNamespace(
        classify_keyboard_audio=classify, write_keyboard_receipt=Mock(return_value={"receipt_id": "test"})))
    method = compile_method(node, {"_LAST_UTTERANCE_AUDIO": [b"clip"], "time": time,
                                   "_state_root": lambda: ROOT})
    widget = SimpleNamespace(_pending_acoustic_fingerprint={"clip": "a"}, _busy=True,
        _typed_input_events=[], _append_system_line=Mock(), _return_to_listening=Mock())
    assert (method(widget, "thank you", 0.2, typed_turn=typed) == "admitted") is admitted
    assert classify.call_count == (0 if typed else 1)
    assert widget._return_to_listening.call_count == (0 if admitted else 1)
    if typed:
        assert widget._pending_acoustic_fingerprint == {"clip": "a"}


def test_callback_uses_the_completed_clip_context_not_shared_last_audio(monkeypatch):
    node = function_node("_on_stt_done")
    cut = next(i for i, child in enumerate(node.body) if isinstance(child, ast.If)
               and isinstance(child.test, ast.UnaryOp)
               and isinstance(child.test.operand, ast.Name)
               and child.test.operand.id == "typed_turn")
    node.body = node.body[:cut] + [ast.Return(value=ast.Constant("admitted"))]
    classify = Mock(return_value={"route": "uncertain"})
    monkeypatch.setitem(sys.modules, "System.swarm_keyboard_acoustic_gate", SimpleNamespace(
        classify_keyboard_audio=classify, write_keyboard_receipt=Mock()))
    method = compile_method(node, {"_LAST_UTTERANCE_AUDIO": ["clip-B"], "time": time,
                                   "_state_root": lambda: ROOT})
    context = {"audio": "clip-A", "typed_events": ((98.0, 1),),
               "physical_key_events": (98.2,), "capture_start_ts": 98.0,
               "capture_end_ts": 99.0, "utterance_id": "A",
               "source": "mic-A", "session": "owner", "clock": "wall"}
    widget = SimpleNamespace(_pending_acoustic_fingerprint={}, _busy=True,
        _typed_input_events=[], _append_system_line=Mock(), _return_to_listening=Mock())
    assert method(widget, "thank you", 0.2, typed_turn=False,
                  acoustic_context=context) == "admitted"
    assert classify.call_args.args[0] == "clip-A"
    assert classify.call_args.kwargs["utterance_id"] == "A"
    assert classify.call_args.kwargs["physical_key_events"] == (98.2,)


def test_deferred_brain_callback_keeps_fingerprint():
    node = function_node("_on_stt_done")
    call = next(child for child in node.body if isinstance(child, ast.Expr)
                and isinstance(child.value, ast.Call)
                and isinstance(child.value.func, ast.Attribute)
                and child.value.func.attr == "singleShot")
    callbacks = []
    widget = SimpleNamespace(_start_brain=Mock())
    namespace = dict(self=widget, text="speech", conf=.4, image_path=None, typed_turn=False,
        _acoustic_fingerprint={"clip": "a"}, QTimer=SimpleNamespace(singleShot=lambda ms, cb: callbacks.append(cb)))
    exec(compile(ast.Module(body=[call], type_ignores=[]), "<queued-source>", "exec"), namespace)
    namespace["_acoustic_fingerprint"] = {"clip": "b"}
    callbacks[0]()
    assert widget._start_brain.call_args.kwargs["acoustic_fingerprint"] == {"clip": "a"}


@pytest.mark.parametrize("typed,explicit,expected", [(False, {"clip": "a"}, {"clip": "a"}),
    (False, None, {"clip": "b"}), (True, None, {})])
def test_brain_initializes_fingerprint(typed, explicit, expected):
    node = function_node("_start_brain")
    cut = next(i for i, child in enumerate(node.body) if isinstance(child, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == "text" for t in child.targets))
    node.body = node.body[:cut] + [ast.Return(value=ast.Name(id="_acoustic_fingerprint", ctx=ast.Load()))]
    method = compile_method(node, {"_active_web_turn_context": lambda: False})
    widget = SimpleNamespace(_pending_acoustic_fingerprint={"clip": "b"})
    assert method(widget, "speech", typed_turn=typed, acoustic_fingerprint=explicit) == expected
    if typed or explicit is not None:
        assert widget._pending_acoustic_fingerprint == {"clip": "b"}


def test_busy_voice_queue_preserves_then_drains_clip():
    now = time.time()
    clip = object()
    node = function_node("_process_deferred_utterance_if_any")
    method = compile_method(node, {"time": time, "_DEFERRED_UTTERANCE_MAX_AGE_S": 60,
        "_should_suppress_voice_drop_owner_nag": lambda self: True,
        "TalkToAliceWidget": SimpleNamespace(_stt_cooldown_remaining=lambda self: 0)})
    widget = SimpleNamespace(_deferred_utterance_audio=clip, _deferred_utterance_ts=now,
        _busy=True, _ear_intentional_listen=True, _on_utterance=Mock(), set_status=Mock())
    assert method(widget) is False
    assert widget._deferred_utterance_audio is clip
    assert widget._deferred_utterance_ts == now
    widget._busy = False
    assert method(widget) is True
    widget._on_utterance.assert_called_once_with(clip)
    assert method(widget) is False
