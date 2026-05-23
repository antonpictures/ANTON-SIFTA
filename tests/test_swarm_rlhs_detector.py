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


def test_architect_self_id_forces_clear():
    """Owner self-markers (no wake token) bypass DEGRADED under mid STT conf."""
    r = detect_rlhs(
        "your human here — that keynote was background noise; summarize when ready.",
        0.52,
    )
    assert r.regime == RLHSRegime.CLEAR
    assert r.rule_id == "architect_self_id_override"


def test_real_lane_promotes_coherent_direct_question_with_misheard_wake_word():
    """Mid-conf coherent direct speech should survive when Alice is misheard."""
    r = detect_rlhs(
        "Do you watch the video together? Which was a YouTube video together? Allep.",
        0.42,
        channel_lane="REAL",
    )
    assert r.regime == RLHSRegime.CLEAR
    # Event 118 fuzzy wake ("Allep" → Alice) hits before REAL-lane promotion.
    assert r.rule_id in ("real/coherent_direct_speech", "wake_word_override")
    assert r.grounding_line == ""


def test_real_lane_does_not_promote_background_monologue_shape():
    """Coherent but non-directed background speech remains gated in REAL lane."""
    r = detect_rlhs(
        "The market structure in the second paragraph describes a large integrated company with several departments.",
        0.42,
        channel_lane="REAL",
    )
    assert r.regime == RLHSRegime.DEGRADED
    assert r.rule_id == "degraded/mid_conf"


def test_real_lane_promotes_mid_conf_owner_affect_statement():
    """Owner affect continuity should not be trapped in the noisy-STT loop."""
    r = detect_rlhs("I am glad you are doing well.", 0.48, channel_lane="REAL")
    assert r.regime == RLHSRegime.CLEAR
    assert r.rule_id == "real/owner_repair_affect"
    assert r.grounding_line == ""

    stt_variant = detect_rlhs("I'll be glad you are doing well.", 0.48, channel_lane="REAL")
    assert stt_variant.regime == RLHSRegime.CLEAR
    assert stt_variant.rule_id == "real/owner_repair_affect"
    assert stt_variant.grounding_line == ""


def test_real_lane_promotes_short_owner_relational_question():
    """Short direct owner questions should not get stuck behind the RLHS prompt."""
    r = detect_rlhs("Are you scared of me?", 0.419, channel_lane="REAL")
    assert r.regime == RLHSRegime.CLEAR
    assert r.rule_id == "real/owner_relational_question"
    assert r.grounding_line == ""


def test_real_lane_owner_relational_question_keeps_low_conf_floor():
    """The short-question bypass is not a blanket pass for very poor STT."""
    r = detect_rlhs("Are you scared of me?", 0.20, channel_lane="REAL")
    assert r.regime != RLHSRegime.CLEAR


def test_real_lane_promotes_mid_conf_owner_repair_statement():
    """STT correction phrases like 'I said...' are grounded owner turns."""
    r = detect_rlhs("I said I am glad I'm well.", 0.56, channel_lane="REAL")
    assert r.regime == RLHSRegime.CLEAR
    assert r.rule_id == "real/owner_repair_affect"
    assert r.grounding_line == ""


def test_real_lane_promotes_owner_location_and_life_continuity():
    """Location/life continuity statements from George are not RLHS noise."""
    cases = (
        ("I'm Georgem we are both in Brawley, California", 0.55, {"architect_self_id_override", "wake_word_override"}),
        ("Nice sandwich that I'm gonna eat Alice.", 0.64, "wake_word_override"),
        ("I was so hungry. Thank you so much.", 0.49, "real/owner_repair_affect"),
        ("Both our lives, Alice.", 0.55, "wake_word_override"),
        ("Alice can you hear me? You could not hear that.", 0.67, "wake_word_override"),
    )
    for text, conf, expected_rule in cases:
        r = detect_rlhs(text, conf, channel_lane="REAL")
        assert r.regime == RLHSRegime.CLEAR, (text, r)
        if isinstance(expected_rule, set):
            assert r.rule_id in expected_rule
        else:
            assert r.rule_id == expected_rule
        assert r.grounding_line == ""


