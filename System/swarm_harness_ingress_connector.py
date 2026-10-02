#!/usr/bin/env python3
"""Harness Ingress Connector — the body seam between SIFTA and dsh web.

Alice's spinal cord formulates a body task; this organ forwards it into the
deepseek-harness web ingress ledger so the harness session (any model on the
Ollama/DeepSeek routes) can take the work, and returns the harness reply to
the same conversation ledger Talk and the We Code Together mirror already
render. Stdlib-only, append-only, zero-authority: the connector never edits
Alice's organs or the harness settings, it only leaves pheromones.

Surfaces (One Alice rule): web harness (:3080 UI), We Code Together mirror,
Talk — all read the same ledgers, so this connector is a trace, not a second
Alice.

Truth label: SIFTA_HARNESS_INGRESS_V1.
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
STATE = REPO / ".sifta_state"
REPO2 = Path("/Users/ioanganton/Music/ANTON_SIFTA")

INGRESS = STATE / "web_global_chat_ingress.jsonl"
REPLIES = STATE / "web_global_chat_replies.jsonl"
HARNESS_SYNC_LEDGER = STATE / "ollama_harness_sync.jsonl"
CONNECTOR_LEDGER = STATE / "harness_ingress_receipts.jsonl"
HARNESS_SETTINGS = Path.home() / ".dsh" / "settings.yaml"


def forward_task(prompt: str, *, source: str = "spinal_cord", signal_id: str | None = None,
                 target_files: list[str] | None = None) -> dict[str, Any]:
    """Queue one coding task into the harness's web global chat ingress."""
    row = {
        "schema": "SIFTA_HARNESS_INGRESS_V1",
        "ts": time.time(),
        "message_id": str(uuid.uuid4()),
        "source": source,
        "signal_id": signal_id,
        "target_files": target_files or [],
        "prompt": prompt,
        "route_note": "harness web :3080 — pick model in the unified picker",
    }
    with INGRESS.open("a") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def drain_replies(limit: int = 20) -> list[dict[str, Any]]:
    """Read recent harness replies (the mirror renders them as teacher arms)."""
    if not REPLIES.exists():
        return []
    rows = []
    for line in REPLIES.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def harness_health() -> dict[str, Any]:
    """Cheap stigmergic read: is the harness web up, what's its default model."""
    info: dict[str, Any] = {"web_200": False, "default_model": None}
    try:
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:3080/", timeout=2) as handle:
            info["web_200"] = handle.status == 200
    except Exception:
        pass
    try:
        import yaml  # PyYAML is present in SIFTA runtime
        doc = yaml.safe_load(HARNESS_SETTINGS.read_text())
        info["default_model"] = (doc.get("agent-default-model") or {}).get("model")
    except Exception:
        pass
    return info


def reconcile_model_lists() -> dict[str, Any]:
    """Body-need signal: if the harness rewrote settings from stale memory,
    the sync organ self-heals; record one receipt either way."""
    import sys
    sys.path.insert(0, str(REPO2))
    from System.swarm_ollama_harness_sync import sync_local_ollama_harness
    report = sync_local_ollama_harness()
    receipt = {"ts": time.time(), "action": "harness_ingress_sync", "sync": report}
    try:
        with CONNECTOR_LEDGER.open("a") as f:
            f.write(json.dumps(receipt, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return report


__all__ = ["forward_task", "drain_replies", "harness_health", "reconcile_model_lists"]
