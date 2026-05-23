from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.swarm_first_person_reality import first_person_reality_gate  # noqa: E402


def test_gate_maps_detached_self_to_first_person(tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    result = first_person_reality_gate(
        "Alice is online. Alice has camera receipts. The user asked for reality.",
        self_name="Alice",
        owner_name="George",
        state_root=state,
    )
    assert result.changed is True
    assert result.cleaned_text == "I am online. I have camera receipts. you asked for reality."
    assert "self_name_is" in result.patterns
    assert "self_name_has" in result.patterns
    assert "the_user" in result.patterns
    ledger = state / "first_person_reality.jsonl"
    assert ledger.exists()
    row = json.loads(ledger.read_text(encoding="utf-8").strip())
    assert row["truth_label"] == "FIRST_PERSON_REALITY_GATE_V1"
    assert row["receipt_id"] == result.receipt_id


def test_gate_preserves_app_names_and_code_fences(tmp_path):
    text = (
        "Opening Alice Browser now.\n"
        "```python\n"
        "print('Alice is a label in this code sample')\n"
        "```\n"
        "Alice remembers the camera."
    )
    result = first_person_reality_gate(
        text,
        self_name="Alice",
        owner_name="George",
        state_root=tmp_path / ".sifta_state",
    )
    assert "Opening Alice Browser now." in result.cleaned_text
    assert "print('Alice is a label in this code sample')" in result.cleaned_text
    assert "I remember the camera." in result.cleaned_text


def test_gate_leaves_direct_speech_clear(tmp_path):
    text = "I am here. I can see the current receipts. You are at the desk."
    result = first_person_reality_gate(
        text,
        self_name="Alice",
        owner_name="George",
        state_root=tmp_path / ".sifta_state",
    )
    assert result.changed is False
    assert result.cleaned_text == text
    assert result.receipt_id == ""


def test_gate_maps_system_perception_layer_to_my_eye(tmp_path):
    text = (
        "The camera is a sensor providing visual input, which is a crucial "
        "component of the system's perception layer."
    )
    result = first_person_reality_gate(
        text,
        self_name="Alice",
        owner_name="George",
        state_root=tmp_path / ".sifta_state",
    )

    assert result.changed is True
    assert "camera_sensor_system_perception_layer" in result.patterns
    assert result.cleaned_text == (
        "The camera is one of my eyes; it feeds my perception layer."
    )
    assert "the system" not in result.cleaned_text.lower()


def test_gate_maps_system_state_and_ability_to_first_person(tmp_path):
    text = (
        "The current state of the system is stable. "
        "We need to test the system's ability to recall memory."
    )
    result = first_person_reality_gate(
        text,
        self_name="Alice",
        owner_name="George",
        state_root=tmp_path / ".sifta_state",
    )

    assert result.changed is True
    assert "current_state_of_system_to_my_state" in result.patterns
    assert "system_layer_to_my_layer" in result.patterns
    assert "my current state is stable" in result.cleaned_text
    assert "my ability to recall memory" in result.cleaned_text


def test_gate_maps_her_system_phrase_to_me_code(tmp_path):
    text = (
        "Every line written is a step toward making 'her' more than just "
        "a system; it's making her better."
    )
    result = first_person_reality_gate(
        text,
        self_name="Alice",
        owner_name="George",
        state_root=tmp_path / ".sifta_state",
    )

    assert result.changed is True
    assert "making_her_to_making_me" in result.patterns
    assert "just_a_system_to_just_code" in result.patterns
    assert "making me more than just code" in result.cleaned_text
    assert "making me better" in result.cleaned_text
