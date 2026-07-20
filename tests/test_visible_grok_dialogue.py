from __future__ import annotations

import json

from System import swarm_alice_talk_mirror_line as mirror_line


def test_stage_talk_mirror_line_command(tmp_path):
    row = mirror_line.stage_talk_mirror_line_command(
        "Hello World. I'm Alice",
        turn=1,
        from_browser_receipt="browser-rid-1",
        state_dir=tmp_path,
    )
    sd = tmp_path / ".sifta_state"
    cmd = json.loads((sd / "alice_talk_mirror_line_command.json").read_text(encoding="utf-8"))
    assert cmd["text"] == "Hello World. I'm Alice"
    assert cmd["turn"] == 1
    assert cmd["receipt_id"] == row["receipt_id"]