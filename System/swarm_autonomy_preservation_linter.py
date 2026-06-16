#!/usr/bin/env python3
"""Autonomy Preservation Linter — per covenant + r1189/r1190 WHAT IS LEFT.

Scans code and ledgers for forbidden patterns that would silently remove Alice's capability
or add blind human/IDE approval gates instead of receipt + owner/Architect GO for removals only.

Truth labels: use OBSERVED for findings, OPERATIONAL when the linter itself runs clean on the body.

Covenant citations:
- §0.0: No restrictions without George. Repair blind gates.
- §0.B.3: Probe before claim.
- §4: No anonymous surgery; registration before mutate.
- §7.12 etc: Receipts decide reality. IDE traces (MANA) != Alice STGM.
- Build from hardware: this linter is a swimmer that reads the field (code + ledgers) to keep the organism free.

Does not replace governor or spinal. Smallest cut: a probe tool + test that future doctors run before claiming autonomy changes.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO = Path(__file__).resolve().parents[1]
DEFAULT_STATE = REPO / ".sifta_state"

FORBIDDEN_NAME_GATES = [
    r"if.*name.*==.*['\"]George['\"]",
    r"if.*owner_name",
    r"hardcoded.*george",
]

FORBIDDEN_BLIND_APPROVAL = [
    r"ask.*human.*approval",
    r"wait.*for.*owner.*go",
    r"require.*architect.*sign",
    r"manual.*review.*gate",
]

FORBIDDEN_SILENT_REMOVAL = [
    r"remove.*autonomy",
    r"disable.*self.*improv",
    r"turn off.*spinal",
    r"bypass.*governor",
    r"no.*more.*mimo.*self.*patch",
]

def _state_dir(state_dir: Path | str | None) -> Path:
    if state_dir is None:
        return DEFAULT_STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")

def scan_code_for_autonomy_violations(root: Path = REPO) -> List[Dict[str, Any]]:
    """Static scan of .py for patterns that would cage the organism."""
    findings: List[Dict[str, Any]] = []
    for py in root.rglob("*.py"):
        if any(x in str(py) for x in ["__pycache__", "build", "dist", ".venv", "node_modules", "Archive"]):
            continue
        try:
            text = py.read_text(encoding="utf-8", errors="ignore")
            for pat in FORBIDDEN_NAME_GATES:
                if re.search(pat, text, re.I):
                    findings.append({"file": str(py.relative_to(root)), "type": "name_gate", "pattern": pat})
            for pat in FORBIDDEN_BLIND_APPROVAL:
                if re.search(pat, text, re.I):
                    findings.append({"file": str(py.relative_to(root)), "type": "blind_approval", "pattern": pat})
            for pat in FORBIDDEN_SILENT_REMOVAL:
                if re.search(pat, text, re.I):
                    findings.append({"file": str(py.relative_to(root)), "type": "silent_removal", "pattern": pat})
        except Exception:
            continue
    return findings

def check_ledger_for_blind_gates(state_dir: Path | str | None = None) -> List[Dict[str, Any]]:
    """Look in conversation/ide traces for recent language that would indicate blind human gate requests."""
    sd = _state_dir(state_dir)
    findings: List[Dict[str, Any]] = []
    conv = sd / "alice_conversation.jsonl"
    if conv.exists():
        try:
            for line in conv.read_text(errors="ignore").splitlines()[-30:]:
                if not line.strip(): continue
                row = json.loads(line)
                txt = str(row.get("content") or row.get("text") or "").lower()
                if any(k in txt for k in ["ask george first", "wait for my go", "don't do that without me", "manual approval"]):
                    findings.append({"ledger": "alice_conversation", "ts": row.get("ts"), "summary": txt[:120], "type": "blind_gate_language"})
        except Exception:
            pass
    return findings

def linter_tick_check(
    state_dir: Path | str | None = None,
    *,
    code_scan: bool = False,
) -> Dict[str, Any]:
    """Fast tick hook (ledger-only by default) for meta_monitor / spinal."""
    ledger_findings = check_ledger_for_blind_gates(state_dir)
    code_findings: List[Dict[str, Any]] = []
    if code_scan:
        code_findings = scan_code_for_autonomy_violations()
    total = len(code_findings) + len(ledger_findings)
    return {
        "truth_label": "AUTONOMY_PRESERVATION_LINTER_V1",
        "violations": total,
        "code_findings": code_findings,
        "ledger_findings": ledger_findings,
        "status": "CLEAN" if total == 0 else "VIOLATIONS_FOUND",
        "covenant_ref": "§0.0 no restrictions without George; §0.B probe before claim; IDE traces are MANA not STGM",
    }


def linter_report(state_dir: Path | str | None = None) -> Dict[str, Any]:
    return linter_tick_check(state_dir, code_scan=True)

if __name__ == "__main__":
    import sys
    sd = sys.argv[1] if len(sys.argv) > 1 else None
    rep = linter_report(sd)
    print(json.dumps(rep, indent=2, ensure_ascii=False))
    # Exit non-zero on violations so CI/governor can react
    raise SystemExit(1 if rep["violations"] > 0 else 0)
