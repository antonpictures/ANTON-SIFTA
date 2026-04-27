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
    demo_organs = {
        "field",
        "rl",
        "octopus",
        "cuttlefish",
        "electric",
        "honeybee",
        "starling",
        "fly",
    }

    for key in demo_organs:
        assert state[key]["truth_status"] == body.TRUTH_DEMO
        assert state[key]["truth_source"] == body.DEMO_SOURCE


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

