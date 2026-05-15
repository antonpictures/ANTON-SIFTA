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

    assert entry is not None
    assert entry.startswith("05-11-26_14:24")
    row = json.loads((tmp_path / "alice_journal" / "2026-05-11.jsonl").read_text(encoding="utf-8"))
    assert row["local_journal_label"] == "05-11-26_14:24"
    assert row["truth_label"] == "OBSERVED"
