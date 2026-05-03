#!/usr/bin/env python3
"""Owner unified field read-back context for Alice.

Several organs can write owner-field receipts: desktop presence, STIGTIME work
receipts, and schedule anchors. This module closes the other half of the loop:
compact those receipts into a prompt block so Alice can reason from the real
owner field instead of saying she has no information.

No surveillance inference happens here. Unknown intervals stay unknown.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from System.jsonl_file_lock import read_text_locked
except Exception:  # pragma: no cover - direct script fallback
    read_text_locked = None  # type: ignore[assignment]

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"

PRESENCE_NAME = "owner_desktop_presence.json"
WORK_RECEIPTS_NAME = "work_receipts.jsonl"
SCHEDULE_NAME = "stigmergic_schedule.jsonl"

TRUTH_LABEL = "OWNER_UNIFIED_FIELD_CONTEXT_V1"
OWNER_RHYTHM_SPEC = (
    "Primary locus: desk typing on the SIFTA hardware. Secondary loci: kitchen "
    "and bedroom/sleep. Owner safety and finite owner-life history are primary."
)


def _state_dir(state_dir: Path | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else STATE_DIR


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        if read_text_locked is not None:
            raw = read_text_locked(path, encoding="utf-8")
        else:
            raw = path.read_text(encoding="utf-8", errors="replace")
        data = json.loads(raw) if raw.strip() else {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _tail_jsonl(path: Path, n: int = 64, *, max_bytes: int = 256 * 1024) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        with path.open("rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            start = max(0, size - max_bytes)
            fh.seek(start)
            lines = fh.read().splitlines()
    except OSError:
        return []
    if start > 0 and lines:
        lines = lines[1:]
    rows: list[dict[str, Any]] = []
    for raw in lines:
        try:
            row = json.loads(raw.decode("utf-8", errors="replace"))
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows[-max(1, int(n)) :]


def _row_ts(row: dict[str, Any]) -> float:
    for key in ("ts", "timestamp", "created", "deposit_time"):
        try:
            value = float(row.get(key, 0.0) or 0.0)
        except Exception:
            continue
        return value / 1000.0 if value > 10_000_000_000 else value
    return 0.0


def _age_s(ts: float, now: float) -> float | None:
    if ts <= 0:
        return None
    return max(0.0, now - ts)


def _human_duration(seconds: float | None) -> str:
    if seconds is None:
        return "unknown"
    seconds = max(0.0, float(seconds))
    if seconds < 90:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds // 60)}m"
    if seconds < 86400:
        return f"{seconds / 3600:.1f}h"
    return f"{seconds / 86400:.1f}d"


def _compact_text(value: Any, limit: int = 420) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit]


def _latest_owner_boot_receipt(state: Path) -> dict[str, Any]:
    for row in reversed(_tail_jsonl(state / WORK_RECEIPTS_NAME, 256, max_bytes=512 * 1024)):
        action = str(row.get("action") or "")
        stigtime = str(row.get("stigtime") or "")
        if action == "OWNER_UNIFIED_FIELD_BOOT" or "owner-unified-field-boot" in stigtime:
            return row
    return {}


def _latest_schedule_anchor(state: Path) -> dict[str, Any]:
    for row in reversed(_tail_jsonl(state / SCHEDULE_NAME, 256, max_bytes=512 * 1024)):
        text = str(row.get("text") or "")
        source = str(row.get("source") or "")
        if "OWNER UNIFIED FIELD" in text or source == "System.swarm_owner_unified_field_boot":
            return row
    return {}


def owner_field_context(
    *,
    state_dir: Path | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Return compact receipt facts for owner-field prompt grounding."""
    state = _state_dir(state_dir)
    now_ts = float(now if now is not None else time.time())
    presence = _read_json(state / PRESENCE_NAME)
    boot = _latest_owner_boot_receipt(state)
    schedule = _latest_schedule_anchor(state)

    last_alive = 0.0
    try:
        last_alive = float(presence.get("last_alive_ts", 0.0) or 0.0)
    except Exception:
        last_alive = 0.0
    last_boot = 0.0
    try:
        last_boot = float(presence.get("last_boot_ts", 0.0) or 0.0)
    except Exception:
        last_boot = 0.0

    gap_s = None
    for value in (
        presence.get("last_gap_seconds_at_boot"),
        boot.get("gap_seconds_at_boot"),
        boot.get("gap_seconds"),
    ):
        try:
            if value is not None:
                gap_s = float(value)
                break
        except Exception:
            pass

    evidence_count = sum(1 for x in (presence, boot, schedule) if x)
    return {
        "truth_label": TRUTH_LABEL,
        "ts": now_ts,
        "evidence_count": evidence_count,
        "owner_rhythm": OWNER_RHYTHM_SPEC,
        "presence": {
            "available": bool(presence),
            "last_alive_ts": last_alive or None,
            "last_alive_age_s": _age_s(last_alive, now_ts),
            "last_alive_age_human": _human_duration(_age_s(last_alive, now_ts)),
            "last_boot_ts": last_boot or None,
            "last_boot_age_human": _human_duration(_age_s(last_boot, now_ts)),
            "last_gap_seconds_at_boot": gap_s,
            "last_gap_human": _human_duration(gap_s),
        },
        "boot_receipt": {
            "available": bool(boot),
            "ts": _row_ts(boot) or None,
            "age_human": _human_duration(_age_s(_row_ts(boot), now_ts)),
            "trace_id": boot.get("trace_id"),
            "stigtime": _compact_text(boot.get("stigtime"), 260),
            "truth_note": _compact_text(boot.get("truth_note"), 300),
        },
        "schedule_anchor": {
            "available": bool(schedule),
            "ts": _row_ts(schedule) or None,
            "age_human": _human_duration(_age_s(_row_ts(schedule), now_ts)),
            "text": _compact_text(schedule.get("text"), 500),
            "source": schedule.get("source"),
        },
        "readback_rule": (
            "Use these receipts before answering owner-location, owner-schedule, "
            "gap, boot, or 'were you watching with me' questions. Do not invent "
            "what happened during unsampled gaps."
        ),
    }


