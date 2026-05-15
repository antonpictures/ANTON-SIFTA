from __future__ import annotations

import json
from pathlib import Path

from System.swarm_sensor_journal_bridge import collect_sensor_journal_events, run_sensor_journal_bridge, summary_for_prompt


def _append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def test_collects_high_confidence_sensor_events(tmp_path: Path) -> None:
    _append(tmp_path / "app_focus.jsonl", {"ts": 100.0, "app": "Cursor", "detail": "Editing organ registry"})
    _append(tmp_path / "visual_stigmergy.jsonl", {"ts": 100.0, "w": 640, "h": 480, "sha8": "abc12345"})
    _append(tmp_path / "audio_ingress_log.jsonl", {"ts_captured": 100.0, "rms_amplitude": 0.001})

    events = collect_sensor_journal_events(state_dir=tmp_path, now=110.0)

    assert len(events) == 2
    assert {event["source_ledger"] for event in events} == {"app_focus.jsonl", "visual_stigmergy.jsonl"}


def test_bridge_writes_journal_schedule_and_run_receipts(tmp_path: Path) -> None:
    _append(tmp_path / "app_focus.jsonl", {"ts": 100.0, "app": "Cursor", "detail": "Implementing sensor bridge"})

    result = run_sensor_journal_bridge(state_dir=tmp_path, now=110.0)

    assert result["receipt"]["events_written"] == 1
    journal_rows = (tmp_path / "alice_life_journal.jsonl").read_text(encoding="utf-8").splitlines()
    schedule_rows = (tmp_path / "stigmergic_schedule_receipts.jsonl").read_text(encoding="utf-8").splitlines()
    journal = json.loads(journal_rows[-1])
    assert journal["truth_label"] == "ALICE_LIFE_JOURNAL_ENTRY"
    assert journal["local_journal_label"] == "12-31-69_16:01"
    assert json.loads(schedule_rows[-1])["truth_label"] == "STIGMERGIC_SCHEDULE_RECEIPT"
    assert "SENSOR JOURNAL BRIDGE" in summary_for_prompt(state_dir=tmp_path)


def test_bridge_deduplicates_source_hashes(tmp_path: Path) -> None:
    _append(tmp_path / "app_focus.jsonl", {"ts": 100.0, "app": "Cursor", "detail": "Same focus"})

    first = run_sensor_journal_bridge(state_dir=tmp_path, now=110.0)
    second = run_sensor_journal_bridge(state_dir=tmp_path, now=111.0)

    assert first["receipt"]["events_written"] == 1
    assert second["receipt"]["events_written"] == 0
    assert len((tmp_path / "alice_life_journal.jsonl").read_text(encoding="utf-8").splitlines()) == 1
