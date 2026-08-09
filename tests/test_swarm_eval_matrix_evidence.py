"""Eval matrix evidence rows expose the shadow-swimmer panel."""
from __future__ import annotations

import os
import time

from System.swarm_eval_matrix_evidence import (
    evidence_score_for_row,
    panel_evidence_rows,
    score_panel_evidence_rows,
)


def test_shadow_swimmer_panel_evidence_declares_mana_boundary():
    rows = {row["panel"]: row for row in panel_evidence_rows()}
    shadow = rows["shadow_swimmer_quarantine"]
    assert shadow["path"] == "System/swarm_ide_trace_quarantine.py"
    assert shadow["ledger"] == ".sifta_state/ide_stigmergic_trace.jsonl"
    assert shadow["mana_is_crypto"] is False
    assert shadow["stgm_is_crypto"] is True


def test_eval_cell_without_named_evidence_cannot_be_green(tmp_path):
    row = {"panel": "claim_only", "path": ""}

    scored = evidence_score_for_row(row, repo_root=tmp_path, now=1000.0)

    assert scored["status"] == "red"
    assert "missing_evidence_path" in scored["problems"]
    assert "missing_named_receipt_or_ledger" in scored["problems"]


def test_eval_cell_with_fresh_real_path_and_ledger_is_green(tmp_path):
    code = tmp_path / "System" / "organ.py"
    ledger = tmp_path / ".sifta_state" / "organ_receipts.jsonl"
    code.parent.mkdir(parents=True)
    ledger.parent.mkdir(parents=True)
    code.write_text("# organ\n", encoding="utf-8")
    ledger.write_text('{"truth_label":"OBSERVED"}\n', encoding="utf-8")
    now = time.time()
    os.utime(code, (now, now))
    os.utime(ledger, (now, now))

    scored = evidence_score_for_row(
        {"panel": "organ", "path": "System/organ.py", "ledger": ".sifta_state/organ_receipts.jsonl"},
        repo_root=tmp_path,
        now=now,
    )

    assert scored["status"] == "green"
    assert scored["score"] == 1.0


def test_eval_cell_stale_evidence_decays_below_green(tmp_path):
    code = tmp_path / "System" / "organ.py"
    ledger = tmp_path / ".sifta_state" / "organ_receipts.jsonl"
    code.parent.mkdir(parents=True)
    ledger.parent.mkdir(parents=True)
    code.write_text("# organ\n", encoding="utf-8")
    ledger.write_text('{"truth_label":"OBSERVED"}\n', encoding="utf-8")
    now = time.time()
    stale = now - 4 * 24 * 3600
    os.utime(code, (stale, stale))
    os.utime(ledger, (stale, stale))

    scored = evidence_score_for_row(
        {"panel": "organ", "path": "System/organ.py", "ledger": ".sifta_state/organ_receipts.jsonl"},
        repo_root=tmp_path,
        now=now,
        half_life_s=24 * 3600,
    )

    assert scored["status"] == "yellow"
    assert scored["score"] < 0.75


def test_score_panel_evidence_requires_all_green(tmp_path):
    good_code = tmp_path / "System" / "good.py"
    good_ledger = tmp_path / ".sifta_state" / "good.jsonl"
    good_code.parent.mkdir(parents=True)
    good_ledger.parent.mkdir(parents=True)
    good_code.write_text("# good\n", encoding="utf-8")
    good_ledger.write_text('{"ok":true}\n', encoding="utf-8")

    scored = score_panel_evidence_rows(
        [
            {"panel": "good", "path": "System/good.py", "ledger": ".sifta_state/good.jsonl"},
            {"panel": "bad", "path": "System/missing.py", "ledger": ".sifta_state/missing.jsonl"},
        ],
        repo_root=tmp_path,
    )

    assert scored["ok"] is False
    assert scored["green_count"] == 1


# ── r1744 cut #1 (WCT r1743 §2, the jewel-beetle failure) ────────────────────
# Hoffman's beetle mates with a beer bottle because "dimpled, glossy, brown"
# was the only icon it had. A ledger that exists and has a fresh mtime is the
# same kind of icon; rows inside it are the reality. A green cell must prove
# it holds evidence, not merely that a file with the right name is on disk.


def _cell(tmp_path, ledger_body: str, *, suffix: str = ".jsonl"):
    code = tmp_path / "System" / "organ.py"
    ledger = tmp_path / ".sifta_state" / f"organ_receipts{suffix}"
    code.parent.mkdir(parents=True, exist_ok=True)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    code.write_text("# organ\n", encoding="utf-8")
    ledger.write_text(ledger_body, encoding="utf-8")
    now = time.time()
    os.utime(code, (now, now))
    os.utime(ledger, (now, now))
    return evidence_score_for_row(
        {
            "panel": "organ",
            "path": "System/organ.py",
            "ledger": f".sifta_state/organ_receipts{suffix}",
        },
        repo_root=tmp_path,
        now=now,
    )


def test_empty_but_freshly_touched_ledger_cannot_be_green(tmp_path):
    """The exact live shape of .sifta_state/reply_language_mismatch.jsonl."""
    scored = _cell(tmp_path, "")

    assert scored["evidence_rows"] == 0
    assert "empty_ledger" in scored["problems"]
    assert scored["status"] != "green", "zero rows is a bottle, not evidence"


def test_evidence_rows_are_counted_and_exposed(tmp_path):
    scored = _cell(tmp_path, '{"a":1}\n{"a":2}\n{"a":3}\n')

    assert scored["evidence_rows"] == 3
    assert scored["status"] == "green"


def test_final_line_without_newline_still_counts(tmp_path):
    scored = _cell(tmp_path, '{"a":1}\n{"a":2}')

    assert scored["evidence_rows"] == 2


def test_snapshot_artifact_counts_as_one_piece_of_evidence(tmp_path):
    """.json/.html panels are not append ledgers; non-empty is one evidence."""
    scored = _cell(tmp_path, "<html>matrix</html>", suffix=".html")

    assert scored["evidence_rows"] == 1
    assert scored["status"] == "green"


def test_live_matrix_reports_a_row_count_for_every_cell():
    """No panel may hide how much evidence stands behind it."""
    from System.swarm_eval_matrix_evidence import validate_panel_evidence

    verdict = validate_panel_evidence()
    for scored in verdict["scores"]:
        assert "evidence_rows" in scored, scored["panel"]
        if scored["status"] == "green":
            assert scored["evidence_rows"], f"{scored['panel']} is green with no rows"
