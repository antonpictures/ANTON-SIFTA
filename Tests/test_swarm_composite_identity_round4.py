from __future__ import annotations

import time
from pathlib import Path


def test_round4_organs_enter_identity_prompt(tmp_path: Path, monkeypatch) -> None:
    from System import swarm_composite_identity as sci

    now = time.time()
    tmp_path.mkdir(exist_ok=True)
    (tmp_path / "motor_bus.jsonl").write_text(
        f'{{"ts": {now}, "coherence": 0.88, "arms_active": 8}}\n',
        encoding="utf-8",
    )
    (tmp_path / "cuttlefish_display.jsonl").write_text(
        f'{{"ts": {now}, "contrast": 0.71, "pattern": "mottle"}}\n',
        encoding="utf-8",
    )
    (tmp_path / "electric_field.jsonl").write_text(
        f'{{"ts": {now}, "phase": 0.2, "jar_active": true}}\n',
        encoding="utf-8",
    )
    (tmp_path / "waggle_quorum.jsonl").write_text(
        f'{{"ts": {now}, "angle": 1.1, "vigor": 0.93, "route": "idle"}}\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(sci, "_STATE", tmp_path)
    sci.invalidate_cache()

    snap = sci.current_identity(cache_ttl_s=0)
    block = sci.identity_system_block(snap)

    assert "octopus" in snap.organs_present
    assert "cuttlefish" in snap.organs_present
    assert "electric" in snap.organs_present
    assert "honeybee" in snap.organs_present
    assert "biological_field:" in block
    assert "octopus_arms=8" in block
    assert "cuttlefish_pattern=mottle" in block
    assert "electric_jar_active=True" in block
    assert "waggle_route=idle" in block


def test_body_monitor_organ_field_enters_identity_prompt(monkeypatch) -> None:
    from System import swarm_body_monitor as body
    from System import swarm_composite_identity as sci

    monkeypatch.setattr(
        body,
        "summary_for_alice",
        lambda: "STIGMERGIC ORGAN FIELD (Body Monitor; declared organs only):\n"
        "- truth_counts: REAL=17 DEMO=0 BROKEN=0 UNKNOWN=0\n"
        "- organs: field:REAL:live_ledger:test",
    )

    block = sci.identity_system_block(sci.IdentitySnapshot())

    assert "STIGMERGIC ORGAN FIELD" in block
    assert "REAL=17 DEMO=0 BROKEN=0 UNKNOWN=0" in block
    assert "field:REAL:live_ledger:test" in block


def test_high_dimensional_field_enters_identity_prompt(tmp_path: Path, monkeypatch) -> None:
    from System import swarm_composite_identity as sci

    now = time.time()
    (tmp_path / "organ_field_vector.jsonl").write_text(
        '{"ts": %s, "payload": {"dimension_count": 49, "field_energy": 0.42, "coupling_edge_count": 31, "coupling_density": 0.633, "declared_organ_count": 17, "connected_organ_count": 17, "swimmer_count": 45, "organ_health": {"field": 0.42, "td_learner": 1.0, "bg_selector": 0.5}, "unknown_vector_count": 2, "low_resolution_vector_count": 9, "weak_vector_count": 1, "field_completeness": 0.882352, "cost_pressure": 0.125, "metabolic_cost": {"latency_ms": 100.0, "estimated_joules": 0.8, "thermal_stress": 0.0}, "field_homeostasis_state": "VIABLE", "field_control_action": "maintain", "field_memory_retention": 0.75, "motor_effector_policy": {"selected_motor_policy": "heartbeat"}, "truth_reward": -0.1, "unknown_vectors": [{"organ": "reflex"}, {"organ": "corvid"}], "source_ledgers": ["waggle_quorum.jsonl", "motor_bus.jsonl", "electric_field.jsonl", "cuttlefish_display.jsonl"]}}\n'
        % now,
        encoding="utf-8",
    )
    monkeypatch.setattr(sci, "_STATE", tmp_path)
    sci.invalidate_cache()

    snap = sci.current_identity(cache_ttl_s=0)
    block = sci.identity_system_block(snap)

    assert "high_dimensional_field" in snap.organs_present
    assert "high_dimensional_field:" in block
    assert "dims=49" in block
    assert "edges=31" in block
    assert "organs=17/17" in block
    assert "swimmers=45" in block
    assert "density=0.633" in block
    assert "energy=0.420" in block
    assert "organ_health_mean=0.640" in block
    assert "unknowns=2" in block
    assert "lowres=9" in block
    assert "weak=1" in block
    assert "completeness=0.882" in block
    assert "cost=0.125" in block
    assert "latency_ms=100.0" in block
    assert "joules=0.800" in block
    assert "thermal=0.000" in block
    assert "homeostasis=VIABLE" in block
    assert "control=maintain" in block
    assert "retention=0.750" in block
    assert "motor=heartbeat" in block
    assert "truth_reward=-0.100" in block
    assert "unknown_organs=reflex,corvid" in block


def test_working_body_field_digest_is_bounded_front_context() -> None:
    from System import swarm_composite_identity as sci

    snap = sci.IdentitySnapshot(
        soma_score=0.568,
        soma_label="STRESSED",
        pain_intensity=0.2,
        energy_reserve=0.4,
        visceral_source="visceral_field.jsonl",
        visceral_age_s=12.34,
        somatic_contradictions=["claimed_sleep_without_ledger"],
        truth_continuity_score=0.91,
        truth_continuity_flags=["somatic_gap"],
        field_dimension_count=53,
        field_coupling_edge_count=46,
        field_declared_organ_count=17,
        field_connected_organ_count=17,
        field_completeness=1.0,
        field_unknown_vector_count=0,
        field_low_resolution_vector_count=14,
        field_cost_pressure=0.268,
        field_homeostasis_state="VIABLE",
        field_control_action="maintain",
        field_memory_retention=0.957,
        field_motor_policy="alarm",
        field_truth_reward=-0.09,
    )

    digest = sci.working_body_field_digest(snap)

    assert digest.startswith("WORKING BODY FIELD DIGEST")
    assert "soma_score=0.568" in digest
    assert "source=visceral_field.jsonl" in digest
    assert "score=0.910" in digest
    assert "td_reward=-0.090" in digest
    assert "dims=53" in digest
    assert "organs=17/17" in digest
    assert "unknowns=0" in digest
    assert "lowres=14" in digest
    assert "homeostasis=VIABLE" in digest
    assert "alive_real: OPERATIONAL_UNDER_POWER" in digest
    assert "AGI_arbitrary_domain_open_ended=NOT_CERTIFIED_UNTIL_DECLARED_GATE_SUITE" in digest