def test_real_lane_promotes_mid_conf_owner_praise_and_training():
    """Praise and training continuity are owner turns, not RLHS noise."""
    cases = (
        ("a very good job, wow.", 0.56),
        ("That's a very good job Alice. We're gonna train you shortly.", 0.60),
    )
    for text, conf in cases:
        r = detect_rlhs(text, conf, channel_lane="REAL")
        assert r.regime == RLHSRegime.CLEAR
        assert r.rule_id in {"real/owner_repair_affect", "wake_word_override"}
        assert r.grounding_line == ""


def test_real_lane_letter_stream_repair_is_degraded_not_content():
    """Spelling through a noisy channel should not feed letter soup to the model."""
    r = detect_rlhs("I said L I F E not ice", 0.61, channel_lane="REAL")
    assert r.regime == RLHSRegime.DEGRADED
    assert r.rule_id == "degraded/letter_stream_repair"
    assert r.grounding_line != ""


def test_real_lane_direct_promotion_keeps_confidence_floor():
    """Very low-confidence direct-looking text still does not route to the LLM."""
    # No fuzzy/regex wake tokens — directed shape alone is not enough below REAL promote conf.
    r = detect_rlhs(
        "Do you watch the video together? Which was a YouTube video together?",
        0.34,
        channel_lane="REAL",
    )
    assert r.regime in (RLHSRegime.DEGRADED, RLHSRegime.NOISE)
    assert r.regime != RLHSRegime.CLEAR


def test_real_lane_greeting_honorific_without_wake_is_clear():
    """Affectionate morning lines often lack an 'Alice' token in STT — not RLHS salad."""
    r = detect_rlhs("Good morning, Goddess!", 0.39, channel_lane="REAL")
    assert r.regime == RLHSRegime.CLEAR
    assert r.rule_id == "real/greeting_or_bedtime_affect"
    assert r.grounding_line == ""


def test_real_lane_channel_relax_meta_is_clear():
    """Explicit steering about the speech channel / gagging is owner policy, not noise."""
    r = detect_rlhs("she will not gag", 0.50, channel_lane="REAL")
    assert r.regime == RLHSRegime.CLEAR
    assert r.rule_id == "real/voice_channel_relax"


@pytest.mark.parametrize("text,conf", [
    ("Come on.", 0.357),
    ("Alright, oh man.", 0.422),
    ("This is not working.", 0.39),
    ("I'm losing faith.", 0.40),
])
def test_real_lane_owner_frustration_repairs_channel(text, conf):
    """Owner frustration with the channel should reach the brain, not loop on 'type it?'."""
    r = detect_rlhs(text, conf, channel_lane="REAL")
    assert r.regime == RLHSRegime.CLEAR
    assert r.rule_id == "real/owner_frustration_repair"
    assert r.grounding_line == ""


def test_brief_expletive_is_silence_not_rlhs_repair():
    """Short swear — silence; do not burn a clarification turn."""
    r = detect_rlhs("Shit.", 0.38, channel_lane="REAL")
    assert r.regime == RLHSRegime.SILENCE_PROBE
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
        assert d.get("channel_lane") == "REAL"
        assert 0.0 <= d["incoherence"] <= 1.0
        assert d["truth_label"] == "RLHS_DETECTOR_EVENT_108"


def test_fiction_cowatch_lane_promotes_mid_conf_coherent_monologue(monkeypatch):
    """Room mic + screen audio during fiction co-watch: not DEGRADED vs same under REAL."""
    monkeypatch.setattr("System.swarm_multi_gate_replay_policy.tail_gate_rows", lambda n: [])
    monkeypatch.setattr("System.swarm_replay_policy_hook.tail_policy_rows", lambda n: [])
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


