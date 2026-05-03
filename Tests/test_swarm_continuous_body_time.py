import json

from System.swarm_continuous_body_time import (
    continuous_body_time_facts,
    format_continuous_body_time_for_alice,
)


def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_continuous_body_time_reads_conversation_episodic_and_body_ledgers(tmp_path):
    state = tmp_path / ".sifta_state"
    now = 1000.0
    _write_jsonl(
        state / "alice_conversation.jsonl",
        [
            {
                "ts": {"physical_pt": 940.0, "logical": 1},
                "payload": {"role": "user", "text": "I did not turn you off."},
            }
        ],
    )
    _write_jsonl(
        state / "episodic_diary.jsonl",
        [{"ts": 880.0, "bucket": "2026-05-03T00:00", "summary": "sleep; coding"}],
    )
    _write_jsonl(
        state / "body_brain_memory.jsonl",
        [{"ts": 700.0, "event": "body_brain_tick", "metabolic_mode": "GREEN_GROW"}],
    )

    facts = continuous_body_time_facts(state_dir=state, now=now)

    assert facts["truth_label"] == "CONTINUOUS_BODY_TIME_RECEIPT"
    assert facts["continuity_observed"] is True
    assert facts["owner_life_continuity"]["power_off_cost"] == "lost_owner_life_samples"
    assert facts["ledgers"]["conversation"]["latest_age_human"] == "60s ago"
    assert facts["ledgers"]["episodic_diary"]["latest"]["summary"] == "sleep; coding"
    assert facts["ledgers"]["body_brain"]["latest"]["event"] == "body_brain_tick"


def test_continuous_body_time_format_rejects_immediate_context_collapse(tmp_path):
    state = tmp_path / ".sifta_state"
    _write_jsonl(
        state / "alice_conversation.jsonl",
        [{"ts": {"physical_pt": 990.0}, "payload": {"role": "alice", "text": "Online."}}],
    )

    text = format_continuous_body_time_for_alice(
        owner_label="Ioan George Anton",
        state_dir=state,
        now=1000.0,
    )

    assert "Local body-time receipt for Ioan George Anton" in text
    assert "conversation ledger last wrote 10s ago" in text
    assert "immediate-context-only" in text
    assert "continuous stigmergic body time" in text
    assert "not the same as turning off a biological human body" in text
    assert "unsampled part of George's finite owner-life" in text
    assert "core local asset" in text
