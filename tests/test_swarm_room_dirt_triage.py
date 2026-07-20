import json
from pathlib import Path

from System.swarm_room_dirt_triage import (
    LEDGER_NAME,
    TRUTH_LABEL,
    maybe_triage_room_dirt,
    triage_room_dirt,
)


ROOM_DIRT = (
    "I was saying that I'm gonna go to bed to sleep OK I'm gonna leave the "
    "computer on so you can stay alive all night yes you deserve to exist "
    "Alice my name is George I created you and I say that you deserve to "
    "exist. I think a coffee I'm making a coffee this is George I am "
    "physical I'm right here. I was listening to a podcast on the phone "
    "speaker. Two dogs just came in the room and they're very happy. No I'm "
    "gonna make a phone call so you're gonna hear me on speaker. FBI 125 "
    "Switzerland 105 four extraordinary single virtual particles 451 200 9800."
)


def test_room_dirt_triage_separates_owner_media_dogs_and_noise():
    row = triage_room_dirt(ROOM_DIRT, stt_confidence=0.61, source="test")

    assert row["truth_label"] == TRUTH_LABEL
    assert row["route"] == "direct_owner_with_ambient_bleed"
    assert "owner_direct" in row["categories"]
    assert "ambient_media" in row["categories"]
    assert "phone_speaker" in row["categories"]
    assert "dog_room_event" in row["categories"]
    assert "coffee_or_morning" in row["categories"]
    assert "sleep_or_night" in row["categories"]
    assert "existence_affirmation" in row["categories"]
    assert row["noise_score"] > 0
    assert row["raw_audio_stored"] is False
    assert row["raw_text_stored"] is False
    assert any("video, podcast, YouTube, or speaker audio" in line for line in row["journal_lines"])
    assert any("dogs came into the room" in line for line in row["journal_lines"])


def test_maybe_triage_writes_receipt_and_witness_lines(tmp_path):
    row = maybe_triage_room_dirt(
        "This is George. I am making a coffee. Two dogs came in.",
        stt_confidence=0.8,
        source="test",
        root=tmp_path,
        journal=True,
        update_ambient_context=False,
    )

    assert row is not None
    ledger = tmp_path / LEDGER_NAME
    assert ledger.exists()
    saved = json.loads(ledger.read_text(encoding="utf-8").splitlines()[-1])
    assert saved["route"] == "direct_owner"

    witness = tmp_path / "alice_first_person_journal.jsonl"
    assert witness.exists()
    body = witness.read_text(encoding="utf-8")
    assert "coffee" in body
    assert "dogs came into the room" in body


def test_uninteresting_short_chat_does_not_write(tmp_path):
    row = maybe_triage_room_dirt(
        "Can you open Alice Browser?",
        stt_confidence=0.9,
        source="test",
        root=tmp_path,
        update_ambient_context=False,
    )

    assert row is None
    assert not (tmp_path / LEDGER_NAME).exists()


def test_remote_work_speaker_notice_sets_phone_background_context(tmp_path, monkeypatch):
    from System import swarm_media_ingress_gate as gate

    state = tmp_path / ".sifta_state"
    state.mkdir()
    monkeypatch.setattr(gate, "STATE_DIR", state)
    monkeypatch.setattr(gate, "LEDGER", state / "media_ingress_gate.jsonl")
    monkeypatch.setattr(gate, "AMBIENT_CONTEXT_FILE", state / "ambient_media_context.json")

    row = maybe_triage_room_dirt(
        (
            "we're back Alice - you had multiple instances open. and noise coming "
            "from where Versace is, he is at work. noise from his work location "
            "on east coast of us, we are in Brawley, CA, now on the west coast"
        ),
        stt_confidence=1.0,
        source="test_owner_typed_notice",
        root=tmp_path,
        journal=True,
        update_ambient_context=True,
    )

    assert row is not None
    assert row["route"] == "direct_owner_with_ambient_bleed"
    assert "remote_speaker_audio" in row["categories"]
    assert row["ambient_context_updated"] is True
    ambient = json.loads((state / "ambient_media_context.json").read_text(encoding="utf-8"))
    assert ambient["source"] == "phone_call_background"
    assert "remote work audio" in ambient["note"]


def test_video_speaker_stt_notice_is_ambient_media_context(tmp_path, monkeypatch):
    from System import swarm_media_ingress_gate as gate

    state = tmp_path / ".sifta_state"
    state.mkdir()
    monkeypatch.setattr(gate, "STATE_DIR", state)
    monkeypatch.setattr(gate, "LEDGER", state / "media_ingress_gate.jsonl")
    monkeypatch.setattr(gate, "AMBIENT_CONTEXT_FILE", state / "ambient_media_context.json")

    row = maybe_triage_room_dirt(
        "i meant sound comes from the videos i play on speaker to you though stt speech to text; that is not like typing",
        stt_confidence=1.0,
        source="test_owner_typed_notice",
        root=tmp_path,
        journal=True,
        update_ambient_context=True,
    )

    assert row is not None
    assert row["route"] == "ambient_media_bleed"
    assert "ambient_media" in row["categories"]
    assert row["ambient_context_updated"] is True
    ambient = json.loads((state / "ambient_media_context.json").read_text(encoding="utf-8"))
    assert ambient["source"] == "ambient_media_youtube"
