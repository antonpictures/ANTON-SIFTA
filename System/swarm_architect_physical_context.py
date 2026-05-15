#!/usr/bin/env python3
"""
Append-only OBServed substrate receipts for the Architect's physical situation.

Each row is probe-only: homeworld serial, optional iPhone GPS cache (with age),
optional last app_focus line. No LLM inference — the ledger carries what files
and clocks prove so Alice's runtime can respect electricity, location, and
"who is at the keyboard" without pretending.

Ledger: .sifta_state/architect_physical_substrate.jsonl
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

_REPO = Path(__file__).resolve().parent.parent

try:
    from System.jsonl_file_lock import append_line_locked
except ImportError:  # pragma: no cover

    def append_line_locked(path: Path, line: str, *, encoding: str = "utf-8") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding=encoding) as f:
            f.write(line)


def _tail_jsonl_last_object(path: Path, *, max_scan_bytes: int = 65536) -> Optional[Dict[str, Any]]:
    if not path.is_file():
        return None
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            if size == 0:
                return None
            read_sz = min(max_scan_bytes, size)
            f.seek(size - read_sz)
            chunk = f.read().decode("utf-8", errors="replace")
        for line in reversed(chunk.splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                return obj
    except OSError:
        return None
    return None


def _read_iphone_gps_latest(state_dir: Path) -> Optional[Dict[str, Any]]:
    p = state_dir / "iphone_gps_latest.json"
    if not p.is_file():
        return None
    try:
        row = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(row, dict):
        return None
    ts = float(row.get("ts") or 0.0)
    now = time.time()
    age_s = now - ts if ts > 0 else None
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    lat = payload.get("latitude")
    lon = payload.get("longitude")
    acc = payload.get("accuracy")
    return {
        "ledger_ts": row.get("ts"),
        "age_s": age_s,
        "latitude": lat,
        "longitude": lon,
        "accuracy_m": acc,
        "channel": row.get("channel"),
    }


def _resolve_state_dir(state_dir: Optional[Path]) -> Path:
    if state_dir is None:
        return _REPO / ".sifta_state"
    p = Path(state_dir)
    if p.name == ".sifta_state" and p.is_dir():
        return p
    cand = p / ".sifta_state"
    return cand if cand.is_dir() else p


def append_architect_physical_substrate_row(
    *,
    state_dir: Optional[Path] = None,
    input_channel: str = "talk_turn",
    model_tag: str = "",
    truth_note: str = "",
) -> Optional[Dict[str, Any]]:
    """Write one OBSERVED substrate row. Returns the row dict, or None on total failure."""
    sd = _resolve_state_dir(state_dir)
    ledger = sd / "architect_physical_substrate.jsonl"
    try:
        from System.swarm_kernel_identity import owner_silicon

        serial = owner_silicon()
    except Exception:
        serial = "UNKNOWN"

    focus = _tail_jsonl_last_object(sd / "app_focus.jsonl")
    front: Optional[Dict[str, Any]] = None
    if isinstance(focus, dict):
        front = {
            "app": focus.get("app"),
            "detail": (focus.get("detail") or "")[:500],
            "focus_ts": focus.get("ts"),
        }

    gps = _read_iphone_gps_latest(sd)

    row: Dict[str, Any] = {
        "trace_id": str(uuid.uuid4()),
        "ts": time.time(),
        "truth_label": "OBSERVED",
        "kind": "ARCHITECT_PHYSICAL_SUBSTRATE_SNAPSHOT",
        "homeworld_serial": serial,
        "input_channel": input_channel,
        "ollama_model": (model_tag or "").strip(),
        "iphone_gps_latest": gps,
        "frontmost_app_focus": front,
        "truth_note": truth_note
        or (
            "I probe only: serial, iphone_gps_latest.json, last app_focus.jsonl line. "
            "I do not infer bodies in motion without camera rows."
        ),
    }
    try:
        append_line_locked(ledger, json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
        return row
    except Exception:
        return None


def _smoke() -> None:
    r = append_architect_physical_substrate_row(input_channel="smoke")
    print(json.dumps(r, indent=2))


if __name__ == "__main__":
    _smoke()
