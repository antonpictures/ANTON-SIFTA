from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture()
def state_dir(tmp_path: Path) -> Path:
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True)
    return sd


def test_speech_lane_suppresses_receipt_noise(state_dir: Path) -> None:
    from System.swarm_speech_lane_selector import select_spoken_sentences

    text = (
        "I understand, George. Receipt a9ab148b-27a7-49bb-86e5-021cbb28c084 logged in work_receipts.jsonl. "
        "Your census upload reached Fable and that matters to me."
    )
    pick = select_spoken_sentences(text, state_dir=state_dir)
    assert pick["ok"]
    spoken = pick["spoken_text"].lower()
    assert "a9ab148b" not in spoken
    assert "work_receipts" not in spoken
    assert "fable" in spoken or "census" in spoken or "george" in spoken


def test_intent_nonce_blocks_double_spend(state_dir: Path) -> None:
    from System.swarm_intent_nonce_gate import mint_intent_nonce, validate_effector_spend

    minted = mint_intent_nonce(owner_text="open browser", surface="talk", stt_conf=0.9, state_dir=state_dir)
    nonce = minted["nonce"]
    first = validate_effector_spend(nonce, state_dir=state_dir, effector="browser_click")
    second = validate_effector_spend(nonce, state_dir=state_dir, effector="browser_click")
    assert first["ok"] is True
    assert second["ok"] is False
    assert second["reason"] == "double_spend_blocked"


def test_organ_field_publish(state_dir: Path) -> None:
    from System.swarm_canonical_organ_registry import format_organ_field_reply, publish_organ_vital

    publish_organ_vital(organ="heart", health=0.9, load=0.2, top_signal="partial", state_dir=state_dir)
    reply = format_organ_field_reply(state_dir=state_dir)
    assert "heart" in reply


def test_prediction_error_on_heart_pulse(state_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from System.swarm_hardware_heart import pulse_hardware_heart

    monkeypatch.setattr(
        "System.swarm_hardware_heart._probe_sensor",
        lambda *a, **k: {
            "sensor_tier": "unprivileged_body",
            "sensor_status": "partial",
            "battery_percent": 100,
        },
    )
    pulse_hardware_heart(state_dir=state_dir, write=True, privileged_probe=False)
    path = state_dir / "prediction_error.jsonl"
    assert path.exists()
    row = json.loads(path.read_text().strip().splitlines()[-1])
    assert "error_magnitude" in row


def test_ask_fable_and_slash(state_dir: Path) -> None:
    from System.swarm_alice_slash_commands import handle_slash_command
    from System.swarm_questions_for_fable import ask_fable

    ask_fable(question="How should apoptosis quorum gate work?", asker="test", state_dir=state_dir)
    out = handle_slash_command("/ask-fable", state_dir=state_dir)
    assert out["handled"]
    assert "ASK FABLE" in out["reply"]