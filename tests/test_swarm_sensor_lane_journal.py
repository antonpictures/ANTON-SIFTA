import json
from pathlib import Path

from System.swarm_life_journal_consolidator import (
    SENSOR_LANE_JOURNAL_NAME,
    consolidate_sensor_lanes_once,
    format_recent_sensor_lanes_for_prompt,
)


def test_sensor_lane_consolidation_writes_clean_journal_and_receipt(tmp_path: Path) -> None:
    state = tmp_path
    (state / "app_focus.jsonl").write_text(
        json.dumps(
            {
                "ts": 1000.0,
                "app": "Final Cut Pro",
                "window": "Client edit timeline",
                "status": "frontmost",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = consolidate_sensor_lanes_once(
        state_dir=state,
        now=1010.0,
        sources=({"lane": "active_focus", "ledger": "app_focus.jsonl", "summary": "active app focus trace"},),
    )

    assert len(result["emitted"]) == 1
    rows = [json.loads(line) for line in (state / SENSOR_LANE_JOURNAL_NAME).read_text().splitlines()]
    assert rows[0]["lane"] == "active_focus"
    assert "Final Cut Pro" in rows[0]["summary"]
    assert (state / "journal_schedule_receipts.jsonl").exists()
    assert list((state / "owner_schedule").glob("*.md"))
    assert "Final Cut Pro" in format_recent_sensor_lanes_for_prompt(state_dir=state)


def test_sensor_lane_consolidation_dedupes_recent_rows(tmp_path: Path) -> None:
    state = tmp_path
    row = {"ts": 1000.0, "status": "frontmost", "app": "Cursor", "window": "ANTON_SIFTA"}
    (state / "app_focus.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    source = ({"lane": "active_focus", "ledger": "app_focus.jsonl", "summary": "active app focus trace"},)

    first = consolidate_sensor_lanes_once(state_dir=state, now=1010.0, sources=source)
    second = consolidate_sensor_lanes_once(state_dir=state, now=1020.0, sources=source)

    assert len(first["emitted"]) == 1
    assert second["emitted"] == []
    assert second["skipped"][0]["reason"] == "deduped"