def format_owner_field_for_prompt(
    *,
    state_dir: Path | None = None,
    now: float | None = None,
) -> str:
    ctx = owner_field_context(state_dir=state_dir, now=now)
    if int(ctx.get("evidence_count") or 0) <= 0:
        return ""
    presence = ctx["presence"]
    boot = ctx["boot_receipt"]
    schedule = ctx["schedule_anchor"]
    lines = [
        "OWNER UNIFIED FIELD READBACK:",
        f"- truth_label={ctx['truth_label']}",
        f"- owner_rhythm={ctx['owner_rhythm']}",
        "- rule=owner schedule and owner safety are primary; unknown gaps stay unknown.",
    ]
    if presence.get("available"):
        lines.append(
            "- desktop_presence="
            f"last_alive_age={presence.get('last_alive_age_human')} "
            f"last_boot_age={presence.get('last_boot_age_human')} "
            f"last_boot_gap={presence.get('last_gap_human')}"
        )
    if boot.get("available"):
        lines.append(
            "- boot_stigtime="
            f"{boot.get('stigtime')} receipt={boot.get('trace_id')} age={boot.get('age_human')}"
        )
    if schedule.get("available"):
        lines.append(
            "- schedule_anchor="
            f"{schedule.get('text')} age={schedule.get('age_human')}"
        )
    lines.append(f"- readback_rule={ctx['readback_rule']}")
    return "\n".join(lines)


__all__ = [
    "TRUTH_LABEL",
    "format_owner_field_for_prompt",
    "owner_field_context",
]


if __name__ == "__main__":
    print(format_owner_field_for_prompt())
