from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from System.canonical_schemas import LEDGER_SCHEMAS
from System.swarm_ide_screen_swimmers import (
    build_snapshot,
    glyph_from_grid,
    map_to_grid,
    parse_osascript_bounds,
    write_snapshot,
)


def _windows():
    return [
        {"name": "Cursor", "app_name": "Cursor", "x": 0, "y": 0, "w": 500, "h": 500, "is_active": True},
        {"name": "Codex", "app_name": "Codex", "x": 500, "y": 0, "w": 500, "h": 500, "is_active": False},
        {"name": "Antigravity", "app_name": "Electron", "x": 0, "y": 500, "w": 500, "h": 500, "is_active": False},
    ]


def test_parse_osascript_bounds_maps_electron_to_antigravity():
    rows = parse_osascript_bounds("Cursor:0,0,100,100:true\nElectron:100,0,100,100:false\n")

    assert [r["name"] for r in rows] == ["Antigravity", "Cursor"]
    assert rows[0]["app_name"] == "Electron"
    assert rows[1]["is_active"] is True


def test_map_to_grid_weights_frontmost_ide_more_strongly():
    field = map_to_grid(_windows(), grid_size=10, screen_w=1000, screen_h=1000)

    assert field.shape == (10, 10)
    assert float(field.max()) == 1.0
    # Cursor occupies top-left and is active, so its normalized cells should be
    # stronger than Codex's inactive top-right cells.
    assert field[1, 1] > field[1, 7]


def test_build_snapshot_matches_canonical_schema_and_contains_clusters():
    row = build_snapshot(windows=_windows(), grid_size=10, screen_w=1000, screen_h=1000, source="test", now=123.0)

    assert set(row) == LEDGER_SCHEMAS["ide_screen_swimmers.jsonl"]
    assert row["active_ide"] == "Cursor"
    assert row["clusters"]
    assert row["glyph"]
    assert row["ts"] == 123.0


def test_write_snapshot_appends_jsonl_row(tmp_path: Path):
    ledger = tmp_path / "ide_screen_swimmers.jsonl"

    row = write_snapshot(windows=_windows(), ledger_path=ledger, grid_size=10, source="test")

    written = json.loads(ledger.read_text(encoding="utf-8"))
    assert written["event"] == "ide_screen_swimmers"
    assert written["active_ide"] == row["active_ide"]


def test_glyph_from_grid_renders_nonempty_ascii():
    field = np.zeros((4, 4), dtype=np.float32)
    field[1, 2] = 1.0

    glyph = glyph_from_grid(field)

    assert "@" in glyph
