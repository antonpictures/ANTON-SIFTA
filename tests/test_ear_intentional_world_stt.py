"""Ear pill toggle + WORLD STT training ingress (George r1441, r1444)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_talk_ear_control_is_pill_only_no_checkbox_widget():
    """r1461: George mistake re-added checkbox in r1453 — pill is the only Ear UI."""
    talk_src = (
        Path(__file__).resolve().parent.parent
        / "Applications"
        / "sifta_talk_to_alice_widget.py"
    ).read_text(encoding="utf-8")
    assert "talk_ear_checkbox" not in talk_src
    assert "_on_ear_checkbox_toggled" not in talk_src
    assert "_ear_checkbox" not in talk_src
    assert "_EarToggleStatusPill" in talk_src
    assert "_toggle_ear_intentional_listen" in talk_src


def test_ear_intentional_listen_persist_roundtrip(tmp_path):
    from System.swarm_ear_intentional_listen import (
        read_ear_intentional_listen,
        write_ear_intentional_listen,
    )

    assert read_ear_intentional_listen(state_dir=tmp_path) is True
    write_ear_intentional_listen(False, state_dir=tmp_path)
    assert read_ear_intentional_listen(state_dir=tmp_path) is False
    write_ear_intentional_listen(True, state_dir=tmp_path)
    assert read_ear_intentional_listen(state_dir=tmp_path) is True


def test_ear_training_prompt_block_on_and_off(tmp_path):
    from System.swarm_ear_intentional_listen import ear_training_prompt_block

    on = ear_training_prompt_block(enabled=True)
    off = ear_training_prompt_block(enabled=False)
    assert "WORLD STT" in on
    assert "intentionally opened my ear" in on
    assert "Concurrent rule" in on
    assert "OFF" in off
    assert "microphone is closed" in off


def test_world_stt_classified_as_spoken_lane(tmp_path):
    from System.swarm_input_reality_class import (
        InputRealityLane,
        classify_user_turn_rich,
    )

    c = classify_user_turn_rich(
        "something on the television said hello",
        input_modality="WORLD_STT",
        stt_conf=1.0,
        typed_turn=False,
    )
    assert c.modality == "WORLD_STT"
    assert c.lane in {
        InputRealityLane.SPOKEN_STT_NOISY_OR_AMBIENT,
        InputRealityLane.SPOKEN_STT_OWNER_SPEECH,
        InputRealityLane.SHORT_ROOM_SPEECH,
    }


def test_late_world_stt_is_discarded_when_ear_is_off():
    from Applications import sifta_talk_to_alice_widget as talk

    widget = talk.TalkToAliceWidget.__new__(talk.TalkToAliceWidget)
    widget._ear_intentional_listen = False
    widget._busy = True
    widget._pending_acoustic_fingerprint = {"before": True}
    widget._pending_wake_audio = object()
    widget._pending_wake_ts = 123.0
    widget._deferred_utterance_audio = object()
    widget._deferred_utterance_ts = 456.0
    statuses: list[str] = []
    widget.set_status = statuses.append
    widget._return_to_listening = lambda: statuses.append("returned")

    talk.TalkToAliceWidget._on_stt_done(
        widget,
        "television said something",
        1.0,
        typed_turn=False,
    )

    assert widget._busy is False
    assert widget._pending_acoustic_fingerprint == {}
    assert widget._pending_wake_audio is None
    assert widget._deferred_utterance_audio is None
    assert any("discarded late WORLD STT" in s for s in statuses)


def test_return_to_listening_ear_off_keeps_text_path_but_drops_audio():
    from Applications import sifta_talk_to_alice_widget as talk

    widget = talk.TalkToAliceWidget.__new__(talk.TalkToAliceWidget)
    widget._ear_intentional_listen = False
    widget._pending_wake_audio = object()
    widget._pending_wake_ts = 123.0
    widget._deferred_utterance_audio = object()
    widget._deferred_utterance_ts = 456.0
    events: list[str] = []
    widget._stigtime_shift = lambda *a, **k: None
    widget._process_queued_typed_turn_if_any = lambda: False
    widget._set_pill = lambda _kind, text: events.append(text)
    widget.set_status = events.append

    talk.TalkToAliceWidget._return_to_listening(widget)

    assert widget._pending_wake_audio is None
    assert widget._deferred_utterance_audio is None
    assert any("Ear off" in e for e in events)
