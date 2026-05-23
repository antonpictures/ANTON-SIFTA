#!/usr/bin/env python3
"""Tests for System/swarm_syrinx.py — Alice's music/noise classifier."""
import sys
from pathlib import Path

import numpy as np
import pytest

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.swarm_syrinx import SwarmSyrinx


# ── Aliases for the two entry points ─────────────────────────────────────────
# The module exposes both the class method and a module-level shorthand.
# We test the class directly.

def _make_syrinx() -> SwarmSyrinx:
    return SwarmSyrinx(sample_rate=16000)


# ── Classification tests ─────────────────────────────────────────────────────

def test_white_noise_classified_as_speech():
    """White noise (broadband, high entropy) → NOISE_OR_SPEECH."""
    syrinx = _make_syrinx()
    np.random.seed(42)
    noise = np.random.normal(0, 1.0, 16000).astype(np.float32)
    cls, ent = syrinx.classify(noise, "TEST_NOISE")
    assert cls == "NOISE_OR_SPEECH"
    assert ent > 0.65


def test_pure_tone_classified_as_music():
    """Single sine wave (pure tone, very low entropy) → HARMONIC_SYMPHONY."""
    syrinx = _make_syrinx()
    t = np.linspace(0, 1.0, 16000)
    tone = np.sin(2 * np.pi * 440 * t).astype(np.float32)
    cls, ent = syrinx.classify(tone, "TEST_TONE")
    assert cls == "HARMONIC_SYMPHONY"
    assert ent < 0.3


def test_chord_classified_as_music():
    """A Major chord (440+554+659 Hz) + mild room noise → HARMONIC_SYMPHONY."""
    syrinx = _make_syrinx()
    t = np.linspace(0, 1.0, 16000)
    chord = (np.sin(2 * np.pi * 440 * t) +
             np.sin(2 * np.pi * 554 * t) +
             np.sin(2 * np.pi * 659 * t))
    chord += np.random.normal(0, 0.1, 16000)  # room noise
    chord = chord.astype(np.float32)
    cls, ent = syrinx.classify(chord, "TEST_CHORD")
    assert cls == "HARMONIC_SYMPHONY"
    assert ent < 0.65


def test_silence_classified_as_noise():
    """Silence → high entropy (no structure to detect)."""
    syrinx = _make_syrinx()
    silence = np.zeros(16000, dtype=np.float32)
    cls, ent = syrinx.classify(silence, "TEST_SILENCE")
    assert cls == "NOISE_OR_SPEECH"
    assert ent >= 0.99  # silence = max entropy (no signal)


def test_short_buffer_falls_back():
    """Buffer shorter than MIN_BUFFER_SAMPLES → safe fallback."""
    syrinx = _make_syrinx()
    short = np.sin(np.linspace(0, 1, 100)).astype(np.float32)
    cls, ent = syrinx.classify(short, "TEST_SHORT")
    assert cls == "NOISE_OR_SPEECH"  # too short to classify → safe default


# ── State tracking tests ─────────────────────────────────────────────────────

def test_is_music_active_after_detection():
    """After classifying music, is_music_active() returns True within window."""
    syrinx = _make_syrinx()
    t = np.linspace(0, 1.0, 16000)
    tone = np.sin(2 * np.pi * 440 * t).astype(np.float32)
    syrinx.classify(tone, "TEST")
    assert syrinx.is_music_active(lookback_seconds=2.0)


def test_is_music_active_false_initially():
    """Before any classification, is_music_active() is False."""
    syrinx = _make_syrinx()
    assert not syrinx.is_music_active()


def test_summary_for_alice_empty_when_no_music():
    """No music detected → empty prompt block."""
    syrinx = _make_syrinx()
    assert syrinx.summary_for_alice() == ""


def test_summary_for_alice_nonempty_after_music():
    """After music detection → prompt block mentions Symphony."""
    syrinx = _make_syrinx()
    t = np.linspace(0, 1.0, 16000)
    tone = np.sin(2 * np.pi * 440 * t).astype(np.float32)
    syrinx.classify(tone, "TEST")
    summary = syrinx.summary_for_alice()
    assert "HARMONIC" in summary or "Symphony" in summary


# ── Proof of property ────────────────────────────────────────────────────────

def test_proof_of_property():
    """The full proof_of_property() passes."""
    from System.swarm_syrinx import proof_of_property
    assert proof_of_property() is True
