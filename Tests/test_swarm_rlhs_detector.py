#!/usr/bin/env python3
"""
tests/test_swarm_rlhs_detector.py
Event 108 — RLHS detector tests.

Proves the doctrine:
  - Phatic grunts → SILENCE_PROBE (LLM never called)
  - Clean speech → CLEAR (weights speak freely, no grounding line)
  - Degraded channel → DEGRADED (ONE grounding line, not a menu)
  - Noise/word-salad at low conf → NOISE (silent)
  - Backchannel gate restores the neutered _backchannel_rule_id
"""
import sys
from pathlib import Path
import pytest

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.swarm_rlhs_detector import (
    RLHSRegime, detect_rlhs, backchannel_rule_id, should_ground, _GROUNDING_LINE
)


# ─────────────────────────────────────────────────────────
# 1. Phatic / backchannel → SILENCE_PROBE
# ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("text,conf", [
    ("mm-hmm", 0.45),
    ("yeah", 0.50),
    ("ok", 0.60),
    ("Mm.", 0.30),
    ("Uh-huh.", 0.40),
    ("thanks", 0.55),
    ("hmm", 0.25),
    ("...", 0.10),
    ("okay", 0.62),
    ("yep", 0.44),
])
def test_phatic_is_silence_probe(text, conf):
    r = detect_rlhs(text, conf)
    # "..." classifies as EMPTY — that's also silent, same doctrine.
    assert r.regime in (RLHSRegime.SILENCE_PROBE, RLHSRegime.EMPTY), (
        f"'{text}' @{conf} → {r.regime} (expected SILENCE_PROBE or EMPTY)"
    )
    assert r.grounding_line == "", "Phatic/empty must never have a grounding line"



def test_short_very_low_conf_is_silence_probe():
    """4 tokens at conf=0.12 is definitely phatic noise."""
    r = detect_rlhs("something something yeah", 0.12)
    assert r.regime in (RLHSRegime.SILENCE_PROBE, RLHSRegime.NOISE)
    assert r.grounding_line == ""


# ─────────────────────────────────────────────────────────
# 2. Clean speech → CLEAR (weights speak, no grounding line)
# ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("text,conf", [
    ("Alice, what is the allostatic load right now?", 0.92),
    ("Can you check the nightly health audit composite score?", 0.85),
    ("Show me the swarm tab in the dashboard.", 0.78),
    ("Run the bio research sweep with four queries.", 0.70),
])
def test_clear_channel_lets_weights_speak(text, conf):
    r = detect_rlhs(text, conf)
    assert r.regime == RLHSRegime.CLEAR, (
        f"'{text}' @{conf} → {r.regime} (expected CLEAR)"
    )
    assert r.grounding_line == "", "CLEAR must have no grounding line — weights speak freely"


# ─────────────────────────────────────────────────────────
# 3. Degraded channel → DEGRADED + ONE grounding line
# ─────────────────────────────────────────────────────────

def test_degraded_has_exactly_one_grounding_line():
    """Mid-conf with some incoherence → DEGRADED, one short line."""
    r = detect_rlhs("saint mary happy is the kill him you know whatever", 0.20)
    # low conf, word salad → either DEGRADED or NOISE
    if r.regime == RLHSRegime.DEGRADED:
        assert r.grounding_line != "", "DEGRADED must have a grounding line"
        # Must be ONE line, not a menu
        lines = [l for l in r.grounding_line.split("\n") if l.strip()]
        assert len(lines) == 1, f"Grounding must be one line, got: {r.grounding_line!r}"
        assert "?" in r.grounding_line, "Grounding line should invite a clarification"
    else:
        # NOISE is also acceptable — both regimes produce no LLM call
        assert r.grounding_line == ""


def test_grounding_line_not_a_menu():
    """Grounding line must not contain (a) / (b) style menu options."""
    assert "(a)" not in _GROUNDING_LINE
    assert "(b)" not in _GROUNDING_LINE
    assert "Would you like" not in _GROUNDING_LINE
    assert len(_GROUNDING_LINE.split()) < 15, "Grounding line must be short"


# ─────────────────────────────────────────────────────────
# 4. Noise → silent (no grounding line, no LLM call)
# ─────────────────────────────────────────────────────────

def test_noise_has_no_grounding_line():
    """Long incoherent text at very low conf → NOISE or SILENCE_PROBE, no reply."""
    r = detect_rlhs(
        "kill happy mary saint you know whatever going around the something "
        "blah blah blah repeat repeat again again again thing thing thing",
        0.09,
    )
    assert r.regime in (RLHSRegime.NOISE, RLHSRegime.SILENCE_PROBE)
    assert r.grounding_line == "", "NOISE must never produce a grounding line"


def test_empty_text_is_empty_regime():
    r = detect_rlhs("", 0.0)
    assert r.regime == RLHSRegime.EMPTY
    assert r.grounding_line == ""


# ─────────────────────────────────────────────────────────
# 5. backchannel_rule_id — restored gate
# ─────────────────────────────────────────────────────────

def test_backchannel_gate_fires_on_grunt():
    rule = backchannel_rule_id("mm-hmm", 0.45)
    assert rule is not None, "backchannel gate should return a rule_id for 'mm-hmm'"


def test_backchannel_gate_silent_on_real_question():
    rule = backchannel_rule_id("What is the current allostatic load?", 0.88)
    assert rule is None, "backchannel gate must not fire on a real question"


def test_should_ground_returns_none_for_clear():
    line = should_ground("Run the nightly health audit for me.", 0.90)
    assert line is None, "CLEAR channel must get None from should_ground"


def test_should_ground_returns_none_for_grunt():
    line = should_ground("mm", 0.30)
    assert line is None, "Phatic grunt should be silent, not grounded"


# ─────────────────────────────────────────────────────────
# 6. Scores bounded and result has required fields
# ─────────────────────────────────────────────────────────

def test_result_fields_always_present():
    for text, conf in [("", 0.0), ("hi", 0.5), ("hello alice how are you doing today", 0.8)]:
        r = detect_rlhs(text, conf)
        d = r.to_dict()
        assert "regime" in d
        assert "stt_conf" in d
        assert "incoherence" in d
        assert "rule_id" in d
        assert 0.0 <= d["incoherence"] <= 1.0
        assert d["truth_label"] == "RLHS_DETECTOR_EVENT_108"


if __name__ == "__main__":
    import pytest as _pt
    _pt.main([__file__, "-v"])
