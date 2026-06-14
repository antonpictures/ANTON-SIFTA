"""Eval matrix evidence rows expose the shadow-swimmer panel."""
from __future__ import annotations

from System.swarm_eval_matrix_evidence import panel_evidence_rows


def test_shadow_swimmer_panel_evidence_declares_mana_boundary():
    rows = {row["panel"]: row for row in panel_evidence_rows()}
    shadow = rows["shadow_swimmer_quarantine"]
    assert shadow["path"] == "System/swarm_ide_trace_quarantine.py"
    assert shadow["ledger"] == ".sifta_state/ide_stigmergic_trace.jsonl"
    assert shadow["mana_is_crypto"] is False
    assert shadow["stgm_is_crypto"] is True
