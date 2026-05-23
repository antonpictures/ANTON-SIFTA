import json

import pytest

from System.swarm_civilization_shock_lab import (
    DEFAULT_SHOCKS,
    LEDGER_NAME,
    TRUTH_BOUNDARY,
    TRUTH_LABEL,
    CivilizationState,
    ShockConfig,
    ShockSpec,
    apply_shock,
    render_summary,
    run_civilization_shock_suite,
    run_single_shock,
    stability_score,
)


def test_state_and_shock_validation():
    with pytest.raises(ValueError):
        CivilizationState(name="").validate()
    with pytest.raises(ValueError):
        CivilizationState(resources=1.5).validate()
    with pytest.raises(ValueError):
        ShockSpec("unknown", 0.5).validate()
    with pytest.raises(ValueError):
        ShockSpec("memory_erase", 1.5).validate()


def test_memory_erase_reduces_memory_mass():
    base = CivilizationState()
    shocked = apply_shock(base, ShockSpec("memory_erase", 0.7))

    assert shocked.memory_mass < base.memory_mass
    assert shocked.trust_coherence < base.trust_coherence


def test_sentinel_loss_reduces_sentinels_and_raises_misinformation():
    base = CivilizationState()
    shocked = apply_shock(base, ShockSpec("sentinel_loss", 0.8))

    assert shocked.sentinels < base.sentinels * 0.5
    assert shocked.misinformation > base.misinformation


def test_resource_collapse_is_more_damaging_than_mild_write_tax():
    cfg = ShockConfig(recovery_ticks=60)
    base = CivilizationState()
    write_tax = run_single_shock(ShockSpec("write_tax", 0.2), baseline=base, config=cfg)
    collapse = run_single_shock(ShockSpec("resource_collapse", 0.9), baseline=base, config=cfg)

    assert collapse["damage"] > write_tax["damage"]
    assert collapse["stgm_cost"] > write_tax["stgm_cost"]


def test_competing_civilization_adds_pressure_but_can_increase_diversity():
    base = CivilizationState()
    shocked = apply_shock(base, ShockSpec("competing_civilization", 0.7))

    assert shocked.external_pressure > base.external_pressure
    assert shocked.diversity > base.diversity


def test_suite_writes_truth_label_receipt(tmp_path):
    result = run_civilization_shock_suite(state_root=tmp_path, write=True)

    assert result["truth_label"] == TRUTH_LABEL
    assert result["truth_class"] == "HYPOTHESIS"
    assert result["simulated"] is True
    assert result["no_real_world_prediction"] is True
    assert result["truth_boundary"] == TRUTH_BOUNDARY
    assert result["summary"]["shock_count"] == len(DEFAULT_SHOCKS)
    assert result["summary"]["recovered_count"] <= len(DEFAULT_SHOCKS)

    rows = [
        json.loads(line)
        for line in (tmp_path / LEDGER_NAME).read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 1
    assert rows[0]["kind"] == "CIVILIZATION_SHOCK_SUITE"
    assert rows[0]["truth_label"] == TRUTH_LABEL
    assert rows[0]["truth_boundary"] == TRUTH_BOUNDARY


def test_stability_score_penalizes_misinformation_and_pressure():
    clean = CivilizationState()
    noisy = CivilizationState(misinformation=0.7, external_pressure=0.6)

    assert stability_score(noisy) < stability_score(clean)


def test_render_summary_lists_monster_shocks():
    result = run_civilization_shock_suite(write=False)
    text = render_summary(result)

    assert "Civilization Shock Lab" in text
    assert "memory_erase" in text
    assert "competing_civilization" in text

