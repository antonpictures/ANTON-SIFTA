from __future__ import annotations

import pytest
from PIL import Image

from System.swarm_visual_mhc_exosome import SwarmVisualMHC, proof_of_property


def test_visual_mhc_round_trips_single_row_payload():
    mhc = SwarmVisualMHC(marker_height=4)
    image = Image.new("RGB", (256, 32), color=(123, 123, 123))
    state = {"identity": "CG55M", "ide": "cursor", "model": "GPT-5.5 Medium"}

    exosome = mhc.apply_exosome_to_image(image, state)
    decoded = mhc.decode_exosome(exosome)

    assert decoded.state == state
    assert decoded.payload_sha256
    assert exosome.height > image.height


def test_visual_mhc_round_trips_multi_row_payload():
    mhc = SwarmVisualMHC(marker_height=3)
    image = Image.new("RGB", (32, 20), color=(255, 255, 255))
    state = {
        "identity": "C55M_DR_CODEX",
        "ide": "codex",
        "model": "GPT-5.5 Extra High",
        "role": "Oracle Matrix",
        "long_context": "x" * 200,
    }

    exosome = mhc.apply_exosome_to_image(image, state)

    assert exosome.height > image.height + mhc.marker_height
    assert mhc.parse_exosome_from_image(exosome) == state


def test_visual_mhc_digest_detects_corruption():
    mhc = SwarmVisualMHC(marker_height=4)
    image = Image.new("RGB", (64, 20), color=(0, 0, 0))
    exosome = mhc.apply_exosome_to_image(image, {"identity": "AG31"})

    px = exosome.load()
    # Flip one marker pixel in the payload area. The codons may still be found,
    # but the sha256 payload digest must reject the mutation.
    px[20, image.height + 2] = (255, 255, 255) if px[20, image.height + 2] == (0, 0, 0) else (0, 0, 0)

    with pytest.raises(ValueError, match="MHC"):
        mhc.parse_exosome_from_image(exosome)


def test_visual_mhc_rejects_plain_image():
    mhc = SwarmVisualMHC(marker_height=4)
    image = Image.new("RGB", (64, 20), color=(255, 255, 255))

    with pytest.raises(ValueError, match="MHC"):
        mhc.parse_exosome_from_image(image)


def test_proof_of_property_passes():
    assert proof_of_property() is True
