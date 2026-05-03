import json
import pytest
from System.swarm_causal_intervention_logger import CausalInterventionLogger


def _sample(tmp_path, **kwargs):
    logger = CausalInterventionLogger(root=tmp_path)
    defaults = dict(
        tick_id=1,
        do_vars={"gate": "explore_novel", "wm_lr": 0.05},
        expected_effect_on="replay_buffer_composition",
        observed_shift={"kl_divergence_pre_post": 0.31, "direction_matches": True},
        causal_effect_size=0.28,
        confounder_check={"owner_switch": False, "global_surprise": 1.2},
        organ="arbiter",
    )
    defaults.update(kwargs)
    return logger, logger.log_intervention(**defaults)


def test_intervention_writes_exact_schema(tmp_path):
    logger, row = _sample(tmp_path)
    assert row["truth_label"] == "CAUSAL_CLOSURE_INTERVENTION"
    assert isinstance(row["causal_effect_size"], float)
    assert "intervention" in row
    assert row["intervention"]["do"]["gate"] == "explore_novel"
    assert row["direction_matches"] is True


def test_causal_effect_size_always_float(tmp_path):
    _, row = _sample(tmp_path, causal_effect_size=1)
    assert isinstance(row["causal_effect_size"], float)


def test_confounder_flag_when_owner_switch(tmp_path):
    _, row = _sample(
        tmp_path,
        confounder_check={"owner_switch": True, "global_surprise": 0.2},
    )
    # Row is still written but confounder_clean is False
    assert "intervention" in row
    assert row["confounder_clean"] is False


def test_log_written_to_jsonl(tmp_path):
    logger, _ = _sample(tmp_path)
    _sample(tmp_path)  # second row
    rows = logger.recent(10)
    assert len(rows) == 2
    for r in rows:
        assert r["truth_label"] == "CAUSAL_CLOSURE_INTERVENTION"


def test_causal_closure_gate_requires_min_interventions(tmp_path):
    logger = CausalInterventionLogger(root=tmp_path)
    # No interventions yet
    assert not logger.causal_closure_proven(min_interventions=1)

    # One clean, directional hit
    logger.log_intervention(
        tick_id=1,
        do_vars={"gate": "explore"},
        expected_effect_on="replay",
        observed_shift={"direction_matches": True},
        causal_effect_size=0.5,
        confounder_check={"owner_switch": False},
    )
    assert logger.causal_closure_proven(min_interventions=1)
    assert not logger.causal_closure_proven(min_interventions=2)


def test_summary_for_prompt_empty_when_no_data(tmp_path):
    logger = CausalInterventionLogger(root=tmp_path)
    assert logger.summary_for_prompt() == ""


def test_summary_for_prompt_non_empty_after_interventions(tmp_path):
    logger, _ = _sample(tmp_path)
    s = logger.summary_for_prompt()
    assert "Event 138" in s
    assert "intervention" in s.lower()
