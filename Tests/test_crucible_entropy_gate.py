from __future__ import annotations

import json

from Applications.sifta_crucible_swarm_sim import CrucibleConfig, CrucibleSim
from System import swarm_camera_target as camera_target
from swarmrl.tasks import EntropyGateConfig, StigmergicEntropyGate


def test_entropy_gate_exports_from_task_package():
    task = StigmergicEntropyGate(EntropyGateConfig(grid_size=12, deposit_strength=0.2))

    assert task.field.shape == (12, 12)


def test_crucible_swimmers_write_stigmergic_memory():
    cfg = CrucibleConfig(
        agents=16,
        seed=2026,
        base_packets_per_tick=2,
        onslaught_packets_per_tick=6,
        server_capacity=20,
        stigmergic_deposit_strength=0.2,
        stigmergic_decay=0.97,
    )
    sim = CrucibleSim(cfg)
    sim.trigger_onslaught()

    metrics = {}
    for _ in range(8):
        metrics = sim.step()

    assert metrics["stig_field_max"] > 0.0
    assert metrics["stig_reward_max"] > 0.0
    assert sim.stigmergic_task.glyph()
    assert sim.swimmer_rewards.shape == (len(sim.swimmers),)
    assert sim.swimmer_field_sense.shape == (len(sim.swimmers),)


def test_crucible_anomalies_activate_immune_quorum_repair():
    cfg = CrucibleConfig(
        agents=18,
        seed=2027,
        base_packets_per_tick=0,
        onslaught_packets_per_tick=12,
        anomaly_prob_onslaught=1.0,
        server_capacity=60,
        immune_grid_size=48,
        immune_damage_max_centers=12,
    )
    sim = CrucibleSim(cfg)
    sim.trigger_onslaught()

    metrics = {}
    for _ in range(18):
        metrics = sim.step()

    assert metrics["immune_danger_max"] > 0.0
    assert metrics["immune_signal_max"] > 0.0
    assert metrics["immune_repair_max"] > 0.0
    assert sim.immune_quorum.glyph()
    assert sim.immune_rewards.shape == (len(sim.swimmers),)
    assert sim.immune_sense.shape == (len(sim.swimmers), 3)


def test_crucible_foveated_gaze_writes_saccade_target_into_entropy_loop():
    cfg = CrucibleConfig(
        agents=18,
        seed=2028,
        base_packets_per_tick=0,
        onslaught_packets_per_tick=10,
        anomaly_prob_onslaught=1.0,
        server_capacity=60,
        immune_grid_size=48,
        immune_damage_max_centers=12,
        gaze_grid_size=48,
        gaze_every=1,
        gaze_saliency_threshold=0.01,
    )
    sim = CrucibleSim(cfg)
    sim.trigger_onslaught()

    metrics = {}
    for _ in range(12):
        metrics = sim.step()

    assert metrics["gaze_saccades"] > 0.0
    assert metrics["gaze_saliency_peak"] > 0.0
    assert 0.0 <= metrics["gaze_target_x"] <= 1.0
    assert 0.0 <= metrics["gaze_target_y"] <= 1.0
    assert metrics["gaze_foveal_count"] > 0.0
    assert sim.foveated_gaze.glyph("saliency")
    assert sim.stigmergic_task.field.max() >= cfg.gaze_stigmergic_deposit


def test_crucible_unified_field_couples_all_local_substrates():
    cfg = CrucibleConfig(
        agents=20,
        seed=2029,
        base_packets_per_tick=0,
        onslaught_packets_per_tick=10,
        anomaly_prob_onslaught=1.0,
        server_capacity=60,
        immune_grid_size=48,
        immune_damage_max_centers=12,
        gaze_grid_size=48,
        gaze_every=1,
        gaze_saliency_threshold=0.01,
        unified_field_grid_size=48,
        unified_field_follow_strength=0.012,
    )
    sim = CrucibleSim(cfg)
    sim.trigger_onslaught()

    metrics = {}
    for _ in range(14):
        metrics = sim.step()

    assert metrics["unified_field_max"] > 0.0
    assert metrics["unified_field_min"] < metrics["unified_field_max"]
    assert metrics["unified_gradient_mean"] > 0.0
    assert 0.0 <= metrics["unified_peak_x"] <= 1.0
    assert 0.0 <= metrics["unified_peak_y"] <= 1.0
    assert sim.unified_field.glyph("total")
    assert sim.unified_field.memory.max() > 0.0
    assert sim.unified_field.prediction.max() > 0.0
    assert sim.unified_field.salience.max() > 0.0
    assert sim.unified_field.danger.max() > 0.0


def test_crucible_embodied_gaze_forwards_camera_target_state(monkeypatch, tmp_path):
    target_json = tmp_path / "active_saccade_target.json"
    target_txt = tmp_path / "active_saccade_target.txt"
    monkeypatch.setattr(camera_target, "TARGET_JSON", target_json)
    monkeypatch.setattr(camera_target, "TARGET_TXT_LEGACY", target_txt)

    cfg = CrucibleConfig(
        agents=20,
        seed=2030,
        base_packets_per_tick=0,
        onslaught_packets_per_tick=10,
        anomaly_prob_onslaught=1.0,
        server_capacity=60,
        immune_grid_size=48,
        immune_damage_max_centers=12,
        gaze_grid_size=48,
        gaze_every=1,
        gaze_saliency_threshold=0.01,
        unified_field_grid_size=48,
        embodied_gaze=True,
        embodied_gaze_every=1,
        embodied_gaze_min_salience=0.01,
    )
    sim = CrucibleSim(cfg)
    sim.trigger_onslaught()

    metrics = {}
    for _ in range(12):
        metrics = sim.step()

    assert metrics["embodied_gaze_writes"] > 0.0
    assert target_json.exists()
    assert target_txt.exists()

    record = json.loads(target_json.read_text(encoding="utf-8"))
    assert record["writer"] == "crucible_unified_field"
    assert record["priority"] == cfg.embodied_gaze_priority
    assert record["lease_until"] is not None
    assert record["index"] in {0, 1, 2, 3, 4, 5, 6}
    assert record["name"] == camera_target.name_for_index(record["index"])
    assert int(target_txt.read_text(encoding="utf-8").strip()) == record["index"]
    assert metrics["embodied_camera_index"] == float(record["index"])
    assert 0.0 <= metrics["embodied_gaze_target_x"] <= 1.0
    assert 0.0 <= metrics["embodied_gaze_target_y"] <= 1.0


def test_crucible_resets_entropy_gate_when_swimmer_count_changes():
    cfg = CrucibleConfig(agents=8, seed=7, base_packets_per_tick=1, onslaught_packets_per_tick=2)
    sim = CrucibleSim(cfg)
    for _ in range(3):
        sim.step()

    sim.agent_target_count = 13
    sim.step()
    sim.step()

    assert len(sim.swimmers) == 13
    assert sim.swimmer_rewards.shape == (13,)
    assert sim.immune_rewards.shape == (13,)
    assert sim.stigmergic_task.prev_positions is not None
    assert sim.stigmergic_task.prev_positions.shape[0] == 13
    assert sim.immune_quorum.prev_positions is not None
    assert sim.immune_quorum.prev_positions.shape[0] == 13
