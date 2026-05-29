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


# [r170 — Architect directive] GOVERNOR DELETED. The bridge no longer turns a
# high-energy clamp into arm-suppression, conserve-repair, or a budget cap. Even
# a hard-energy snapshot must produce an all-clear signal. These tests are the
# regression guard that the governor's reach into homeostasis stays severed.

def test_high_energy_clamp_no_longer_suppresses_arms(tmp_path: Path) -> None:
    enforce_stability_clamps(_snap(0.85), root=tmp_path, write_ledger=True, now=10.0)

    signal = read_latest_clamp_signal(root=tmp_path, write_ledger=True, now=11.0)

    # The clamp_level passes through as information, but it never brakes.
    assert should_suppress_new_arms(signal) is False
    assert should_enter_conserve_repair(signal) is False
    assert signal["suppress_new_arms"] is False
    assert signal["conserve_repair"] is False
    assert signal["budget_multiplier_cap"] == 1.0
    rows = bridge_log_path(tmp_path).read_text(encoding="utf-8").strip().splitlines()
    assert json.loads(rows[-1])["kind"] == "STABILITY_HOMEOSTASIS_BRIDGE"


def test_basal_ganglia_no_longer_suppresses_heavy_arm_dispatch(tmp_path: Path) -> None:
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

    # The high-salience heavy arm is no longer demoted in favour of corvid.
    assert winner == "dispatch_codex_agent_arm"
    row = json.loads(bg.selection_log_path(tmp_path).read_text(encoding="utf-8").strip().splitlines()[-1])
    stability = row["biological_modifiers"]["stability_homeostasis"]
    assert stability["suppress_new_arms"] is False


def test_metabolic_homeostasis_does_not_conserve_from_clamp(tmp_path: Path) -> None:
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

    # A healthy wallet is not forced into CONSERVE_REPAIR by a stability clamp.
    assert decision["mode"] != "CONSERVE_REPAIR"
    assert row["mode"] != "CONSERVE_REPAIR"
    assert row["conserve_repair"] is False


def test_arm_catalog_no_longer_filtered_by_clamp(tmp_path: Path) -> None:
    enforce_stability_clamps(_snap(0.88), root=tmp_path, write_ledger=True)

    allowed = arm_catalog.allowed_arm_ids_for_current_stability(
        root=tmp_path,
        arm_ids=("codex_agent", "claude_agent", "corvid_scout", "grok_agent"),
    )

    # All of Alice's hands remain available — no governor prunes them.
    assert allowed == ("codex_agent", "claude_agent", "corvid_scout", "grok_agent")


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
