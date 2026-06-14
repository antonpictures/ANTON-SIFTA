from __future__ import annotations

import json


def test_talk_backchannel_writes_relational_steering_receipt(tmp_path, monkeypatch):
    from Applications import sifta_talk_to_alice_widget as talk
    from System import swarm_face_detection

    class Presence:
        stale = False
        audience = "architect"
        faces_detected = 1
        max_confidence = 0.91
        age_s = 2.0
        source = "test"

    monkeypatch.setattr(talk, "_STATE_DIR", tmp_path)
    monkeypatch.setattr(swarm_face_detection, "current_presence_safe", lambda: Presence())

    result = talk._relational_steering_for_backchannel("ok", 1.0, source="typed")

    assert result is not None
    assert result.route == "RELATIONAL_ACK"
    ledger = tmp_path / "relational_steering.jsonl"
    assert ledger.exists()
    row = json.loads(ledger.read_text(encoding="utf-8").splitlines()[-1])
    assert row["truth_label"] == "SIFTA_RELATIONAL_STEERING_V1"
    assert row["route"] == "RELATIONAL_ACK"
    assert row["source"] == "typed"
    assert row["signals"]["owner_face_present"] is True
