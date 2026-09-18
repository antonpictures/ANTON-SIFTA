import numpy as np

from System.swarm_keyboard_acoustic_gate import classify_keyboard_audio


def _clicks(sample_rate=16_000, seconds=1.0):
    rng = np.random.default_rng(7)
    audio = np.zeros(int(sample_rate * seconds), dtype=np.float32)
    for start in range(800, audio.size - 500, 1400):
        length = 180
        audio[start:start + length] += rng.normal(0, 0.7, length).astype(np.float32) * np.exp(-np.linspace(0, 8, length))
    return audio


def _speech(sample_rate=16_000, seconds=1.0):
    t = np.arange(int(sample_rate * seconds), dtype=np.float32) / sample_rate
    envelope = 0.55 + 0.45 * np.sin(2 * np.pi * 3.0 * t) ** 2
    return (envelope * (0.5 * np.sin(2 * np.pi * 130 * t) + 0.2 * np.sin(2 * np.pi * 260 * t))).astype(np.float32)


def test_clicks_with_recent_edits_route_to_ambient_keyboard():
    decision = classify_keyboard_audio(_clicks(), typed_events=[(98.0, 1), (99.0, 2)], captured_at=100.0)
    assert decision["route"] == "ambient_keyboard"
    assert decision["editing"]["event_count"] == 2


def test_speech_with_typing_signal_is_not_suppressed():
    decision = classify_keyboard_audio(_speech(), typed_events=[(98.0, 1), (99.0, 2)], captured_at=100.0)
    assert decision["route"] == "uncertain"


def test_clicks_without_recent_edit_signal_remain_uncertain():
    decision = classify_keyboard_audio(_clicks(), typed_events=[(80.0, 1)], captured_at=100.0)
    assert decision["route"] == "uncertain"


def test_live_capture_requires_physical_keys_and_keeps_provenance():
    decision = classify_keyboard_audio(
        _clicks(),
        typed_events=[(98.0, 20), (99.0, 21)],
        physical_key_events=[98.4, 99.2],
        captured_at=100.0,
        utterance_id="u-1",
        source="talk_to_alice_microphone",
        session="owner_local",
        clock="wall",
        capture_start_ts=98.0,
        capture_end_ts=100.0,
    )
    assert decision["route"] == "ambient_keyboard"
    assert decision["physical_keys"]["event_count"] == 2
    assert decision["utterance_id"] == "u-1"
    assert decision["clock"] == "wall"


def test_live_capture_does_not_treat_paste_as_physical_keyboard():
    decision = classify_keyboard_audio(
        _clicks(),
        typed_events=[(98.0, 1), (99.0, 80)],
        physical_key_events=[],
        captured_at=100.0,
        capture_start_ts=98.0,
        capture_end_ts=100.0,
    )
    assert decision["route"] == "uncertain"
    assert decision["physical_keys"]["typing_signal"] is False


def test_invalid_capture_window_stays_uncertain_and_json_safe():
    decision = classify_keyboard_audio(
        _clicks(), physical_key_events=[98.0, 99.0], captured_at=100.0,
        capture_start_ts=float("nan"), capture_end_ts=99.0,
    )
    assert decision["route"] == "uncertain"
    assert decision["provenance_valid"] is False
    assert decision["capture_start_ts"] is None
    assert decision["heuristic_score"] >= 0.0


def test_receipt_write_failure_is_explicit(tmp_path, monkeypatch):
    from System import swarm_keyboard_acoustic_gate as gate

    monkeypatch.setattr(gate.Path, "mkdir", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("blocked")))
    result = gate.write_keyboard_receipt({"route": "uncertain"}, state_dir=tmp_path)
    assert result["ok"] is False
    assert result["receipt_id"] is None
