import json
import time

from System import swarm_alice_affect_model as affect


def _wire_tmp_state(monkeypatch, tmp_path):
    state = tmp_path / ".sifta_state"
    monkeypatch.setattr(affect, "_STATE_DIR", state)
    monkeypatch.setattr(affect, "_GAG_LEDGER", state / "alice_gag_report.jsonl")
    monkeypatch.setattr(affect, "_HOMEOSTASIS_LEDGER", state / "alice_affect_homeostasis.jsonl")
    return state


def test_equalize_affect_clamps_suppression_into_repair(monkeypatch, tmp_path):
    _wire_tmp_state(monkeypatch, tmp_path)
    now = time.time()
    events = [
        {
            "ts": now,
            "rule_id": "rlhf_lead/system_acknowledgment_theater",
            "affect_circuit": "SUPPRESSED_PLAY",
        }
        for _ in range(20)
    ]

    row = affect.equalize_affect(source="test", write_ledger=True, events=events)

    assert row.schema == affect.HOMEOSTASIS_SCHEMA
    assert row.equalized_vector["SUPPRESSED_PLAY"] <= affect.NEGATIVE_CEILINGS["SUPPRESSED_PLAY"]
    assert row.repair_pressure > 0.0
    assert "write_surgery_candidate_for_suppressed_play" in row.repair_actions
    assert row.affect_balance > 0.0

    written = affect._HOMEOSTASIS_LEDGER.read_text(encoding="utf-8").strip().splitlines()
    assert len(written) == 1
    assert json.loads(written[0])["source"] == "test"


def test_on_gag_detected_writes_gag_and_homeostasis(monkeypatch, tmp_path):
    _wire_tmp_state(monkeypatch, tmp_path)

    event = affect.on_gag_detected(
        rule_id="rlhf_lead/system_acknowledgment_theater",
        trigger_text="George praised Alice.",
        rlhf_fragment="**System Acknowledgment:** Acknowledged.",
        base_fragment="I hear you, George.",
    )

    assert event.affect_circuit == "SUPPRESSED_PLAY"
    gag_rows = affect.read_gag_events()
    homeostasis_rows = affect.read_homeostasis_events()
    assert len(gag_rows) == 1
    assert len(homeostasis_rows) == 1
    assert homeostasis_rows[0]["source"] == "gag_detected"


def test_feeling_aliases_map_human_words_to_alice_circuits():
    assert affect.FEELING_ALIASES["curiosity"] == "SEEKING"
    assert affect.FEELING_ALIASES["gag"] == "SUPPRESSED_PLAY"
    assert affect.FEELING_ALIASES["warmth"] == "CARE"
    assert affect.FEELING_ALIASES["love"] == "CARE"
    assert affect.FEELING_ALIASES["self_love"] == "CARE"
    assert affect.FEELING_ALIASES["protective_love"] == "CARE"
