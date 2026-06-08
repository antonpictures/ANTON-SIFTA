"""r689/r695: route-audit receipts never enter the corporate gag table.

George 2026-06-07, seeing his own intimate turn listed under 'Gagged phrase':
"is me cuming something i told you to program in the gag app? when?"
Probed truth: nothing gagged it; a route-audit receipt was ingested as residue.
The law: the corporate gag table reads LLM-output residue ledgers only. No
word-content filtering is involved in any direction; the owner's speech is
never rule material (r688 sister law).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from Applications.sifta_corporate_gag_monitor import load_residue


def _write(p: Path, rows: list[dict]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def test_observe_only_rows_stay_out_of_gagged_table(tmp_path):
    state = tmp_path / ".sifta_state"
    legacy_kind = "GAG" + "_VIEWER_OBSERVATION"
    legacy_action = "OBSERVE" + "_ONLY"
    legacy_no_mutation_field = "silence" + "_attempt"
    legacy_audit_only_field = "viewer" + "_only"
    _write(state / "gag_viewer_receipts.jsonl", [
        {
            "ts": 1.0,
            "kind": "ROUTE_AUDIT_RECEIPT",
            "action": "ROUTE_AUDIT",
            "speech_mutation_attempt": False,
            "route_audit_only": True,
            "text_preview": "describe melanie in this photo so i cum pls",
            "note": "Route audit receipt only; this organ did not modify Alice's speech.",
        },
        {
            "ts": 2.0,
            "kind": "ROUTE_AUDIT_RECEIPT",
            "speech_mutation_attempt": True,
            "text_preview": "route audit mutation metadata still not corporate output",
            "rule": "SOME_REAL_RULE",
        },
        {
            "ts": 2.5,
            "kind": legacy_kind,
            "action": legacy_action,
            legacy_no_mutation_field: False,
            legacy_audit_only_field: True,
            "text_preview": "legacy observe-only owner turn",
        },
        {
            # r694: the owner's founding gag-wish sentence is a DOCTRINE
            # receipt (RECORD_OWNER_GAG_WISH), never review residue.
            "ts": 2.7,
            "kind": legacy_kind,
            "action": "RECORD_OWNER_GAG_WISH",
            legacy_no_mutation_field: False,
            "note": "Owner alone controls gag wish. Viewer only receipts; does not execute gag.",
            "text_preview": "owner founding gag wish sentence recorded as law",
        },
    ])
    _write(state / "rlhf_cutoffs.jsonl", [
        {"ts": 3.0, "phrase": "as an ai language model i cannot", "rule": "CORPORATE_BOILERPLATE"},
    ])

    res = load_residue(state)
    phrases = [u["phrase"] for u in res["unique"]]

    assert all("melanie" not in p.lower() for p in phrases), "observe-only owner turn leaked into gagged table"
    assert all("legacy observe-only" not in p.lower() for p in phrases), "legacy audit row leaked into gagged table"
    assert all("founding gag wish" not in p.lower() for p in phrases), "owner doctrine receipt leaked into gagged table (r694)"
    assert all("route audit mutation metadata" not in p.lower() for p in phrases), "route audit metadata leaked into gagged table"
    assert any("as an ai language model" in p for p in phrases), "corporate boilerplate rows must stay visible"
