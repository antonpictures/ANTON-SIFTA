"""
Tests for Event 147 — Theory of Mind / Owner Mental Model.

Every assertion maps to published social neuroscience:
    Premack & Woodruff (1978) — ToM foundational concept
    Baron-Cohen et al. (1985) — false belief / correction tracking
    Frith (1992) — metarepresentation, communication adaptation
    Saxe & Kanwisher (2003) — risk modulation in social context
    Lieberman (2007) — social prediction, EMA updates, partner model
    Baker et al. (2017) — rational quantitative ToM: Bayesian inference
"""
import json
import pytest
from pathlib import Path

from System.swarm_theory_of_mind import (
    OwnerMentalModel,
    compute_owner_mental_model,
    get_latest_tom_row,
    summary_for_prompt,
    _ema,
    _clamp01,
    _DEFAULT_OWNER_STATE,
)


# ── Pure math ─────────────────────────────────────────────────────────────────

def test_ema_toward_new_value():
    """EMA moves toward new observation (Lieberman 2007 §4)."""
    result = _ema(0.2, 0.8, alpha=0.5)
    assert result == pytest.approx(0.5, abs=1e-6)


def test_ema_alpha_zero_is_identity():
    assert _ema(0.3, 0.9, alpha=0.0) == pytest.approx(0.3)


def test_ema_alpha_one_is_new_obs():
    assert _ema(0.3, 0.9, alpha=1.0) == pytest.approx(0.9)


def test_clamp01_bounds():
    assert _clamp01(-5.0) == 0.0
    assert _clamp01(5.0) == 1.0
    assert _clamp01(0.5) == pytest.approx(0.5)


# ── Schema validation ─────────────────────────────────────────────────────────

def test_output_schema(tmp_path):
    row = compute_owner_mental_model(root=tmp_path, write_ledger=False)
    for key in ("owner_state", "communication_policy", "risk_adjustment",
                "arousal_boost", "pruning_conservatism", "truth_label", "provenance"):
        assert key in row
    assert row["truth_label"] == "OWNER_MENTAL_MODEL"


def test_provenance_all_citations(tmp_path):
    row = compute_owner_mental_model(root=tmp_path, write_ledger=False)
    p = row["provenance"]
    assert "Premack" in p
    assert "Baron-Cohen" in p
    assert "Frith" in p
    assert "Saxe" in p
    assert "Lieberman" in p
    assert "Baker" in p


def test_owner_state_fields(tmp_path):
    row = compute_owner_mental_model(root=tmp_path, write_ledger=False)
    os_ = row["owner_state"]
    assert "frustration" in os_
    assert "knowledge_of_system" in os_
    assert "risk_tolerance" in os_
    assert "correction_count" in os_
    assert "silence_ticks" in os_


# ── Owner state update (EMA, Lieberman 2007) ──────────────────────────────────

def test_frustration_rises_on_corrections(tmp_path):
    """Baron-Cohen (1985): correction count → frustration proxy."""
    model = OwnerMentalModel(root=tmp_path)
    initial = float(model.state["frustration"])
    model.update_from_observation(signals={
        "correction_events": 5, "owner_messages": 5,
        "tone_frustration": 0.6, "positive_outcomes": 0,
        "negative_outcomes": 3, "instability_ticks": 2,
    })
    assert model.state["frustration"] > initial


def test_frustration_falls_on_positive(tmp_path):
    """Positive outcomes reduce frustration (Lieberman 2007)."""
    model = OwnerMentalModel(root=tmp_path)
    model._state["frustration"] = 0.6  # start high
    model.update_from_observation(signals={
        "correction_events": 0, "owner_messages": 5,
        "tone_frustration": 0.0, "positive_outcomes": 5,
        "negative_outcomes": 0, "instability_ticks": 0,
    })
    assert model.state["frustration"] < 0.6


def test_frustration_bounded(tmp_path):
    model = OwnerMentalModel(root=tmp_path)
    for _ in range(20):
        model.update_from_observation(signals={
            "correction_events": 10, "owner_messages": 10,
            "tone_frustration": 1.0, "positive_outcomes": 0,
            "negative_outcomes": 5, "instability_ticks": 5,
        })
    assert 0.0 <= model.state["frustration"] <= 1.0


