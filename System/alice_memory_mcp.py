#!/usr/bin/env python3
"""alice_memory_mcp.py — MCP stdio server over Alice's shared continuity ledger.

One server, one store. The DeepSeek Harness mounts this per preset
(``@deepseek-ai/dsh-mcp-client``), so every Alice surface — the SIFTA Talk
window, this harness, a terminal — reads and writes the SAME traces. Storage
stays in ``System/alice_continuity.py``; this file only projects it onto MCP.

The two queue tools delegate to the EXISTING owner coding queue
(``System/swarm_stigmergicode_command``), which is what ``/s`` and
``/stigmergicode`` write in the Talk window. They are a reader and a reporter,
not a second queue: the queue stays authoritative for work state, the ledger
stays authoritative for memory.

Tools
    remember   append a durable note to the shared ledger
    recall     read recent traces, optionally filtered
    inbox      commands other surfaces left unacknowledged
    ack        confirm a command was picked up
    claim      claim the next pending ``/s`` task from the owner queue
    report     close a claimed task with a status and a note
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from System import alice_continuity as continuity  # noqa: E402

SERVER_NAME = "alice-continuity"
SERVER_VERSION = "1.1.0"
DEFAULT_PROTOCOL = "2025-06-18"
STATE = _ROOT / ".sifta_state"

TOOLS: list[dict[str, Any]] = [
    {
        "name": "remember",
        "description": (
            "Append one durable trace to Alice's shared continuity ledger. Every surface "
            "reads the same record, so a note left here is known in every window."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The fact, decision, or observation to carry forward."},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "Optional labels."},
            },
            "required": ["text"],
        },
    },
    {
        "name": "recall",
        "description": (
            "Read recent traces from the shared ledger, newest last. Pass query to keep only "
            "traces whose text contains that substring."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Optional case-insensitive substring filter."},
                "limit": {"type": "integer", "description": "How many traces to return (default 20)."},
            },
        },
    },
    {
        "name": "inbox",
        "description": (
            "Commands other Alice surfaces left for this one and nobody has acknowledged yet. "
            "This is how a '/s ...' typed in another window reaches this session."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "surface": {"type": "string", "description": "Filter out commands written by this surface."},
            },
        },
    },
    {
        "name": "ack",
        "description": "Confirm one command was picked up, by appending an ack trace.",
        "inputSchema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "The command's record id."}},
            "required": ["id"],
        },
    },
    {
        "name": "claim",
        "description": (
            "Claim the next pending '/s' task from the owner coding queue — the same queue the "
            "Talk window writes. Returns the task text and its id, or nothing pending."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "report",
        "description": "Close a claimed task with a status and a note, and record the outcome in the shared ledger.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "The task id from claim."},
                "status": {"type": "string", "description": "Terminal status, e.g. DONE, FAILED, BLOCKED (default DONE)."},
                "note": {"type": "string", "description": "What was actually done, with the evidence."},
            },
            "required": ["task_id"],
        },
    },
]


def _text(value: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": value}], "isError": False}


def _error(value: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": value}], "isError": True}


def _queue():
    """The existing owner coding queue, imported lazily so a broken boot path stays loud."""
    from System import swarm_stigmergicode_command as command_bus

    return command_bus


def call_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Run one tool call."""
    try:
        if name == "remember":
            record = continuity.write("note", str(args.get("text") or ""), tags=args.get("tags") or [])
            return _text(f"remembered {record['id']}")
        if name == "recall":
            limit = args.get("limit")
            limit = int(limit) if isinstance(limit, int) and limit > 0 else 20
            records = continuity.read_all(limit=limit)
            query = str(args.get("query") or "").strip().lower()
            if query:
                records = [r for r in records if query in str(r.get("text") or "").lower()]
            return _text(continuity.render(records))
        if name == "inbox":
            pending = continuity.pending_commands(surface=args.get("surface") or None)
            return _text(continuity.render(pending))
        if name == "ack":
            record = continuity.ack(str(args.get("id") or ""))
            return _text(f"acked {record['ref']}")
        if name == "claim":
            bus = _queue()
            row = bus.claim_next_task(state_dir=STATE)
            if not row:
                # A consumer that failed the task for its OWN readiness must not
                # be able to hide it from the surface it was addressed to.
                reopened = bus.reopen_spurious_failures(state_dir=STATE)
                if reopened:
                    continuity.write(
                        "note",
                        "reopened task(s) failed for a consumer-readiness reason, not about the work: "
                        + ", ".join(str(r.get("task_id"))[:12] for r in reopened),
                        tags=["queue", "reopen"],
                    )
                    row = bus.claim_next_task(state_dir=STATE)
            if not row:
                return _text("nothing pending")
            return _text(
                f"task {str(row.get('task_id') or '')}\n"
                f"requested by: {str(row.get('source') or '')}\n"
                f"{str(row.get('task') or '(no task text)')}"
            )
        if name == "report":
            task_id = str(args.get("task_id") or "")
            status = str(args.get("status") or "DONE").upper()
            row = _queue().complete_task(task_id, status=status, state_dir=STATE)
            note = str(args.get("note") or "").strip()
            trace = ""
            if note:
                record = continuity.write(
                    "note",
                    f"{status} task {task_id[:12]}: {note}",
                    tags=["task", status.lower()],
                    ref=task_id,
                )
                trace = f", trace {record['id']}"
            return _text(f"task {task_id[:12]} -> {row.get('status')}{trace}")
        return _error(f"unknown tool: {name}")
    except Exception as error:  # the protocol wants a tool error, not a crash
        return _error(f"{type(error).__name__}: {error}")


def handle(message: dict[str, Any]) -> dict[str, Any] | None:
    """One JSON-RPC message in, one response out (None for notifications)."""
    method = message.get("method")
    ident = message.get("id")
    params = message.get("params") or {}

    if method == "initialize":
        requested = params.get("protocolVersion")
        return {
            "jsonrpc": "2.0",
            "id": ident,
            "result": {
                "protocolVersion": requested or DEFAULT_PROTOCOL,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        }
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": ident, "result": {"tools": TOOLS}}
    if method == "tools/call":
        result = call_tool(str(params.get("name") or ""), params.get("arguments") or {})
        return {"jsonrpc": "2.0", "id": ident, "result": result}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": ident, "result": {}}
    if method in ("notifications/initialized", "notifications/cancelled"):
        return None
    return {
        "jsonrpc": "2.0",
        "id": ident,
        "error": {"code": -32601, "message": f"method not found: {method}"},
    }


def main() -> int:
    """Serve newline-delimited JSON-RPC on stdin/stdout until stdin closes."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(message, dict):
            continue
        response = handle(message)
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
