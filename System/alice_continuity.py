#!/usr/bin/env python3
"""alice_continuity.py — the one shared record every Alice surface reads and writes.

Stigmergy: an append-only JSONL ledger is the medium. No surface owns it and no
surface rewrites it; each surface leaves a trace and reads the traces the others
left. The ledger is canonical storage (see System/memory_search.py): everything
else — the MCP tool, the recall view, the CLI — builds views over it.

Record kinds
    note     a durable fact, decision, or observation worth carrying forward
    command  work one surface hands to another (the ``/s ...`` channel)
    ack      a surface confirming it picked a command up

Usage
    python3 System/alice_continuity.py note  "text" [--tag t] [--surface s]
    python3 System/alice_continuity.py send  "text" [--surface s]      # a command
    python3 System/alice_continuity.py ack   <record-id> [--surface s]
    python3 System/alice_continuity.py inbox [--surface s]             # unacked commands
    python3 System/alice_continuity.py tail  [N]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Iterable

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover - damaged boot path
    append_line_locked = None  # type: ignore[assignment]

_REPO = Path(__file__).resolve().parents[1]
_STATE = _REPO / ".sifta_state"
LEDGER = _STATE / "alice_continuity.jsonl"

KINDS = ("note", "command", "ack")


def surface_name(explicit: str | None = None) -> str:
    """The writing surface: explicit > ``ALICE_SURFACE`` > ``dsh``."""
    if explicit:
        return explicit.strip()
    return (os.environ.get("ALICE_SURFACE") or "dsh").strip()


def _record_id(ts: float, surface: str, kind: str, text: str) -> str:
    digest = hashlib.sha256(f"{ts:.6f}|{surface}|{kind}|{text}".encode("utf-8")).hexdigest()
    return digest[:12]


def write(
    kind: str,
    text: str,
    *,
    surface: str | None = None,
    tags: Iterable[str] | None = None,
    ref: str | None = None,
    ledger: Path | None = None,
) -> dict[str, Any]:
    """Append one trace and return the record as written."""
    if kind not in KINDS:
        raise ValueError(f"unknown kind {kind!r}; expected one of {KINDS}")
    body = str(text).strip()
    if not body:
        raise ValueError("text must not be empty")
    path = Path(ledger) if ledger else LEDGER
    ts = time.time()
    name = surface_name(surface)
    record: dict[str, Any] = {
        "schema": "ALICE_CONTINUITY_V1",
        "id": _record_id(ts, name, kind, body),
        "ts": ts,
        "iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(ts)),
        "kind": kind,
        "surface": name,
        "text": body,
    }
    if tags:
        record["tags"] = [str(tag) for tag in tags if str(tag).strip()]
    if ref:
        record["ref"] = str(ref)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False) + "\n"
    if append_line_locked is not None:
        append_line_locked(path, line)
    else:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)
    return record


def read_all(*, ledger: Path | None = None, limit: int | None = None) -> list[dict[str, Any]]:
    """Every parseable trace, oldest first; unreadable lines are skipped."""
    path = Path(ledger) if ledger else LEDGER
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                records.append(value)
    if limit is not None and limit > 0:
        records = records[-limit:]
    return records


def pending_commands(*, ledger: Path | None = None, surface: str | None = None) -> list[dict[str, Any]]:
    """Commands with no later ``ack`` naming them."""
    records = read_all(ledger=ledger)
    acked = {str(r.get("ref")) for r in records if r.get("kind") == "ack" and r.get("ref")}
    pending = [r for r in records if r.get("kind") == "command" and str(r.get("id")) not in acked]
    if surface:
        return [r for r in pending if str(r.get("surface")) != surface.strip()]
    return pending


def ack(record_id: str, *, surface: str | None = None, ledger: Path | None = None) -> dict[str, Any]:
    """Confirm one command was picked up, by appending an ``ack`` trace."""
    return write("ack", f"picked up {record_id}", surface=surface, ref=record_id, ledger=ledger)


def render(records: list[dict[str, Any]]) -> str:
    """One compact line per trace, for a CLI or a tool result."""
    if not records:
        return "(empty)"
    lines = []
    for record in records:
        kind = str(record.get("kind") or "?")
        who = str(record.get("surface") or "?")
        when = str(record.get("iso") or "")
        ident = str(record.get("id") or "")
        text = " ".join(str(record.get("text") or "").split())
        lines.append(f"[{when}] {kind:<7} {who:<12} {ident}  {text}")
    return "\n".join(lines)


def prompt_block(
    *,
    max_traces: int = 4,
    max_chars: int = 160,
    ledger: Path | None = None,
) -> str:
    """A compact digest of the shared record, for injection into a model prompt.

    Readers with a small context window must keep this short — the Talk chorus
    runs at ``num_ctx=1024`` — so every trace is truncated and unacknowledged
    commands sort first: they are the ones that change what the reader does.
    Returns ``""`` when the record is empty, so a caller can skip the block.
    """
    commands = pending_commands(ledger=ledger)
    notes = [r for r in read_all(ledger=ledger) if r.get("kind") == "note"]
    budget = max(1, int(max_traces))
    selected = commands[:budget]
    if len(selected) < budget:
        selected += notes[-(budget - len(selected)):]
    if not selected:
        return ""
    limit = max(40, int(max_chars))
    lines = []
    for record in selected:
        text = " ".join(str(record.get("text") or "").split())
        if len(text) > limit:
            text = text[: limit - 1].rstrip() + "…"
        if record.get("kind") == "command":
            lines.append(f"- PENDING work handed over by {record.get('surface')}: {text}")
        else:
            lines.append(f"- [{record.get('iso')}] {record.get('surface')}: {text}")
    return (
        "SHARED CONTINUITY RECORD (one memory; every Alice surface reads and writes it):\n"
        + "\n".join(lines)
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Alice's shared continuity ledger.")
    parser.add_argument("--surface", default=None, help="writing surface name (default $ALICE_SURFACE or 'dsh')")
    sub = parser.add_subparsers(dest="verb", required=True)

    for verb in ("note", "send"):
        node = sub.add_parser(verb, help="append a note, or a command for another surface")
        node.add_argument("text")
        node.add_argument("--tag", action="append", default=[])

    ack_node = sub.add_parser("ack", help="confirm a command was picked up")
    ack_node.add_argument("record_id")

    sub.add_parser("inbox", help="list commands no surface has acknowledged")
    tail = sub.add_parser("tail", help="show the most recent traces")
    tail.add_argument("count", nargs="?", type=int, default=20)

    args = parser.parse_args(argv)
    if args.verb == "note":
        record = write("note", args.text, surface=args.surface, tags=args.tag)
        print(record["id"])
    elif args.verb == "send":
        record = write("command", args.text, surface=args.surface, tags=args.tag)
        print(record["id"])
    elif args.verb == "ack":
        record = ack(args.record_id, surface=args.surface)
        print(record["id"])
    elif args.verb == "inbox":
        print(render(pending_commands(surface=args.surface)))
    elif args.verb == "tail":
        print(render(read_all(limit=args.count)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
