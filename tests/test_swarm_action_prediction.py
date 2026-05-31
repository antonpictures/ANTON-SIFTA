#!/usr/bin/env python3
"""Tests: predict consequences, learn from mistakes (George 2026-05-30)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System import swarm_action_prediction as ap


def test_match_when_actual_agrees_with_expected(tmp_path):
    ap.predict("open Alice Browser", "the browser window opens and shows my home page",
               now=1.0, state_dir=tmp_path)
    out = ap.observe("open Alice Browser", "browser window opened showing the home page",
                     now=2.0, state_dir=tmp_path)
    assert out["outcome"] == "MATCH"
    assert out["prediction_error"] < 0.7


def test_mistake_when_actual_diverges(tmp_path):
    ap.predict("open Alice Browser", "the browser opens to my home page",
               now=1.0, state_dir=tmp_path)
    out = ap.observe("open Alice Browser", "an error dialog appeared, nothing opened",
                     now=2.0, state_dir=tmp_path)
    assert out["outcome"] == "MISTAKE"
    assert out["prediction_error"] > 0.5
    assert "lesson" in out and out["lesson"]


def test_owner_correction_forces_mistake(tmp_path):
    ap.predict("open browser", "it was already open", now=1.0, state_dir=tmp_path)
    out = ap.observe("open browser", "it was already open", owner_confirmed=False,
                     now=2.0, state_dir=tmp_path)
    assert out["outcome"] == "MISTAKE"  # owner says wrong, even if text matched


def test_unpredicted_action_flagged(tmp_path):
    out = ap.observe("close app", "the app closed", now=1.0, state_dir=tmp_path)
    assert out["outcome"] == "UNPREDICTED"


def test_accuracy_and_learning_block(tmp_path):
    ap.predict("a", "x happens", now=1.0, state_dir=tmp_path)
    ap.observe("a", "x happens", now=2.0, state_dir=tmp_path)            # match
    ap.predict("b", "y happens", now=3.0, state_dir=tmp_path)
    ap.observe("b", "totally different zzz", now=4.0, state_dir=tmp_path)  # mistake
    acc = ap.prediction_accuracy(state_dir=tmp_path)
    assert acc["graded"] == 2 and acc["matches"] == 1 and acc["mistakes"] == 1
    block = ap.learning_block(state_dir=tmp_path)
    assert "mistakes are how I learn" in block
    assert "predictions matched" in block


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
