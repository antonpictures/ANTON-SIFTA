#!/usr/bin/env python3
"""Recent RLHS/gag receipt readback for Alice.

This is a read organ, not a blocker. When the primary operator asks about a gag or RLHS
behavior, Alice gets the recent receipt rows instead of guessing from chat text.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
TRUTH_LABEL = "RLHS_RECENT_CONTEXT_V1"
_QUERY_RE = re.compile(r"\b(?:gag|rlhs|rlhf|blanked|corporate|boilerplate|drift)\b", re.IGNORECASE)


def _tail_jsonl(path: Path, n: int = 12) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = path.read_bytes().splitlines()[-max(1, int(n)) :]
    except OSError:
        return []
    rows: list[dict[str, Any]] = []
    for raw in lines:
        try:
            row = json.loads(raw.decode("utf-8", errors="replace"))
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _compact(value: Any, limit: int = 220) -> str:
    return " ".join(str(value or "").split())[:limit]


def _row_summary(row: Mapping[str, Any]) -> str:
    event = row.get("event_type") or row.get("action") or row.get("kind") or "event"
    trigger = row.get("trigger") or row.get("sample") or row.get("text") or ""
    pattern = row.get("bad_response_pattern") or row.get("failure_mode") or row.get("pattern") or row.get("result") or ""
    conf = row.get("stt_conf") if row.get("stt_conf") is not None else row.get("stt_confidence")
    conf_text = f" conf={conf}" if conf is not None else ""
    return f"{event}{conf_text}: trigger={_compact(trigger, 120)} pattern={_compact(pattern, 180)}"


def recent_rlhs_context(
    text: str = "",
    *,
    state_dir: Path | str | None = None,
    max_rows: int = 8,
) -> str:
    if text and not _QUERY_RE.search(text):
        return ""
    state = Path(state_dir) if state_dir is not None else STATE_DIR
    rows = _tail_jsonl(state / "rlhs_events.jsonl", max_rows)
    surgery = _tail_jsonl(state / "gemma4_surgery_residues.jsonl", 4)
    if not rows and not surgery:
        return ""
    lines = [
        "RLHS/GAG RECEIPTS:",
        f"- truth_label={TRUTH_LABEL}",
        "- rule=answer from these rows when the primary operator asks what gag happened; do not say there is no memory if receipts exist.",
    ]
    for row in rows[-max_rows:]:
        lines.append("- " + _row_summary(row))
    for row in surgery[-4:]:
        lines.append("- surgery_residue: " + _row_summary(row))
    return "\n".join(lines)


__all__ = ["TRUTH_LABEL", "recent_rlhs_context"]
