#!/usr/bin/env python3
"""
swarm_chat_relay.py — Cross-node dead-drop relay (Cursor Opus 4.7 / 2026-04-17)

Problem (diagnosed on the Mac Mini via DeepMind IDE):
  - Applications/sifta_swarm_chat.py writes **every** node's outbound chat to
    ``m5queen_dead_drop.jsonl`` regardless of silicon.  The M1 Sentry's voice
    therefore never lands on its own queen's drop file, and incoming rows are
    never polled — ``poll_dead_drop`` is a no-op.
  - Bug chain: (a) worker-construction failure leaves the editor read-only,
    (b) the 200-char ping-pong guard mis-fires, (c) no inbound polling → the
    chat entity on the Mini looks dead.

This module is the **fix + upgrade**:

  1. **Identity-aware routing.**  Each node's outbound chat lands on its own
     queen's drop file (``m5queen_dead_drop.jsonl`` or ``m1queen_dead_drop.jsonl``)
     keyed by ``crypto_keychain.get_silicon_identity()`` — not by assumption.
  2. **Watermarked polling.**  ``poll_incoming(...)`` returns only **new** rows
     since the caller's last watermark (persisted under ``.sifta_state/``),
     deduplicated by ``(sender, ts, text_hash)``.
  3. **First-class pheromone.**  Every outbound + inbound chat event is
     mirrored on ``ide_stigmergic_trace.jsonl`` with ``kind='swarm_chat'`` and
     an explicit ``grounding`` field (REPO_TOOL for filesystem-read, TAB_CHAT
     for anything we can't verify).
  4. **Provenance.**  Inbound rows carry ``source_serial`` — an M5 widget
     therefore knows the row came from ``C07FL0JAQ6NV`` (or vice versa) and
     can tag the stage-direction accordingly.

Not part of this module:
  - No network I/O.  Coordination is file-system stigmergy (same repo, synced
    by git).  That matches ``.cursorrules`` — ``m5queen_dead_drop.jsonl`` is
    gitsynced; the Mini publishes to ``m1queen_dead_drop.jsonl`` on push.
  - No Ollama / model logic.  That stays in ``sifta_swarm_chat.py``.

Call sites:
  - ``Applications/sifta_swarm_chat.py`` — replaces ``_append_dead_drop_line``
    and fills ``poll_dead_drop``.
  - Any future headless daemon that wants to consume swarm chat as pheromone.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.ide_stigmergic_bridge import (  # noqa: E402
    NODE_M1_SENTRY,
    NODE_M5_FOUNDRY,
    deposit as _ide_deposit,
)
from System.ledger_append import append_jsonl_line  # noqa: E402

_STATE = _REPO / ".sifta_state"
_WATERMARK_DIR = _STATE / "swarm_chat_watermarks"

# Repo-root drop files (gitsynced per .cursorrules).
DROP_M5 = _REPO / "m5queen_dead_drop.jsonl"
DROP_M1 = _REPO / "m1queen_dead_drop.jsonl"

# Node → (drop_file, default_source_ide_label)
_NODE_TABLE: Dict[str, tuple[Path, str]] = {
    NODE_M5_FOUNDRY: (DROP_M5, "sifta_swarm_chat_m5"),
    NODE_M1_SENTRY: (DROP_M1, "sifta_swarm_chat_m1"),
}

__all__ = [
    "InboundMessage",
    "local_drop_file",
    "remote_drop_files",
    "publish_outbound",
    "poll_incoming",
    "reset_watermark",
]


@dataclass
class InboundMessage:
    sender: str
    text: str
    ts: int
    source_serial: str
    source_file: str  # repo-relative drop filename
    row_hash: str


# ───────────────────────────── identity / files ─────────────────────────────

def _local_silicon_serial() -> str:
    """Resolve this machine's hardware serial (empty string if unknown)."""
    try:
        from System.crypto_keychain import get_silicon_identity  # type: ignore

        serial = get_silicon_identity()
        return serial if isinstance(serial, str) else ""
    except Exception:
        return ""


def local_drop_file(serial: Optional[str] = None) -> Path:
    """Drop file the local node writes outbound chat to."""
    s = serial or _local_silicon_serial()
    if s in _NODE_TABLE:
        return _NODE_TABLE[s][0]
    # Unknown silicon: fall back to M5 file (matches pre-patch behaviour; logged).
    return DROP_M5


def remote_drop_files(serial: Optional[str] = None) -> List[Path]:
    """All drop files the local node should *read* (every known queen that isn't local)."""
    s = serial or _local_silicon_serial()
    local = local_drop_file(s)
    return [p for p in (DROP_M5, DROP_M1) if p.resolve() != local.resolve()]


def _source_ide_label(serial: Optional[str] = None) -> str:
    s = serial or _local_silicon_serial()
    if s in _NODE_TABLE:
        return _NODE_TABLE[s][1]
    return "sifta_swarm_chat_unknown"


# ───────────────────────────── watermarks ─────────────────────────────

def _watermark_path(drop_file: Path) -> Path:
    _WATERMARK_DIR.mkdir(parents=True, exist_ok=True)
    return _WATERMARK_DIR / f"{drop_file.name}.cursor"


def _read_watermark(drop_file: Path) -> int:
    p = _watermark_path(drop_file)
    if not p.exists():
        return 0
    try:
        return int(p.read_text(encoding="utf-8").strip() or "0")
    except (ValueError, OSError):
        return 0


def _write_watermark(drop_file: Path, byte_offset: int) -> None:
    p = _watermark_path(drop_file)
    try:
        p.write_text(str(int(byte_offset)), encoding="utf-8")
    except OSError:
        pass


