"""
System/swarm_arm_session_ingest.py
══════════════════════════════════
Round 50 (2026-05-27) — Arm-session ingestion into the memory card.

Builds a compact "what my arms have been doing" block from the
append-only arm ledgers so Alice's cortex sees its own arm activity as
short-term memory, not as an external mystery:

  - .sifta_state/agent_arm_receipts.jsonl
  - .sifta_state/alice_agent_arm_briefings.jsonl
  - .sifta_state/agent_arm_async_evidence.jsonl
  - .sifta_state/matrix_terminal_process_trace.jsonl   (GROK_RESULT events)

The block is consumed by `swarm_memory_card.compose_memory_card` as a
new section (`arm_session_block`). When the owner asks "what did Codex
do?" / "did Grok finish?" / "what arm last touched my body?" the cortex
can answer from receipts instead of hallucinating.

This module READS only. Never writes. Never raises out.

Public surface
══════════════
    fetch_arm_session_block(state_dir, *, user_text="",
                            max_age_s=86400.0, max_n=12) -> str

Tested by tests/test_swarm_arm_session_ingest.py.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

TRUTH_LABEL = "ARM_SESSION_INGEST_V1"

DEFAULT_MAX_AGE_S = 24 * 3600.0
DEFAULT_MAX_N = 12

# Trace event types in matrix_terminal_process_trace.jsonl that prove an
# arm actually produced an output (vs just being spawned).
_GROK_RESULT_EVENTS = (
    "GROK_RESULT",
    "GROK_FINAL",
    "HICKS_RESULT",
    "ARM_OUTPUT_LANDED",
)


def _read_tail(path: Path, *, max_lines: int = 400) -> list[dict[str, Any]]:
    """Return up to the last `max_lines` parseable JSON rows. Never raises."""
    if not path.exists():
        return []
    try:
        data = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    rows: list[dict[str, Any]] = []
    for line in data.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows[-max_lines:]


def _to_float(value: Any) -> Optional[float]:
    try:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            return float(value)
    except (TypeError, ValueError):
        return None
    return None


def _fmt_relative(ts: float, *, now_ts: float) -> str:
    delta = max(0.0, float(now_ts) - float(ts))
    if delta < 60.0:
        return f"{int(delta)}s ago"
    if delta < 3600.0:
        return f"{int(delta / 60.0)}m ago"
    if delta < 86400.0:
        return f"{int(delta / 3600.0)}h ago"
    return f"{int(delta / 86400.0)}d ago"


def _summarise_arm_receipt(row: dict[str, Any]) -> Optional[dict[str, Any]]:
    ts = _to_float(row.get("ts"))
    if ts is None:
        return None
    return {
        "ts": ts,
        "kind": "arm_receipt",
        "arm": str(row.get("arm_id") or row.get("display_name") or "unknown_arm"),
        "model": str(row.get("actual_model") or row.get("model") or "").strip(),
        "receipt_id": str(row.get("receipt_id") or "").strip(),
        "truth_label": str(row.get("truth_label") or "").strip(),
        "summary_text": str(
            row.get("summary")
            or row.get("intent")
            or row.get("task")
            or ""
        ).strip(),
    }


def _summarise_arm_briefing(row: dict[str, Any]) -> Optional[dict[str, Any]]:
    ts = _to_float(row.get("ts"))
    if ts is None:
        return None
    return {
        "ts": ts,
        "kind": "arm_briefing",
        "arm": str(row.get("arm_id") or "unknown_arm"),
        "model": str(row.get("model") or "").strip(),
        "receipt_id": str(row.get("briefing_id") or row.get("id") or "").strip(),
        "truth_label": "",
        "summary_text": str(
            row.get("summary")
            or row.get("dispatch_text")
            or row.get("prompt_head")
            or ""
        ).strip(),
    }


def _summarise_arm_async_evidence(row: dict[str, Any]) -> Optional[dict[str, Any]]:
    ts = _to_float(row.get("ts"))
    if ts is None:
        return None
    status = str(row.get("status") or "").strip()
    arm = str(row.get("arm_id") or "unknown_arm")
    return {
        "ts": ts,
        "kind": "arm_async_evidence",
        "arm": arm,
        "model": str(row.get("model") or "").strip(),
        "receipt_id": str(row.get("job_id") or "").strip(),
        "truth_label": status,
        "summary_text": str(
            row.get("note")
            or row.get("intent")
            or row.get("decision")
            or ""
        ).strip(),
    }


def _summarise_matrix_trace_event(row: dict[str, Any]) -> Optional[dict[str, Any]]:
    ts = _to_float(row.get("ts"))
    if ts is None:
        return None
    event = str(row.get("event") or row.get("kind") or "").upper().strip()
    if event not in _GROK_RESULT_EVENTS:
        return None
    text = str(row.get("text") or row.get("result_text") or row.get("body") or "").strip()
    if len(text) > 240:
        text = text[:237] + "..."
    return {
        "ts": ts,
        "kind": event.lower(),
        "arm": str(row.get("arm") or row.get("cli") or "grok_pty"),
        "model": str(row.get("model") or "grok").strip(),
        "receipt_id": str(row.get("event_id") or row.get("id") or "").strip(),
        "truth_label": event,
        "summary_text": text,
    }


def fetch_arm_session_block(
    state_dir: Path | str,
    *,
    user_text: str = "",
    max_age_s: float = DEFAULT_MAX_AGE_S,
    max_n: int = DEFAULT_MAX_N,
    now_ts: Optional[float] = None,
) -> str:
    """
    Compose the arm-session block as plain text for inclusion in the
    memory card. Returns "" when no arm activity exists in the lookback
    window (idle node).

    Sources:
      - agent_arm_receipts.jsonl
      - alice_agent_arm_briefings.jsonl
      - agent_arm_async_evidence.jsonl
      - matrix_terminal_process_trace.jsonl  (GROK_RESULT only)

    `user_text` is currently unused but accepted so the memory card
    fetcher signature is unified with the other section fetchers; a
    future round may bias selection by topical relevance.
    """
    _ = user_text  # placeholder for relevance ranking; see future task.
    sd = Path(state_dir)
    now = now_ts if now_ts is not None else time.time()
    cutoff = now - float(max_age_s)

    sources: tuple[tuple[Path, Any], ...] = (
        (sd / "agent_arm_receipts.jsonl",        _summarise_arm_receipt),
        (sd / "alice_agent_arm_briefings.jsonl", _summarise_arm_briefing),
        (sd / "agent_arm_async_evidence.jsonl",  _summarise_arm_async_evidence),
        (sd / "matrix_terminal_process_trace.jsonl", _summarise_matrix_trace_event),
    )

    events: list[dict[str, Any]] = []
    for path, summariser in sources:
        try:
            rows = _read_tail(path, max_lines=400)
        except Exception:
            rows = []
        for row in rows:
            try:
                ev = summariser(row)
            except Exception:
                ev = None
            if not ev:
                continue
            if ev["ts"] < cutoff:
                continue
            events.append(ev)

    if not events:
        return ""

    # De-duplicate by (kind, arm, receipt_id, ts) — matrix_trace and the
    # arm_receipts may double-log the same event.
    seen: set[tuple] = set()
    unique: list[dict[str, Any]] = []
    for ev in events:
        key = (ev.get("kind"), ev.get("arm"), ev.get("receipt_id"), round(float(ev.get("ts", 0.0)), 1))
        if key in seen:
            continue
        seen.add(key)
        unique.append(ev)

    unique.sort(key=lambda e: float(e.get("ts", 0.0)), reverse=True)
    selected = unique[:max_n]

    lines: list[str] = []
    lines.append("ARM SESSIONS — what your arms have been doing (read-only ledger evidence):")
    for ev in selected:
        rel = _fmt_relative(ev["ts"], now_ts=now)
        kind = ev.get("kind", "")
        arm = ev.get("arm", "")
        model = ev.get("model", "")
        truth = ev.get("truth_label", "")
        rid = ev.get("receipt_id", "")
        summary_text = ev.get("summary_text", "")
        head_bits: list[str] = [rel, f"[{kind}]", arm]
        if model:
            head_bits.append(f"model={model}")
        if truth:
            head_bits.append(f"truth={truth}")
        if rid:
            head_bits.append(f"id={rid[:24]}")
        line = "  • " + "  ".join(b for b in head_bits if b)
        if summary_text:
            # Keep each entry compact so the memory card budget can hold
            # several arm rows alongside the other sections.
            head_text = summary_text.replace("\n", " ").strip()
            if len(head_text) > 240:
                head_text = head_text[:237] + "..."
            line += f"\n      {head_text}"
        lines.append(line)
    return "\n".join(lines)


__all__ = [
    "TRUTH_LABEL",
    "DEFAULT_MAX_AGE_S",
    "DEFAULT_MAX_N",
    "fetch_arm_session_block",
]
