from __future__ import annotations

from System.swarm_cowatch_body_loop import run_cowatch_commentary_body_loop


def test_cowatch_commentary_writes_action_prediction(tmp_path):
    run_cowatch_commentary_body_loop(
        context="youtube: test video",
        reply="Hey George — novel software idea here.",
        receipt_id="test-receipt-1",
        url="https://www.youtube.com/watch?v=test",
        decision={"reason": "novelty_pressure"},
        state_dir=tmp_path,
    )
    ledger = tmp_path / ".sifta_state" / "action_prediction.jsonl"
    assert ledger.exists()
    text = ledger.read_text(encoding="utf-8")
    assert "cowatch_commentary_speak" in text
    assert "prediction" in text
    assert "outcome" in text