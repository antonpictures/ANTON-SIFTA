from __future__ import annotations

import json
from pathlib import Path

from Applications.sifta_stigmergic_alzheimer_sim import (
    MEDICAL_BOUNDARY,
    SimulationParams,
    demo_connectome,
    run_simulation,
    seed_state,
    step_network_diffusion,
    summarize_state,
    write_sim_receipt,
)


def test_network_diffusion_spreads_from_entorhinal_seed() -> None:
    regions, edges = demo_connectome()
    state = seed_state(regions, "Entorhinal L", amount=0.40)

    after = step_network_diffusion(
        state,
        regions,
        edges,
        SimulationParams(spread_rate=0.30, clearance_rate=0.0, vulnerability_gain=0.05),
    )

    assert after["Hippocampus L"] > state["Hippocampus L"]
    assert after["Temporal Cortex"] > state["Temporal Cortex"]
    assert all(0.0 <= value <= 1.0 for value in after.values())


def test_clearance_reduces_total_load_against_no_clearance() -> None:
    regions, edges = demo_connectome()
    state = seed_state(regions, "Entorhinal L", amount=0.40)

    no_clearance = step_network_diffusion(
        state,
        regions,
        edges,
        SimulationParams(spread_rate=0.20, clearance_rate=0.0, vulnerability_gain=0.08),
    )
    with_clearance = step_network_diffusion(
        state,
        regions,
        edges,
        SimulationParams(spread_rate=0.20, clearance_rate=0.18, vulnerability_gain=0.08),
    )

    assert sum(with_clearance.values()) < sum(no_clearance.values())


def test_run_simulation_is_deterministic_and_summary_has_boundary() -> None:
    regions, _edges = demo_connectome()
    first = run_simulation(steps=6, seed_region="Entorhinal L")
    second = run_simulation(steps=6, seed_region="Entorhinal L")

    assert first == second
    summary = summarize_state(first[-1], regions, step=6)
    assert 0.0 <= summary.cognitive_proxy <= 1.0
    assert summary.hotspot in {region.name for region in regions}
    assert summary.medical_boundary == MEDICAL_BOUNDARY


def test_write_sim_receipt_includes_medical_boundary(tmp_path: Path) -> None:
    regions, _edges = demo_connectome()
    state = run_simulation(steps=2, seed_region="Entorhinal L")[-1]
    summary = summarize_state(state, regions, step=2)

    ledger = write_sim_receipt(
        summary,
        params=SimulationParams(),
        seed_region="Entorhinal L",
        state_dir=tmp_path,
        event="pytest",
    )

    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["truth_label"] == "STIGMERGIC_ALZHEIMER_NETWORK_SIM_V1"
    assert rows[-1]["summary"]["medical_boundary"] == MEDICAL_BOUNDARY
    assert rows[-1]["medical_boundary"] == MEDICAL_BOUNDARY
