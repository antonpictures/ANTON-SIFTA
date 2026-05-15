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
from System.swarm_ide_boot_identity import classify_model_claim  # noqa: E402
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
    selected_model: str | None = None,
    reasoning: str = "auto",
    mode: str = "read-only",
    lane: str = "Probe",
    dry_run: bool = False,
) -> dict:
    serial = owner_silicon()
    ts = time.time()
    registry_model_label = None
    try:
        from System.swarm_ide_boot_identity import resolve_boot_identity

        ident = resolve_boot_identity(ide_app_id)
        agent = ident.trigger_code
        registry_model_label = ident.model_label
        surface = ident.ide_surface or ide_app_id
    except Exception:
        agent = persona
        surface = ide_app_id

    claim = classify_model_claim(ide_app_id, selected_model if selected_model is not None else "Auto")
    declared_model = claim.declared_model
    router_visible = claim.router_visible
    grounding = claim.grounding_label
    banner = f"{agent}@{surface} / {declared_model} / Cursor IDE"
    stigauth_line = f"{agent}@{ide_app_id}: {declared_model} [{grounding}]"

    row = {
        "trace_id": str(uuid.uuid4()),
        "ts": ts,
        "source_ide": "Cursor",
        "ide_name": "Cursor",
        "kind": "STIGALL",
        "event": "AGENT_SIGN_IN",
        "context": context,
        "agent": agent,
        "doctor": agent,
        "model": declared_model,
        "selected_model": declared_model,
        "reasoning": reasoning,
        "mode": mode,
        "lane": lane,
        "action": "AGENT_SIGN_IN",
        "homeworld_serial": serial,
        "stigauth": _STIGAUTH_BRIDGE,
        "sig": _sig_material(agent, serial, ts, context),
        "payload": banner,
        "known_limits": claim.known_limits,
        "meta": {
            "identity_label": persona,
            "stigauth_line": stigauth_line,
            "bridge": "CURSOR_M5",
            "router_visible": router_visible,
            "model_confidence": claim.model_confidence,
            "registry_model_label": registry_model_label,
            "grounding_label": grounding,
            "raw_model_label": claim.raw_model_label,
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
    p.add_argument(
        "--selected-model",
        default=None,
        help=(
            "Exact model only when the Cursor endpoint is visible. Omit this "
            "under Auto so the row records AUTO_OPAQUE."
        ),
    )
    p.add_argument("--reasoning", default="auto", help="reasoning level reported by the UI")
    p.add_argument("--mode", default="read-only", help="Covenant mode for this sign-in")
    p.add_argument("--lane", default="Probe", help="Covenant lane for this sign-in")
    args = p.parse_args()
    row = sign_in(
        context=args.context,
        selected_model=args.selected_model,
        reasoning=args.reasoning,
        mode=args.mode,
        lane=args.lane,
        dry_run=args.dry_run,
    )
    if args.dry_run:
        print(json.dumps(row, indent=2, ensure_ascii=False))
    else:
        print(row["payload"])
        print(f"→ appended {_TRACE}  trace_id={row['trace_id']}  sig={row['sig']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
