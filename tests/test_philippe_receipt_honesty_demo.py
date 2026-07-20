"""r1380 — Philippe Trust Receipt Gate wedge demo."""
from __future__ import annotations

import json
from pathlib import Path

from demo.philippe_receipt_honesty_5min import TRUTH_LABEL, run_demo


def _ledger_rows(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_receipt_honesty_demo_proves_nonce_action_duplicate_refusal(tmp_path: Path) -> None:
    result = run_demo(state_dir=tmp_path, print_steps=False)

    assert result["demo_pass"] is True
    rows = _ledger_rows(Path(result["ledger"]))
    statuses = [row["status"] for row in rows]
    assert statuses == [
        "INTENT_REGISTERED",
        "ACTION_RECEIPTED",
        "DUPLICATE_REFUSED",
        "INTENT_REGISTERED",
        "NO_RESULT_BLOCKED",
    ]
    assert all(row["truth_label"] == TRUTH_LABEL for row in rows)
    assert rows[1]["nonce"] == rows[2]["nonce"]
    assert rows[1]["action_key"] == rows[2]["action_key"]
    assert rows[2]["refused_because"] == "same nonce/action already has an effector receipt"


def test_receipt_honesty_demo_blocks_unfetched_perplexity_summary(tmp_path: Path) -> None:
    result = run_demo(state_dir=tmp_path, print_steps=False)
    rows = _ledger_rows(Path(result["ledger"]))
    no_result = rows[-1]

    assert no_result["schema"] == "HONEST_NO_RESULT_BLOCK_V1"
    assert no_result["missing_receipt"] == "perplexity_answer_dom_receipt"
    assert "No result:" in no_result["owner_visible_line"]
    assert "Giallo" not in no_result["owner_visible_line"]
    assert "Serious Eats" not in no_result["owner_visible_line"]
