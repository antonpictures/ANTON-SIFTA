from __future__ import annotations

import json
from pathlib import Path

from System import memory_search
from System import stigmergic_memory_bus as memory_bus


def test_supersession_hides_old_fact_without_rewriting_ledger() -> None:
    rows = [
        {"trace_id": "old", "raw_text": "George's preferred camera is OBS virtual camera."},
        {
            "trace_id": "new",
            "raw_text": "George's preferred camera is Logitech USB.",
            "supersedes_trace_id": "old",
        },
    ]

    active = memory_search.active_memory_rows(rows)

    assert [row["trace_id"] for row in active] == ["new"]
    assert [row["trace_id"] for row in memory_search.active_memory_rows(rows, include_superseded=True)] == ["old", "new"]


def test_rrf_merge_rewards_rows_that_rank_in_multiple_lanes() -> None:
    merged = memory_search.rrf_merge([
        ["logitech", "macbook", "obs"],
        ["macbook", "logitech", "iphone"],
    ])

    assert merged[0][0] in {"logitech", "macbook"}
    assert dict(merged)["logitech"] > dict(merged)["obs"]
    assert dict(merged)["macbook"] > dict(merged)["iphone"]


def test_typed_memory_lanes_are_views_over_same_rows() -> None:
    rows = [
        {"trace_id": "fact1", "raw_text": "George's owner name is George.", "memory_lane": "facts"},
        {"trace_id": "ep1", "raw_text": "At 19:15 George ate soup while JRE played.", "source": "hippocampus"},
        {"trace_id": "proc1", "raw_text": "Procedure: open Alice Browser, then load file path."},
    ]

    facts = memory_search.typed_memory_rows(rows, lanes=["facts"])
    episodes = memory_search.typed_memory_rows(rows, lanes=["episodes"])
    procedures = memory_search.typed_memory_rows(rows, lanes=["procedures"])

    assert [row["trace_id"] for row in facts] == ["fact1"]
    assert [row["trace_id"] for row in episodes] == ["ep1"]
    assert [row["trace_id"] for row in procedures] == ["proc1"]


def test_search_memory_rows_uses_bm25_and_filters_superseded() -> None:
    rows = [
        {"trace_id": "old", "raw_text": "Robin Wood is a folk hero.", "memory_lane": "facts"},
        {
            "trace_id": "new",
            "raw_text": "Robinhood is the trading app George invested in.",
            "memory_lane": "facts",
            "supersedes_trace_id": "old",
        },
        {"trace_id": "episode", "raw_text": "George discussed Robinhood with Vitaly on speakerphone.", "source": "hippocampus"},
    ]

    results = memory_search.search_memory_rows("Robinhood trading app", rows, lanes=["facts"])

    assert [result["trace_id"] for result in results] == ["new"]
    assert results[0]["memory_lane"] == "facts"
    assert results[0]["bm25_score"] > 0


def test_memory_bus_hybrid_recall_skips_superseded_rows(tmp_path: Path, monkeypatch) -> None:
    ledger = tmp_path / "memory_ledger.jsonl"
    stgm = tmp_path / "stgm.jsonl"
    now = 1_700_000_000.0
    rows = [
        {
            "trace_id": "old",
            "architect_id": "IOAN_M5",
            "app_context": "test",
            "raw_text": "The active camera is OBS.",
            "semantic_tags": ["general"],
            "timestamp": now,
            "stgm_paid": 0.05,
            "epistemic_label": "HYPOTHESIS",
            "memory_lane": "facts",
        },
        {
            "trace_id": "new",
            "architect_id": "IOAN_M5",
            "app_context": "test",
            "raw_text": "The active camera is Logitech USB.",
            "semantic_tags": ["general"],
            "timestamp": now,
            "stgm_paid": 0.05,
            "epistemic_label": "HYPOTHESIS",
            "memory_lane": "facts",
            "supersedes_trace_id": "old",
        },
    ]
    ledger.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    monkeypatch.setattr(memory_bus, "LEDGER_FILE", ledger)
    monkeypatch.setattr(memory_bus, "STGM_LOG_FILE", stgm)
    monkeypatch.setattr(memory_bus.time, "time", lambda: now)

    bus = memory_bus.StigmergicMemoryBus("IOAN_M5")
    ranked = bus.hybrid_recall("active camera", "test", top_k=5, lanes=["facts"])

    assert [trace.trace_id for _score, trace, _breakdown in ranked] == ["new"]
    assert ranked[0][2]["memory_lane"] == "facts"
