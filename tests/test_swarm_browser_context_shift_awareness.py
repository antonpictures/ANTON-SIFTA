from __future__ import annotations

import json


def test_browser_context_shift_writes_alert_diary_and_prompt_block(tmp_path):
    from System.swarm_browser_context_shift_awareness import (
        LEDGER,
        latest_browser_context_shift_block,
        record_browser_context_shift,
    )

    state = tmp_path / ".sifta_state"
    row = record_browser_context_shift(
        url="https://www.youtube.com/watch?v=d5uhih_l7Jw",
        title="Madison Beer Lives Out Her Dream While Eating Spicy Wings | Hot Ones",
        source="url_changed",
        media_status={"ok": True, "status": "playing", "current_time": 5.0},
        state_dir=state,
        now=1000.0,
    )

    assert row["truth_label"] == "BROWSER_CONTEXT_SHIFT_AWARENESS_V1"
    assert row["event_type"] == "browser_context_shift"
    assert "Madison Beer" in row["title"]
    assert (state / LEDGER).exists()
    assert (state / "browser_context_shift_latest.json").exists()
    assert (state / "episodic_diary.jsonl").exists()

    block = latest_browser_context_shift_block(state_dir=state)
    assert "ALICE BROWSER CONTEXT SHIFT ALERT" in block
    assert "Madison Beer" in block
    assert "old page-state is stale" in block

    diary = [
        json.loads(line)
        for line in (state / "episodic_diary.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert diary[-1]["event_type"] == "browser_page_loaded"
    assert diary[-1]["source"] == "context_shift:url_changed"


def test_browser_context_shift_dedupes_same_signal(tmp_path):
    from System.swarm_browser_context_shift_awareness import (
        LEDGER,
        record_browser_context_shift,
    )

    state = tmp_path / ".sifta_state"
    first = record_browser_context_shift(
        url="https://example.com/video",
        title="Example",
        source="title_changed",
        state_dir=state,
        now=10.0,
    )
    second = record_browser_context_shift(
        url="https://example.com/video",
        title="Example",
        source="title_changed",
        state_dir=state,
        now=11.0,
    )

    assert first
    assert second == {}
    rows = [line for line in (state / LEDGER).read_text().splitlines() if line.strip()]
    assert len(rows) == 1