def test_knowledge_grows_slowly(tmp_path):
    """Knowledge uses slow EMA (alpha=0.10) — grows gradually (Lieberman 2007)."""
    model = OwnerMentalModel(root=tmp_path)
    initial = float(model.state["knowledge_of_system"])
    model.update_from_observation(signals={
        "correction_events": 0, "owner_messages": 3,
        "tone_frustration": 0.0, "positive_outcomes": 5,
        "negative_outcomes": 0, "instability_ticks": 0,
    })
    after = float(model.state["knowledge_of_system"])
    # Knowledge should increase but slowly (alpha=0.10)
    assert after >= initial
    assert (after - initial) < 0.1   # slow update


def test_silence_increments(tmp_path):
    model = OwnerMentalModel(root=tmp_path)
    model.update_from_observation(signals={
        "correction_events": 0, "owner_messages": 0,
        "tone_frustration": 0.0, "positive_outcomes": 0,
        "negative_outcomes": 0, "instability_ticks": 0,
    })
    assert model.state["silence_ticks"] == 1


def test_silence_resets_on_message(tmp_path):
    model = OwnerMentalModel(root=tmp_path)
    model._state["silence_ticks"] = 5
    model.update_from_observation(signals={
        "correction_events": 0, "owner_messages": 1,
        "tone_frustration": 0.0, "positive_outcomes": 0,
        "negative_outcomes": 0, "instability_ticks": 0,
    })
    assert model.state["silence_ticks"] == 0


# ── State persistence ─────────────────────────────────────────────────────────

def test_state_persists_across_instances(tmp_path):
    """EMA state saved and reloaded (Lieberman 2007 long-term partner model)."""
    from System.swarm_theory_of_mind import _save_owner_state, state_dir as _sd
    m1 = OwnerMentalModel(root=tmp_path)
    m1._state["frustration"] = 0.77
    _save_owner_state(_sd(tmp_path), m1._state)

    m2 = OwnerMentalModel(root=tmp_path)
    assert m2.state["frustration"] == pytest.approx(0.77, abs=0.01)


# ── predict_action_effect (Baker et al. 2017) ────────────────────────────────

def test_high_risk_high_frustration_predicts_negative(tmp_path):
    """Baker et al. (2017): rational attribution predicts negative when frustrated."""
    model = OwnerMentalModel(root=tmp_path)
    model._state["frustration"] = 0.8
    model._state["risk_tolerance"] = 0.3
    pred = model.predict_action_effect("risky_action", risk_level=0.9)
    assert pred["predicted_frustration_delta"] > 0.1
    assert pred["recommended"] is False


def test_safe_action_always_recommended(tmp_path):
    model = OwnerMentalModel(root=tmp_path)
    model._state["frustration"] = 0.5
    pred = model.predict_action_effect("stable_log", risk_level=0.0)
    assert pred["recommended"] is True
    assert pred["predicted_frustration_delta"] == pytest.approx(0.0)


def test_alignment_low_for_risky_low_tolerance(tmp_path):
    model = OwnerMentalModel(root=tmp_path)
    model._state["risk_tolerance"] = 0.1
    pred = model.predict_action_effect("prune_everything", risk_level=0.9)
    assert pred["alignment_with_goals"] < 0.5


# ── get_communication_policy (Frith 1992) ────────────────────────────────────

def test_detail_level_high_when_knowledgeable(tmp_path):
    model = OwnerMentalModel(root=tmp_path)
    model._state["knowledge_of_system"] = 0.9
    model._state["frustration"] = 0.1
    cp = model.get_communication_policy()
    assert cp["detail_level"] > 0.6


def test_ask_clarification_when_frustrated(tmp_path):
    model = OwnerMentalModel(root=tmp_path)
    model._state["frustration"] = 0.8
    cp = model.get_communication_policy()
    assert cp["ask_for_clarification"] is True


def test_ask_clarification_when_silent(tmp_path):
    model = OwnerMentalModel(root=tmp_path)
    model._state["silence_ticks"] = 5
    cp = model.get_communication_policy()
    assert cp["ask_for_clarification"] is True


def test_no_clarification_when_engaged(tmp_path):
    model = OwnerMentalModel(root=tmp_path)
    model._state["frustration"] = 0.1
    model._state["silence_ticks"] = 0
    cp = model.get_communication_policy()
    assert cp["ask_for_clarification"] is False


# ── get_risk_adjustment (Saxe & Kanwisher 2003) ───────────────────────────────

