#!/usr/bin/env python3
"""
sentinel_software_wake.py — Software-only sentinel + wake recommendation.
══════════════════════════════════════════════════════════════════════════════
**Epistemic boundary (non-negotiable):**
  There are **no** nanobots, in-body drones, or physical agents inside a human
  operated by this codebase. “Sentinel swimmers” here mean **watchdog checks,
  HTTP sentry, JSONL heartbeats** — processes on **your machines only**.

This module composes the existing `swarm_integrity_watchdog` with a single
boolean **wake_recommended** flag for orchestration (cron, relay, desktop OS).

Literature: dependability taxonomy (Avizienis *et al.* 2004, IEEE TDSC); for
microrobotics *limits* (not in vivo deployment) see DYOR §21.

Outputs:
  - Append one JSON line to `.sifta_state/sentinel_wake_log.jsonl`
  - Optional mirror dict for callers
══════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_WAKE_LOG = _STATE / "sentinel_wake_log.jsonl"


@dataclass
class SentinelEvaluation:
    """Result of a software sentinel pass (no hardware beyond the host)."""

    ts: float
    software_only: bool
    wake_recommended: bool
    integrity_overall: str
    summary: str
    detail: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ts": self.ts,
            "software_only": self.software_only,
            "wake_recommended": self.wake_recommended,
            "integrity_overall": self.integrity_overall,
            "summary": self.summary,
            "detail": self.detail,
        }


def evaluate_sentinel_orchestration(*, log: bool = True) -> SentinelEvaluation:
    """
    Run integrity watchdog; recommend operator attention if not OK.

    ``wake_recommended`` is **True** when any subsystem is WARN/CRITICAL —
    i.e. “don’t treat the organism as safely idle for maintenance silence.”
    """
    from System.swarm_integrity_watchdog import CheckStatus, run_watchdog

    rep = run_watchdog(verbose=False)
    wake = rep.overall != CheckStatus.OK
    summary = (
        "Wake attention: integrity degraded."
        if wake
        else "Nominal: integrity checks passed; safe for scheduled idle work."
    )
    ev = SentinelEvaluation(
        ts=time.time(),
        software_only=True,
        wake_recommended=wake,
        integrity_overall=rep.overall.value,
        summary=summary,
        detail=rep.to_dict(),
    )
    if log:
        _append_wake_log(ev)
    return ev


def _append_wake_log(ev: SentinelEvaluation) -> None:
    from System.jsonl_file_lock import append_line_locked

    _STATE.mkdir(parents=True, exist_ok=True)
    append_line_locked(_WAKE_LOG, json.dumps(ev.to_dict(), ensure_ascii=False) + "\n")


if __name__ == "__main__":  # pragma: no cover
    ev = evaluate_sentinel_orchestration()
    print(json.dumps(ev.to_dict(), indent=2, default=str))
    raise SystemExit(0 if not ev.wake_recommended else 2)
