#!/usr/bin/env python3
"""Filename + filesystem time anchors — how Alice learns when reality happened.

George (r1388): LLMs lose passing time. Owner screenshots often encode the moment in the
filename (`Screenshot 2026-06-19 at 5.48.34 PM.png`) and in file creation/mtime. Those
marks are stigmergic timeline coordinates — Alice reads them instead of inventing "now."

Truth label: FILENAME_TIME_ANCHOR_V1
Ledger: .sifta_state/filename_time_pins.jsonl
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore[misc, assignment]

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover

    def append_line_locked(path: Path, line: str, *, encoding: str = "utf-8") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding=encoding) as handle:
            handle.write(line)

TRUTH_LABEL = "FILENAME_TIME_ANCHOR_V1"
SCHEMA = "FILENAME_TIME_PIN_V1"
LEDGER_NAME = "filename_time_pins.jsonl"

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_OWNER_TZ = ZoneInfo("America/Los_Angeles") if ZoneInfo else None

_MAC_SCREENSHOT_RE = re.compile(
    r"Screenshot[\s_]+(\d{4})-(\d{2})-(\d{2})[\s_]+at[\s_]+"
    r"(\d{1,2})\.(\d{2})\.(\d{2})[\s_]*(AM|PM)\b",
    re.IGNORECASE,
)
_DATE_IN_NAME_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_POLENTA_ANCHOR = "polenta kitchen thread"
_POLENTA_EVIDENCE_DIR = "outputs/polenta_kitchen"
_POLENTA_STAGE_BINDINGS: tuple[tuple[str, str], ...] = (
    ("5.26.14", "stage=prep_dry | dry polenta + eggs on stove"),
    ("5.41.51", "stage=eggs_in_pot | smashed eggs + polenta cooking"),
    ("5.48.34", "stage=pour_moment | George named this filename — pour imminent"),
    ("5.52.03", "stage=finished_bowl | completed mound in black bowl"),
)
_PHOTO_EVIDENCE_BINDINGS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    (
        "outputs/JOY_BEHAR_JD_VANCE_SCREENSHOT_2026-06-19.jpg",
        ("Joy Behar", "JD Vance"),
        "The View news clip — George attached pixels",
    ),
    (
        "outputs/PHILIPPE_CHAT_SCREENSHOT_2026-06-19.jpg",
        ("Phillipe",),
        "Commercial viability iMessage — Phillipe bar",
    ),
)


def _state_dir(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return _STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


@dataclass(frozen=True)
class FileTimePin:
    path: str
    epoch: float
    local_human: str
    local_iso: str
    time_source: str
    filename_parsed: bool
    owner_created_epoch: float
    owner_modified_epoch: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "epoch": self.epoch,
            "local_human": self.local_human,
            "local_iso": self.local_iso,
            "time_source": self.time_source,
            "filename_parsed": self.filename_parsed,
            "owner_created_epoch": self.owner_created_epoch,
            "owner_modified_epoch": self.owner_modified_epoch,
        }


def _local_dt(epoch: float) -> datetime:
    if _OWNER_TZ is not None:
        return datetime.fromtimestamp(epoch, tz=_OWNER_TZ)
    return datetime.fromtimestamp(epoch)


def _parse_mac_screenshot_filename(name: str) -> Optional[datetime]:
    m = _MAC_SCREENSHOT_RE.search(name)
    if not m:
        return None
    year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
    hour = int(m.group(4))
    minute, second = int(m.group(5)), int(m.group(6))
    ampm = m.group(7).upper()
    if ampm == "PM" and hour != 12:
        hour += 12
    if ampm == "AM" and hour == 12:
        hour = 0
    if _OWNER_TZ is not None:
        return datetime(year, month, day, hour, minute, second, tzinfo=_OWNER_TZ)
    return datetime(year, month, day, hour, minute, second)


def _file_stat_times(path: Path) -> tuple[float, float]:
    try:
        st = path.stat()
    except OSError:
        return 0.0, 0.0
    birth = getattr(st, "st_birthtime", None)
    created = float(birth) if birth is not None else float(st.st_mtime)
    return created, float(st.st_mtime)


def resolve_file_time_pin(
    file_path: str | Path,
    *,
    prefer_filename: bool = True,
) -> Optional[FileTimePin]:
    """Resolve when the owner created this file — filename first, then birthtime/mtime."""
    path = Path(file_path).expanduser()
    if not path.is_absolute():
        path = (_REPO / path).resolve()
    if not path.exists():
        return None
    created, modified = _file_stat_times(path)
    name = path.name
    parsed_dt = _parse_mac_screenshot_filename(name) if prefer_filename else None
    if parsed_dt is None and prefer_filename:
        dm = _DATE_IN_NAME_RE.search(name)
        if dm and created:
            parsed_dt = _local_dt(created)
            time_source = "filename_date_plus_file_birthtime"
        else:
            time_source = "file_birthtime_or_mtime"
    elif parsed_dt is not None:
        time_source = "mac_screenshot_filename"
    else:
        time_source = "file_birthtime_or_mtime"

    epoch = parsed_dt.timestamp() if parsed_dt else (created or modified)
    if epoch <= 0:
        return None
    local = _local_dt(epoch)
    return FileTimePin(
        path=str(path),
        epoch=epoch,
        local_human=local.strftime("%A %B %d %Y, %I:%M %p %Z").replace("  ", " "),
        local_iso=local.isoformat(),
        time_source=time_source,
        filename_parsed=parsed_dt is not None and time_source == "mac_screenshot_filename",
        owner_created_epoch=created,
        owner_modified_epoch=modified,
    )


def _resolve_evidence_glob(rel_dir: str, fragment: str) -> Optional[Path]:
    """Find evidence file by stable time fragment (avoids macOS narrow-space filename quirks)."""
    directory = _REPO / rel_dir
    if not directory.is_dir():
        return None
    hits = sorted(directory.glob(f"*{fragment}*"), key=lambda p: ("Screenshot" not in p.name, p.name))
    return hits[0] if hits else None


def correlate_conversation_near_epoch(
    epoch: float,
    *,
    window_sec: float = 420.0,
    keywords: tuple[str, ...] = (),
    state_dir: Optional[Path | str] = None,
    max_rows: int = 6000,
) -> list[dict[str, Any]]:
    """Find alice_conversation turns near a file-time pin — filename meets chat history."""
    sd = _state_dir(state_dir)
    conv_path = sd / "alice_conversation.jsonl"
    if not conv_path.exists() or epoch <= 0:
        return []
    hits: list[dict[str, Any]] = []
    for line in conv_path.read_text(encoding="utf-8", errors="replace").splitlines()[-max_rows:]:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        payload = row.get("payload") or {}
        text = str(payload.get("text") or "")
        clock = payload.get("clock_receipt") or {}
        row_ts = row.get("ts")
        physical_pt = row_ts.get("physical_pt") if isinstance(row_ts, dict) else 0
        ts = float(clock.get("epoch") or payload.get("ts") or physical_pt or 0)
        if ts <= 0 or abs(ts - epoch) > window_sec:
            continue
        lower = text.lower()
        if keywords and not any(k in lower for k in keywords):
            continue
        hits.append(
            {
                "role": payload.get("role") or "",
                "epoch": ts,
                "delta_sec": round(ts - epoch, 1),
                "local_human": clock.get("local_human") or _local_dt(ts).strftime("%A %B %d %Y, %I:%M %p %Z"),
                "text": text[:220],
            }
        )
    hits.sort(key=lambda h: abs(float(h.get("delta_sec") or 0)))
    return hits[:4]


def ensure_polenta_kitchen_anchor(*, state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    """Register the Joy-kitchen polenta thread as a CONFIRMED shared-experience coordinate."""
    from System.swarm_stigmergic_shared_experience_anchors import (
        _latest_anchor_row,
        register_shared_experience_anchor,
    )

    if _latest_anchor_row(_POLENTA_ANCHOR, state_dir=state_dir):
        return {"ok": True, "already": True}
    row = register_shared_experience_anchor(
        _POLENTA_ANCHOR,
        status="CONFIRMED",
        anchor_kind="shared_experience",
        concept_label="stigmergic training on the job — Joy kitchen polenta",
        experience_snippet=(
            "George cooked polenta with eggs, butter, cheese; screenshots encode when each stage happened"
        ),
        evidence_kind="owner_photo_timeline",
        evidence_status="filename_time_thread",
        source="filename_time_seed",
        state_dir=state_dir,
    )
    return {"ok": True, "anchor": row}


def _append_pin_ledger(row: dict[str, Any], *, state_dir: Optional[Path | str] = None) -> None:
    path = _state_dir(state_dir) / LEDGER_NAME
    row = {**row, "schema": SCHEMA, "truth_label": TRUTH_LABEL, "ts": time.time()}
    append_line_locked(path, json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def pin_file_time_to_anchor(
    file_path: str | Path,
    anchor_name: str,
    *,
    timeline_note: str = "",
    editor: str = "filename_time_organ",
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Attach filesystem/filename time to a shared-experience anchor row."""
    pin = resolve_file_time_pin(file_path)
    if pin is None:
        return {"ok": False, "reason": "file_missing_or_unparsed", "path": str(file_path)}
    from System.swarm_stigmergic_shared_experience_anchors import edit_shared_experience_anchor

    note_parts = [
        f"file_time={pin.local_human}",
        f"source={pin.time_source}",
        f"path={Path(pin.path).name}",
    ]
    if timeline_note:
        note_parts.append(timeline_note)
    chat_hits = correlate_conversation_near_epoch(
        pin.epoch,
        keywords=("polenta", "garlic", "joy", "pour", "egg", "kitchen", "phillipe", "receipt"),
        state_dir=state_dir,
    )
    if chat_hits:
        nearest = chat_hits[0]
        note_parts.append(
            f"chat@{nearest.get('local_human')} delta={nearest.get('delta_sec')}s "
            f"{nearest.get('text','')[:80]}"
        )
    row = edit_shared_experience_anchor(
        anchor_name,
        timeline_label=pin.local_human,
        timeline_note=" | ".join(note_parts)[:280],
        editor=editor,
        evidence_source="swarm_filename_time_anchor",
        state_dir=state_dir,
    )
    if not row:
        return {"ok": False, "reason": "anchor_not_found", "anchor_name": anchor_name}
    row = {
        **row,
        "evidence_kind": row.get("evidence_kind") or "owner_photo_file",
        "evidence_ref": pin.path,
        "evidence_status": row.get("evidence_status") or "file_time_pinned",
        "file_time_epoch": pin.epoch,
        "file_time_source": pin.time_source,
    }
    from System.swarm_stigmergic_shared_experience_anchors import _append_row, _ledger_path

    _append_row(row, state_dir=state_dir)
    _append_pin_ledger(
        {
            "anchor_name": anchor_name,
            "anchor_id": row.get("anchor_id"),
            "file_path": pin.path,
            "file_time_epoch": pin.epoch,
            "file_time_human": pin.local_human,
            "file_time_source": pin.time_source,
            "timeline_note": timeline_note,
            "conversation_hits": chat_hits,
        },
        state_dir=state_dir,
    )
    return {"ok": True, "pin": pin.as_dict(), "anchor": row, "conversation_hits": chat_hits}


