#!/usr/bin/env python3
"""Tests for swarm_autonomy_preservation_linter."""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
import sys

if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from System.swarm_autonomy_preservation_linter import (
    check_ledger_for_blind_gates,
    linter_tick_check,
)


def test_ledger_blind_gate_detection(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir()
    (sd / "alice_conversation.jsonl").write_text(
        json.dumps({"ts": 1.0, "content": "ask george first before you patch"}) + "\n",
        encoding="utf-8",
    )
    findings = check_ledger_for_blind_gates(tmp_path)
    assert len(findings) == 1
    assert findings[0]["type"] == "blind_gate_language"


def test_linter_tick_check_fast_path(tmp_path):
    rep = linter_tick_check(tmp_path, code_scan=False)
    assert rep["truth_label"] == "AUTONOMY_PRESERVATION_LINTER_V1"
    assert "violations" in rep