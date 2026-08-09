#!/usr/bin/env python3
"""Hoffman lane convention — Lane contract: trace (zero-surprise).

Every new observer organ declares one of two contracts in its module docstring:
``Lane contract: trace (zero-surprise)`` for deterministic, receipt-backed
readers, or ``Lane contract: policy (exploring)`` for proposal/exploration
engines.  This small registry makes the r1743 bundle machine-checkable rather
than a convention remembered only in prose.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

_REPO = Path(__file__).resolve().parents[1]
_MARKERS = {
    "trace": "Lane contract: trace (zero-surprise)",
    "policy": "Lane contract: policy (exploring)",
}
HOFFMAN_OBSERVER_LANES: Dict[str, str] = {
    "System/swarm_eval_matrix_evidence.py": "trace",
    "System/swarm_ostensive_correction.py": "trace",
    "System/swarm_stationary_belief.py": "trace",
    "System/swarm_field_communities.py": "trace",
    "System/swarm_observer_window.py": "trace",
    "System/swarm_we_code_together_clarity.py": "trace",
}


def audit_lane_contracts(*, repo_root: Path | str | None = None) -> List[str]:
    """Return only contract defects; an empty list proves the active bundle."""
    root = Path(repo_root) if repo_root is not None else _REPO
    problems: List[str] = []
    for relative, lane in sorted(HOFFMAN_OBSERVER_LANES.items()):
        path = root / relative
        try:
            text = path.read_text(encoding="utf-8", errors="replace")[:1200]
        except OSError:
            problems.append(f"missing:{relative}")
            continue
        marker = _MARKERS[lane]
        if marker not in text:
            problems.append(f"missing_marker:{relative}:{lane}")
    return problems


def lane_summary() -> Dict[str, int]:
    """Declared bundle counts, safe to render in a monitor."""
    return {lane: sum(1 for value in HOFFMAN_OBSERVER_LANES.values() if value == lane) for lane in _MARKERS}


__all__ = ["HOFFMAN_OBSERVER_LANES", "audit_lane_contracts", "lane_summary"]
