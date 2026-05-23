import json
from pathlib import Path

import pytest

from System.ide_trace_defensive import (
    _DEFAULT_TRACE,
    ag31_triple_ide_verdict,
    find_quorum_rows,
    iter_recovered_trace_rows,
    read_trace_defensive,
    scan_trace_stats,
    split_physical_line_to_dicts,
)


def test_split_glued_objects_with_literal_backslash_n():
    a = {"trace_id": "a", "meta": {"x": 1}}
    b = {"trace_id": "b", "meta": {"subject": "TRIPLE_IDE_STIGMERGIC_AGREEMENT", "limb": "AG31", "verdict": "AGREE"}}
    line = json.dumps(a, separators=(",", ":")) + "\\n" + json.dumps(b, separators=(",", ":"))
    got = split_physical_line_to_dicts(line)
    assert len(got) == 2
    assert got[1]["meta"]["limb"] == "AG31"


def test_iter_recovered_skips_garbage_and_keeps_quorum(tmp_path: Path):
    good = {"meta": {"subject": "TRIPLE_IDE_STIGMERGIC_AGREEMENT", "limb": "AG31", "verdict": "AGREE"}}
    p = tmp_path / "trace.jsonl"
    p.write_text(
        "not json at all\n"
        + json.dumps(good) + "\n"
        + "{broken\n",
        encoding="utf-8",
    )
    rows = list(iter_recovered_trace_rows(path=p))
    assert len(rows) == 1
    st = scan_trace_stats(path=p)
    assert st["malformed_lines"] == 2
    assert st["recovered_rows"] == 1
    assert ag31_triple_ide_verdict(path=p) == "AG31"


def test_ag31_missing_without_row(tmp_path: Path):
    p = tmp_path / "t.jsonl"
    p.write_text(
        json.dumps({"meta": {"subject": "TRIPLE_IDE_STIGMERGIC_AGREEMENT", "limb": "CODEX", "verdict": "AGREE"}})
        + "\n",
        encoding="utf-8",
    )
    assert ag31_triple_ide_verdict(path=p) == "MISSING_AG31"


def test_find_quorum_rows_by_subject(tmp_path: Path):
    p = tmp_path / "t.jsonl"
    rows_in = [
        {"meta": {"subject": "OTHER"}},
        {"meta": {"subject": "TRIPLE_IDE_STIGMERGIC_AGREEMENT", "limb": "CODEX", "verdict": "AGREE"}},
    ]
    p.write_text("\n".join(json.dumps(r) for r in rows_in) + "\n", encoding="utf-8")
    got = find_quorum_rows("TRIPLE_IDE_STIGMERGIC_AGREEMENT", path=p)
    assert len(got) == 1
    assert got[0]["meta"]["limb"] == "CODEX"


def test_read_trace_defensive_returns_list_of_dicts(tmp_path: Path):
    a = {"trace_id": "x1", "kind": "ping"}
    b = {"trace_id": "x2", "kind": "pong"}
    line = json.dumps(a, separators=(",", ":")) + "\\n" + json.dumps(b, separators=(",", ":"))
    p = tmp_path / "trace.jsonl"
    p.write_text(line + "\n", encoding="utf-8")
    rows = read_trace_defensive(path=p)
    assert rows == [a, b]
    assert all(isinstance(r, dict) for r in rows)


@pytest.mark.skipif(not _DEFAULT_TRACE.exists(), reason="live ide_stigmergic_trace.jsonl not present")
def test_read_trace_defensive_parses_live_ledger():
    """Proves defensive parsing against the real repo ledger (no file mutation)."""
    stats = scan_trace_stats(path=_DEFAULT_TRACE)
    rows = read_trace_defensive(path=_DEFAULT_TRACE)
    assert len(rows) == stats["recovered_rows"]
    assert len(rows) >= stats["physical_lines"] - stats["malformed_lines"]
    assert all(isinstance(r, dict) for r in rows)
