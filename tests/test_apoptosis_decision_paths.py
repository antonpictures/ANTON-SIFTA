"""Apoptosis decision paths — zero-coverage organ now probed (r1018)."""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from System.apoptosis import (
    SCAR_DEATH_THRESHOLD,
    Apoptosis,
    DeathReason,
    SwimmerVitals,
)
from System.apoptosis_engine import (
    ApoptosisEngine,
    is_metabolically_viable,
    metabolic_survival_threshold,
    salvage_through_memory_bus,
)
from System.apoptosis_organ_safety import (
    refuse_apoptosis_targets,
    should_refuse_organ_apoptosis,
)


def _vitals(**kwargs) -> SwimmerVitals:
    now = time.time()
    base = dict(
        swimmer_id="TEST_SWIM",
        born_at=now - 7200,
        last_active=now - 60,
        scars=0,
        stgm_earned=0.5,
        stgm_cost=0.1,
        skill_vector={"code": 0.8},
        task_count=5,
    )
    base.update(kwargs)
    return SwimmerVitals(**base)


def test_should_die_scar_accumulation() -> None:
    v = _vitals(scars=SCAR_DEATH_THRESHOLD)
    assert Apoptosis.should_die(v) == DeathReason.SCAR_ACCUMULATION


def test_should_die_metabolic_waste_idle_no_tasks() -> None:
    now = time.time()
    v = _vitals(
        born_at=now - 50000,
        last_active=now - 50000,
        task_count=0,
        stgm_earned=0.0,
    )
    assert Apoptosis.should_die(v) == DeathReason.METABOLIC_WASTE


def test_should_die_healthy_swimmer_lives() -> None:
    assert Apoptosis.should_die(_vitals()) is None


def test_should_die_economic_parasite_under_pressure() -> None:
    now = time.time()
    v = _vitals(
        born_at=now - 36000,
        stgm_earned=0.01,
        task_count=1,
    )
    reason = Apoptosis.should_die(v, lambda_norm=0.9)
    assert reason == DeathReason.ECONOMIC_PARASITE


def test_should_die_metabolic_starvation_when_lambda_high(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "System.stgm_metabolic.calculate_dynamic_store_fee",
        lambda _lam: 0.5,
    )
    v = _vitals(stgm_earned=0.02, stgm_cost=0.4)
    reason = Apoptosis.should_die(v, lambda_norm=0.8)
    assert reason == DeathReason.METABOLIC_STARVATION


def test_tagged_but_imported_refuses_organ_apoptosis() -> None:
    assert should_refuse_organ_apoptosis(
        tagged_apoptosis_candidate=True,
        is_imported_live=True,
    )
    assert not should_refuse_organ_apoptosis(
        tagged_apoptosis_candidate=True,
        is_imported_live=False,
    )
    assert not should_refuse_organ_apoptosis(
        tagged_apoptosis_candidate=False,
        is_imported_live=True,
    )


def test_refuse_apoptosis_targets_filters_live_imports() -> None:
    allowed = refuse_apoptosis_targets(
        ["System/apoptosis.py", "System/dead_module.py"],
        {"System/apoptosis.py"},
    )
    assert "System/dead_module.py" in allowed
    assert "System/apoptosis.py" not in allowed


def test_metabolic_survival_threshold_rises_with_lambda() -> None:
    low = metabolic_survival_threshold(0.0)
    high = metabolic_survival_threshold(0.95)
    assert high >= low


def test_is_metabolically_viable_boundary() -> None:
    thresh = metabolic_survival_threshold(0.5)
    assert is_metabolically_viable(thresh, 0.5)
    assert not is_metabolically_viable(thresh * 0.5, 0.5)


def test_salvage_skips_low_fitness_traces() -> None:
    bus = MagicMock()
    bus.remember.return_value = True
    with patch(
        "System.adaptive_constraint_memory_field.AdaptiveConstraintMemoryField"
    ) as acmf_cls:
        acmf = acmf_cls.return_value
        acmf.get_fitness.return_value = 1.0
        written = salvage_through_memory_bus(
            bus,
            "SWIM_1",
            [{"text": "high-signal salvage payload", "trace_id": "t-low"}],
            lambda_norm=0.4,
            fitness_floor=1.15,
        )
    assert written == 0
    bus.remember.assert_not_called()


def test_salvage_writes_high_fitness_trace() -> None:
    bus = MagicMock()
    bus.remember.return_value = True
    with patch(
        "System.adaptive_constraint_memory_field.AdaptiveConstraintMemoryField"
    ) as acmf_cls:
        acmf = acmf_cls.return_value
        acmf.get_fitness.return_value = 1.5
        written = salvage_through_memory_bus(
            bus,
            "SWIM_2",
            [{"text": "salvage this high-fitness trace", "trace_id": "t-high"}],
            lambda_norm=0.2,
        )
    assert written == 1
    bus.remember.assert_called_once()


def test_apoptosis_engine_delegates_viability() -> None:
    bus = MagicMock()
    engine = ApoptosisEngine(bus)
    assert engine.check_metabolic_viability("X", 1.0, 0.0) is True