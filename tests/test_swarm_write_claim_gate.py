from __future__ import annotations

import json
import time
from pathlib import Path

from System.swarm_write_claim_gate import verify_write_claims


def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_naked_schedule_claim_is_rewritten_and_tracker_receipted(tmp_path: Path):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    since = time.time()

    out = verify_write_claims(
        "Consider it added to your schedule!",
        since,
        state_dir=state,
        owner_text="please add mom surgery to my schedule",
    )

    assert out["changed"] is True
    assert "NOT written" in out["reply_text"]
    assert not (state / "stigmergic_schedule.jsonl").exists()
    tracker = _rows(state / "deterministic_mistakes.jsonl")
    assert tracker
    assert tracker[-1]["bypass_type"] == "phantom_action"
    receipts = _rows(state / "write_claim_gate.jsonl")
    assert receipts[-1]["status"] == "claim_rewritten_no_receipt"


def test_true_schedule_claim_with_fresh_row_passes(tmp_path: Path):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    since = time.time()
    (state / "stigmergic_schedule.jsonl").write_text(
        json.dumps({"ts": since + 0.01, "text": "call Adrian", "schedule_id": "s1"}) + "\n",
        encoding="utf-8",
    )

    reply = "Consider it added to your schedule!"
    out = verify_write_claims(reply, since, state_dir=state)

    assert out["changed"] is False
    assert out["reply_text"] == reply
    assert out["status"] == "claim_receipted"


def test_parseable_schedule_claim_backfills_row(tmp_path: Path):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    since = time.time()
    reply = "Added to my schedule: call Adrian about surgery."

    out = verify_write_claims(reply, since, state_dir=state)

    assert out["changed"] is False
    assert out["backfilled"] is True
    rows = _rows(state / "stigmergic_schedule.jsonl")
    assert rows[-1]["text"] == "call Adrian about surgery"
    assert rows[-1]["claim_backfilled_by_gate"] is True


def test_journal_claim_backfills_journal(tmp_path: Path):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    since = time.time()

    out = verify_write_claims("I noted this in my journal: George travels with Alice.", since, state_dir=state)

    assert out["backfilled"] is True
    journal = _rows(state / "alice_first_person_journal.jsonl")
    assert journal[-1]["claim_backfilled_by_gate"] is True
    assert "George travels" in journal[-1]["line"]


def test_talk_widget_wires_write_claim_gate():
    source = Path("Applications/sifta_talk_to_alice_widget.py").read_text(encoding="utf-8")
    assert "from System.swarm_write_claim_gate import verify_write_claims" in source
    assert "_current_owner_turn_started_ts" in source
    assert "WRITE CLAIM GATE" in source
