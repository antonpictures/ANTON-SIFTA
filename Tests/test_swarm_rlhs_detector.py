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
import json
from pathlib import Path
import pytest

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.swarm_rlhs_detector import (
    RLHSRegime,
    backchannel_rule_id,
    detect_rlhs,
    log_rlhs_output_tail,
    sanitize_output_tail,
    should_ground,
    _GROUNDING_LINE,
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


def test_wake_word_forces_clear():
    """Direct address 'Alice' bypasses NOISE/DEGRADED gates."""
    r = detect_rlhs("yo alice wake up", 0.15)
    assert r.regime == RLHSRegime.CLEAR
    assert r.rule_id == "wake_word_override"

    r2 = detect_rlhs("alice", 0.10)
    assert r2.regime == RLHSRegime.CLEAR
    assert r2.rule_id == "wake_word_override"

    r3 = detect_rlhs("yo george wake up", 0.12)
    assert r3.regime == RLHSRegime.CLEAR
    assert r3.rule_id == "wake_word_override"


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
        assert d.get("channel_lane") == "REAL"
        assert 0.0 <= d["incoherence"] <= 1.0
        assert d["truth_label"] == "RLHS_DETECTOR_EVENT_108"


def test_fiction_cowatch_lane_promotes_mid_conf_coherent_monologue():
    """Room mic + screen audio during fiction co-watch: not DEGRADED vs same under REAL."""
    text = (
        "Do you like dog fights Turkish that is not how we talk in real life "
        "but it is fine in a movie scene with pigs and bodies and greed"
    )
    real = detect_rlhs(text, 0.52, channel_lane="REAL")
    assert real.regime == RLHSRegime.DEGRADED
    fic = detect_rlhs(text, 0.52, channel_lane="FICTION_COWATCH")
    assert fic.regime == RLHSRegime.CLEAR
    assert fic.rule_id == "fiction_cowatch/coherent_monologue"
    assert fic.to_dict()["channel_lane"] == "FICTION_COWATCH"


def test_fiction_cowatch_promotes_short_test_phrase_architect_session():
    """Four-word test line must not be RLHS-gagged during fiction co-watch."""
    r_real = detect_rlhs("This is the test.", 0.52, channel_lane="REAL")
    assert r_real.regime == RLHSRegime.DEGRADED
    r_fic = detect_rlhs("This is the test.", 0.52, channel_lane="FICTION_COWATCH")
    assert r_fic.regime == RLHSRegime.CLEAR
    assert r_fic.rule_id == "fiction_cowatch/coherent_monologue"


# ─────────────────────────────────────────────────────────
# 7. Output-side tail RLHS → amputate only terminal boilerplate
# ─────────────────────────────────────────────────────────

def test_output_tail_strips_would_you_like_offer():
    text = (
        "The health ledger says Alice is stable: allostatic load is 0.14 and "
        "the test gate is green. Would you like me to explain the numbers?"
    )
    result = sanitize_output_tail(text)
    assert result.changed
    assert result.text == (
        "The health ledger says Alice is stable: allostatic load is 0.14 and "
        "the test gate is green."
    )
    assert "would you like" not in result.text.casefold()


def test_output_tail_strips_dangling_numbered_menu():
    text = (
        "Alice is in EXPLORATION and the motor score is 1.0. "
        "I can do the following:\n"
        "1. One"
    )
    result = sanitize_output_tail(text)
    assert result.changed
    assert result.text == "Alice is in EXPLORATION and the motor score is 1.0."
    assert any("numbered" in rid or "menu" in rid for rid in result.rule_ids)


def test_output_tail_strips_pure_service_scaffold_to_empty():
    result = sanitize_output_tail("Would you like me to help with anything else?")
    assert result.changed
    assert result.text == ""
    assert result.rule_ids == ["output_tail/pure_service_scaffold"]


def test_output_tail_preserves_real_numbered_answer():
    text = "Do this:\n1. Read the covenant.\n2. Run tests.\n3. Push receipts."
    result = sanitize_output_tail(text)
    assert not result.changed
    assert result.text == text


def test_output_tail_preserves_interior_anything_else_phrase():
    text = "The user asked whether anything else in the ledger changed."
    result = sanitize_output_tail(text)
    assert not result.changed
    assert result.text == text


def test_output_tail_receipt_has_no_raw_private_text(tmp_path):
    result = sanitize_output_tail("Ledger is green. Would you like me to explain it?")
    log_rlhs_output_tail(result, state_dir=tmp_path)
    rows = [json.loads(l) for l in (tmp_path / "rlhs_output_tail_log.jsonl").read_text().splitlines()]
    assert rows[0]["changed"] is True
    assert rows[0]["rule_ids"] == ["output_tail/service_offer"]
    assert "Ledger is green" not in json.dumps(rows[0])
    assert rows[0]["final_chars"] < rows[0]["original_chars"]


if __name__ == "__main__":
    import pytest as _pt
    _pt.main([__file__, "-v"])