def seed_polenta_kitchen_file_times(*, state_dir: Optional[Path | str] = None) -> list[dict[str, Any]]:
    """Pin George's macOS-named polenta screenshots to the kitchen thread anchor."""
    ensure_polenta_kitchen_anchor(state_dir=state_dir)
    results: list[dict[str, Any]] = []
    for fragment, note in _POLENTA_STAGE_BINDINGS:
        full = _resolve_evidence_glob(_POLENTA_EVIDENCE_DIR, fragment)
        if full is None:
            results.append({"ok": False, "fragment": fragment, "reason": "missing"})
            continue
        results.append(
            pin_file_time_to_anchor(
                full,
                _POLENTA_ANCHOR,
                timeline_note=note,
                editor="seed_polenta_kitchen",
                state_dir=state_dir,
            )
        )
    return results


def seed_known_evidence_file_times(*, state_dir: Optional[Path | str] = None) -> list[dict[str, Any]]:
    """Pin known output screenshots to their anchors (Joy/polenta/Phillipe threads)."""
    results: list[dict[str, Any]] = []
    results.extend(seed_polenta_kitchen_file_times(state_dir=state_dir))
    for rel_path, anchors, note in _PHOTO_EVIDENCE_BINDINGS:
        full = _REPO / rel_path
        if not full.exists():
            results.append({"ok": False, "path": rel_path, "reason": "missing"})
            continue
        for anchor in anchors:
            results.append(
                pin_file_time_to_anchor(
                    full,
                    anchor,
                    timeline_note=note,
                    editor="seed_known_evidence",
                    state_dir=state_dir,
                )
            )
    return results


