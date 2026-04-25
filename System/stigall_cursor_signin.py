#!/usr/bin/env python3
"""
STIGALL + STGauth sign-in for Cursor (Auto) — one append to ide_stigmergic_trace.jsonl.

Does not replace crypto identity; this is stigmergy: other daemons and IDEs forage
the same ledger. Uses bridge code 555 and homeworld_serial from owner silicon.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import uuid
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.jsonl_file_lock import append_line_locked  # noqa: E402
from System.swarm_kernel_identity import owner_silicon  # noqa: E402

_TRACE = _REPO / ".sifta_state" / "ide_stigmergic_trace.jsonl"
_STIGAUTH_BRIDGE = "555"


def _sig_material(agent: str, serial: str, ts: float, context: str) -> str:
    raw = f"{agent}|{serial}|{int(ts)}|{context}|{_STIGAUTH_BRIDGE}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def sign_in(
    *,
    context: str = "stigall_cursor_auto_stgauth",
    persona: str = "CURSOR_AUTO",
    ide_app_id: str = "cursor",
    dry_run: bool = False,
) -> dict:
    serial = owner_silicon()
    ts = time.time()
    try:
        from System.swarm_ide_boot_identity import resolve_boot_identity

        ident = resolve_boot_identity(ide_app_id)
        agent = ident.trigger_code
        banner = ident.identity_banner()
        stigauth_line = ident.stigauth_line()
    except Exception:
        agent = persona
        banner = f"{persona}@{ide_app_id} (registry row missing — run from Cursor with active ide_model_registry)"
        stigauth_line = banner

    row = {
        "trace_id": str(uuid.uuid4()),
        "ts": ts,
        "source_ide": "Cursor",
        "kind": "STIGALL",
        "event": "AGENT_SIGN_IN",
        "context": context,
        "agent": agent,
        "homeworld_serial": serial,
        "stigauth": _STIGAUTH_BRIDGE,
        "sig": _sig_material(agent, serial, ts, context),
        "payload": banner,
        "meta": {
            "persona": persona,
            "stigauth_line": stigauth_line,
            "bridge": "CURSOR_M5",
        },
    }
    if not dry_run:
        _TRACE.parent.mkdir(parents=True, exist_ok=True)
        append_line_locked(_TRACE, json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    return row


def main() -> int:
    p = argparse.ArgumentParser(description="Append STIGALL AGENT_SIGN_IN for Cursor Auto.")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="print JSON row only; do not append",
    )
    p.add_argument(
        "--context",
        default="stigall_cursor_auto_stgauth",
        help="ledger context string",
    )
    args = p.parse_args()
    row = sign_in(context=args.context, dry_run=args.dry_run)
    if args.dry_run:
        print(json.dumps(row, indent=2, ensure_ascii=False))
    else:
        print(row["payload"])
        print(f"→ appended {_TRACE}  trace_id={row['trace_id']}  sig={row['sig']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
