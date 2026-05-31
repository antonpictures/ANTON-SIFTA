#!/usr/bin/env python3
"""Tests: generalized visual-form taxonomy (SIFTA r235).

George 2026-05-31: Alice must scan ANY body/object type, not only human bodies + clothing.
infer_form_category was generalized from {human/car/airplane/other} to an open taxonomy
(human_body / animal / car / airplane / vehicle / product / building / food / nature /
other), grounded in open-vocabulary recognition (OWL-ViT, GLIP, Detic, RegionCLIP). The
SUBJECT of a photo wins over its SETTING on ties (a woman on a beach is human_body)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System import swarm_visual_form_memory as fm


@pytest.mark.parametrize("desc,expected", [
    ("A young woman in a red dress on a beach", "human_body"),   # subject beats setting
    ("A silver Ferrari sedan with chrome wheels", "car"),
    ("A Boeing airliner on the runway", "airplane"),
    ("A golden retriever puppy in the grass", "animal"),
    ("A stainless steel diver watch with a blue dial", "product"),
    ("A red motorcycle parked on the street", "vehicle"),
    ("A plate of sushi and a bowl of soup", "food"),
    ("A glass skyscraper downtown at dusk", "building"),
    ("A misty mountain forest at sunrise", "nature"),
    ("An abstract blur of colours", "other"),
])
def test_open_taxonomy_categories(desc, expected):
    assert fm.infer_form_category(desc) == expected


def test_backward_compat_human_car_airplane_constants():
    assert fm.HUMAN_BODY == "human_body"
    assert fm.CAR == "car"
    assert fm.AIRPLANE == "airplane"
    assert fm.OTHER == "other"


def test_empty_is_other():
    assert fm.infer_form_category("") == "other"
    assert fm.infer_form_category(None) == "other"  # type: ignore


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
