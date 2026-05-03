"""
Multimodal cortex verification harness.

Use after a primary cortex switch or before promotion. The harness is receipt
first: it accepts probe scores from real probe runners and decides whether the
new cortex is safe to promote. It does not fake vision/audio/tool competence.

Truth label: MULTIMODAL_CORTEX_VERIFICATION
Kill-switch: SIFTA_CORTEX_VERIFICATION_DISABLE=1.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from System.jsonl_file_lock import append_line_locked, read_text_locked
from System.swarm_persistent_owner_history import state_dir

LOG_NAME = "cortex_verification.jsonl"
PROBES = ("vision", "audio", "tool", "owner_continuity")
MIN_OVERALL = 0.82
MIN_PROBE = 0.75


def log_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / LOG_NAME


def _disabled() -> bool:
    return os.environ.get("SIFTA_CORTEX_VERIFICATION_DISABLE", "").strip() == "1"


def _score(value: Any) -> Optional[float]:
    if isinstance(value, dict):
        value = value.get("score")
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return round(max(0.0, min(1.0, f)), 4)


def normalize_probe_results(probe_results: Optional[Dict[str, Any]]) -> Dict[str, Optional[float]]:
    raw = probe_results or {}
    return {name: _score(raw.get(name)) for name in PROBES}


def promotion_gate(row: Dict[str, Any]) -> bool:
    if row.get("disabled"):
        return True
    scores = row.get("probes") or {}
    if any(scores.get(name) is None for name in PROBES):
        return False
    if float(row.get("overall", 0.0)) < MIN_OVERALL:
        return False
    return all(float(scores[name]) >= MIN_PROBE for name in PROBES)


def run_harness(
    cortex_id: str,
    probe_results: Optional[Dict[str, Any]] = None,
    *,
    root: Optional[Path] = None,
    write_ledger: bool = True,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    scores = normalize_probe_results(probe_results)
    valid = [v for v in scores.values() if v is not None]
    overall = round(sum(valid) / len(valid), 4) if valid else 0.0
    missing = [name for name, value in scores.items() if value is None]
    row: Dict[str, Any] = {
        "ts": time.time() if now is None else float(now),
        "trace_id": str(uuid.uuid4()),
        "kind": "MULTIMODAL_CORTEX_VERIFICATION",
        "truth_label": "MULTIMODAL_CORTEX_VERIFICATION",
        "cortex_id": str(cortex_id or "unknown"),
        "probes": scores,
        "vision_score": scores["vision"],
        "audio_score": scores["audio"],
        "tool_score": scores["tool"],
        "owner_continuity_score": scores["owner_continuity"],
        "overall": overall,
        "missing_probes": missing,
        "thresholds": {"overall": MIN_OVERALL, "per_probe": MIN_PROBE},
        "disabled": _disabled(),
    }
    row["pass"] = promotion_gate(row)
    if write_ledger and not row["disabled"]:
        append_line_locked(
            log_path(root),
            json.dumps(row, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return row


def verify_after_switch(
    old_cortex: str,
    new_cortex: str,
    *,
    before_results: Optional[Dict[str, Any]] = None,
    after_results: Optional[Dict[str, Any]] = None,
    root: Optional[Path] = None,
    write_ledger: bool = True,
) -> Dict[str, Any]:
    before = run_harness(old_cortex, before_results, root=root, write_ledger=False)
    after = run_harness(new_cortex, after_results, root=root, write_ledger=False)
    delta = {}
    for probe in PROBES:
        b = before["probes"].get(probe)
        a = after["probes"].get(probe)
        delta[probe] = None if b is None or a is None else round(float(a) - float(b), 4)
    row = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "kind": "MULTIMODAL_CORTEX_SWITCH_VERIFICATION",
        "truth_label": "MULTIMODAL_CORTEX_VERIFICATION",
        "old_cortex": old_cortex,
        "new_cortex": new_cortex,
        "before": before,
        "after": after,
        "delta": delta,
        "pass": bool(after["pass"]),
        "disabled": _disabled(),
    }
    if write_ledger and not row["disabled"]:
        append_line_locked(
            log_path(root),
            json.dumps(row, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return row


def tail_verification_rows(max_rows: int = 8, *, root: Optional[Path] = None) -> list[Dict[str, Any]]:
    path = log_path(root)
    if not path.exists():
        return []
    raw = read_text_locked(path, encoding="utf-8", errors="replace")
    rows = []
    for line in raw.splitlines()[-max(1, min(max_rows, 100)) :]:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def summary_for_prompt(*, root: Optional[Path] = None) -> str:
    rows = tail_verification_rows(1, root=root)
    if not rows:
        return ""
    row = rows[-1]
    return (
        "CORTEX VERIFICATION: "
        f"{row.get('cortex_id') or row.get('new_cortex')} pass={row.get('pass')} "
        f"overall={row.get('overall') or (row.get('after') or {}).get('overall')}"
    )


__all__ = [
    "MIN_OVERALL",
    "MIN_PROBE",
    "PROBES",
    "log_path",
    "normalize_probe_results",
    "promotion_gate",
    "run_harness",
    "summary_for_prompt",
    "tail_verification_rows",
    "verify_after_switch",
]
