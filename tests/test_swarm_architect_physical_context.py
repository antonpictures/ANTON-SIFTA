import json
import time
from pathlib import Path

from System.swarm_architect_physical_context import (
    append_architect_physical_substrate_row,
)


def test_append_architect_physical_substrate_row(tmp_path: Path) -> None:
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True)
    now = time.time()
    (sd / "iphone_gps_latest.json").write_text(
        json.dumps(
            {
                "ts": now - 120.0,
                "channel": "ios_shortcut_http_post",
                "payload": {"latitude": 37.4, "longitude": -122.1, "accuracy": 12.0},
            }
        ),
        encoding="utf-8",
    )
    focus_row = {"ts": now, "app": "Safari", "detail": "Example tab"}
    (sd / "app_focus.jsonl").write_text(json.dumps(focus_row) + "\n", encoding="utf-8")

    row = append_architect_physical_substrate_row(
        state_dir=tmp_path,
        input_channel="test",
        model_tag="alice-m5-cortex-8b-6.3gb:latest",
    )
    assert row is not None
    assert row["truth_label"] == "OBSERVED"
    assert row["kind"] == "ARCHITECT_PHYSICAL_SUBSTRATE_SNAPSHOT"
    assert row["input_channel"] == "test"
    assert row["iphone_gps_latest"] is not None
    assert row["iphone_gps_latest"]["latitude"] == 37.4
    assert row["frontmost_app_focus"] is not None
    assert row["frontmost_app_focus"]["app"] == "Safari"

    lines = (sd / "architect_physical_substrate.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    back = json.loads(lines[0])
    assert back["trace_id"] == row["trace_id"]
