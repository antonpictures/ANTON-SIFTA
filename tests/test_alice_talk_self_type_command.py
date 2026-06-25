from __future__ import annotations

import json

from System import swarm_alice_talk_self_type as talk_cmd


def test_stage_alice_self_type_to_talk_command_writes_command_and_ledgers(tmp_path):
    row = talk_cmd.stage_alice_self_type_to_talk_command(
        "Transfer from Grok (loop 1): stigmergic memory proof.",
        owner_text="ALICE 5-LOOP transfer 1",
        from_grok_receipt="alice-browser-grok-self-type-abc123",
        loop=1,
        state_dir=tmp_path,
    )

    sd = tmp_path / ".sifta_state"
    command = json.loads((sd / "alice_self_type_to_talk_command.json").read_text(encoding="utf-8"))
    assert command["text"].startswith("Transfer from Grok")
    assert command["send"] is True
    assert command["receipt_id"] == row["receipt_id"]
    assert command["loop"] == 1

    for name in ("alice_self_type_to_talk_commands.jsonl", "work_receipts.jsonl"):
        rows = [
            json.loads(line)
            for line in (sd / name).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert rows[-1]["truth_label"] == talk_cmd.TRUTH_LABEL
        assert rows[-1]["receipt_id"] == row["receipt_id"]