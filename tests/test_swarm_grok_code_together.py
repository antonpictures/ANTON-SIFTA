from __future__ import annotations

from System import swarm_grok_code_together as grok_pulse


def test_grok_code_together_pulse_writes_receipt(tmp_path):
    row = grok_pulse.record_grok_code_together_pulse(
        prompt="Alice ask Grok OAuth for one improvement",
        lane="oauth",
        status="finished",
        ok=True,
        elapsed_s=1.25,
        model="grok-4",
        result={"stdout": "Add a live teacher pulse lane."},
        state_dir=tmp_path,
        now=123.0,
    )

    assert row["truth_label"] == grok_pulse.TRUTH_LABEL
    assert row["action"] == "grok_code_together_pulse"
    assert row["receipt_id"].startswith("grok-pulse-")
    assert row["prompt_sha"]
    assert row["result_preview"] == "Add a live teacher pulse lane."

    rows = grok_pulse.latest_grok_code_together_pulses(state_dir=tmp_path)
    assert rows[-1]["receipt_id"] == row["receipt_id"]
