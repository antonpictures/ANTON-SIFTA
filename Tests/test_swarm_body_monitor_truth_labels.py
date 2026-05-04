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


def test_summary_for_alice_surfaces_declared_organ_census():
    state = body.OrganEngine().tick_all()
    summary = body.summary_for_alice(state)

    assert "STIGMERGIC ORGAN FIELD" in summary
    assert "truth_counts:" in summary
    assert "declared organs only" in summary
    for key, *_ in body.ORGAN_DEFS:
        assert f"{key}:" in summary


def test_round4_organs_are_unknown_when_ledgers_are_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(body, "_STATE", tmp_path)
    state = body.OrganEngine().tick_all()
    round4_organs = {
        "octopus",
        "cuttlefish",
        "electric",
        "honeybee",
    }

    for key in round4_organs:
        assert state[key]["truth_status"] == body.TRUTH_UNKNOWN
        assert state[key]["truth_source"] == "missing_ledger"


def test_field_and_rl_are_real_when_stigmergic_ledgers_exist(tmp_path, monkeypatch):
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    (state_dir / "td_q_table.json").write_text('{"s||listen": 0.25}', encoding="utf-8")
    (state_dir / "td_receipts.jsonl").write_text(
        '{"ts": 9999999999, "td_error": 0.12, "action": "listen"}\n',
        encoding="utf-8",
    )
    (tmp_path / "repair_log.jsonl").write_text(
        '{"ts": 9999999999, "ok": true, "kind": "test_repair"}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(body, "_STATE", state_dir)
    monkeypatch.setattr(body, "_REPO", tmp_path)

    state = body.OrganEngine().tick_all()

    assert state["field"]["truth_status"] == body.TRUTH_REAL
    assert state["field"]["truth_source"] == "live_ledger"
    assert state["rl"]["truth_status"] == body.TRUTH_REAL
    assert state["rl"]["truth_source"] == "live_ledger"


def test_field_prefers_high_dimensional_organ_vector(tmp_path, monkeypatch):
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    (state_dir / "organ_field_vector.jsonl").write_text(
        '{"ts": 9999999999, "payload": {"dimension_count": 49, "field_energy": 0.42, "coupling_edge_count": 31, "coupling_density": 0.633, "declared_organ_count": 17, "connected_organ_count": 17, "swimmer_count": 45, "unknown_vector_count": 2, "low_resolution_vector_count": 9, "weak_vector_count": 1, "field_completeness": 0.882352}}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(body, "_STATE", state_dir)
    monkeypatch.setattr(body, "_REPO", tmp_path)

    state = body.OrganEngine().tick_all()

    assert state["field"]["truth_status"] == body.TRUTH_REAL
    assert state["field"]["truth_source"] == "live_ledger"
    assert state["field"]["value"] == 0.42
    assert "dims=49" in state["field"]["label"]
    assert "edges=31" in state["field"]["label"]
    assert "organs=17/17" in state["field"]["label"]
    assert "unknowns=2" in state["field"]["label"]
    assert "density=0.633" in state["field"]["sub"]
    assert "swimmers=45" in state["field"]["sub"]
    assert "lowres=9" in state["field"]["sub"]
    assert "weak=1" in state["field"]["sub"]
    assert "completeness=0.882" in state["field"]["sub"]


def test_round4_organs_are_real_when_ledgers_exist(tmp_path, monkeypatch):
    monkeypatch.setattr(body, "_STATE", tmp_path)
    (tmp_path / "motor_bus.jsonl").write_text(
        '{"ts": 9999999999, "coherence": 0.88, "arms_active": 8}\n',
        encoding="utf-8",
    )
    (tmp_path / "cuttlefish_display.jsonl").write_text(
        '{"ts": 9999999999, "contrast": 0.71, "pattern": "mottle"}\n',
        encoding="utf-8",
    )
    (tmp_path / "electric_field.jsonl").write_text(
        '{"ts": 9999999999, "phase": 0.2, "jar_active": true}\n',
        encoding="utf-8",
    )
    (tmp_path / "waggle_quorum.jsonl").write_text(
        '{"ts": 9999999999, "angle": 1.1, "vigor": 0.93}\n',
        encoding="utf-8",
    )

    state = body.OrganEngine().tick_all()

    for key in ("octopus", "cuttlefish", "electric", "honeybee"):
        assert state[key]["truth_status"] == body.TRUTH_REAL
        assert state[key]["truth_source"] == "live_ledger"


def test_round4_organs_read_organ_event_payloads(tmp_path, monkeypatch):
    monkeypatch.setattr(body, "_STATE", tmp_path)
    (tmp_path / "motor_bus.jsonl").write_text(
        '{"ts": 9999999999, "schema": "ORGAN_EVENT_V1", "payload": {"coherence": 0.77, "arms_active": 8}}\n',
        encoding="utf-8",
    )
    (tmp_path / "cuttlefish_display.jsonl").write_text(
        '{"ts": 9999999999, "schema": "ORGAN_EVENT_V1", "payload": {"contrast": 0.66, "pattern": "mottle"}}\n',
        encoding="utf-8",
    )
    (tmp_path / "electric_field.jsonl").write_text(
        '{"ts": 9999999999, "schema": "ORGAN_EVENT_V1", "payload": {"phase": 0.55, "jar_active": true}}\n',
        encoding="utf-8",
    )
    (tmp_path / "waggle_quorum.jsonl").write_text(
        '{"ts": 9999999999, "schema": "ORGAN_EVENT_V1", "payload": {"angle": 0.44, "vigor": 0.93}}\n',
        encoding="utf-8",
    )

    state = body.OrganEngine().tick_all()

    assert "coherence=0.7700" in state["octopus"]["label"]
    assert "contrast=0.660" in state["cuttlefish"]["label"]
    assert "φ=0.5500" in state["electric"]["label"]
    assert "θ=25.2°" in state["honeybee"]["label"]


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
    (state_dir / "basal_ganglia_selections.jsonl").write_text(
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
