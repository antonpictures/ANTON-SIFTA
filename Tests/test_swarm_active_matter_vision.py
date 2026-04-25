from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from System.canonical_schemas import LEDGER_SCHEMAS
from System.swarm_active_matter_vision import (
    ActiveMatterVisionField,
    VisualFrame,
    append_active_matter_row,
    decode_quantized_grid,
    row_from_snapshot,
    summarize_frames,
)


def _frame(x: int, y: int, *, ts: float = 1.0, size: int = 4, sha8: str = "abc") -> VisualFrame:
    saliency = np.zeros((size, size), dtype=np.float32)
    motion = np.zeros((size, size), dtype=np.float32)
    saliency[y, x] = 1.0
    motion[y, x] = 0.5
    return VisualFrame(ts=ts, saliency=saliency, motion=motion, sha8=sha8)


def _hex_grid(size: int, x: int, y: int, value: str = "f") -> str:
    cells = ["0"] * (size * size)
    cells[y * size + x] = value
    return "".join(cells)


def test_decode_quantized_grid_requires_square_hex():
    grid = decode_quantized_grid("0f00")

    assert grid.shape == (2, 2)
    assert grid[0, 1] == 1.0

    try:
        decode_quantized_grid("abc")
    except ValueError as exc:
        assert "square" in str(exc)
    else:
        raise AssertionError("non-square grid must be rejected")


def test_stable_attractor_builds_persistent_energy():
    field = ActiveMatterVisionField(decay=0.9, diffusion=0.05, injection=0.4)

    snaps = [field.update(_frame(3, 1, ts=i)) for i in range(5)]

    assert snaps[-1].field_energy > snaps[0].field_energy
    assert snaps[-1].attractor_x > 0.60
    assert 0.20 < snaps[-1].attractor_y < 0.50
    assert snaps[-1].persistence > 0.95


def test_novelty_increases_when_attractor_moves():
    field = ActiveMatterVisionField()
    field.update(_frame(0, 0, ts=1.0))
    still = field.update(_frame(0, 0, ts=2.0))
    moved = field.update(_frame(3, 3, ts=3.0))

    assert still.novelty == 0.0
    assert moved.novelty > still.novelty


def test_append_row_matches_canonical_schema(tmp_path: Path):
    visual = tmp_path / "visual_stigmergy.jsonl"
    out = tmp_path / "visual_active_matter.jsonl"
    row = {
        "ts": 1.0,
        "sha8": "tailhash",
        "entropy_bits": 7.0,
        "hue_deg": 30.0,
        "saliency_q": _hex_grid(4, 2, 1),
        "motion_q": _hex_grid(4, 2, 1, "8"),
    }
    visual.write_text(json.dumps(row) + "\n", encoding="utf-8")

    result = append_active_matter_row(
        visual_path=visual,
        ledger_path=out,
        limit=4,
        max_age_s=None,
    )

    assert result is not None
    written = json.loads(out.read_text(encoding="utf-8").strip())
    assert set(written.keys()) == LEDGER_SCHEMAS["visual_active_matter.jsonl"]
    assert written["event"] == "visual_active_matter_update"
    assert written["source_tail_sha8"] == "tailhash"


def test_row_from_snapshot_is_deterministic_shape():
    snap = summarize_frames([_frame(1, 1), _frame(1, 1, ts=2.0, sha8="tail")])
    assert snap is not None

    row = row_from_snapshot(snap, frames_observed=2, source_tail_sha8="tail")

    assert row["schema"] == "SIFTA_VISUAL_ACTIVE_MATTER_V1"
    assert row["frames_observed"] == 2
    assert len(row["field_hash"]) == 64
