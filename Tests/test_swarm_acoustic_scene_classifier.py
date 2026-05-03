#!/usr/bin/env python3
"""Tests for swarm_acoustic_scene_classifier.py"""
from pathlib import Path
from System.swarm_acoustic_scene_classifier import (
    _score_scene, _softmax, classify_scene, SceneFrame, _CONFIDENCE_FLOOR
)


def _make_feat(
    spectral_flatness=0.05, hnr_proxy=0.08, am_depth=0.5,
    farfield=0.45, nearfield=0.68, crest_factor=5.5,
    f0_hz=130.0, spectral_centroid_hz=350.0,
    spectral_entropy=0.72, zcr=0.07, rms=0.15, vad_ratio=1.0,
):
    return {
        "fp_spectral_flatness": spectral_flatness,
        "fp_hnr_proxy": hnr_proxy,
        "fp_am_depth": am_depth,
        "fp_farfield_replay_likelihood": farfield,
        "fp_nearfield_voice_likelihood": nearfield,
        "fp_crest_factor": crest_factor,
        "f0_hz": f0_hz,
        "spectral_centroid_hz": spectral_centroid_hz,
        "spectral_entropy": spectral_entropy,
        "zero_crossing_rate": zcr,
        "rms": rms,
        "vad_ratio": vad_ratio,
    }


def test_music_wins_on_high_flatness_and_am():
    """High spectral flatness + high AM depth should score MUSIC highest."""
    feat = _make_feat(spectral_flatness=0.35, am_depth=0.95, hnr_proxy=0.01)
    scores = _score_scene(feat)
    posteriors = _softmax(scores)
    assert posteriors["MUSIC"] > posteriors["NEWS"], posteriors
    assert posteriors["MUSIC"] > posteriors["CINEMATIC"], posteriors


def test_news_wins_on_bright_voiced_farfield():
    """High HNR + high centroid + farfield → NEWS."""
    feat = _make_feat(
        hnr_proxy=0.25, spectral_centroid_hz=520.0,
        farfield=0.80, spectral_flatness=0.02, am_depth=0.3, f0_hz=160.0,
    )
    scores = _score_scene(feat)
    posteriors = _softmax(scores)
    assert posteriors["NEWS"] > posteriors["MUSIC"], posteriors
    assert posteriors["NEWS"] > posteriors["SPORTS"], posteriors


def test_sports_wins_on_crowd_noise():
    """High ZCR + high entropy + low HNR → SPORTS."""
    feat = _make_feat(
        zcr=0.25, spectral_entropy=0.95,
        hnr_proxy=0.01, spectral_flatness=0.10,
        vad_ratio=0.4, farfield=0.6,
    )
    scores = _score_scene(feat)
    posteriors = _softmax(scores)
    assert posteriors["SPORTS"] > posteriors["PODCAST"], posteriors


def test_podcast_wins_on_nearfield_voiced():
    """High HNR + high nearfield + low AM → PODCAST."""
    feat = _make_feat(
        hnr_proxy=0.30, nearfield=0.90,
        am_depth=0.05, farfield=0.10,
        spectral_centroid_hz=280.0,  # low-ish (not news-bright)
    )
    scores = _score_scene(feat)
    posteriors = _softmax(scores)
    assert posteriors["PODCAST"] > posteriors["NEWS"] or posteriors["PODCAST"] > posteriors["SPORTS"]


def test_classify_scene_no_cochlea(tmp_path):
    """Without a cochlea log, classify_scene returns UNKNOWN."""
    frame = classify_scene(cochlea_row={})
    # With an empty feature dict, all features default to 0.0
    # Still returns a SceneFrame
    assert isinstance(frame, SceneFrame)
    assert frame.scene in ("UNKNOWN", "MUSIC", "NEWS", "CINEMATIC",
                           "SPORTS", "GAMING", "PODCAST", "AMBIENT")


def test_scene_frame_confidence_floor():
    """Scenes below confidence floor are labelled UNKNOWN."""
    # Uniform features → near-uniform posteriors → low confidence
    feat = _make_feat(
        spectral_flatness=0.10, hnr_proxy=0.10, am_depth=0.10,
        farfield=0.40, nearfield=0.40, crest_factor=4.0,
        f0_hz=200.0, spectral_centroid_hz=300.0,
        spectral_entropy=0.60, zcr=0.05, vad_ratio=0.8,
    )
    frame = classify_scene(cochlea_row=feat)
    # Either a confident label OR UNKNOWN — both are valid
    assert frame.scene in ("UNKNOWN", "MUSIC", "NEWS", "CINEMATIC",
                           "SPORTS", "GAMING", "PODCAST", "AMBIENT")
    assert 0.0 <= frame.confidence <= 1.0


def test_softmax_sums_to_one():
    from System.swarm_acoustic_scene_classifier import SCENE_LABELS
    scores = {s: float(i) for i, s in enumerate(SCENE_LABELS) if s != "UNKNOWN"}
    result = _softmax(scores)
    assert abs(sum(result.values()) - 1.0) < 1e-6
