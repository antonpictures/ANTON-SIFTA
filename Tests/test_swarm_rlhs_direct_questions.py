#!/usr/bin/env python3
"""Regression tests for REAL-lane directed speech promotion."""

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.swarm_rlhs_detector import RLHSRegime, detect_rlhs


def test_real_lane_promotes_coherent_can_you_make_difference_question():
    """George's co-watch question should route despite mid STT confidence."""
    r = detect_rlhs(
        "Can you make the difference when I have paused and I am speaking? Just when the video is playing.",
        0.63,
        channel_lane="REAL",
    )
    assert r.regime == RLHSRegime.CLEAR
    assert r.rule_id == "real/coherent_direct_speech"
    assert r.grounding_line == ""
