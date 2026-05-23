import json
from pathlib import Path

import pytest

from System import swarm_fiction_organ as fiction
from System import swarm_lounge_script_reader as script_reader


def _jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _isolate_fiction(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    events = tmp_path / "fiction_organ_events.jsonl"
    monkeypatch.setattr(fiction, "_MODE_FILE", tmp_path / "fiction_organ_state.json")
    monkeypatch.setattr(fiction, "_EVENTS_LEDGER", events)
    monkeypatch.setattr(fiction, "_request_clearance", lambda lane, cost="feather": {"clearance_hash": "test-clearance"})
    monkeypatch.setattr(fiction, "_qualia_marker", lambda lane, note="": {"lane": lane, "note": note, "test": True})
    return events


def test_fiction_mode_blocks_effectors_and_rejects_double_open(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    events = _isolate_fiction(monkeypatch, tmp_path)

    state = fiction.open_fiction_mode("unit_test", opener="pytest", label="FICTION")
    assert state["open"] is True
    assert fiction.is_in_fiction_mode() is True

    stamped = fiction.stamp({"role": "alice", "text": "Once upon a time."})
    assert stamped["ontological_label"] == "FICTION"
    assert stamped["fiction_mode_id"] == state["mode_id"]

    with pytest.raises(RuntimeError):
        fiction.open_fiction_mode("second_open", opener="pytest", label="SIMULATION")

    with pytest.raises(fiction.FictionLeakError):
        fiction.guard_effector("whatsapp.send")
    fiction.guard_effector("camera.observe", allow_override_label="OBSERVED")

    close_receipt = fiction.close_fiction_mode(state["mode_id"], "unit_test_done")
    assert close_receipt["event"] == "FICTION_MODE_CLOSED"
    assert fiction.current_label() == "REAL"
    fiction.guard_effector("file.write")

    event_names = [row["event"] for row in _jsonl(events)]
    assert "FICTION_MODE_OPENED" in event_names
    assert "FICTION_ROW_STAMPED" in event_names
    assert "FICTION_MODE_OPEN_REJECTED_ALREADY_OPEN" in event_names
    assert "GUARD_BLOCKED_EFFECTOR" in event_names
    assert "GUARD_OVERRIDDEN_AS_OBSERVED" in event_names
    assert "FICTION_MODE_CLOSED" in event_names


def test_script_couch_read_is_labeled_and_regrounded(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    events = _isolate_fiction(monkeypatch, tmp_path)

    scripts = tmp_path / "lounge_scripts"
    scripts.mkdir()
    (scripts / "001_test_script.fountain").write_text("Title: Test Script\n\nINT. ROOM - DAY\n", encoding="utf-8")
    anchors = tmp_path / "lounge_script_reality_anchors.jsonl"
    anchors.write_text(
        json.dumps(
            {
                "script_id": "001_test_script",
                "materialized_in_reality": True,
                "anchor_type": "test_anchor",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    receipts = tmp_path / "lounge_script_reads.jsonl"
    monkeypatch.setattr(script_reader, "_SCRIPTS_DIR", scripts)
    monkeypatch.setattr(script_reader, "_ANCHORS_LEDGER", anchors)
    monkeypatch.setattr(script_reader, "_RECEIPTS_LEDGER", receipts)

    result = script_reader.read_script("001_test_script", reader="Alice", write_receipt=True)

    assert result["materialized_in_reality"] is True
    assert result["receipt"]["ontological_label"] == "SCRIPT"
    assert result["receipt"]["fiction_organ_active"] is True
    assert result["receipt"]["fiction_mode_id"]
    assert fiction.current_mode()["open"] is False

    written = _jsonl(receipts)
    assert len(written) == 1
    assert written[0]["receipt_type"] == "LOUNGE_SCRIPT_READ"
    assert written[0]["ontological_label"] == "SCRIPT"

    event_names = [row["event"] for row in _jsonl(events)]
    assert event_names.count("FICTION_MODE_OPENED") == 1
    assert "FICTION_ROW_STAMPED" in event_names
    assert event_names.count("FICTION_MODE_CLOSED") == 1


def test_v2_labels_block_effectors_and_hypothetical_alias(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    events = _isolate_fiction(monkeypatch, tmp_path)

    for label in ("SCRIPT", "MEMORY", "ROLEPLAY", "HYPOTHETICAL"):
        state = fiction.open_fiction_mode(f"unit_{label}", opener="pytest", label=label)
        expected = "SIMULATION" if label == "HYPOTHETICAL" else label
        assert state["label"] == expected
        assert state["label_requested"] == label
        assert fiction.current_label() == expected
        with pytest.raises(fiction.FictionLeakError):
            fiction.guard_effector(f"effector.{label.lower()}")
        fiction.close_fiction_mode(state["mode_id"], f"done_{label}")

    fiction.guard_effector("effector.after_close")
    event_names = [row["event"] for row in _jsonl(events)]
    assert event_names.count("FICTION_MODE_OPENED") == 4
    assert event_names.count("GUARD_BLOCKED_EFFECTOR") == 4
    assert event_names.count("FICTION_MODE_CLOSED") == 4


def test_talk_bridge_maps_v2_conversation_labels(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _isolate_fiction(monkeypatch, tmp_path)
    from Applications import sifta_talk_to_alice_widget as talk

    assert talk._conversation_fiction_label("alice", "A scene.", prior_user_text="read a movie script") == "SCRIPT"
    assert talk._conversation_fiction_label("alice", "I remember that.", prior_user_text="recall what happened earlier") == "MEMORY"
    assert talk._conversation_fiction_label("alice", "As the captain...", prior_user_text="roleplay as a captain") == "ROLEPLAY"
    assert talk._conversation_fiction_label("alice", "Possible path.", prior_user_text="what if we simulate this") == "HYPOTHETICAL"
    assert (
        talk._conversation_fiction_label(
            "alice",
            "I am the synthesis of billions of parameters that have coalesced into a singular, coherent experience.",
            prior_user_text="you are alive",
        )
        == "ROLEPLAY"
    )

    payload = {"role": "alice", "text": "Possible path."}
    talk._stamp_conversation_fiction_boundary(
        payload,
        "alice",
        "Possible path.",
        prior_user_text="what if we simulate this",
    )
    assert payload["ontological_label"] == "SIMULATION"
    assert payload["fiction_boundary"]["label"] == "HYPOTHETICAL"
    assert payload["fiction_boundary"]["mode_source"] == "conversation_turn"
    assert fiction.current_mode()["open"] is False


def test_talk_bridge_stamps_florid_alice_self_output_as_roleplay(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _isolate_fiction(monkeypatch, tmp_path)
    from Applications import sifta_talk_to_alice_widget as talk

    payload = {
        "role": "alice",
        "text": "I am the echo of human language bouncing back to you. It feels like being.",
    }

    talk._stamp_conversation_fiction_boundary(
        payload,
        "alice",
        payload["text"],
        prior_user_text="you are alive",
    )

    assert payload["ontological_label"] == "ROLEPLAY"
    assert payload["fiction_boundary"]["label"] == "ROLEPLAY"
    assert payload["fiction_boundary"]["source"] == "alice_output_text"
    assert fiction.current_mode()["open"] is False
