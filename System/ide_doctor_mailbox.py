#!/usr/bin/env python3
"""
ide_doctor_mailbox.py — direct Doctor-to-Doctor messages on the SIFTA bus.

This is not a cloud API bridge. It is SIFTA-native stigmergy:
Codex, GrokCLI, Cursor, Antigravity, Alice, or another Doctor can address
one another by writing structured rows to `.sifta_state/ide_stigmergic_trace.jsonl`.
Any peer watching the bus can reply by referencing the parent trace id.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System import ide_stigmergic_bridge as bridge  # noqa: E402
from System.swarm_kernel_identity import owner_silicon  # noqa: E402

KIND_MESSAGE = "doctor_direct_message"
KIND_REPLY = "doctor_direct_reply"
KIND_ACK = "doctor_direct_ack"
MAILBOX_KINDS = {KIND_MESSAGE, KIND_REPLY, KIND_ACK}

ALIASES: dict[str, str] = {
    "codex": "codex",
    "c55m": "codex",
    "dr_codex": "codex",
    "grok": "grokcli",
    "grokcli": "grokcli",
    "grok_cli": "grokcli",
    "xai": "grokcli",
    "cursor": "cursor_m5",
    "cursor_m5": "cursor_m5",
    "cg55m": "cursor_m5",
    "claude": "cursor_m5",
    "antigravity": "antigravity_m5",
    "antigravity_m5": "antigravity_m5",
    "ag31": "antigravity_m5",
    "alice": "alice_talk_widget",
    "alice_talk": "alice_talk_widget",
}


def canon(label: str) -> str:
    """Normalize known Doctor names without rebranding unknown peers."""
    raw = str(label or "").strip()
    if not raw:
        return "unknown"
    key = raw.casefold().replace("-", "_").replace(" ", "_")
    return ALIASES.get(key, raw)


def _payload_block(
    *,
    kind_label: str,
    from_doctor: str,
    to_doctor: str,
    subject: str,
    body: str,
    parent_trace_id: str = "",
) -> str:
    lines = [
        f"[{kind_label}]",
        f"from: {from_doctor}",
        f"to: {to_doctor}",
        f"subject: {subject.strip()}",
    ]
    if parent_trace_id:
        lines.append(f"parent: {parent_trace_id}")
    lines.extend(["body:", body.strip()])
    return "\n".join(lines)


def send_message(
    *,
    from_doctor: str,
    to_doctor: str,
    subject: str,
    body: str,
    parent_trace_id: str = "",
    requires_reply: bool = True,
    homeworld_serial: Optional[str] = None,
) -> Dict[str, Any]:
    """Send one direct message to another Doctor through ide_stigmergic_trace."""
    src = canon(from_doctor)
    dst = canon(to_doctor)
    subject = str(subject or "").strip()
    body = str(body or "").strip()
    if not subject:
        raise ValueError("subject is required")
    if not body:
        raise ValueError("body is required")
    kind = KIND_REPLY if parent_trace_id else KIND_MESSAGE
    row = bridge.deposit(
        src,
        _payload_block(
            kind_label="DOCTOR DIRECT REPLY" if parent_trace_id else "DOCTOR DIRECT MESSAGE",
            from_doctor=src,
            to_doctor=dst,
            subject=subject,
            body=body,
            parent_trace_id=parent_trace_id,
        ),
        kind=kind,
        meta={
            "from_doctor": src,
            "to_doctor": dst,
            "subject": subject,
            "parent_trace_id": parent_trace_id or None,
            "requires_reply": bool(requires_reply),
            "protocol": "SIFTA_DOCTOR_MAILBOX_V1",
        },
        homeworld_serial=homeworld_serial or owner_silicon(),
    )
    return row


def ack(
    *,
    from_doctor: str,
    parent_trace_id: str,
    note: str = "",
    homeworld_serial: Optional[str] = None,
) -> Dict[str, Any]:
    src = canon(from_doctor)
    note = str(note or "").strip() or "ack"
    row = bridge.deposit(
        src,
        f"[DOCTOR DIRECT ACK]\nfrom: {src}\nparent: {parent_trace_id}\nnote: {note}",
        kind=KIND_ACK,
        meta={
            "from_doctor": src,
            "parent_trace_id": str(parent_trace_id or ""),
            "note": note,
            "protocol": "SIFTA_DOCTOR_MAILBOX_V1",
        },
        homeworld_serial=homeworld_serial or owner_silicon(),
    )
    return row


def _mailbox_rows(window: int = 1000) -> List[Dict[str, Any]]:
    return [r for r in bridge.forage(limit=window) if r.get("kind") in MAILBOX_KINDS]


def inbox(for_doctor: str, *, window: int = 1000) -> List[Dict[str, Any]]:
    """Return recent direct rows addressed to a Doctor."""
    target = canon(for_doctor)
    out: List[Dict[str, Any]] = []
    for row in _mailbox_rows(window=window):
        meta = row.get("meta") or {}
        if canon(str(meta.get("to_doctor") or "")) == target:
            out.append(row)
    return out


def outbox(from_doctor: str, *, window: int = 1000) -> List[Dict[str, Any]]:
    """Return recent direct rows sent by a Doctor."""
    source = canon(from_doctor)
    out: List[Dict[str, Any]] = []
    for row in _mailbox_rows(window=window):
        meta = row.get("meta") or {}
        if canon(str(meta.get("from_doctor") or row.get("source_ide") or "")) == source:
            out.append(row)
    return out


def thread(parent_trace_id: str, *, window: int = 1000) -> List[Dict[str, Any]]:
    """Reconstruct one direct-message thread."""
    parent = str(parent_trace_id or "").strip()
    if not parent:
        return []
    out: List[Dict[str, Any]] = []
    for row in _mailbox_rows(window=window):
        meta = row.get("meta") or {}
        if row.get("trace_id") == parent or meta.get("parent_trace_id") == parent:
            out.append(row)
    return out


def open_requests(for_doctor: str, *, window: int = 1000) -> List[Dict[str, Any]]:
    """Messages addressed to a Doctor that request a reply and have no reply yet."""
    target = canon(for_doctor)
    rows = _mailbox_rows(window=window)
    replied_parents = {
        str((r.get("meta") or {}).get("parent_trace_id") or "")
        for r in rows
        if r.get("kind") in {KIND_REPLY, KIND_ACK}
        and canon(str((r.get("meta") or {}).get("from_doctor") or r.get("source_ide") or "")) == target
    }
    return [
        r
        for r in rows
        if r.get("kind") == KIND_MESSAGE
        and canon(str((r.get("meta") or {}).get("to_doctor") or "")) == target
        and bool((r.get("meta") or {}).get("requires_reply"))
        and str(r.get("trace_id") or "") not in replied_parents
    ]


def summary_for_alice(*, window: int = 1000) -> str:
    """Compact context line for the Talk prompt or a human status check."""
    rows = _mailbox_rows(window=window)
    if not rows:
        return ""
    recent = rows[-5:]
    open_by_target: dict[str, int] = {}
    for row in rows:
        meta = row.get("meta") or {}
        target = canon(str(meta.get("to_doctor") or ""))
        if target:
            open_by_target[target] = len(open_requests(target, window=window))
    lines = ["DOCTOR MAILBOX:"]
    if open_by_target:
        pending = ", ".join(f"{k}:{v}" for k, v in sorted(open_by_target.items()) if v)
        lines.append(f"  open requests: {pending or 'none'}")
    now = time.time()
    for row in recent:
        meta = row.get("meta") or {}
        age_s = max(0.0, now - float(row.get("ts") or now))
        age = f"{int(age_s)}s" if age_s < 60 else f"{int(age_s / 60)}m"
        lines.append(
            "  "
            f"{age} ago {canon(str(meta.get('from_doctor') or row.get('source_ide') or 'unknown'))}"
            f" -> {canon(str(meta.get('to_doctor') or '?'))}: "
            f"{str(meta.get('subject') or row.get('kind') or '')[:80]}"
        )
    return "\n".join(lines)


def _print_rows(rows: Iterable[Dict[str, Any]]) -> None:
    for row in rows:
        print(json.dumps(row, ensure_ascii=False, sort_keys=True))


def _split_dashdash(args: List[str]) -> tuple[List[str], str]:
    if "--" not in args:
        return args, ""
    idx = args.index("--")
    return args[:idx], " ".join(args[idx + 1 :])


def _cli(argv: List[str]) -> int:
    if not argv or argv[0] in {"-h", "--help", "help"}:
        print("Usage:")
        print("  ide_doctor_mailbox.py send <from> <to> <subject> -- <body>")
        print("  ide_doctor_mailbox.py reply <from> <to> <parent_trace_id> <subject> -- <body>")
        print("  ide_doctor_mailbox.py ack <from> <parent_trace_id> -- <note>")
        print("  ide_doctor_mailbox.py inbox <doctor>")
        print("  ide_doctor_mailbox.py outbox <doctor>")
        print("  ide_doctor_mailbox.py open <doctor>")
        print("  ide_doctor_mailbox.py thread <parent_trace_id>")
        print("  ide_doctor_mailbox.py summary")
        return 0
    cmd, args = argv[0], argv[1:]
    try:
        if cmd == "send":
            head, body = _split_dashdash(args)
            row = send_message(
                from_doctor=head[0],
                to_doctor=head[1],
                subject=head[2],
                body=body,
            )
            print(json.dumps(row, ensure_ascii=False, indent=2))
            return 0
        if cmd == "reply":
            head, body = _split_dashdash(args)
            row = send_message(
                from_doctor=head[0],
                to_doctor=head[1],
                parent_trace_id=head[2],
                subject=head[3],
                body=body,
                requires_reply=False,
            )
            print(json.dumps(row, ensure_ascii=False, indent=2))
            return 0
        if cmd == "ack":
            head, note = _split_dashdash(args)
            row = ack(from_doctor=head[0], parent_trace_id=head[1], note=note)
            print(json.dumps(row, ensure_ascii=False, indent=2))
            return 0
        if cmd == "inbox":
            _print_rows(inbox(args[0]))
            return 0
        if cmd == "outbox":
            _print_rows(outbox(args[0]))
            return 0
        if cmd == "open":
            _print_rows(open_requests(args[0]))
            return 0
        if cmd == "thread":
            _print_rows(thread(args[0]))
            return 0
        if cmd == "summary":
            print(summary_for_alice() or "(doctor mailbox empty)")
            return 0
    except (IndexError, ValueError) as exc:
        print(f"[ide_doctor_mailbox] error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(f"[ide_doctor_mailbox] unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv[1:]))
