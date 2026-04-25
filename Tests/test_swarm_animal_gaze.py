from __future__ import annotations

import numpy as np
import pytest

from System.swarm_animal_gaze import AnimalGazeConfig, SwarmAnimalGaze, proof_of_property


def _frame() -> np.ndarray:
    frame = np.zeros((120, 200), dtype=np.float32)
    frame[70:105, 145:185] = 1.0
    return frame


def test_animal_gaze_observes_salient_region():
    gaze = SwarmAnimalGaze(
        200,
        120,
        AnimalGazeConfig(
            scouts=48,
            foveal_agents=120,
            peripheral_steps=8,
            foveal_steps=10,
            peripheral_sigma=5.0,
            seed=555,
        ),
    )

    result = gaze.observe(_frame())
    points = result["foveal_points"]

    assert 70 <= result["target_y"] <= 105
    assert 145 <= result["target_x"] <= 185
    assert 70 <= float(np.mean(points[:, 0])) <= 105
    assert 145 <= float(np.mean(points[:, 1])) <= 185
    assert result["memory"].max() > 0.0
    assert result["inhibition"].max() > 0.0


def test_nearest_peak_avoids_top_left_plateau_bias():
    patch = np.ones((9, 9), dtype=np.float32)

    y, x = SwarmAnimalGaze._nearest_peak(patch, 4, 4)

    assert (y, x) == (4, 4)


def test_motion_saliency_changes_second_frame_target():
    cfg = AnimalGazeConfig(
        scouts=36,
        foveal_agents=80,
        peripheral_steps=6,
        foveal_steps=6,
        peripheral_sigma=4.0,
        seed=123,
    )
    gaze = SwarmAnimalGaze(200, 120, cfg)
    first = _frame()
    second = np.zeros_like(first)
    second[15:35, 20:45] = 1.0

    gaze.observe(first)
    result = gaze.observe(second)

    assert 10 <= result["target_y"] <= 45
    assert 15 <= result["target_x"] <= 55


def test_frame_shape_validation():
    gaze = SwarmAnimalGaze(200, 120)

    with pytest.raises(ValueError, match="frame"):
        gaze.observe(np.zeros((40, 40), dtype=np.float32))


def test_proof_of_property_passes():
    assert proof_of_property() is True