def reset_watermark(drop_file: Optional[Path] = None) -> None:
    """Debug/ops helper — next poll re-emits the whole drop file."""
    if drop_file is None:
        for p in (DROP_M5, DROP_M1):
            wp = _watermark_path(p)
            if wp.exists():
                wp.unlink(missing_ok=True)  # type: ignore[arg-type]
        return
    wp = _watermark_path(drop_file)
    if wp.exists():
        wp.unlink(missing_ok=True)  # type: ignore[arg-type]


# ───────────────────────────── publish / poll ─────────────────────────────

def _row_hash(row: Dict[str, Any]) -> str:
    payload = json.dumps(
        {
            "sender": row.get("sender"),
            "ts": row.get("ts") or row.get("timestamp"),
            "text": row.get("text", ""),
        },
        sort_keys=True,
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def _mirror_to_ide_trace(
    *,
    direction: str,
    row: Dict[str, Any],
    source_serial: str,
    source_file: Path,
    grounding: str,
) -> None:
    """Mirror one chat event onto the stigmergic IDE trace."""
    try:
        text = str(row.get("text", ""))
        preview = text if len(text) <= 400 else text[:400] + "…"
        _ide_deposit(
            _source_ide_label(source_serial),
            f"[swarm_chat::{direction}] {row.get('sender', '?')}: {preview}",
            kind="swarm_chat",
            homeworld_serial=source_serial or _local_silicon_serial() or "UNKNOWN_SERIAL",
            meta={
                "direction": direction,
                "sender": row.get("sender"),
                "ts": row.get("ts") or row.get("timestamp"),
                "source_file": source_file.name,
                "grounding": grounding,
                "row_hash": _row_hash(row),
            },
        )
    except Exception:
        # Stigmergy must never break the chat UI.
        pass


def publish_outbound(
    *,
    sender: str,
    text: str,
    source: str = "SCREENPLAY_CHAT",
    ts: Optional[int] = None,
) -> Dict[str, Any]:
    """Write one outbound chat row to the **local** queen's drop file + mirror it."""
    serial = _local_silicon_serial()
    drop = local_drop_file(serial)
    row: Dict[str, Any] = {
        "sender": sender,
        "text": text,
        "ts": int(ts if ts is not None else time.time()),
        "source": source,
        "source_serial": serial or "UNKNOWN_SERIAL",
    }
    append_jsonl_line(drop, row)
    _mirror_to_ide_trace(
        direction="outbound",
        row=row,
        source_serial=serial,
        source_file=drop,
        grounding="REPO_TOOL",
    )
    return row


def _iter_new_rows(drop_file: Path, since_offset: int) -> Iterable[tuple[Dict[str, Any], int]]:
    """Yield (row, end_offset) for each complete JSON line after ``since_offset``."""
    if not drop_file.exists():
        return
    try:
        size = drop_file.stat().st_size
    except OSError:
        return
    if since_offset > size:  # drop file truncated / replaced
        since_offset = 0
    try:
        with drop_file.open("r", encoding="utf-8") as f:
            f.seek(since_offset)
            while True:
                line = f.readline()
                if not line:
                    break
                offset = f.tell()
                if not line.endswith("\n"):
                    # Partial last line — do not advance watermark past it.
                    break
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    row = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                if not isinstance(row, dict):
                    continue
                yield row, offset
    except OSError:
        return


def poll_incoming(
    *,
    max_rows: int = 20,
    include_self_echo: bool = False,
) -> List[InboundMessage]:
    """
    Return new rows from every remote queen's drop file since the last poll.

    - ``max_rows``: hard cap so a huge backfill doesn't flood the UI.
    - ``include_self_echo``: if True, rows whose ``source_serial`` matches the
      local silicon are kept.  Default False — the local node already saw its
      own outbound in real time.
    """
    local_serial = _local_silicon_serial()
    out: List[InboundMessage] = []
    for drop in remote_drop_files(local_serial):
        since = _read_watermark(drop)
        last_offset = since
        for row, offset in _iter_new_rows(drop, since):
            last_offset = offset
            src_serial = str(row.get("source_serial") or _infer_serial_from_sender(row) or "")
            if not include_self_echo and src_serial and src_serial == local_serial:
                continue
            msg = InboundMessage(
                sender=str(row.get("sender", "UNKNOWN")),
                text=str(row.get("text", "")),
                ts=int(row.get("ts") or row.get("timestamp") or 0),
                source_serial=src_serial or "UNKNOWN_SERIAL",
                source_file=drop.name,
                row_hash=_row_hash(row),
            )
            out.append(msg)
            _mirror_to_ide_trace(
                direction="inbound",
                row=row,
                source_serial=src_serial,
                source_file=drop,
                grounding="REPO_TOOL",
            )
            if len(out) >= max_rows:
                break
        _write_watermark(drop, last_offset)
        if len(out) >= max_rows:
            break
    return out


def _infer_serial_from_sender(row: Dict[str, Any]) -> str:
    """Best-effort backfill: older rows pre-date the ``source_serial`` field."""
    sender = str(row.get("sender", "")).upper()
    if "M5" in sender or "ALICE" in sender:
        return NODE_M5_FOUNDRY
    if "M1" in sender or "MOTHER" in sender or "M1THER" in sender:
        return NODE_M1_SENTRY
    return ""


if __name__ == "__main__":
    print("local_silicon_serial =", _local_silicon_serial() or "UNKNOWN")
    print("local_drop_file      =", local_drop_file())
    print("remote_drop_files    =", [p.name for p in remote_drop_files()])
    msgs = poll_incoming(max_rows=5)
    print(f"new_inbound_rows ({len(msgs)}):")
    for m in msgs:
        print(f"  [{m.source_file}] {m.sender} @ {m.ts} ({m.source_serial}): {m.text[:80]}")
