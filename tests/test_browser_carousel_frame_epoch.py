#!/usr/bin/env python3
"""Tests: carousel frame epoch (SIFTA r212).

George 2026-05-31 ("no tight floral shorts, tiara?"): an Instagram carousel shares
ONE url across MANY frames. The photo description is url-keyed, so the cover frame's
description ("reclining, pink bralette, floral shorts, tiara") was recited for a LATER
frame the owner had swiped to ("standing in hot-pink flared bell-bottom pants"). The
frame epoch fixes this: a swipe/navigation stamps a change time; a description is only
current if recorded at/after that time. Stale frames are never recited."""
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System import swarm_browser_photo_description as pd

URL = "https://www.instagram.com/p/CkhSC2KNJfi/"


def _sd():
    return Path(tempfile.mkdtemp())


def test_description_fresh_before_any_frame_change():
    sd = _sd()
    pd.record_photo_description(URL, description="cover frame: reclining, floral shorts, tiara",
                                arm="grok_agent", now=100.0, state_dir=sd)
    got = pd.latest_photo_description(url=URL, now=101.0, state_dir=sd)
    assert got["frame_stale"] is False


def test_swipe_makes_prior_frame_stale():
    sd = _sd()
    pd.record_photo_description(URL, description="cover frame: reclining, floral shorts, tiara",
                                arm="grok_agent", now=100.0, state_dir=sd)
    pd.mark_frame_changed(url=URL, now=200.0, state_dir=sd)
    got = pd.latest_photo_description(url=URL, now=201.0, state_dir=sd)
    assert got["frame_stale"] is True


def test_block_refuses_to_recite_stale_frame():
    sd = _sd()
    pd.record_photo_description(URL, description="reclining, floral shorts, tiara",
                                arm="grok_agent", now=100.0, state_dir=sd)
    pd.mark_frame_changed(url=URL, now=200.0, state_dir=sd)
    block = pd.photo_description_block(url=URL, now=201.0, state_dir=sd)
    assert "NOT looked at the frame currently on screen" in block
    assert "floral shorts" not in block


def test_epoch_self_heals_after_fresh_describe():
    sd = _sd()
    pd.record_photo_description(URL, description="reclining, floral shorts, tiara",
                                arm="grok_agent", now=100.0, state_dir=sd)
    pd.mark_frame_changed(url=URL, now=200.0, state_dir=sd)
    pd.record_photo_description(URL, description="standing in hot-pink flared bell-bottom pants, halter top",
                                arm="grok_agent", now=210.0, state_dir=sd)
    got = pd.latest_photo_description(url=URL, now=211.0, state_dir=sd)
    assert got["frame_stale"] is False
    assert "flared" in got["description"]
    block = pd.photo_description_block(url=URL, now=211.0, state_dir=sd)
    assert "flared" in block and "NOT looked" not in block


def test_no_epoch_file_means_not_stale():
    sd = _sd()
    pd.record_photo_description(URL, description="some frame", arm="grok_agent", now=100.0, state_dir=sd)
    got = pd.latest_photo_description(url=URL, now=101.0, state_dir=sd)
    assert got["frame_stale"] is False
    assert pd.frame_epoch(state_dir=sd) == 0.0


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
