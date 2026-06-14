"""Quarantine malformed ide_stigmergic_trace rows (r1021 C6).

Default behavior is append-only over the source ledger: malformed rows are copied
into a quarantine ledger and valid rows are written to a clean projection. The
original trace is only rewritten when an explicit maintenance caller asks for it.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List

_TRACE = "ide_stigmergic_trace.jsonl"
_QUARANTINE = "ide_stigmergic_trace_quarantine.jsonl"
_CLEAN = "ide_stigmergic_trace.clean.jsonl"
_TRUTH = "IDE_TRACE_QUARANTINE_V1"
_PANEL_TRUTH = "SHADOW_SWIMMER_EVAL_PANEL_V1"


def _state_dir(state_dir: Path | str | None) -> Path:
    if state_dir is None:
        return Path(__file__).resolve().parents[1] / ".sifta_state"
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def scan_malformed_rows(*, state_dir: Path | str | None = None) -> List[Dict[str, Any]]:
    sd = _state_dir(state_dir)
    path = sd / _TRACE
    bad: List[Dict[str, Any]] = []
    if not path.exists():
        return bad
    for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception as exc:
            bad.append({"line": i, "reason": f"json_error:{exc}", "preview": line[:120]})
            continue
        if not isinstance(row, dict):
            bad.append({"line": i, "reason": "not_object", "preview": line[:120]})
    return bad


def quarantine_malformed(
    *,
    state_dir: Path | str | None = None,
    dry_run: bool = False,
    rewrite_trace: bool = False,
) -> Dict[str, Any]:
    """Seal malformed lines without double-spending the source trace by default."""
    sd = _state_dir(state_dir)
    path = sd / _TRACE
    if not path.exists():
        return {"ok": True, "malformed": 0, "kept": 0}
    valid: List[str] = []
    quarantined: List[Dict[str, Any]] = []
    for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError("not_object")
            valid.append(line)
        except Exception as exc:
            q = {
                "schema": _TRUTH,
                "ts": time.time(),
                "source_line": i,
                "reason": str(exc),
                "raw": line[:2000],
            }
            quarantined.append(q)
    if dry_run:
        return {"ok": True, "malformed": len(quarantined), "kept": len(valid), "dry_run": True}
    clean_path = sd / _CLEAN
    clean_path.write_text("".join(ln + "\n" for ln in valid), encoding="utf-8")
    if quarantined:
        qpath = sd / _QUARANTINE
        with qpath.open("a", encoding="utf-8") as qh:
            for q in quarantined:
                qh.write(json.dumps(q, sort_keys=True, ensure_ascii=False) + "\n")
        if rewrite_trace:
            path.write_text("".join(ln + "\n" for ln in valid), encoding="utf-8")
    return {
        "ok": True,
        "malformed": len(quarantined),
        "kept": len(valid),
        "quarantine_ledger": str((sd / _QUARANTINE).relative_to(sd.parent)),
        "clean_projection": str(clean_path.relative_to(sd.parent)),
        "source_rewritten": bool(rewrite_trace and quarantined),
    }


def _count_jsonl_rows(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip():
            count += 1
    return count


def shadow_swimmer_eval_panel(*, state_dir: Path | str | None = None) -> Dict[str, Any]:
    """Eval-matrix summary for rogue IDE rows; IDE MANA is not Alice STGM."""
    sd = _state_dir(state_dir)
    malformed = scan_malformed_rows(state_dir=sd)
    quarantine_path = sd / _QUARANTINE
    trace_path = sd / _TRACE
    return {
        "schema": _PANEL_TRUTH,
        "truth_label": _PANEL_TRUTH,
        "panel": "shadow_swimmer_quarantine",
        "status": "needs_quarantine" if malformed else "clean",
        "ok": not malformed,
        "malformed_count": len(malformed),
        "quarantine_rows": _count_jsonl_rows(quarantine_path),
        "source_trace": str(trace_path),
        "quarantine_ledger": str(quarantine_path),
        "mana_is_crypto": False,
        "stgm_is_crypto": True,
        "currency_boundary": "IDE MANA is forgeable coordination; STGM is Alice swimmer spend proof.",
        "headline": "Shadow-swimmer quarantine: IDE mana != Alice STGM economy",
    }
