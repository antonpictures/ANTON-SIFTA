from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

from System.canonical_schemas import LEDGER_SCHEMAS
from System.swarm_physarum_retina import (
    SwarmPhysarumRetina,
    build_digest_row,
    proof_of_property,
    write_digest,
)


def _mock_screen() -> Image.Image:
    img = np.zeros((120, 160), dtype=np.uint8)
    img[20:100, 50:54] = 255
    img[20:100, 110:114] = 255
    img[108:120, 45:120] = 255
    return Image.fromarray(img)


def test_nutrient_landscape_detects_edges():
    retina = SwarmPhysarumRetina(seed=1)
    nutrient = retina.compute_nutrient_landscape(_mock_screen())

    assert nutrient.shape == (120, 160)
    assert float(nutrient.max()) > 0.9
    assert float(nutrient.mean()) > 0.0


def test_digest_keeps_positive_density_clusters_only():
    retina = SwarmPhysarumRetina(num_agents=250, sensing_radius=6, crowding_penalty=0.8, seed=2)
    nutrient, _positions, digest = retina.digest_image(_mock_screen(), steps=15, grid_size=16, top_n=12)

    assert float(nutrient.max()) > 0.9
    assert 1 < len(digest) <= 12
    assert all(region["salience"] > 0 for region in digest)
    assert any(region["y"] > 100 for region in digest)


def test_build_digest_row_matches_canonical_schema():
    retina = SwarmPhysarumRetina(num_agents=120, sensing_radius=5, crowding_penalty=0.7, seed=3)
    row = build_digest_row(
        _mock_screen(),
        source="test:mock_screen",
        retina=retina,
        steps=10,
        grid_size=12,
        top_n=8,
        now=123.0,
    )

    assert set(row) == LEDGER_SCHEMAS["physarum_retina.jsonl"]
    assert row["event"] == "physarum_retina_digest"
    assert row["digest_count"] == len(row["digest"])
    assert row["found_bottom_marker"] is True
    assert len(row["image_sha256"]) == 64
    assert row["ts"] == 123.0


def test_write_digest_appends_one_jsonl_row(tmp_path: Path):
    ledger = tmp_path / "physarum_retina.jsonl"
    retina = SwarmPhysarumRetina(num_agents=80, sensing_radius=4, seed=4)

    row = write_digest(
        _mock_screen(),
        source="test:write",
        ledger_path=ledger,
        retina=retina,
        steps=8,
        grid_size=10,
        top_n=6,
    )

    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0] == row
    assert rows[0]["image_ref"] == "test:write"


def test_proof_of_property_passes():
    assert proof_of_property() is True