def filename_time_prompt_block(
    *,
    max_chars: int = 1200,
    state_dir: Optional[Path | str] = None,
) -> str:
    """Short prompt slice: Alice learns passing time from owner file marks."""
    ledger = _state_dir(state_dir) / LEDGER_NAME
    if not ledger.exists():
        return ""
    rows: list[dict[str, Any]] = []
    for line in ledger.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if not rows:
        return ""
    lines = [
        "## FILENAME / FILE-CREATION TIME ANCHORS (owner reality clock — not LLM guess)",
        "When George attaches a screenshot, read the filename time and file birthtime first.",
    ]
    rows.sort(key=lambda r: float(r.get("file_time_epoch") or r.get("ts") or 0), reverse=True)
    for row in rows[:12]:
        line = (
            f"- {row.get('anchor_name')}: {row.get('file_time_human')} "
            f"({row.get('file_time_source')}) file={Path(str(row.get('file_path') or '')).name}"
        )
        note = str(row.get("timeline_note") or "")
        if note:
            line += f" | {note[:100]}"
        hits = row.get("conversation_hits") or []
        if hits:
            nearest = hits[0]
            line += f" | chat~{nearest.get('local_human','')}: {str(nearest.get('text') or '')[:60]}"
        lines.append(line)
    block = "\n".join(lines)
    return block[:max_chars] if len(block) > max_chars else block


__all__ = [
    "TRUTH_LABEL",
    "FileTimePin",
    "resolve_file_time_pin",
    "correlate_conversation_near_epoch",
    "ensure_polenta_kitchen_anchor",
    "pin_file_time_to_anchor",
    "seed_polenta_kitchen_file_times",
    "seed_known_evidence_file_times",
    "filename_time_prompt_block",
]