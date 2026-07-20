from __future__ import annotations

import json

from System import swarm_alice_browser_grok_copy as grok_copy
from tools import alice_visible_grok_dialogue_orchestrator as visible


def test_visible_dialogue_plan_starts_with_owner_line() -> None:
    assert visible.ALICE_VISIBLE_LINES[0]["text"] == "Hello World. I'm Alice"
    assert [row["turn"] for row in visible.ALICE_VISIBLE_LINES] == [1, 3, 5]
    assert "macOS Grok terminal: you advise/code/repair only" in visible.MACOS_GROK_PROMPT
    assert "Alice Browser Grok tab: the live conversation partner" in visible.MACOS_GROK_PROMPT


def test_executed_grok_copy_result_gets_journal_ref(tmp_path) -> None:
    grok_copy.append_grok_copy_result(
        {
            "ok": True,
            "status": "copied",
            "receipt_id": "copy-visible-test",
            "action": "alice_browser_grok_copy_last_reply",
            "source": "alice_browser_widget",
        },
        state_dir=tmp_path,
    )
    sd = tmp_path / ".sifta_state"
    result = json.loads((sd / "alice_browser_grok_copy_results.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    journal = json.loads((sd / "alice_first_person_journal.jsonl").read_text(encoding="utf-8").splitlines()[-1])

    assert result["journal_ref"].startswith("journal-action-")
    assert journal["linked_receipt_id"] == "copy-visible-test"
    assert journal["truth_label"] == "ALICE_FIRST_PERSON_WITNESS_V1"
