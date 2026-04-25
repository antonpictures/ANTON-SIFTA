from __future__ import annotations

import pytest
from PIL import Image

from System.swarm_mhc_visual_exosome import SwarmVisualMHC, proof_of_property


def test_visual_mhc_round_trips_small_payload():
    mhc = SwarmVisualMHC(marker_height=4)
    base = Image.new("RGB", (320, 80), color=(240, 240, 240))
    state = {
        "identity": "C55M",
        "ide": "codex_app_m5",
        "role": "judge",
    }

    exosome = mhc.apply_exosome_to_image(base, state)

    assert exosome.size[0] == base.size[0]
    assert exosome.size[1] > base.size[1]
    assert mhc.parse_exosome_from_image(exosome) == state


def test_visual_mhc_round_trips_multi_row_payload_that_bishop_v1_missed():
    mhc = SwarmVisualMHC(marker_height=3)
    base = Image.new("RGB", (37, 20), color=(255, 255, 255))
    state = {
        "identity": "CG55M",
        "ide": "cursor_ide_m5",
        "role": "motor_lane",
        "long_context": "x" * 300,
    }

    exosome = mhc.apply_exosome_to_image(base, state)

    assert exosome.size[1] - base.size[1] > mhc.marker_height
    assert mhc.parse_exosome_from_image(exosome) == state


def test_visual_mhc_rejects_plain_image_without_exosome():
    mhc = SwarmVisualMHC(marker_height=4)
    plain = Image.new("RGB", (64, 64), color=(255, 255, 255))

    with pytest.raises(ValueError, match="Foreign or corrupted exosome"):
        mhc.parse_exosome_from_image(plain, max_marker_groups=4)


def test_visual_mhc_detects_corrupted_marker_crc():
    mhc = SwarmVisualMHC(marker_height=4)
    base = Image.new("RGB", (128, 40), color=(255, 255, 255))
    exosome = mhc.apply_exosome_to_image(base, {"identity": "AG31", "ide": "antigravity"})
    corrupted = exosome.copy()
    px = corrupted.load()
    y = corrupted.height - (mhc.marker_height // 2)
    for x in range(24, 40):
        px[x, y] = (255, 255, 255) if px[x, y] == (0, 0, 0) else (0, 0, 0)

    with pytest.raises(ValueError, match="Foreign or corrupted exosome|CRC mismatch"):
        mhc.parse_exosome_from_image(corrupted)


def test_visual_mhc_proof_of_property_passes():
    assert proof_of_property() is True
