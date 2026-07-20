from __future__ import annotations

import json
from pathlib import Path
import time

import System.swarm_bloat_tax_monitor as bloat_monitor
from System.swarm_bloat_tax_monitor import (
    bloat_tax_monitor_lines,
    compute_bloat_tax_snapshot,
    maybe_record_bloat_tax_snapshot,
    write_forager_compression_plan,
)


def _write_bytes(path: Path, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)


def test_bloat_tax_snapshot_scores_top_entries_and_stgm_per_mib(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    _write_bytes(state / "saccadic_blink_vision.jsonl", 2 * 1024 * 1024)
    _write_bytes(state / "small.jsonl", 128)
    (state / "stgm_memory_rewards.jsonl").write_text(
        json.dumps({"amount": 4.0}) + "\n" + json.dumps({"amount": -1.0}) + "\n",
        encoding="utf-8",
    )

    snap = compute_bloat_tax_snapshot(state_dir=tmp_path, top_n=3, now=1000.0)

    assert snap["state_bytes"] >= 2 * 1024 * 1024
    assert snap["positive_stgm"] == 4.0
    assert snap["net_stgm"] == 3.0
    assert snap["stgm_per_mib"] > 0
    assert snap["top_entries"][0]["path"] == "saccadic_blink_vision.jsonl"
    assert "vision_forager" in snap["top_entries"][0]["compression_action"]
    assert snap["landauer_min_joules"] > 0


def test_bloat_tax_growth_uses_previous_snapshot(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    state.mkdir(parents=True)
    (state / "bloat_tax_snapshots.jsonl").write_text(
        json.dumps({"ts": 1000.0, "state_bytes": 1024}) + "\n",
        encoding="utf-8",
    )
    _write_bytes(state / "alice_body_heart.jsonl", 2048)

    snap = compute_bloat_tax_snapshot(state_dir=tmp_path, now=1000.0 + 86400.0)

    assert snap["growth_bytes_per_day"] >= 1024
    assert "KiB/day" in snap["growth_human_per_day"]


def test_bloat_tax_growth_waits_for_real_window(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    state.mkdir(parents=True)
    (state / "bloat_tax_snapshots.jsonl").write_text(
        json.dumps({"ts": 1000.0, "state_bytes": 1024}) + "\n",
        encoding="utf-8",
    )
    _write_bytes(state / "alice_body_heart.jsonl", 4096)

    snap = compute_bloat_tax_snapshot(state_dir=tmp_path, now=1300.0)

    assert snap["growth_bytes_per_day"] == 0.0
    assert snap["growth_human_per_day"] == "warming_up(<1h sample)"


def test_maybe_record_snapshot_throttles_small_repeat(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    state.mkdir(parents=True)
    snap = {
        "schema": "SIFTA_BLOAT_TAX_SNAPSHOT_V1",
        "truth_label": "SIFTA_BLOAT_TAX_MONITOR_V1",
        "ts": 1000.0,
        "state_bytes": 1024,
    }

    first = maybe_record_bloat_tax_snapshot(snap, state_dir=tmp_path)
    second = maybe_record_bloat_tax_snapshot({**snap, "ts": 1010.0}, state_dir=tmp_path)

    rows = (state / "bloat_tax_snapshots.jsonl").read_text(encoding="utf-8").splitlines()
    assert first["written"] is True
    assert second["written"] is False
    assert len(rows) == 1


def test_forager_compression_plan_is_dry_run(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    _write_bytes(state / "browser_stigmergic_memory.jsonl", 2 * 1024 * 1024)

    plan = write_forager_compression_plan(state_dir=tmp_path, top_n=5)

    assert plan["mode"] == "dry_run_non_destructive"
    assert (state / "forager_compression_plan.json").exists()
    assert plan["expected_receipts"]


def test_candidates_do_not_double_count_parent_and_child(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(bloat_monitor, "_MB", 1024)
    state = tmp_path / ".sifta_state"
    _write_bytes(state / "ledger_archive" / "old.jsonl", 2 * 1024 * 1024)
    _write_bytes(state / "saccadic_blink_vision.jsonl", 2 * 1024 * 1024)

    snap = compute_bloat_tax_snapshot(state_dir=tmp_path, top_n=5)
    paths = [row["path"] for row in snap["compression_candidates"]]

    assert "ledger_archive" in paths
    assert "ledger_archive/old.jsonl" not in paths


def test_bloat_tax_monitor_lines_are_human_visible(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    _write_bytes(state / "fractal_pheromone_field.jsonl", 2 * 1024 * 1024)

    lines = bloat_tax_monitor_lines(state_dir=tmp_path, top_n=2, record=False)

    joined = "\n".join(lines)
    assert "BLOAT TAX / LANDAUER METABOLISM" in joined
    assert "fractal_pheromone_field.jsonl" in joined
    assert "culling/rotation requires a separate explicit receipt" in joined


def test_bloat_tax_monitor_lines_can_use_cached_snapshot(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    state.mkdir(parents=True)
    (state / "bloat_tax_snapshots.jsonl").write_text(
        json.dumps(
            {
                "schema": "SIFTA_BLOAT_TAX_SNAPSHOT_V1",
                "truth_label": "SIFTA_BLOAT_TAX_MONITOR_V1",
                "ts": time.time(),
                "state_bytes": 1234,
                "state_human": "1.2 KiB",
                "growth_human_per_day": "0 B/day",
                "stgm_per_mib": 0.1,
                "stgm_rows": 1,
                "positive_stgm": 0.5,
                "net_stgm": 0.5,
                "landauer_min_joules": 1e-20,
                "risk": "ok",
                "top_entries": [
                    {
                        "human": "1.2 KiB",
                        "risk": "watch",
                        "path": "cached.jsonl",
                        "compression_action": "measure_before_cull",
                    }
                ],
                "compression_candidates": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _write_bytes(state / "new_large_file.jsonl", 2 * 1024 * 1024)

    lines = bloat_tax_monitor_lines(state_dir=tmp_path, top_n=2, record=True, cache_s=3600.0)

    joined = "\n".join(lines)
    assert "cached.jsonl" in joined
    assert "new_large_file" not in joined
    assert "cached_snapshot" in joined
