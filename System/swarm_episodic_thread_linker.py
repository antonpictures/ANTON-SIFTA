#!/usr/bin/env python3
"""Cross-day episodic thread linker for Alice's daily journal.

This organ reads `.sifta_state/alice_journal/YYYY-MM-DD.jsonl`, detects
token-overlap links across different dates, and writes a compact append-only
thread graph to `.sifta_state/episodic_threads.jsonl`.

v1 is deterministic and lightweight (no LLM inference): keyword/entity overlap
+ time ordering.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from System.jsonl_file_lock import append_line_locked


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"

THREAD_LEDGER = "episodic_threads.jsonl"
JOURNAL_DIR = "alice_journal"
TRUTH_LABEL = "EPISODIC_THREADS_V1"

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_'-]{3,}")
_STOPWORDS = {
    "alice",
    "george",
    "today",
    "yesterday",
    "tomorrow",
    "local",
    "source",
    "truth",
    "label",
    "entry",
    "event",
    "observed",
    "trace",
    "sensor",
    "status",
    "media",
    "window",
    "focus",
    "camera",
    "attention",
}


def _state_dir(state_dir: Path | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else STATE_DIR


def _tail_jsonl(path: Path, max_rows: int = 1024) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = path.read_bytes().splitlines()[-max(1, int(max_rows)) :]
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for raw in lines:
        try:
            row = json.loads(raw.decode("utf-8", errors="replace"))
        except Exception:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _stable_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:16]


def _parse_local_label_ts(label: str) -> float | None:
    text = (label or "").strip()
    if not text:
        return None
    for fmt in ("%m-%d-%y_%H:%M", "%m-%d-%Y_%H:%M"):
        try:
            return datetime.strptime(text, fmt).timestamp()
        except Exception:
            continue
    return None


def _row_ts(row: dict[str, Any]) -> float:
    for key in ("ts", "timestamp", "source_ts"):
        try:
            value = float(row.get(key) or 0.0)
        except Exception:
            continue
        if value > 0:
            return value
    label = str(row.get("local_journal_label") or "").strip()
    parsed = _parse_local_label_ts(label)
    if parsed is not None:
        return parsed
    return 0.0


def _tokenize(text: str) -> set[str]:
    out: set[str] = set()
    for token in _WORD_RE.findall(text or ""):
        low = token.lower()
        if low in _STOPWORDS:
            continue
        out.add(low)
    return out


def _journal_files(state: Path, *, window_days: int) -> list[Path]:
    journal_dir = state / JOURNAL_DIR
    if not journal_dir.exists():
        return []
    files = sorted(
        p for p in journal_dir.glob("*.jsonl") if p.is_file() and re.match(r"\d{4}-\d{2}-\d{2}\.jsonl", p.name)
    )
    if not files:
        return []
    cutoff = datetime.fromtimestamp(time.time()) - timedelta(days=max(1, int(window_days)))
    keep: list[Path] = []
    for path in files:
        try:
            day = datetime.strptime(path.stem, "%Y-%m-%d")
        except Exception:
            keep.append(path)
            continue
        if day >= cutoff:
            keep.append(path)
    return keep or files[-max(1, int(window_days)) :]


def _collect_events(
    state: Path,
    *,
    window_days: int,
    max_rows_per_day: int,
    max_events: int,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for path in _journal_files(state, window_days=window_days):
        rows = _tail_jsonl(path, max_rows=max_rows_per_day)
        local_date = path.stem
        for row in rows:
            entry = " ".join(str(row.get("entry") or "").split()).strip()
            if not entry:
                continue
            tokens = _tokenize(entry)
            if len(tokens) < 2:
                continue
            row_id = str(row.get("journal_id") or "").strip()
            if not row_id:
                row_id = _stable_hash({"d": local_date, "e": entry, "l": row.get("local_journal_label", "")})
            ts = _row_ts(row)
            events.append(
                {
                    "row_id": row_id,
                    "local_date": local_date,
                    "local_journal_label": str(row.get("local_journal_label") or "").strip(),
                    "entry": entry,
                    "ts": ts,
                    "tokens": sorted(tokens),
                    "token_set": tokens,
                }
            )
    events.sort(key=lambda r: (float(r.get("ts") or 0.0), str(r.get("row_id") or "")))
    if len(events) > max_events:
        events = events[-max_events:]
    return events


def _build_threads(events: list[dict[str, Any]], *, min_overlap: int, max_candidates_per_token: int) -> list[dict[str, Any]]:
    if len(events) < 2:
        return []

    parent = list(range(len(events)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a: int, b: int) -> None:
        ra = find(a)
        rb = find(b)
        if ra != rb:
            parent[rb] = ra

    token_index: dict[str, list[int]] = defaultdict(list)
    for i, ev in enumerate(events):
        counts: Counter[int] = Counter()
        for token in ev["token_set"]:
            prev = token_index.get(token, [])
            if prev:
                for j in prev[-max(1, int(max_candidates_per_token)) :]:
                    if events[j]["local_date"] == ev["local_date"]:
                        continue
                    counts[j] += 1
            token_index[token].append(i)
        for j, overlap in counts.items():
            if overlap >= min_overlap:
                union(i, j)

    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(len(events)):
        groups[find(i)].append(i)

    threads: list[dict[str, Any]] = []
    for idxs in groups.values():
        if len(idxs) < 2:
            continue
        cluster = [events[i] for i in idxs]
        dates = sorted({str(ev["local_date"]) for ev in cluster})
        if len(dates) < 2:
            continue
        cluster.sort(key=lambda ev: float(ev.get("ts") or 0.0))
        newest = cluster[-1]
        token_counts: Counter[str] = Counter()
        for ev in cluster:
            token_counts.update(ev["tokens"])
        topic_tokens = [tok for tok, _ in token_counts.most_common(6)]
        row_ids = [str(ev["row_id"]) for ev in cluster]
        thread_id = "ethr_" + _stable_hash({"rows": row_ids, "dates": dates})[:12]
        refs: list[str] = []
        for ev in cluster[-4:]:
            label = ev.get("local_journal_label") or "unknown"
            refs.append(f"alice_journal/{ev['local_date']}.jsonl#journal_id:{ev['row_id']}#label:{label}")
        threads.append(
            {
                "thread_id": thread_id,
                "day_count": len(dates),
                "event_count": len(cluster),
                "first_ts": float(cluster[0].get("ts") or 0.0),
                "last_ts": float(newest.get("ts") or 0.0),
                "topic_tokens": topic_tokens,
                "latest_entry": str(newest.get("entry") or "")[:220],
                "latest_label": str(newest.get("local_journal_label") or ""),
                "latest_date": str(newest.get("local_date") or ""),
                "refs": refs,
            }
        )

    threads.sort(key=lambda row: (float(row.get("last_ts") or 0.0), int(row.get("event_count") or 0)), reverse=True)
    return threads


def _latest_row(state: Path) -> dict[str, Any]:
    rows = _tail_jsonl(state / THREAD_LEDGER, max_rows=256)
    return rows[-1] if rows else {}


def write_episodic_threads(
    *,
    state_dir: Path | None = None,
    window_days: int = 14,
    max_rows_per_day: int = 2048,
    max_events: int = 900,
    min_overlap: int = 2,
    max_candidates_per_token: int = 80,
) -> dict[str, Any]:
    """Build and append one cross-day episodic thread snapshot row.

    The ledger is append-only and idempotent by source_hash.
    """

    state = _state_dir(state_dir)
    state.mkdir(parents=True, exist_ok=True)
    events = _collect_events(
        state,
        window_days=window_days,
        max_rows_per_day=max_rows_per_day,
        max_events=max_events,
    )
    if not events:
        return {}

    source_signature = [
        {
            "row_id": ev["row_id"],
            "local_date": ev["local_date"],
            "label": ev["local_journal_label"],
            "tokens": ev["tokens"][:10],
        }
        for ev in events
    ]
    source_hash = _stable_hash(source_signature)
    latest = _latest_row(state)
    if str(latest.get("source_hash") or "") == source_hash:
        return {}

    threads = _build_threads(
        events,
        min_overlap=max(1, int(min_overlap)),
        max_candidates_per_token=max(8, int(max_candidates_per_token)),
    )
    row = {
        "ts": time.time(),
        "truth_label": TRUTH_LABEL,
        "window_days": int(window_days),
        "journal_event_count": len(events),
        "thread_count": len(threads),
        "source_hash": source_hash,
        "threads": threads[:16],
    }
    append_line_locked(
        state / THREAD_LEDGER,
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n",
    )
    return row


def latest_threads(*, state_dir: Path | None = None) -> dict[str, Any]:
    return _latest_row(_state_dir(state_dir))


def format_latest_threads_for_prompt(*, state_dir: Path | None = None, max_threads: int = 4) -> str:
    row = latest_threads(state_dir=state_dir)
    if not row:
        return ""
    threads = row.get("threads") if isinstance(row.get("threads"), list) else []
    if not threads:
        return ""
    lines = ["EPISODIC THREADS (cross-day links):"]
    for thread in threads[: max(1, int(max_threads))]:
        if not isinstance(thread, dict):
            continue
        topic = ",".join(str(x) for x in thread.get("topic_tokens", [])[:5]) or "unknown"
        lines.append(
            f"- thread={thread.get('thread_id')} days={thread.get('day_count')} "
            f"events={thread.get('event_count')} topic={topic}"
        )
        latest_ref = ""
        refs = thread.get("refs") if isinstance(thread.get("refs"), list) else []
        if refs:
            latest_ref = str(refs[-1])
        if latest_ref:
            lines.append(f"  latest_ref={latest_ref}")
        latest_entry = str(thread.get("latest_entry") or "").strip()
        if latest_entry:
            lines.append(f"  latest_entry={latest_entry[:180]}")
    lines.append(
        f"Receipt: {THREAD_LEDGER} source_hash={row.get('source_hash')} "
        f"thread_count={row.get('thread_count')}"
    )
    return "\n".join(lines)


__all__ = [
    "TRUTH_LABEL",
    "THREAD_LEDGER",
    "latest_threads",
    "format_latest_threads_for_prompt",
    "write_episodic_threads",
]

