from pathlib import Path

from System import swarm_body_monitor as body


def test_all_organs_emit_truth_labels():
    state = body.OrganEngine().tick_all()

    for key, *_ in body.ORGAN_DEFS:
        organ = state[key]
        assert organ["truth_status"] in {
            body.TRUTH_REAL,
            body.TRUTH_DEMO,
            body.TRUTH_BROKEN,
            body.TRUTH_UNKNOWN,
        }
        assert organ["truth_source"]
        assert organ["truth_note"]


def test_internal_oscillator_organs_are_marked_demo():
    state = body.OrganEngine().tick_all()
    # Fly is excluded: it reads from active_window.jsonl (REAL when present, DEMO when absent)
    demo_organs = {
        "field",
        "rl",
        "octopus",
        "cuttlefish",
        "electric",
        "honeybee",
    }

    for key in demo_organs:
        assert state[key]["truth_status"] == body.TRUTH_DEMO
        assert state[key]["truth_source"] == body.DEMO_SOURCE


def test_fly_efference_is_real_when_active_window_exists():
    """Fly Efference Copy reads from active_window.jsonl — REAL when present."""
    state = body.OrganEngine().tick_all()
    aw_path = body._STATE / "active_window.jsonl"
    if aw_path.exists():
        assert state["fly"]["truth_status"] == body.TRUTH_REAL
    else:
        assert state["fly"]["truth_status"] == body.TRUTH_DEMO


def test_fly_efference_is_demo_when_no_active_window(tmp_path, monkeypatch):
    """Fly falls back to DEMO when active_window.jsonl is missing."""
    monkeypatch.setattr(body, "_STATE", Path(tmp_path))
    state = body.OrganEngine().tick_all()
    assert state["fly"]["truth_status"] == body.TRUTH_DEMO


def test_starling_topo_is_real_when_network_topology_is_fresh(tmp_path, monkeypatch):
    """Starling Topo reads the live network topology daemon ledger."""
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    (state_dir / "network_topology.jsonl").write_text(
        '{"ts": 9999999999, "node": "en0", "peers": ["en1", "en2"], "signal_strength": -45.0}\n'
        '{"ts": 9999999999, "node": "en1", "peers": ["en0"], "signal_strength": -50.0}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(body, "_STATE", state_dir)

    state = body.OrganEngine().tick_all()

    assert state["starling"]["truth_status"] == body.TRUTH_REAL
    assert state["starling"]["truth_source"] == "live_ledger"
    assert "nodes=2" in state["starling"]["label"]


def test_starling_topo_stays_demo_when_network_topology_is_stale(tmp_path, monkeypatch):
    """Stale topology is not live truth; Starling falls back to the oscillator."""
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    (state_dir / "network_topology.jsonl").write_text(
        '{"ts": 1, "node": "en0", "peers": ["en1"], "signal_strength": -45.0}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(body, "_STATE", state_dir)

    state = body.OrganEngine().tick_all()

    assert state["starling"]["truth_status"] == body.TRUTH_DEMO
    assert state["starling"]["truth_source"] == body.DEMO_SOURCE


def test_live_process_organs_are_marked_real():
    state = body.OrganEngine().tick_all()

    assert state["metabolic"]["truth_status"] == body.TRUTH_REAL
    assert state["metabolic"]["truth_source"] == "live_process"
    assert state["time"]["truth_status"] == body.TRUTH_REAL
    assert state["time"]["truth_source"] == "live_process"


def test_live_ledger_organs_are_real_when_ledgers_exist(tmp_path, monkeypatch):
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    (state_dir / "reflex_arc_trace.jsonl").write_text(
        '{"ts": 9999999999, "category": "test", "latency_ms": 0.1}\n',
        encoding="utf-8",
    )
    (state_dir / "corvid_apprentice_trace.jsonl").write_text(
        '{"ts": 9999999999, "task": "test", "latency_s": 0.2, "success": true}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(body, "_STATE", state_dir)

    state = body.OrganEngine().tick_all()

    assert state["reflex"]["truth_status"] == body.TRUTH_REAL
    assert state["reflex"]["truth_source"] == "live_ledger"
    assert state["corvid"]["truth_status"] == body.TRUTH_REAL
    assert state["corvid"]["truth_source"] == "live_ledger"


def test_live_ledger_organs_are_unknown_when_ledgers_are_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(body, "_STATE", Path(tmp_path))

    state = body.OrganEngine().tick_all()

    assert state["reflex"]["truth_status"] == body.TRUTH_UNKNOWN
    assert state["corvid"]["truth_status"] == body.TRUTH_UNKNOWN


def test_predator_v7_organs_use_real_ledger_paths_when_sources_exist(tmp_path, monkeypatch):
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    (state_dir / "td_q_table.json").write_text('{"s||ENGAGE": 0.15}', encoding="utf-8")
    (state_dir / "dopamine_reward_ledger.jsonl").write_text(
        '{"ts": 9999999999, "delta": 0.7, "marker": "nice"}\n',
        encoding="utf-8",
    )
    (state_dir / "hippocampus").mkdir()
    (state_dir / "hippocampus" / "events.jsonl").write_text(
        '{"ts": 9999999999, "type": "episode", "event_type": "episode"}\n',
        encoding="utf-8",
    )
    (state_dir / "sensor_gate_lock.json").write_text(
        '{"ts": 9999999999, "locked": true, "reason": "lock_success"}',
        encoding="utf-8",
    )
    (state_dir / "swarm_action_selector_trace.jsonl").write_text(
        '{"ts": 9999999999, "winner": "ENGAGE"}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(body, "_STATE", state_dir)

    state = body.OrganEngine().tick_all()

    for key in ["td_learner", "dopamine", "hippocampus", "sensor_gate", "bg_selector"]:
        assert state[key]["truth_status"] == body.TRUTH_REAL
        assert state[key]["truth_source"] == "live_ledger"


def test_sensor_gate_not_attempted_is_unknown_even_if_file_exists(tmp_path, monkeypatch):
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    (state_dir / "sensor_gate_lock.json").write_text(
        '{"ts": 9999999999, "locked": false, "reason": "not_attempted"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(body, "_STATE", state_dir)

    state = body.OrganEngine().tick_all()

    assert state["sensor_gate"]["truth_status"] == body.TRUTH_UNKNOWN
    assert state["sensor_gate"]["truth_source"] == "no_runtime_attempt"


def test_sensor_gate_ensure_lock_state_does_not_create_ledger(tmp_path, monkeypatch):
    import Organs.sensor_gate as sensor_gate

    lock_path = tmp_path / "sensor_gate_lock.json"
    monkeypatch.setattr(sensor_gate, "_LOCK_STATE", lock_path)

    state = sensor_gate.ensure_lock_state()

    assert state["reason"] == "not_attempted"
    assert not lock_path.exists()