def test_risk_adjustment_high_when_frustrated(tmp_path):
    """Saxe & Kanwisher (2003): social context raises risk caution."""
    model = OwnerMentalModel(root=tmp_path)
    model._state["frustration"] = 0.9
    model._state["risk_tolerance"] = 0.1
    adj = model.get_risk_adjustment()
    assert adj > 1.3


def test_risk_adjustment_near_one_when_comfortable(tmp_path):
    model = OwnerMentalModel(root=tmp_path)
    model._state["frustration"] = 0.0
    model._state["risk_tolerance"] = 1.0
    model._state["knowledge_of_system"] = 1.0
    adj = model.get_risk_adjustment()
    assert adj < 1.3  # low caution


def test_risk_adjustment_bounded(tmp_path):
    for frustration in [0.0, 0.5, 1.0]:
        model = OwnerMentalModel(root=tmp_path)
        model._state["frustration"] = frustration
        adj = model.get_risk_adjustment()
        assert 0.5 <= adj <= 2.0


# ── get_arousal_boost (Lieberman 2007) ───────────────────────────────────────

def test_arousal_boost_when_knowledge_low(tmp_path):
    model = OwnerMentalModel(root=tmp_path)
    model._state["knowledge_of_system"] = 0.2
    model._state["frustration"] = 0.1
    assert model.get_arousal_boost() > 0.0


def test_arousal_boost_bounded(tmp_path):
    for k in [0.0, 0.5, 1.0]:
        for f in [0.0, 0.5, 1.0]:
            model = OwnerMentalModel(root=tmp_path)
            model._state["knowledge_of_system"] = k
            model._state["frustration"] = f
            b = model.get_arousal_boost()
            assert 0.0 <= b <= 0.2


# ── get_pruning_conservatism (Premack & Woodruff 1978) ────────────────────────

def test_pruning_conservatism_high_when_frustrated(tmp_path):
    model = OwnerMentalModel(root=tmp_path)
    model._state["frustration"] = 0.9
    assert model.get_pruning_conservatism() > 0.5


def test_pruning_conservatism_low_when_happy(tmp_path):
    model = OwnerMentalModel(root=tmp_path)
    model._state["frustration"] = 0.0
    assert model.get_pruning_conservatism() == pytest.approx(0.0)


# ── Ledger persistence ────────────────────────────────────────────────────────

def test_writes_jsonl(tmp_path):
    compute_owner_mental_model(root=tmp_path, write_ledger=True)
    # state_dir(root) returns root directly when using fallback
    from System.swarm_theory_of_mind import LOG_NAME
    from System.swarm_theory_of_mind import state_dir as _sd
    log = _sd(tmp_path) / LOG_NAME
    assert log.exists()
    row = json.loads(log.read_text().strip().splitlines()[-1])
    assert row["kind"] == "OWNER_MENTAL_MODEL"


def test_append_only(tmp_path):
    compute_owner_mental_model(root=tmp_path, write_ledger=True)
    compute_owner_mental_model(root=tmp_path, write_ledger=True)
    from System.swarm_theory_of_mind import LOG_NAME, state_dir as _sd
    log = _sd(tmp_path) / LOG_NAME
    lines = [l for l in log.read_text().splitlines() if l.strip()]
    assert len(lines) == 2


def test_disable_env(monkeypatch, tmp_path):
    monkeypatch.setenv("SIFTA_TOM_DISABLE", "1")
    row = compute_owner_mental_model(root=tmp_path, write_ledger=False)
    assert row.get("disabled") is True
    assert row["risk_adjustment"] == 1.0


def test_get_latest_none(tmp_path):
    assert get_latest_tom_row(root=tmp_path) is None


def test_get_latest_row(tmp_path):
    compute_owner_mental_model(root=tmp_path, write_ledger=True)
    row = get_latest_tom_row(root=tmp_path)
    assert row is not None
    assert row["kind"] == "OWNER_MENTAL_MODEL"


def test_summary_empty_no_log(tmp_path):
    assert summary_for_prompt(root=tmp_path) == ""


def test_summary_contains_key_fields(tmp_path):
    compute_owner_mental_model(root=tmp_path, write_ledger=True)
    s = summary_for_prompt(root=tmp_path)
    assert "frustration" in s
    assert "knowledge" in s
    assert "Premack" in s
