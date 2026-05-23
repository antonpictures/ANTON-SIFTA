import json
import random
from unittest.mock import patch

from System.swarm_consciousness_engine import ConsciousnessEngine
from System.swarm_metabolic_homeostasis import MetabolicState
from System.swarm_now_state import build_now_state, circadian_phase_for_hour, now_state_prompt_block


def _reading(hour: int, *, source: str = "hardware_time_oracle") -> dict:
    return {
        "ok": True,
        "source": source,
        "confidence": 1.0 if source == "hardware_time_oracle" else 0.8,
        "local_human": f"Friday May 01 2026, {hour:02d}:00",
        "local_iso": f"2026-05-01T{hour:02d}:00:00",
        "timezone": "PDT",
        "epoch": 1777651200 + hour * 3600,
        "signature": "abc123",
    }


def test_now_state_truth_labels_and_circadian_phase():
    morning = build_now_state(_reading(8))
    night = build_now_state(_reading(23, source="os_local_clock"))

    assert morning["truth_label"] == "OBSERVED_HARDWARE_SIGNED"
    assert morning["circadian"]["phase"] == "morning"
    assert morning["circadian"]["truth_label"] == "OPERATIONAL_HEURISTIC"
    assert morning["circadian"]["explore_bias"] > 0
    assert night["truth_label"] == "OBSERVED_OS_CLOCK"
    assert night["circadian"]["phase"] == "night"
    assert night["circadian"]["sleep_pressure_bias"] > 0


def test_now_state_prompt_block_is_explicit_about_heuristic():
    block = now_state_prompt_block(build_now_state(_reading(14)))

    assert "NOW STATE (situated time, Event 89)" in block
    assert "circadian_phase=afternoon" in block
    assert "coarse local-hour heuristic" in block


def test_consciousness_tick_records_now_state_without_runaway(tmp_path):
    morning = build_now_state(_reading(8))
    night = build_now_state(_reading(23))
    healthy = MetabolicState(stgm_balance=150.0)

    morning_engine = ConsciousnessEngine(state_dir=tmp_path / "m", rng=random.Random(1))
    night_engine = ConsciousnessEngine(state_dir=tmp_path / "n", rng=random.Random(1))

    morning_state = morning_engine.tick(
        dt_s=60.0,
        now=100.0,
        now_state=morning,
        metabolic_state=healthy,
        commit=True,
    )
    night_state = night_engine.tick(
        dt_s=60.0,
        now=100.0,
        now_state=night,
        metabolic_state=healthy,
        commit=True,
    )

    assert morning_state.now_state["circadian"]["phase"] == "morning"
    assert night_state.now_state["circadian"]["phase"] == "night"
    assert morning_state.circadian_phase == "morning"
    assert night_state.circadian_phase == "night"
    assert abs(morning_state.free_energy - night_state.free_energy) <= 0.02

    row = json.loads((tmp_path / "m" / "consciousness_state.jsonl").read_text().splitlines()[0])
    assert row["now_state"]["schema_version"] == "event89.now_state.v1"
    assert row["truth_labels"]["now_state"] == "OBSERVED_HARDWARE_SIGNED"


def test_body_brain_tick_passes_now_state_into_memory(tmp_path):
    from System.swarm_body_brain_loop import SwarmPhysiology

    now_state = build_now_state(_reading(6))

    with patch("System.swarm_body_brain_loop._STATE_DIR", tmp_path):
        with patch("System.swarm_body_brain_loop.build_now_state", return_value=now_state):
            with patch(
                "System.swarm_body_brain_loop.MetabolicHomeostat.sample_live",
                return_value=MetabolicState(stgm_balance=150.0),
            ):
                with patch("time.sleep"):
                    result = SwarmPhysiology().body_brain_tick()

    row = json.loads((tmp_path / "body_brain_memory.jsonl").read_text().splitlines()[0])
    assert result["now_state"]["circadian"]["phase"] == "morning"
    assert row["now_state"]["schema_version"] == "event89.now_state.v1"
    assert row["circadian_phase"] == "morning"
