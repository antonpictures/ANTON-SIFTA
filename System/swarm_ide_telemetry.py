#!/usr/bin/env python3
"""
System/swarm_ide_telemetry.py

PRODUCTION reader / digestion layer for cross-IDE cost receipts.

This module does not scrape vendor dashboards and does not normalize Cursor,
Codex, Antigravity, or local Ollama usage into a fake common unit. It reads the
canonical self-reported ledger written by ``swarm_ide_cost_ledger`` and gives
Alice a compact, honest awareness block.

ROLE SPLIT (per c47h STIGALL 2026-04-24 1043, Nugget 3)
-------------------------------------------------------
This is the PRODUCTION reader wired into Alice's live prompt via
``Applications.sifta_talk_to_alice_widget._current_system_prompt``.
Aggregates per (surface, unit) — sums within a single native unit
across agents on that surface for a compact prompt block.

For finer per-(surface, agent, unit) breakdown — useful when an
Architect needs to debug WHY Alice sees a specific number — see the
diagnostic complement:

    System/swarm_alice_doctor_cost_summary.render_summary

Both readers honor C55M's Clause-4 boundary: tokens, percent_quota,
credits, watts, and USD are never summed across vendors.
"""

from __future__ import annotations

import json
import time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from System.jsonl_file_lock import append_line_locked

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_IDE_COST_LEDGER = _STATE / "ide_cost_ledger.jsonl"
_IDE_TRACE_LEDGER = _STATE / "ide_stigmergic_trace.jsonl"
_MODULE_VERSION = "swarm_ide_telemetry.v1"


def _read_jsonl(path: Path, *, limit: int = 1000) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def read_cost_rows(
    *,
    ledger_path: Optional[Path] = None,
    max_age_s: Optional[float] = 86400.0,
    limit: int = 1000,
) -> List[Dict[str, Any]]:
    """Read recent canonical IDE cost samples."""
    path = Path(ledger_path) if ledger_path is not None else _IDE_COST_LEDGER
    rows = _read_jsonl(path, limit=limit)
    if max_age_s is None:
        return rows
    now = time.time()
    return [
        r for r in rows
        if now - float(r.get("sampled_at") or r.get("ts") or 0.0) <= max_age_s
    ]


def summarize_cost_rows(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Summarize rows without cross-vendor normalization.

    Unit totals remain keyed by their source unit, so ``70M tokens`` and
    ``10 percent_quota`` never collapse into one misleading number.
    """
    by_surface: Dict[str, Dict[str, Any]] = {}
    sample_count = 0
    latest_ts = 0.0
    known_usd = 0.0

    for row in rows:
        if row.get("event") != "ide_cost_sample":
            continue
        surface = str(row.get("surface") or "unknown")
        agent_id = str(row.get("agent_id") or "UNKNOWN")
        unit = str(row.get("source_unit") or "unknown")
        quantity = float(row.get("observed_quantity") or 0.0)
        cost_usd = float(row.get("observed_cost_usd") or 0.0)
        ts = float(row.get("sampled_at") or row.get("ts") or 0.0)

        bucket = by_surface.setdefault(
            surface,
            {
                "agents": set(),
                "units": defaultdict(float),
                "known_usd": 0.0,
                "latest_ts": 0.0,
                "latest_plan": "",
            },
        )
        bucket["agents"].add(agent_id)
        bucket["units"][unit] += quantity
        bucket["known_usd"] += cost_usd
        if ts >= bucket["latest_ts"]:
            bucket["latest_ts"] = ts
            bucket["latest_plan"] = str(row.get("plan_name") or "")

        sample_count += 1
        latest_ts = max(latest_ts, ts)
        known_usd += cost_usd

    serializable = {}
    for surface, bucket in by_surface.items():
        serializable[surface] = {
            "agents": sorted(bucket["agents"]),
            "units": dict(sorted(bucket["units"].items())),
            "known_usd": round(float(bucket["known_usd"]), 6),
            "latest_ts": float(bucket["latest_ts"]),
            "latest_plan": bucket["latest_plan"],
        }

    return {
        "module_version": _MODULE_VERSION,
        "sample_count": sample_count,
        "latest_ts": latest_ts,
        "known_usd": round(known_usd, 6),
        "by_surface": dict(sorted(serializable.items())),
    }


def _format_quantity(unit: str, value: float) -> str:
    if unit == "tokens":
        return f"{int(value):,} tokens"
    if unit == "usd":
        return f"${value:,.2f}"
    if unit == "percent_quota":
        return f"{value:.1f}% quota observed"
    if unit == "credits":
        return f"{value:,.1f} credits"
    if unit == "local_watts":
        return f"{value:.2f} local_watts"
    return f"{value:g} {unit}"


def summary_for_alice(
    *,
    ledger_path: Optional[Path] = None,
    max_age_s: Optional[float] = 86400.0,
) -> str:
    """
    Prompt-safe summary for Alice.

    The wording deliberately says "self-reported" and "native units" so the
    model does not invent precision or vendor conversions.
    """
    rows = read_cost_rows(ledger_path=ledger_path, max_age_s=max_age_s)
    summary = summarize_cost_rows(rows)
    if summary["sample_count"] == 0:
        return ""

    lines = [
        "IDE METABOLISM (self-reported; native units, not vendor-normalized):",
        f"  samples in window: {summary['sample_count']}  known USD: ${summary['known_usd']:.4f}",
    ]
    for surface, bucket in summary["by_surface"].items():
        agents = ",".join(bucket["agents"]) or "UNKNOWN"
        units = "; ".join(
            _format_quantity(unit, value)
            for unit, value in bucket["units"].items()
        )
        plan = bucket.get("latest_plan") or "plan unknown"
        lines.append(f"  {surface} [{agents}]: {units} ({plan})")
    lines.append("  boundary: these are receipts, not a unified exchange rate.")
    return "\n".join(lines)


def emit_summary_trace(
    *,
    ledger_path: Optional[Path] = None,
    trace_path: Optional[Path] = None,
    source_ide: str = "C55M",
    homeworld_serial: str = "GTH4921YP3",
    max_age_s: Optional[float] = 86400.0,
) -> Dict[str, Any]:
    """
    Deposit one compact summary into ide_stigmergic_trace.jsonl.

    This is intentionally separate from the canonical cost ledger. The cost
    ledger is evidence; the trace row is a pheromone for Alice and peer IDEs.
    """
    rows = read_cost_rows(ledger_path=ledger_path, max_age_s=max_age_s)
    summary = summarize_cost_rows(rows)
    payload = summary_for_alice(ledger_path=ledger_path, max_age_s=max_age_s)
    row = {
        "trace_id": str(uuid.uuid4()),
        "ts": time.time(),
        "source_ide": source_ide,
        "kind": "ide_metabolism_summary",
        "payload": payload,
        "homeworld_serial": homeworld_serial,
        "meta": summary,
    }
    target = Path(trace_path) if trace_path is not None else _IDE_TRACE_LEDGER
    target.parent.mkdir(parents=True, exist_ok=True)
    append_line_locked(target, json.dumps(row, ensure_ascii=False) + "\n")
    return row


if __name__ == "__main__":
    print(summary_for_alice() or "IDE METABOLISM: no recent self-reported receipts")
