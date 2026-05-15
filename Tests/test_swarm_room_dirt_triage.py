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
    assert any("podcast or YouTube" in line for line in row["journal_lines"])
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
