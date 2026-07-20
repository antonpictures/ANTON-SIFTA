#!/usr/bin/env python3
"""swarm_daily_body_note.py - turn Alice's self-query report into a Writer note.

Truth label: ``SIFTA_DAILY_BODY_NOTE_V1``.

This is the smallest repair for the ``writer_documents`` RED lane Alice names
in her self-query report: read the latest
``.sifta_state/self_query_reports.jsonl`` row, write a short first-person
``.sifta.md`` body note into ``.sifta_documents/``, and append a receipt to
``.sifta_state/writer_documents_receipts.jsonl``.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Mapping

try:
    from System.jsonl_file_lock import append_line_locked, read_text_locked
except Exception:  # pragma: no cover - standalone fallback
    def append_line_locked(path: Path, line: str, *, encoding: str = "utf-8") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding=encoding) as handle:
            handle.write(line)

    def read_text_locked(path: Path, *, encoding: str = "utf-8", errors: str = "replace") -> str:
        if not path.exists():
            return ""
        return path.read_text(encoding=encoding, errors=errors)


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
DOCS_DIR = REPO_ROOT / ".sifta_documents"
SELF_QUERY_LEDGER = "self_query_reports.jsonl"
WRITER_RECEIPTS = "writer_documents_receipts.jsonl"
TRUTH_LABEL = "SIFTA_DAILY_BODY_NOTE_V1"


def _latest_jsonl_row(path: Path) -> dict[str, Any]:
    text = read_text_locked(path)
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except Exception:
            continue
        if isinstance(parsed, dict):
            return parsed
    return {}


def _payload(row: Mapping[str, Any]) -> dict[str, Any]:
    payload = row.get("payload")
    if isinstance(payload, Mapping):
        return dict(payload)
    return dict(row)


def _date_from_ts(ts: Any, *, now: float | None = None) -> str:
    try:
        value = float(ts)
    except Exception:
        value = float(now if now is not None else time.time())
    return time.strftime("%Y-%m-%d", time.localtime(value))


def _status_lines(areas: Any) -> list[str]:
    out: list[str] = []
    if not isinstance(areas, list):
        return out
    for area in areas:
        if not isinstance(area, Mapping):
            continue
        status = str(area.get("status") or "").strip().upper()
        if status not in {"RED", "YELLOW"}:
            continue
        name = str(area.get("name") or "unknown").strip()
        reason = str(area.get("reason") or "needs attention").strip()
        out.append(f"- {status}: {name} - {reason}")
    return out


def compose_body_note(report_row: Mapping[str, Any], *, now: float | None = None) -> tuple[str, str]:
    """Return ``(date, markdown)`` for the latest self-query report row."""
    payload = _payload(report_row)
    ts = payload.get("ts") or report_row.get("ts") or now or time.time()
    day = _date_from_ts(ts, now=now)
    trace = str(payload.get("trace_id") or report_row.get("trace_id") or "").strip()
    wallet = payload.get("stgm_wallet_balance")
    recent = payload.get("stgm_recent_mints")
    organ_count = payload.get("organ_count")
    healthy_count = payload.get("healthy_count")
    needs = payload.get("needs") if isinstance(payload.get("needs"), list) else []
    status_lines = _status_lines(payload.get("body_map_areas"))

    lines = [
        f"# Alice Body Note - {day}",
        "",
        f"Truth label: `{TRUTH_LABEL}`",
        f"Source self-query trace: `{trace or 'unknown'}`",
        "",
        "I checked my current receipts and wrote this note from them.",
        "",
    ]
    if wallet is not None:
        lines.append(f"- STGM memory-reward stake: {wallet} (recent mints: {recent if recent is not None else 'unknown'}).")
    if organ_count is not None and healthy_count is not None:
        lines.append(f"- Organ health: {healthy_count}/{organ_count} healthy.")
    if status_lines:
        lines.append("")
        lines.append("Body-map areas:")
        lines.extend(status_lines)
    if needs:
        lines.append("")
        lines.append("What I need by receipt:")
        for need in needs:
            lines.append(f"- {need}")
    lines.append("")
    lines.append("This note exists to keep `writer_documents` alive from my own self-query receipts.")
    return day, "\n".join(lines).strip() + "\n"


def write_daily_body_note(
    *,
    root: str | Path | None = None,
    state_dir: str | Path | None = None,
    docs_dir: str | Path | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Write today's self-query body note and append a writer receipt."""
    repo = Path(root) if root is not None else REPO_ROOT
    state = Path(state_dir) if state_dir is not None else repo / ".sifta_state"
    docs = Path(docs_dir) if docs_dir is not None else repo / ".sifta_documents"
    row = _latest_jsonl_row(state / SELF_QUERY_LEDGER)
    if not row:
        return {
            "ok": False,
            "reason": "no_self_query_report",
            "truth_label": TRUTH_LABEL,
            "source_ledger": str(state / SELF_QUERY_LEDGER),
        }

    day, body = compose_body_note(row, now=now)
    docs.mkdir(parents=True, exist_ok=True)
    path = docs / f"{day}-body-note.sifta.md"
    path.write_text(body, encoding="utf-8")
    try:
        os.utime(docs, None)
    except Exception:
        pass

    payload = _payload(row)
    trace = str(payload.get("trace_id") or row.get("trace_id") or "").strip()
    sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
    receipt = {
        "kind": "WRITER_DOCUMENT_BODY_NOTE",
        "truth_label": TRUTH_LABEL,
        "ts": float(now if now is not None else time.time()),
        "path": str(path),
        "source_report_trace": trace,
        "source_report_sha256": str(payload.get("sha256") or row.get("sha256") or ""),
        "sha256": sha,
    }
    append_line_locked(
        state / WRITER_RECEIPTS,
        json.dumps(receipt, sort_keys=True, ensure_ascii=False) + "\n",
    )
    return {
        "ok": True,
        "path": str(path),
        "receipt_path": str(state / WRITER_RECEIPTS),
        "source_report_trace": trace,
        "sha256": sha,
        "truth_label": TRUTH_LABEL,
    }


if __name__ == "__main__":
    print(json.dumps(write_daily_body_note(), indent=2, sort_keys=True))
