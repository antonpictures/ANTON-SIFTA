#!/usr/bin/env python3
"""
ide_stigmergic_bridge.py — Cross-IDE stigmergy (environment-mediated traces)
═══════════════════════════════════════════════════════════════════════════

Cursor, Antigravity, terminal, or any script on the **same repo** do not share
one chat API. They **do** share the filesystem. This module is the pheromone
field: append-only JSONL traces any tool can deposit and forage.

This is NOT a wire protocol to "merge" IDEs — it is **stigmergy**: indirect
coordination through persistent substrate (see Bonabeau/Dorigo swarm literature).

Trace file: .sifta_state/ide_stigmergic_trace.jsonl (POSIX flock on append + reads)

Distinct from m5queen_dead_drop.jsonl (Swarm chat log). Use this for:
  - Cursor ↔ Antigravity handoffs
  - "Swimmer" micro-tasks (short structured payloads)
  - Base-config or objective hints both IDEs should see

Usage:
    from ide_stigmergic_bridge import deposit, forage, trace_path

    deposit("cursor_m5", "Implement gatekeeper JSONL audit", kind="handoff")
    for row in forage(limit=5):
        print(row)
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.jsonl_file_lock import append_line_locked, read_text_locked  # noqa: E402
_STATE = _REPO / ".sifta_state"
_STATE.mkdir(parents=True, exist_ok=True)
TRACE_PATH = _STATE / "ide_stigmergic_trace.jsonl"

# Known IDE labels (any string allowed)
IDE_CURSOR_M5 = "cursor_m5"
IDE_ANTIGRAVITY = "antigravity_m5"
IDE_ANTIGRAVITY_MINI = "antigravity_mini"   # Mac Mini (M1_SENTRY)
IDE_CLI = "cli"

# ── Node serial registry (homeworld_serial per machine) ──────────
#   M5 Foundry (Mac Studio):  GTH4921YP3
#   M1 Sentry (Mac Mini):     C07FL0JAQ6NV
#   Use the correct serial in deposit() to partition telemetry by silicon.
NODE_M5_FOUNDRY = "GTH4921YP3"
NODE_M1_SENTRY = "C07FL0JAQ6NV"


def trace_path() -> Path:
    return TRACE_PATH


def deposit(
    source_ide: str,
    payload: str,
    *,
    kind: str = "message",
    meta: Optional[Dict[str, Any]] = None,
    homeworld_serial: str = "GTH4921YP3",
) -> Dict[str, Any]:
    """
    Drop one pheromone trace. Append-only; never deletes history.
    """
    row: Dict[str, Any] = {
        "trace_id": str(uuid.uuid4()),
        "ts": time.time(),
        "source_ide": source_ide,
        "kind": kind,
        "payload": payload,
        "homeworld_serial": homeworld_serial,
    }
    if meta:
        row["meta"] = meta
    line = json.dumps(row, ensure_ascii=False) + "\n"
    TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    append_line_locked(TRACE_PATH, line, encoding="utf-8")
    return row


def forage(
    limit: int = 50,
    source_ide: Optional[str] = None,
    kind: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Read recent traces (newest last in file; we return last `limit` matching filters).
    """
    if not TRACE_PATH.exists():
        return []
    lines = read_text_locked(TRACE_PATH, encoding="utf-8", errors="replace").splitlines()
    rows: List[Dict[str, Any]] = []
    for line in lines[-2000:]:  # cap read for sanity
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if source_ide:
        rows = [r for r in rows if r.get("source_ide") == source_ide]
    if kind:
        rows = [r for r in rows if r.get("kind") == kind]
    return rows[-limit:]


def stream_tail(max_lines: int = 100) -> Iterator[Dict[str, Any]]:
    """Iterate last N JSONL rows (for simple watchers)."""
    for r in forage(limit=max_lines):
        yield r


def swimmer_dispatch(
    task_hint: str,
    target_file: Optional[str] = None,
    *,
    source_ide: str = IDE_CURSOR_M5,
) -> Dict[str, Any]:
    """
    Structured 'swimmer' deposit — a small task grain for humans or agents to pick up.
    Does not run agents; only leaves scent on the substrate.
    """
    meta: Dict[str, Any] = {}
    if target_file:
        meta["target_file"] = target_file
    return deposit(
        source_ide,
        task_hint,
        kind="swimmer_dispatch",
        meta=meta or None,
    )


if __name__ == "__main__":
    import sys

    argv = sys.argv[1:]
    if argv and argv[0] == "deposit":
        text = " ".join(argv[1:]) if len(argv) > 1 else "ping"
        d = deposit(IDE_CLI, text, kind="cli_ping")
        print(json.dumps(d, indent=2))
    elif argv and argv[0] in ("forage", "smell", "tail"):
        n = 50
        if len(argv) > 1 and argv[1].isdigit():
            n = int(argv[1])
        print(f"Trace: {TRACE_PATH}")
        for row in forage(limit=n):
            print(json.dumps(row, ensure_ascii=False))
    elif argv and argv[0] in ("-h", "--help", "help"):
        print("Usage: ide_stigmergic_bridge.py [forage [N] | deposit <message>]")
        print(f"  Trace file: {TRACE_PATH}")
    else:
        print(f"Trace: {TRACE_PATH}")
        for row in forage(limit=10):
            print(json.dumps(row, ensure_ascii=False))
