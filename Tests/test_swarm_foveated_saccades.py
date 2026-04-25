from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from System.canonical_schemas import LEDGER_SCHEMAS
from System.swarm_foveated_saccades import (
    FoveatedSaccadeConfig,
    FoveatedSwarmSaccades,
    SwarmSaccadicVision,
    build_digest_row,
    nutrient_from_image,
    proof_of_property,
    write_observation,
)


def _nutrient() -> np.ndarray:
    field = np.zeros((180, 320), dtype=np.float32)
    field[110:155, 230:290] = 1.0
    return field


def test_peripheral_glance_targets_salient_region():
    vision = SwarmSaccadicVision(320, 180, seed=61, peripheral_window=18, peripheral_blur_sigma=4.0)

    target = vision.glance_peripheral(_nutrient(), num_scouts=24, steps=8)

    assert 110 <= target.y <= 155
    assert 230 <= target.x <= 290
    assert target.salience > 0.0


def test_foveal_saccade_stays_on_target_and_builds_digest():
    vision = SwarmSaccadicVision(320, 180, seed=61, foveal_sigma=4.0)

    result = vision.observe(_nutrient(), num_scouts=24, peripheral_steps=8, num_foveal=90, foveal_steps=10)
    mean_y = float(np.mean(result.foveal_positions[:, 0]))
    mean_x = float(np.mean(result.foveal_positions[:, 1]))

    assert 110 <= mean_y <= 155
    assert 230 <= mean_x <= 290
    assert result.foveal_memory.max() > 0.0
    assert result.foveal_digest


def test_digest_row_matches_canonical_schema():
    vision = SwarmSaccadicVision(320, 180, seed=61, peripheral_window=18, peripheral_blur_sigma=4.0)
    result = vision.observe(_nutrient(), num_scouts=24, peripheral_steps=8, num_foveal=90, foveal_steps=10)

    row = build_digest_row(
        result,
        image_ref="mock",
        image_w=320,
        image_h=180,
        peripheral_scouts=24,
        peripheral_steps=8,
        foveal_agents=90,
        foveal_steps=10,
        now=123.0,
    )

    assert set(row) == LEDGER_SCHEMAS["foveated_saccades.jsonl"]
    assert row["event"] == "foveated_saccade_digest"
    assert row["target_x"] >= 230
    assert row["ts"] == 123.0


def test_write_observation_appends_jsonl(tmp_path: Path):
    arr = np.zeros((80, 120), dtype=np.uint8)
    arr[50:70, 90:110] = 255
    image = Image.fromarray(arr)
    ledger = tmp_path / "foveated_saccades.jsonl"

    row = write_observation(
        image,
        image_ref="mock-image",
        ledger_path=ledger,
        seed=61,
        peripheral_scouts=18,
        peripheral_steps=6,
        foveal_agents=50,
        foveal_steps=6,
    )

    written = json.loads(ledger.read_text(encoding="utf-8"))
    assert written == row
    assert written["digest_count"] == len(written["foveal_digest"])


def test_nutrient_from_image_and_validation():
    image = Image.fromarray(np.zeros((20, 30), dtype=np.uint8))
    nutrient = nutrient_from_image(image)
    assert nutrient.shape == (20, 30)

    vision = SwarmSaccadicVision(30, 20)
    with pytest.raises(ValueError, match="shape"):
        vision.glance_peripheral(np.zeros((10, 30), dtype=np.float32))


def test_proof_of_property_passes():
    assert proof_of_property() is True


def test_live_foveated_gaze_ignores_blank_frame():
    gaze = FoveatedSwarmSaccades(
        64,
        64,
        FoveatedSaccadeConfig(
            scouts=24,
            foveal_agents=40,
            peripheral_steps=4,
            foveal_steps=4,
            seed=61,
        ),
    )

    result = gaze.observe(np.zeros((64, 64), dtype=np.float32))

    assert result["saccade_fired"] is False
    assert result["saliency_peak"] == 0.0
    assert len(result["foveal_points"]) == 0
    assert gaze.glyph() == ""


def test_live_foveated_gaze_saccades_to_salient_patch():
    frame = np.zeros((64, 64), dtype=np.float32)
    frame[38:52, 45:60] = 1.0
    gaze = FoveatedSwarmSaccades(
        64,
        64,
        FoveatedSaccadeConfig(
            scouts=36,
            foveal_agents=80,
            peripheral_steps=6,
            foveal_steps=6,
            peripheral_sigma=3.0,
            foveal_sigma=2.5,
            scout_jump=8,
            saliency_threshold=0.01,
            seed=61,
        ),
    )

    result = gaze.observe(frame)
    points = result["foveal_points"]

    assert result["saccade_fired"] is True
    assert 34 <= result["target_y"] <= 54
    assert 42 <= result["target_x"] <= 62
    assert points.shape == (80, 2)
    assert 34 <= float(np.mean(points[:, 0])) <= 54
    assert 42 <= float(np.mean(points[:, 1])) <= 62
    assert result["foveal_box"] is not None
    assert gaze.glyph("saliency")
    assert gaze.glyph("memory")
