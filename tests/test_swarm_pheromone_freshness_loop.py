import json
from pathlib import Path
from unittest.mock import patch

from System import swarm_pheromone_freshness_loop as loop


def _append_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_sample_ledger_freshness_returns_top_active_ledgers(tmp_path):
    state = tmp_path / ".sifta_state"
    _append_jsonl(
        state / "work_receipts.jsonl",
        [{"ts": 1.0, "action": f"work-{i}"} for i in range(6)],
    )
    _append_jsonl(
        state / "episodic_diary.jsonl",
        [{"ts": 1.0, "kind": "small"}],
    )

    row = loop.sample_ledger_freshness(
        state,
        ledger_names=("work_receipts.jsonl", "episodic_diary.jsonl"),
        now=1000.0,
        top_n=2,
    )

    assert row["truth_label"] == loop.TRUTH_LABEL
    assert row["sampled_ledgers"][0]["ledger"] == "work_receipts.jsonl"
    assert row["hottest_ledgers"]
    assert "active=" in row["gradient_note"]


def test_write_freshness_tick_appends_row_and_updates_cache(tmp_path):
    state = tmp_path / ".sifta_state"
    _append_jsonl(
        state / "alice_conversation.jsonl",
        [{"ts": 1.0, "payload": {"text": "hello"}}],
    )

    with patch("System.swarm_pheromone_field.update_pheromone_field") as deposit:
        first = loop.write_freshness_tick(state, now=2000.0)
        second = loop.write_freshness_tick(state, now=2001.0)

    ledger = state / "pheromone_field.jsonl"
    lines = ledger.read_text(encoding="utf-8").splitlines()
    assert first["truth_label"] == loop.TRUTH_LABEL
    assert second["truth_label"] == loop.TRUTH_LABEL
    assert len(lines) == 2
    assert (state / "pheromone_freshness_state.json").exists()
    assert deposit.called


def test_summary_for_prompt_uses_latest_append_only_row(tmp_path):
    state = tmp_path / ".sifta_state"
    _append_jsonl(
        state / "pheromone_field.jsonl",
        [
            {
                "ts": 1.0,
                "truth_label": loop.TRUTH_LABEL,
                "gradient_note": "active=old; stalled=none",
                "sampled_ledgers": [
                    {"ledger": "old.jsonl", "activity_score": 0.1, "age_s": 4.0}
                ],
            },
            {
                "ts": 2.0,
                "truth_label": loop.TRUTH_LABEL,
                "gradient_note": "active=work_receipts.jsonl; stalled=organ_field_vector.jsonl",
                "sampled_ledgers": [
                    {
                        "ledger": "work_receipts.jsonl",
                        "activity_score": 0.9,
                        "age_s": 0.5,
                    }
                ],
            },
        ],
    )

    text = loop.summary_for_prompt(state)

    assert "PHEROMONE FRESHNESS FIELD" in text
    assert "work_receipts.jsonl" in text
    assert "old.jsonl" not in text
