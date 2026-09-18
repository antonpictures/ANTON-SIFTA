"""Small typed-link layer for deterministic boot and action provenance.

This is deliberately not a consciousness claim or a replacement for sensor
organs. It gives each derived action a root boot record, fresh OS clock reading,
cached location status and explicit ``pose=None`` until a real pose receipt
arrives.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Iterable, Optional

ROOT = Path(__file__).resolve().parents[1]


def _paths(state_dir: Path | str) -> tuple[Path, Path]:
    state = Path(state_dir)
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    return state / "stigmergic_boot_context.json", state / "stigmergic_memory_graph.jsonl"


def _append(path: Path, row: dict[str, Any]) -> None:
    from System.jsonl_file_lock import append_line_locked

    append_line_locked(path, json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def boot_context(*, state_dir: Path | str = ROOT / ".sifta_state", epoch: Optional[float] = None) -> dict[str, Any]:
    """Return one boot root for this process, creating it once per state dir."""
    marker, _ = _paths(state_dir)
    try:
        existing = json.loads(marker.read_text(encoding="utf-8"))
        if isinstance(existing, dict) and existing.get("record_id") and existing.get("pid") == os.getpid():
            return existing
    except (OSError, ValueError):
        pass
    from System.swarm_body_snapshot import body_snapshot
    from System.swarm_hardware_time_oracle import live_clock_snapshot

    clock = live_clock_snapshot(epoch=epoch)
    body = body_snapshot(state_dir=state_dir, epoch=clock["epoch"])
    stamp = float(clock["epoch"])
    record = {
        "schema_version": "sifta.memory.record.v1",
        "record_id": uuid.uuid4().hex,
        "record_type": "boot_context",
        "root": True,
        "boot_id": f"{os.getpid()}-{int(stamp * 1000)}",
        "pid": os.getpid(),
        "node_id": "GTH4921YP3",
        "captured_at": stamp,
        "clock": clock,
        "monotonic_origin": time.monotonic(),
        "sensor_capabilities": {
            "camera": "separate_receipt_required",
            "microphone": "separate_receipt_required",
            "pose": "UNAVAILABLE",
            "mac_location": body.get("location", {}).get("status", "UNAVAILABLE"),
        },
        "location": body.get("location", {}),
        "pose": None,
        "source_ids": [],
        "uncertainty": "host_context_only",
        "policy_version": "boot-context-v1",
    }
    marker.write_text(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    marker.chmod(0o600)
    _append(_paths(state_dir)[1], record)
    return record


def append_linked_record(
    record_type: str,
    *,
    state_dir: Path | str = ROOT / ".sifta_state",
    source_ids: Iterable[str] = (),
    payload: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Append a record whose evidence roots are explicit and inspectable."""
    root = boot_context(state_dir=state_dir)
    parents = [str(value) for value in source_ids if str(value)]
    if not parents:
        parents = [str(root["record_id"])]
    row = {
        "schema_version": "sifta.memory.record.v1",
        "record_id": uuid.uuid4().hex,
        "record_type": str(record_type),
        "root": False,
        "captured_at": time.time(),
        "source_ids": parents,
        "boot_record_id": root["record_id"],
        "uncertainty": "derived_from_declared_sources",
    }
    if payload:
        row["payload"] = dict(payload)
    _append(_paths(state_dir)[1], row)
    return row


def validate_graph(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Detect dangling links and cycles without pretending unresolved rows passed."""
    items = [row for row in rows if isinstance(row, dict) and row.get("record_id")]
    by_id = {str(row["record_id"]): row for row in items}
    dangling = []
    edges: dict[str, list[str]] = {}
    for row in items:
        current = str(row["record_id"])
        parents = [str(value) for value in row.get("source_ids", [])]
        edges[current] = parents
        dangling.extend({parent for parent in parents if parent not in by_id})
    cycles: list[list[str]] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def walk(node: str, chain: list[str]) -> None:
        if node in visiting:
            cycles.append(chain[chain.index(node):] + [node])
            return
        if node in visited:
            return
        visiting.add(node)
        for parent in edges.get(node, []):
            walk(parent, chain + [parent])
        visiting.remove(node)
        visited.add(node)

    for node in edges:
        walk(node, [node])
    return {
        "ok": not dangling and not cycles,
        "record_count": len(items),
        "dangling_source_ids": sorted(set(dangling)),
        "cycles": cycles,
        "truth_label": "SIFTA_MEMORY_GRAPH_VALIDATION_V1",
    }


__all__ = ["append_linked_record", "boot_context", "validate_graph"]
