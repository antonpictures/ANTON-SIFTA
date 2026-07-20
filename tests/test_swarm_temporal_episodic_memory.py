from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path


def test_resolve_time_window_narrows_two_days_at_that_time():
    import System.swarm_temporal_episodic_memory as memo

    now = datetime(2026, 6, 23, 9, 30).timestamp()
    start, end = memo.resolve_time_window(
        "what happened two days ago at that time?",
        now=now,
    )
    target = datetime.fromtimestamp(now) - timedelta(days=2)
    target_ts = target.timestamp()

    assert abs(start - (target_ts - 90 * 60)) < 1.0
    assert abs(end - (target_ts + 90 * 60)) < 1.0
    assert end > start


def test_recall_facts_for_query_prefers_narrow_at_that_time_window(tmp_path, monkeypatch):
    import System.swarm_temporal_episodic_memory as memo

    now = datetime(2026, 6, 23, 9, 30).timestamp()
    target_day = datetime.fromtimestamp(now) - timedelta(days=2)
    target_ts = target_day.timestamp()

    ledger = tmp_path / "alice_conversation.jsonl"
    in_window = {
        "ts": {"physical_pt": target_ts - 30 * 60},
        "text": "Outfit sketch review for the dress concept around 9:30 in the evening.",
        "role": "user",
    }
    out_of_window = {
        "ts": {"physical_pt": now - 6 * 3600},
        "text": "I said this was the latest fashion wearables project from five minutes ago.",
        "role": "user",
    }
    ledger.write_text(
        "\n".join(json.dumps(r) for r in (in_window, out_of_window)),
        encoding="utf-8",
    )

    # deterministic fixed now for the "at that time" parse
    monkeypatch.setattr(memo, "_now", lambda: now)
    # Point the recall search to the fixture ledger and keep the rest of the
    # module paths as non-existent-noise rows.
    monkeypatch.setattr(memo, "_CONVO", ledger)

    result = memo.recall_facts_for_query(
        "what happened two days ago at that time and what did we invent in clothing?",
        time_spec="two days ago at that time",
        keywords=["outfit", "clothing", "project"],
    )

    assert result["ok"] is True
    assert len(result["facts"]) == 1
    assert "outfit" in result["facts"][0]["snippet"].lower()
    assert abs(result["facts"][0]["matched_ts"] - (target_ts - 30 * 60)) < 1.0
