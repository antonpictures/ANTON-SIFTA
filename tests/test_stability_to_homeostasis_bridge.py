from __future__ import annotations

import json
from pathlib import Path

from System import swarm_arm_skills_catalog as arm_catalog
from System import swarm_basal_ganglia_action_selector as bg
from System.swarm_metabolic_homeostasis import (
    MetabolicHomeostasisConfig,
    MetabolicHomeostat,
    MetabolicState,
)
from System.swarm_stability_audit import enforce_stability_clamps
from System.swarm_stability_to_homeostasis_bridge import (
    bridge_log_path,
    read_latest_clamp_signal,
    should_enter_conserve_repair,
    should_suppress_new_arms,
)


def _snap(energy: float, delta: float = 0.0) -> dict:
    return {
        "lyapunov_energy": energy,
        "delta_lyapunov_energy": delta,
        "terms": {"astrocyte_heat_norm": 0.0},
        "stable": True,
    }


def test_emergency_clamp_becomes_conserve_repair_signal(tmp_path: Path) -> None:
    receipt = enforce_stability_clamps(_snap(0.85), root=tmp_path, write_ledger=True, now=10.0)

    signal = read_latest_clamp_signal(root=tmp_path, write_ledger=True, now=11.0)

    assert receipt["clamp_level"] == "EMERGENCY"
    assert signal["clamp_level"] == "EMERGENCY"
    assert should_suppress_new_arms(signal) is True
    assert should_enter_conserve_repair(signal) is True
    rows = bridge_log_path(tmp_path).read_text(encoding="utf-8").strip().splitlines()
    assert json.loads(rows[-1])["kind"] == "STABILITY_HOMEOSTASIS_BRIDGE"


def test_basal_ganglia_suppresses_heavy_arm_dispatch_under_emergency(tmp_path: Path) -> None:
    enforce_stability_clamps(_snap(0.9), root=tmp_path, write_ledger=True)
    loops = [
        {
            "name": "dispatch_codex_agent_arm",
            "arm_id": "codex_agent",
            "salience": 1.0,
            "cost": 0.0,
            "reward_potential": 1.0,
        },
        {
            "name": "local_repair_corvid",
            "arm_id": "corvid_scout",
            "salience": 0.35,
            "cost": 0.2,
            "reward_potential": 0.4,
        },
    ]

    winner, _score = bg.select_action(loops, dopamine_level=0.5, root=tmp_path, write_ledger=True)

    assert winner == "local_repair_corvid"
    row = json.loads(bg.selection_log_path(tmp_path).read_text(encoding="utf-8").strip().splitlines()[-1])
    stability = row["biological_modifiers"]["stability_homeostasis"]
    assert stability["clamp_level"] == "EMERGENCY"
    assert stability["suppress_new_arms"] is True
    assert stability["bias"]["reason"] == "conserve_repair"
    assert "dispatch_codex_agent_arm" in stability["bias"]["suppressed_candidates"]


def test_metabolic_homeostasis_enters_conserve_repair_from_signal(tmp_path: Path) -> None:
    enforce_stability_clamps(_snap(0.85), root=tmp_path, write_ledger=True)
    signal = read_latest_clamp_signal(root=tmp_path)
    homeostat = MetabolicHomeostat(
        MetabolicHomeostasisConfig(
            daily_usd_limit=10.0,
            local_unit_limit_24h=100.0,
            stgm_reserve_target=100.0,
            stgm_floor=10.0,
        )
    )
    state = MetabolicState(usd_burn_24h=0.0, local_units_24h=0.0, stgm_balance=150.0)

    decision = homeostat.should_spend(
        state,
        external_usd_cost=0.01,
        local_unit_cost=1.0,
        expected_value=0.5,
        stability_signal=signal,
    )
    row = homeostat.build_ledger_row(state, stability_signal=signal, ts=20.0)

    assert decision["allowed"] is False
    assert decision["mode"] == "CONSERVE_REPAIR"
    assert decision["reason"] == "stability_conserve_repair"
    assert row["mode"] == "CONSERVE_REPAIR"
    assert row["conserve_repair"] is True
    assert row["budget_multiplier"] <= 0.2
    assert row["stability_clamp_level"] == "EMERGENCY"


def test_arm_catalog_filters_to_cheap_local_arm_only_in_conserve_repair(tmp_path: Path) -> None:
    enforce_stability_clamps(_snap(0.88), root=tmp_path, write_ledger=True)

    allowed = arm_catalog.allowed_arm_ids_for_current_stability(
        root=tmp_path,
        arm_ids=("codex_agent", "claude_agent", "corvid_scout", "grok_agent"),
    )

    assert allowed == ("corvid_scout",)


def test_low_energy_clamp_clears_suppression_and_normal_modes(tmp_path: Path) -> None:
    enforce_stability_clamps(_snap(0.1), root=tmp_path, write_ledger=True)
    signal = read_latest_clamp_signal(root=tmp_path)
    homeostat = MetabolicHomeostat()
    state = MetabolicState(usd_burn_24h=0.0, local_units_24h=0.0, stgm_balance=150.0)

    assert should_suppress_new_arms(signal) is False
    assert should_enter_conserve_repair(signal) is False
    assert homeostat.build_ledger_row(state, stability_signal=signal)["mode"] == "GREEN_GROW"
    allowed = arm_catalog.allowed_arm_ids_for_current_stability(
        root=tmp_path,
        arm_ids=("codex_agent", "corvid_scout"),
    )
    assert allowed == ("codex_agent", "corvid_scout")
