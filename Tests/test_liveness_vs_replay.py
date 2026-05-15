import json
import time
from pathlib import Path

from System.swarm_architect_day_segments import log_sensor_presence_segment


def test_sensor_presence_segment_throttling(tmp_path: Path):
    """
    Test that log_sensor_presence_segment enforces a liveness/throttle window
    so that replay attacks or high-frequency sensor spam do not flood the ledger.
    """
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. First event: Liveness (should write a new row)
    now_ts = time.time()
    row1 = log_sensor_presence_segment(
        label="desk_work",
        source="architect_identity",
        context_note="Liveness frame 1",
        state_dir=state_dir,
        now=now_ts,
    )
    assert row1["label"] == "desk_work"
    assert row1["source"] == "architect_identity"
    
    # Verify it wrote to disk
    log_file = state_dir / "architect_day_segments.jsonl"
    assert log_file.exists()
    lines_after_first = log_file.read_text("utf-8").splitlines()
    assert len(lines_after_first) == 1
    
    # 2. Replay/Spam event within the throttle window (e.g. 10s later)
    # The debouncer in log_sensor_presence_segment should return the LAST row 
    # instead of appending a new one.
    row2 = log_sensor_presence_segment(
        label="desk_work",
        source="architect_identity",
        context_note="Liveness frame 2 (spam)",
        state_dir=state_dir,
        now=now_ts + 10.0,
    )
    # It should return the original row
    assert row2["ts"] == row1["ts"]
    
    # File length should still be 1
    lines_after_spam = log_file.read_text("utf-8").splitlines()
    assert len(lines_after_spam) == 1
    
    # 3. Expiration of the throttle window (5 mins + 1s later)
    # Should write a new row
    row3 = log_sensor_presence_segment(
        label="desk_work",
        source="architect_identity",
        context_note="Liveness frame 3 (new bout)",
        state_dir=state_dir,
        now=now_ts + 301.0,
    )
    assert row3["ts"] != row1["ts"]
    assert row3["ts"] == now_ts + 301.0
    
    # File length should now be 2
    lines_after_expire = log_file.read_text("utf-8").splitlines()
    assert len(lines_after_expire) == 2
