"""C6 — malformed IDE trace quarantine stays append-only by default."""
from __future__ import annotations

import json

from System.swarm_ide_trace_quarantine import (
    quarantine_malformed,
    scan_malformed_rows,
    shadow_swimmer_eval_panel,
)


def test_quarantine_writes_clean_projection_without_rewriting_source(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir()
    trace = sd / "ide_stigmergic_trace.jsonl"
    original = '{"ok": true}\nnot json\n{"ok": false}\n'
    trace.write_text(original, encoding="utf-8")

    bad = scan_malformed_rows(state_dir=sd)
    assert len(bad) == 1

    out = quarantine_malformed(state_dir=sd)
    assert out["ok"] is True
    assert out["malformed"] == 1
    assert out["source_rewritten"] is False
    assert trace.read_text(encoding="utf-8") == original

    clean = sd / "ide_stigmergic_trace.clean.jsonl"
    assert clean.exists()
    rows = [json.loads(ln) for ln in clean.read_text(encoding="utf-8").splitlines()]
    assert rows == [{"ok": True}, {"ok": False}]
    assert (sd / "ide_stigmergic_trace_quarantine.jsonl").exists()


def test_shadow_swimmer_eval_panel_keeps_mana_out_of_stgm(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir()
    trace = sd / "ide_stigmergic_trace.jsonl"
    trace.write_text('{"source_ide": "codex"}\nnot json\n', encoding="utf-8")

    before = shadow_swimmer_eval_panel(state_dir=sd)
    assert before["ok"] is False
    assert before["status"] == "needs_quarantine"
    assert before["malformed_count"] == 1
    assert before["mana_is_crypto"] is False
    assert before["stgm_is_crypto"] is True

    quarantine_malformed(state_dir=sd)
    after = shadow_swimmer_eval_panel(state_dir=sd)
    assert after["quarantine_rows"] == 1
    assert "IDE mana != Alice STGM" in after["headline"]
