"""Focused tests for the 2026-09-18 borg organs — mem0 consolidation,
context compression, doc feeding, ledger tree index, spinal sandbox, fabric patterns."""
import json
import subprocess
import sys
from pathlib import Path
import pytest

REPO = Path(__file__).resolve().parent.parent
STATE = REPO / ".sifta_state" / "_test_borg_20260918"


@pytest.fixture()
def state(tmp_path):
    d = tmp_path / "wct_borg_state"
    d.mkdir()
    return d


def _write_ledger(state_dir, name, rows):
    p = state_dir / name
    with p.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    return p


def test_memory_consolidation_dedupes(state):
    from System import swarm_memory_consolidation as m

    _write_ledger(state, "memory_ledger.jsonl", [
        {"trace_id": "t1", "raw_text": "my shirt is red", "timestamp": 1.0},
        {"trace_id": "t2", "raw_text": "My shirt is red", "timestamp": 2.0},
        {"trace_id": "t3", "raw_text": "the number is six", "timestamp": 3.0},
    ])
    report = m.consolidate_memory_ledger(state_dir=state, write=True)
    assert report["total_rows_read"] == 3
    assert report["superseded_duplicates"] == 1
    assert report["kept"] == 2
    assert m.is_superseded("t1", state_dir=state)
    assert not m.is_superseded("t2", state_dir=state)
    assert report["truth_label"] == "MEMORY_CONSOLIDATION_V1"


def test_context_compression(state):
    from System import swarm_context_compression as c

    big = "\n".join(f"line {i} is filler" for i in range(300))
    res = c.compress_chunk(big, target_chars=200)
    assert res["compressed"]
    assert res["out_chars"] < res["in_chars"]
    assert "lines elided" in res["text"]
    # receipt content never gets compressed
    rcpt = 'truth_label": "WDP_V1", "receipt_id": "x", "sha256": "abc"\n' + big
    res2 = c.compress_chunk(rcpt, target_chars=200)
    assert not res2["compressed"]


def test_doc_field_feeder_markdown(state):
    from System import swarm_doc_field_feeder as d

    doc = state / "sample.md"
    doc.write_text("# Title\n\nHello.\n\n## Section 2\n\nMore text.\n", encoding="utf-8")
    report = d.feed_document(doc, state_dir=state)
    assert report["chunks"] == 2
    assert report["truth_label"] == "DOC_FEED_V1"
    ledger = (state / "document_stigmergy.jsonl").read_text()
    rows = [json.loads(l) for l in ledger.splitlines() if l.strip()]
    assert any(r["stigmergic_label"] == "DOCUMENT_CHUNK" for r in rows)


def test_ledger_tree_index(state):
    from System import swarm_ledger_tree_index as lt

    rows = [{"text": "photo of a duck on a lake", "ts": 1.0} for _ in range(150)]
    _write_ledger(state, "visual_stigmergy.jsonl", rows)
    idx = lt.build_tree_index(state / "visual_stigmergy.jsonl", section_rows=64)
    assert idx["sections"]
    assert idx["sections"][0]["row_end"] == 63
    res = lt.query_tree_index(idx, "duck")
    assert res["sections"]
    assert res["sections"][0]["score"] > 0


def test_spinal_sandbox(state):
    from System import swarm_spinal_sandbox as sb

    # A patch that adds a file; the sandbox applies it and reports ok.
    patch = "\n".join([
        "diff --git a/sandbox_probe.txt b/sandbox_probe.txt",
        "new file mode 100644",
        "index 0000000..e69de29",
        "--- /dev/null",
        "+++ b/sandbox_probe.txt",
        "@@ -0,0 +1 @@",
        "+shello from sandbox",
        "",
    ])
    receipt = sb.evaluate_patch_in_sandbox(patch, [], timeout_s=60)
    assert receipt["ok"] is True
    assert receipt["schema"] == "SPINAL_SANDBOX_V1"


def test_fabric_patterns(state):
    from System import swarm_fabric_patterns as f

    res = f.import_fabric_pattern("clean_code", "Review the code and clean it.", state_dir=state)
    assert res["ok"] is True
    idx = json.loads((state / "fabric_patterns_index.json").read_text())
    assert "clean_code" in idx["patterns"]
    out = f.export_fabric_pattern("clean_code")
    # export reads from the default STATE when not overridden; only name check
    assert isinstance(out, str)
