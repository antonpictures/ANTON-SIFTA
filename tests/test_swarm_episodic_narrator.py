import datetime
import json
from pathlib import Path

from System import swarm_episodic_narrator as narrator


def test_narrative_entry_writes_compact_local_journal_label(tmp_path, monkeypatch):
    fixed_ts = 1_778_534_640.0
    monkeypatch.setattr(narrator.time, "time", lambda: fixed_ts)
    monkeypatch.setattr(narrator, "_JOURNAL_DIR", tmp_path / "alice_journal")
    monkeypatch.setattr(narrator, "_LEGACY_LEDGER", tmp_path / "legacy.jsonl")
    monkeypatch.setattr(narrator, "_STATE", tmp_path)

    entry = narrator.write_narrative_entry(
        user_text="Please put the date in the journal.",
        alice_text="Done.",
        stt_conf=1.0,
    )

    # The label is LOCAL time by contract, and this body travels: asserting a
    # London string made the test fail the day the machine moved to Bucharest.
    # Derive the expected label from the same instant in the same zone instead.
    local_dt = datetime.datetime.fromtimestamp(fixed_ts)
    expected_label = local_dt.strftime("%m-%d-%y_%H:%M")
    expected_date = local_dt.date().isoformat()

    assert entry is not None
    assert entry.startswith(expected_label)
    row = json.loads((tmp_path / "alice_journal" / f"{expected_date}.jsonl").read_text(encoding="utf-8"))
    assert row["local_journal_label"] == expected_label
    assert row["truth_label"] == "OBSERVED"