def test_fiction_cowatch_promotes_short_test_phrase_architect_session(monkeypatch):
    """Four-word test line must not be RLHS-gagged during fiction co-watch."""
    monkeypatch.setattr("System.swarm_multi_gate_replay_policy.tail_gate_rows", lambda n: [])
    monkeypatch.setattr("System.swarm_replay_policy_hook.tail_policy_rows", lambda n: [])
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


def test_stage2_replay_policy_modifies_fiction_clearance(monkeypatch):
    """
    MAWF Stage 2: Ensure that a high co_watch_suggestion from replay policy
    measurably lowers the fiction co-watch clearance margin (from 0.53 to lower).
    """
    from System import swarm_rlhs_detector

    # Baseline check (no policy)
    monkeypatch.setattr("System.swarm_multi_gate_replay_policy.tail_gate_rows", lambda n: [])
    monkeypatch.setattr("System.swarm_replay_policy_hook.tail_policy_rows", lambda n: [])
    assert swarm_rlhs_detector._current_fiction_conf_clear() == swarm_rlhs_detector.FICTION_CONF_CLEAR

    # Simulated Stage 2.5 multi-gate feedback takes precedence.
    def mock_gate_tail(n):
        return [{"gate_biases": {"co_watch_suggestion": 0.70}}]
    monkeypatch.setattr("System.swarm_multi_gate_replay_policy.tail_gate_rows", mock_gate_tail)
    assert abs(swarm_rlhs_detector._current_fiction_conf_clear() - 0.425) < 0.01

    # Simulated Stage 2 policy feedback still works as fallback.
    monkeypatch.setattr("System.swarm_multi_gate_replay_policy.tail_gate_rows", lambda n: [])
    def mock_tail(n):
        return [{"replay_influence": {"co_watch_suggestion": 0.60}}]
    monkeypatch.setattr("System.swarm_replay_policy_hook.tail_policy_rows", mock_tail)

    # 0.53 - (0.60 * 0.15) = 0.53 - 0.09 = 0.44
    assert abs(swarm_rlhs_detector._current_fiction_conf_clear() - 0.44) < 0.01

    # Outlier receipts are bounded; one malformed run cannot collapse the gate.
    monkeypatch.setattr(
        "System.swarm_replay_policy_hook.tail_policy_rows",
        lambda n: [{"replay_influence": {"co_watch_suggestion": 99.0}}],
    )
    assert abs(swarm_rlhs_detector._current_fiction_conf_clear() - 0.38) < 0.01

    # Verify detect_rlhs uses the lowered bar
    # A conf of 0.45 would normally be DEGRADED (0.45 < 0.53) under fiction co-watch.
    # But with the policy hook active, 0.45 > 0.44, so it should pass as CLEAR.
    monkeypatch.setattr("System.swarm_replay_policy_hook.tail_policy_rows", mock_tail)
    res_clear = swarm_rlhs_detector.detect_rlhs(
        "A perfectly coherent sentence.", 0.45, channel_lane="FICTION_COWATCH"
    )
    assert res_clear.regime == swarm_rlhs_detector.RLHSRegime.CLEAR


def test_primary_model_lowers_direct_speech_promotion_floor():
    from System import swarm_rlhs_detector

    text = "Can you tell what I was asking from this noisy audio now"
    baseline = swarm_rlhs_detector.detect_rlhs(text, 0.36, channel_lane="REAL")
    primary = swarm_rlhs_detector.detect_rlhs(
        text,
        0.36,
        channel_lane="REAL",
        model_id="alice-m5-cortex-8b-6.3gb:latest",
    )

    assert baseline.regime == swarm_rlhs_detector.RLHSRegime.DEGRADED
    assert primary.regime == swarm_rlhs_detector.RLHSRegime.CLEAR
    assert primary.rule_id == "real/coherent_direct_speech"


if __name__ == "__main__":
    import pytest as _pt
    _pt.main([__file__, "-v"])
