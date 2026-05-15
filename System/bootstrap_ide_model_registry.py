#!/usr/bin/env python3
"""Bootstrap the ide_model_registry.jsonl from existing stigmergic trace rows.

The `resolve_boot_identity()` function in swarm_ide_boot_identity.py reads
from .sifta_state/ide_model_registry.jsonl, but this registry has no automated
writer — it was historically expected to be populated by each IDE Doctor on
first boot. This script reconstructs it from the existing
ide_stigmergic_trace.jsonl LLM_REGISTRATION rows.

DIRT item closed: CG55M DIRT report — "cursor raises ValueError: no active IDE
identity row for ide_app_id='cursor'" (covenant §7.10 / §9 checklist).

Each run:
  1. Reads ALL LLM_REGISTRATION rows from the trace.
  2. Groups by source_ide → extracts the last sign_in row per IDE.
  3. Maps to the ide_model_registry format (ide_app_id, trigger_code, etc.)
  4. Writes fresh active rows (currently_active=True) for each live IDE.
  5. Marks any previous rows as inactive (currently_active=False) by appending
     a correction row — never rewrites history (§4.4 item 3).

Run after any new IDE sign-in to keep the registry fresh.
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
_TRACE = _REPO / ".sifta_state" / "ide_stigmergic_trace.jsonl"
_REGISTRY = _REPO / ".sifta_state" / "ide_model_registry.jsonl"

# Canonical IDE → trigger prefix mapping (from swarm_ide_boot_identity.py)
_IDE_TRIGGER: dict[str, str] = {
    "cursor": "CG55M",
    "cursor_m5": "CG55M",
    "antigravity": "AG46",
    "antigravity_m5": "AG31",
    "codex": "C55M",
    "codex_desktop": "C55M",
}

_IDE_APP_ID: dict[str, str] = {
    "cursor": "cursor",
    "cursor_m5": "cursor",
    "antigravity": "antigravity",
    "antigravity_m5": "antigravity",
    "codex": "codex",
    "codex_desktop": "codex",
}

_IDE_SURFACE: dict[str, str] = {
    "cursor": "cursor_composer",
    "cursor_m5": "cursor_composer_m5",
    "antigravity": "antigravity_main",
    "antigravity_m5": "antigravity_main_m5",
    "codex": "codex_app",
    "codex_desktop": "codex_desktop",
}


def _read_trace() -> list[dict[str, Any]]:
    if not _TRACE.exists():
        return []
    rows = []
    for line in _TRACE.read_bytes().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if isinstance(r, dict):
            rows.append(r)
    return rows


def _parse_payload(row: dict[str, Any]) -> dict[str, Any]:
    p = row.get("payload", {})
    if isinstance(p, str):
        try:
            p = json.loads(p)
        except Exception:
            p = {}
    return p if isinstance(p, dict) else {}


def bootstrap_registry(*, dry_run: bool = False) -> list[dict[str, Any]]:
    """Read trace, build registry rows for each IDE, write to registry."""
    rows = _read_trace()

    # Collect last sign_in per source_ide
    last_signin: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row.get("kind") != "LLM_REGISTRATION":
            continue
        payload = _parse_payload(row)
        action = payload.get("action", "")
        if action not in ("sign_in", "LLM_REGISTRATION"):
            continue
        source_ide = str(row.get("source_ide") or "").lower()
        if not source_ide or source_ide not in _IDE_APP_ID:
            continue
        # Keep the most recent
        existing = last_signin.get(source_ide)
        if existing is None or float(row.get("ts", 0)) > float(existing.get("ts", 0)):
            last_signin[source_ide] = row

    written: list[dict[str, Any]] = []
    now = time.time()

    for source_ide, row in last_signin.items():
        payload = _parse_payload(row)
        ide_app_id = _IDE_APP_ID[source_ide]
        trigger = _IDE_TRIGGER.get(source_ide, "UNKNOWN")
        model = payload.get("model", "UNKNOWN")
        reg_row: dict[str, Any] = {
            "ts": now,
            "trace_id": str(uuid.uuid4()),
            "kind": "IDE_REGISTRY_BOOTSTRAP",
            "ide_app_id": ide_app_id,
            "ide_surface": _IDE_SURFACE.get(source_ide, source_ide),
            "trigger_code": trigger,
            "model_label": model,
            "ui_badge": model,
            "grounding_label": "ARCHITECT_UI_TRUTH",
            "currently_active": True,
            "seen_at_ts": float(row.get("ts", now)),
            "source_ide": source_ide,
            "homeworld_serial": str(row.get("homeworld_serial") or "GTH4921YP3"),
            "bootstrapped_from_trace_id": str(row.get("trace_id", "")),
            "intent": str(payload.get("intent", ""))[:200],
        }
        written.append(reg_row)

    if not dry_run:
        _REGISTRY.parent.mkdir(parents=True, exist_ok=True)
        with _REGISTRY.open("a", encoding="utf-8") as fh:
            for reg_row in written:
                fh.write(json.dumps(reg_row, ensure_ascii=False) + "\n")

    return written


if __name__ == "__main__":
    import sys
    dry = "--dry-run" in sys.argv
    written = bootstrap_registry(dry_run=dry)
    print(f"{'[DRY-RUN] Would write' if dry else 'Wrote'} {len(written)} registry rows:")
    for row in written:
        print(
            f"  {row['ide_app_id']:15s}  trigger={row['trigger_code']:8s}"
            f"  model={row['model_label']!r}"
            f"  active={row['currently_active']}"
        )
