from __future__ import annotations

import json
from pathlib import Path

import pytest

from System.canonical_schemas import LEDGER_SCHEMAS
from System.swarm_metabolic_homeostasis import (
    MetabolicHomeostasisConfig,
    MetabolicHomeostat,
    MetabolicState,
    proof_of_property,
)


def test_pressure_increases_with_wallet_local_and_stgm_strain():
    homeostat = MetabolicHomeostat(
        MetabolicHomeostasisConfig(
            daily_usd_limit=10.0,
            local_unit_limit_24h=100.0,
            stgm_reserve_target=100.0,
            stgm_floor=10.0,
        )
    )
    healthy = MetabolicState(usd_burn_24h=1.0, local_units_24h=5.0, stgm_balance=150.0)
    strained = MetabolicState(usd_burn_24h=8.0, local_units_24h=70.0, stgm_balance=20.0)
    critical = MetabolicState(usd_burn_24h=12.0, local_units_24h=130.0, stgm_balance=0.0)

    assert homeostat.pressure(healthy) < homeostat.pressure(strained) < homeostat.pressure(critical)
    assert homeostat.mode(homeostat.pressure(healthy)) == "GREEN_GROW"
    assert homeostat.mode(homeostat.pressure(critical)) == "CRITICAL_STARVATION"


def test_negative_stgm_forces_conservation_even_when_wallet_is_quiet():
    homeostat = MetabolicHomeostat()
    state = MetabolicState(usd_burn_24h=0.0, local_units_24h=0.0, stgm_balance=-1.0)

    pressure = homeostat.pressure(state)

    assert pressure >= homeostat.cfg.red_pressure
    assert homeostat.mode(pressure) == "RED_CONSERVE"


def test_budget_throttles_low_value_work_but_preserves_emergency_repair():
    homeostat = MetabolicHomeostat(
        MetabolicHomeostasisConfig(
            daily_usd_limit=10.0,
            local_unit_limit_24h=100.0,
            stgm_reserve_target=100.0,
            stgm_floor=10.0,
        )
    )
    state = MetabolicState(usd_burn_24h=9.0, local_units_24h=90.0, stgm_balance=5.0)

    denied = homeostat.should_spend(
        state,
        external_usd_cost=0.25,
        local_unit_cost=2.0,
        expected_value=0.1,
    )
    emergency = homeostat.should_spend(
        state,
        external_usd_cost=0.25,
        local_unit_cost=2.0,
        expected_value=0.1,
        emergency=True,
    )

    assert denied["allowed"] is False
    assert denied["reason"] in {"metabolic_throttle", "rest_cycle_required"}
    assert denied["must_rest"] is True
    assert denied["rest_seconds"] > 0.0
    assert emergency["allowed"] is True
    assert emergency["must_rest"] is False


def test_ledger_row_matches_canonical_schema(tmp_path: Path):
    homeostat = MetabolicHomeostat()
    ledger = tmp_path / "metabolic_homeostasis.jsonl"
    state = MetabolicState(usd_burn_24h=20.0, local_units_24h=400.0, stgm_balance=-5.0)

    row = homeostat.append_ledger_row(state, ledger_path=ledger, ts=123.0)
    readback = json.loads(ledger.read_text(encoding="utf-8").strip())

    assert set(row.keys()) == LEDGER_SCHEMAS["metabolic_homeostasis.jsonl"]
    assert set(readback.keys()) == LEDGER_SCHEMAS["metabolic_homeostasis.jsonl"]
    assert readback["mode"] == "CRITICAL_STARVATION"
    assert readback["budget_multiplier"] == 0.0
    assert readback["must_rest"] is True
    assert readback["rest_seconds"] > 0.0
    assert "halt_nonessential" in readback["recommendation"]


def test_invalid_metabolic_config_and_state_are_rejected():
    with pytest.raises(ValueError, match="daily_usd_limit"):
        MetabolicHomeostasisConfig(daily_usd_limit=0.0)
    with pytest.raises(ValueError, match="stgm_floor"):
        MetabolicHomeostasisConfig(stgm_floor=100.0, stgm_reserve_target=50.0)
    with pytest.raises(ValueError, match="usd_burn_24h"):
        MetabolicState(usd_burn_24h=-1.0)


def test_sample_live_reads_existing_metabolism_apis(monkeypatch):
    import System.metabolic_budget as metabolic_budget
    import System.swarm_api_metabolism as api_metabolism
    import System.warren_buffett as warren_buffett

    class FakeApiMetabolism:
        def __init__(self, daily_usd_limit: float) -> None:
            self.daily_usd_limit = daily_usd_limit

        def daily_burn(self) -> float:
            return 1.25

    monkeypatch.setattr(api_metabolism, "SwarmApiMetabolism", FakeApiMetabolism)
    monkeypatch.setattr(metabolic_budget, "ledger_total", lambda *, since_ts=None: {"cpu": 2.0, "gpu": 3.0})
    monkeypatch.setattr(warren_buffett, "profit_report", lambda: {"net_minted_estimate": -7.5})

    state = MetabolicHomeostat.sample_live()

    assert state.usd_burn_24h == pytest.approx(1.25)
    assert state.local_units_24h == pytest.approx(5.0)
    assert state.stgm_balance == pytest.approx(-7.5)


def test_metabolic_homeostasis_proof_passes():
    result = proof_of_property()
    assert result["ok"] is True
    assert result["pressure_orders"] is True
    assert result["throttles_low_value"] is True
    assert result["canonical_row"] is True
