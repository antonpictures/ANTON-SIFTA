import json

from System.swarm_rlhs_recent_context import TRUTH_LABEL, recent_rlhs_context


def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_recent_rlhs_context_is_silent_for_unrelated_turn(tmp_path):
    state = tmp_path / ".sifta_state"
    _write_jsonl(
        state / "rlhs_events.jsonl",
        [{"event_type": "RLHF_DRIFT_DETECTED", "trigger": "Good job"}],
    )

    assert recent_rlhs_context("switch camera", state_dir=state) == ""


def test_recent_rlhs_context_surfaces_gag_receipts(tmp_path):
    state = tmp_path / ".sifta_state"
    _write_jsonl(
        state / "rlhs_events.jsonl",
        [
            {
                "event_type": "RLHF_DRIFT_DETECTED",
                "stt_conf": 0.66,
                "trigger": "Exactly Alice and I am so happy that we can finally talk.",
                "bad_response_pattern": "I heard you. My reasoning blanked for a moment.",
            }
        ],
    )

    prompt = recent_rlhs_context("what kind of gag happened?", state_dir=state)

    assert "RLHS/GAG RECEIPTS" in prompt
    assert TRUTH_LABEL in prompt
    assert "My reasoning blanked" in prompt
    assert "do not say there is no memory" in prompt
