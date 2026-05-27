#!/usr/bin/env python3
"""Rolling episodic diary compressor for Alice.

Event 118: compress the day's trace soup into durable 2-4 hour story blocks.

The explicit day-segment ledger fixes user-stated blocks such as
"I slept from 11am to 3pm".  This module handles the broader case: Alice should
also keep a rolling diary from traces that already happened, even when George
does not narrate the schedule perfectly.

No raw private transcript expansion happens here.  The compressor keeps bounded
hashes, labels, source counts, and short facts suitable for prompt context.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from System.jsonl_file_lock import append_line_locked


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
DIARY = STATE_DIR / "episodic_diary.jsonl"
APPS_MANIFEST = REPO_ROOT / "Applications" / "apps_manifest.json"
APP_INVENTORY_LEDGER = STATE_DIR / "app_inventory_memory.jsonl"

TRUTH_LABEL = "EPISODIC_DIARY_SUMMARY_V1"
APP_INVENTORY_TRUTH_LABEL = "ALICE_APP_INVENTORY_MEMORY_V1"
PROMPT_CACHE_TTL_SECONDS = 30.0
_PROMPT_CACHE: dict[tuple[str, int, int, int], tuple[float, str]] = {}
DEFAULT_SOURCES = (
    "architect_day_segments.jsonl",
    "body_brain_memory.jsonl",
    "ide_stigmergic_trace.jsonl",
    "sifta_desktop_app_state.jsonl",
    "app_focus.jsonl",
    "app_focus_attention_receipts.jsonl",
    "media_session_memory.jsonl",
    "media_ingress_gate.jsonl",
    "youtube_context.jsonl",
    "youtube_watch_memory.jsonl",
    # George 2026-05-24: Alice must read/learn/write her diary about what she
    # actually lived — including delegating to her external cortexes. These
    # ledgers carry the tournament: what she asked Grok/Claude/Hermes to build,
    # what they returned, and whether the build verified. Sourcing them here means
    # the diary consolidator metabolizes those events into her episodic memory
    # (read → summarize/learn → write), and they flow back into her prompt — so
    # she remembers "I asked Claude to build Sudoku; it crashed; Claude fixed it,"
    # not just a forgotten tool receipt. Stigmergic unified-field consciousness, wired.
    "agent_arm_receipts.jsonl",
    "build_verification.jsonl",
    "work_receipts.jsonl",
    "app_inventory_memory.jsonl",
    "go_receipts.jsonl",
    "sudoku_receipts.jsonl",
    "jigsaw_receipts.jsonl",
)

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_'-]{3,}")
_STOPWORDS = {
    "about",
    "actual",
    "alice",
    "ambient",
    "because",
    "context",
    "direct",
    "george",
    "media",
    "observed",
    "receipt",
    "reason",
    "source",
    "state",
    "that",
    "this",
    "truth",
    "youtube",
}


def _state_dir(state_dir: Path | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else STATE_DIR


def _is_default_state_dir(state_dir: Path) -> bool:
    try:
        return Path(state_dir).resolve() == STATE_DIR.resolve()
    except Exception:
        return False


def _tail_jsonl(path: Path, max_rows: int = 1024) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = path.read_bytes().splitlines()[-max(1, int(max_rows)) :]
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


def read_rows(path: Path, *, max_rows: int = 1024) -> list[dict[str, Any]]:
    """Public bounded JSONL reader used by tests and small tools."""

    return _tail_jsonl(Path(path), max_rows=max_rows)


def row_ts(row: Mapping[str, Any]) -> float:
    """Return best-effort row timestamp in seconds."""

    for key in ("ts", "timestamp", "birth_ts", "deposit_time"):
        try:
            value = float(row[key])
        except Exception:
            continue
        if value > 10_000_000_000:  # timestamp_ms style
            value /= 1000.0
        return value
    try:
        return float(row.get("timestamp_ms", 0.0)) / 1000.0
    except Exception:
        return 0.0


def _local_midnight_ts(now: float | None = None) -> float:
    lt = time.localtime(float(now if now is not None else time.time()))
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, lt.tm_wday, lt.tm_yday, lt.tm_isdst))


def _minute_range_to_ts(row: Mapping[str, Any], *, fallback_ts: float) -> tuple[float, float] | None:
    """Use architect_day_segments minute-of-day fields when available."""

    try:
        start_min = int(row["start_minute_of_day"])
        end_min = int(row["end_minute_of_day"])
    except Exception:
        return None
    local_date = str(row.get("local_date") or "").strip()
    try:
        if local_date:
            base_dt = datetime.strptime(local_date, "%Y-%m-%d")
            base = time.mktime((base_dt.year, base_dt.month, base_dt.day, 0, 0, 0, 0, 0, -1))
        else:
            base = _local_midnight_ts(fallback_ts)
    except Exception:
        base = _local_midnight_ts(fallback_ts)
    if end_min < start_min:
        end_min += 24 * 60
    return base + start_min * 60.0, base + end_min * 60.0


def bucket_key(ts: float, hours: int = 4) -> str:
    if hours <= 0 or hours > 24:
        raise ValueError("hours must be in 1..24")
    dt = datetime.fromtimestamp(float(ts))
    start_hour = (dt.hour // hours) * hours
    return f"{dt.date().isoformat()}T{start_hour:02d}:00"


def _bucket_start_ts(key: str) -> float:
    dt = datetime.strptime(key, "%Y-%m-%dT%H:%M")
    return time.mktime((dt.year, dt.month, dt.day, dt.hour, dt.minute, 0, 0, 0, -1))


def _bucket_keys_for_row(row: Mapping[str, Any], *, hours: int, now: float) -> list[str]:
    ts = row_ts(row)
    if not ts:
        return []
    span = _minute_range_to_ts(row, fallback_ts=ts)
    if not span:
        return [bucket_key(ts, hours)]
    start, end = span
    if end <= start:
        return [bucket_key(start, hours)]
    keys: list[str] = []
    step = max(1, int(hours)) * 3600.0
    cursor = _bucket_start_ts(bucket_key(start, hours))
    while cursor <= end:
        bkey = bucket_key(cursor, hours)
        b_start = _bucket_start_ts(bkey)
        b_end = b_start + step
        if start < b_end and end > b_start:
            keys.append(bkey)
        cursor += step
    return keys or [bucket_key(start, hours)]


def _short(value: Any, limit: int = 220) -> str:
    return " ".join(str(value or "").split())[:limit]


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _manifest_apps(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return a deterministic numbered catalog from Applications/apps_manifest.json.

    The current manifest is flat (title -> app metadata), but older/experimental
    manifests have appeared as category -> title -> metadata. Accept both shapes
    so Alice's app memory keeps working while the app store evolves.
    """

    apps: list[dict[str, Any]] = []

    def add_app(title: str, meta: Mapping[str, Any], *, category_hint: str = "") -> None:
        if meta.get("_retired") or meta.get("hidden") or meta.get("enabled") is False:
            return
        title = str(meta.get("title") or meta.get("name") or title).strip()
        if not title:
            return
        category = str(meta.get("category") or category_hint or "Uncategorized").strip() or "Uncategorized"
        entry_point = str(meta.get("entry_point") or meta.get("file") or "").strip()
        widget_class = str(meta.get("widget_class") or meta.get("class") or "").strip()
        apps.append(
            {
                "title": _short(title, 120),
                "category": _short(category, 80),
                "entry_point": _short(entry_point, 180),
                "widget_class": _short(widget_class, 120),
                "description": _short(meta.get("description") or meta.get("summary") or "", 240),
                "icon": _short(meta.get("icon") or "", 24),
            }
        )

    for key, value in manifest.items():
        if not isinstance(value, Mapping):
            continue
        if "entry_point" in value or "widget_class" in value or "file" in value:
            add_app(str(key), value)
            continue
        for nested_key, nested_value in value.items():
            if isinstance(nested_value, Mapping):
                add_app(str(nested_key), nested_value, category_hint=str(key))

    apps.sort(key=lambda row: (str(row.get("category") or "").casefold(), str(row.get("title") or "").casefold()))
    for idx, app in enumerate(apps, start=1):
        app["number"] = idx
    return apps


def _app_inventory_hash(apps: list[dict[str, Any]]) -> str:
    payload = json.dumps(apps, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8", errors="replace")).hexdigest()[:16]


def _latest_app_inventory_row(state_dir: Path) -> dict[str, Any] | None:
    for row in reversed(_tail_jsonl(state_dir / "app_inventory_memory.jsonl", 128)):
        if row.get("truth_label") == APP_INVENTORY_TRUTH_LABEL:
            return row
    return None


def refresh_app_inventory_memory(
    *,
    state_dir: Path | None = None,
    manifest_path: Path | None = None,
    now: float | None = None,
) -> dict[str, Any] | None:
    """Write Alice's numbered app catalog into the shared diary/memory field.

    This is the stable "all apps can be talked about from global chat" bridge:
    the app store remains the source of truth, and the diary keeps an idempotent
    numbered snapshot whenever that source changes.
    """

    state = _state_dir(state_dir)
    manifest_file = Path(manifest_path) if manifest_path is not None else APPS_MANIFEST
    manifest = _load_json(manifest_file)
    if not isinstance(manifest, Mapping):
        return None
    apps = _manifest_apps(manifest)
    if not apps:
        return None
    manifest_hash = _app_inventory_hash(apps)
    latest = _latest_app_inventory_row(state)
    if latest and str(latest.get("manifest_hash") or "") == manifest_hash:
        return latest

    now_ts = float(now if now is not None else time.time())
    row = {
        "ts": now_ts,
        "truth_label": APP_INVENTORY_TRUTH_LABEL,
        "event_type": "app_inventory_snapshot",
        "source": str(manifest_file),
        "app_count": len(apps),
        "manifest_hash": manifest_hash,
        "summary": (
            f"Alice knows {len(apps)} numbered SIFTA apps from apps_manifest.json; "
            "one global chat can discuss any app by name or number."
        ),
        "apps": apps,
    }
    state.mkdir(parents=True, exist_ok=True)
    append_line_locked(state / "app_inventory_memory.jsonl", json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return row


def _row_digest(row: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "truth_label",
        "event_type",
        "label",
        "location",
        "media_context",
        "context_note",
        "title",
        "video_id",
        "youtube_video_id",
        "route",
        "reason",
        "action",
        "app",
        "app_name",
        "active_app",
        "open_app_count",
        "open_apps",
        "desktop_mode",
        "detail",
        "tab",
        "selection",
        "metadata",
        "category",
        "entry_point",
        "widget_class",
        "description",
        "app_count",
        "manifest_hash",
        "verdict",
        "title",
        "file",
        "status",
        "ok",
        "receipt_id",
        "summary",
        "kind",
        "payload",
        "metabolic_mode",
        "allostatic_policy",
        "allostatic_load",
        "regime",
    )
    out: dict[str, Any] = {}
    for key in keys:
        if key in row and row.get(key) not in ("", None):
            out[key] = _short(row.get(key), 260)
    source = str(row.get("_source") or "")
    if source:
        out["_source"] = Path(source).name
    return out


def _labels_for_text(text: str) -> set[str]:
    low = text.lower()
    labels: set[str] = set()
    if re.search(r"\b(?:sleep|slept|nap|napped|napping|asleep|rest)\b", low):
        labels.add("sleep")
    if re.search(r"\b(?:youtube|video|media|tv|television|caption|cowatch)\b", low):
        labels.add("media")
    if re.search(r"\b(?:commit|pytest|test|coding|codex|cursor|antigravity|ide_stigmergic)\b", low):
        labels.add("coding")
    if re.search(r"\b(?:app_focus|app_inventory|apps_manifest|desktop_app_state|open_app|close_app|build_verified|manifest_entry|widget_class|entry_point)\b", low):
        labels.add("apps")
        labels.add("os_body")
    if re.search(r"\b(?:sudoku|go_receipts|stigmergic go|stigmergic sudoku|jigsaw|maze|brood)\b", low):
        labels.add("stigmergic_apps")
    if re.search(r"\b(?:body_brain|homeostasis|allostatic|metabolic|regime|physiology)\b", low):
        labels.add("alice_physiology")
    if re.search(r"\b(?:rlhs|rlhf|fiction|movie|snatch|brick)\b", low):
        labels.add("fiction_boundary")
    return labels


def summarize_bucket(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    digests = [_row_digest(row) for row in rows]
    text = " ".join(json.dumps(d, sort_keys=True, ensure_ascii=False) for d in digests)
    source_hash = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]
    labels = _labels_for_text(text)
    if any(d.get("title") or d.get("video_id") or d.get("youtube_video_id") or d.get("route") for d in digests):
        labels.add("media")

    source_counts = Counter(str(d.get("_source") or "unknown") for d in digests)
    facts: list[str] = []
    for d in digests:
        label = str(d.get("label") or "")
        loc = str(d.get("location") or "")
        media = str(d.get("media_context") or "")
        note = str(d.get("context_note") or "")
        title = str(d.get("title") or "")
        video_id = str(d.get("video_id") or d.get("youtube_video_id") or "")
        app = str(d.get("app") or d.get("app_name") or d.get("active_app") or "")
        detail = str(d.get("detail") or d.get("selection") or d.get("tab") or "")
        action = str(d.get("action") or "")
        app_count = str(d.get("app_count") or "")
        manifest_hash = str(d.get("manifest_hash") or "")
        verdict = str(d.get("verdict") or "")
        file = str(d.get("file") or d.get("entry_point") or "")
        if app:
            bits = [f"app={app}"]
            if action:
                bits.append(f"action={action}")
            if detail:
                bits.append(detail[:120])
            fact = " ".join(bits)
        elif app_count and manifest_hash:
            fact = f"app_inventory {app_count} apps manifest={manifest_hash}"
        elif verdict and title:
            fact = f"build {title} {verdict}"
            if file:
                fact += f" file={file}"
        elif label:
            bits = [label]
            if loc:
                bits.append(f"loc={loc}")
            if media:
                bits.append(f"media={media}")
            if note:
                bits.append(note[:120])
            fact = " ".join(bits)
        elif title or video_id:
            fact = f"video {title or video_id}"
            if video_id:
                fact += f" [{video_id}]"
        else:
            fact = ""
        if fact and fact not in facts:
            facts.append(fact)
        if len(facts) >= 6:
            break

    token_counts: Counter[str] = Counter()
    for token in _WORD_RE.findall(text):
        low = token.lower()
        if low not in _STOPWORDS:
            token_counts[low] += 1
    keywords = [w for w, n in token_counts.most_common(10) if n >= 2]
    ordered_labels = sorted(labels) or ["ambient"]
    return {
        "source_hash": source_hash,
        "event_count": len(digests),
        "source_counts": dict(source_counts),
        "labels": ordered_labels,
        "summary": "; ".join(ordered_labels),
        "facts": facts,
        "keywords": keywords,
    }


def _source_paths(state_dir: Path) -> list[Path]:
    if _is_default_state_dir(state_dir):
        refresh_app_inventory_memory(state_dir=state_dir)
    return [state_dir / name for name in DEFAULT_SOURCES]


def _existing_diary_hashes(path: Path) -> set[tuple[str, int, str]]:
    out: set[tuple[str, int, str]] = set()
    for row in _tail_jsonl(path, 4096):
        try:
            out.add((str(row.get("bucket")), int(row.get("window_hours")), str(row.get("source_hash"))))
        except Exception:
            continue
    return out


def write_episodic_diary(
    hours: int = 4,
    *,
    state_dir: Path | None = None,
    since_ts: float | None = None,
    now: float | None = None,
) -> list[dict[str, Any]]:
    """Compress recent/today ledgers into append-only diary bucket rows.

    Rows are idempotent by (bucket, window_hours, source_hash). If the same
    source evidence was already summarized, no duplicate is appended.
    """

    if hours <= 0 or hours > 24:
        raise ValueError("hours must be in 1..24")
    state = _state_dir(state_dir)
    now_ts = float(now if now is not None else time.time())
    since = float(since_ts if since_ts is not None else _local_midnight_ts(now_ts))
    all_rows: list[dict[str, Any]] = []
    for path in _source_paths(state):
        for row in read_rows(path):
            ts = row_ts(row)
            span = _minute_range_to_ts(row, fallback_ts=ts or now_ts)
            include_ts = span[1] if span else ts
            if include_ts and include_ts >= since:
                copy = dict(row)
                copy["_source"] = str(path)
                copy["_ts"] = ts
                all_rows.append(copy)

    buckets: dict[str, list[dict[str, Any]]] = {}
    for row in all_rows:
        for key in _bucket_keys_for_row(row, hours=hours, now=now_ts):
            buckets.setdefault(key, []).append(row)

    state.mkdir(parents=True, exist_ok=True)
    diary_path = state / "episodic_diary.jsonl"
    existing = _existing_diary_hashes(diary_path)
    written: list[dict[str, Any]] = []

    for key, rows in sorted(buckets.items()):
        summary = summarize_bucket(rows)
        marker = (key, int(hours), str(summary["source_hash"]))
        if marker in existing:
            continue
        row = {
            "ts": now_ts,
            "truth_label": TRUTH_LABEL,
            "bucket": key,
            "window_hours": int(hours),
            **summary,
        }
        append_line_locked(diary_path, json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        written.append(row)
        existing.add(marker)
    return written


def _latest_rows_for_prompt(state_dir: Path, *, max_rows: int = 6) -> list[dict[str, Any]]:
    rows = _tail_jsonl(state_dir / "episodic_diary.jsonl", 2048)
    latest: dict[tuple[str, int], dict[str, Any]] = {}
    for row in rows:
        key = (str(row.get("bucket") or ""), int(row.get("window_hours") or 0))
        if not key[0]:
            continue
        if key not in latest or float(row.get("ts", 0.0) or 0.0) >= float(latest[key].get("ts", 0.0) or 0.0):
            latest[key] = row
    return sorted(latest.values(), key=lambda r: str(r.get("bucket") or ""))[-max_rows:]


def format_diary_for_prompt(*, state_dir: Path | None = None, max_rows: int = 6) -> str:
    state = _state_dir(state_dir)
    rows = _latest_rows_for_prompt(state, max_rows=max_rows)
    if not rows:
        return ""
    lines = ["EPISODIC DIARY (rolling local day-story summaries):"]
    for row in rows:
        labels = ",".join(str(x) for x in row.get("labels", [])[:5]) or "ambient"
        facts = row.get("facts") if isinstance(row.get("facts"), list) else []
        fact_text = " | ".join(str(f)[:120] for f in facts[:3])
        suffix = f" — {fact_text}" if fact_text else ""
        lines.append(
            f"- {row.get('bucket')}/{row.get('window_hours')}h "
            f"labels={labels} events={row.get('event_count', 0)}{suffix}"
        )
    return "\n".join(lines)


def format_app_inventory_for_prompt(
    *,
    state_dir: Path | None = None,
    max_apps: int = 24,
) -> str:
    state = _state_dir(state_dir)
    row = _latest_app_inventory_row(state)
    if row is None:
        row = refresh_app_inventory_memory(state_dir=state)
    if not row:
        return ""
    apps = row.get("apps") if isinstance(row.get("apps"), list) else []
    categories = Counter(str(app.get("category") or "Uncategorized") for app in apps if isinstance(app, Mapping))
    category_text = ", ".join(f"{name}:{count}" for name, count in categories.most_common(12))
    lines = [
        "ALICE APP INVENTORY (bounded prompt view; full numbered catalog is in .sifta_state/app_inventory_memory.jsonl):"
    ]
    if category_text:
        lines.append(f"- Total apps={row.get('app_count')} categories={category_text}")
    lines.append("- one global chat can discuss any app by name or number; load the full ledger when exact long-tail details are needed.")
    for app in apps[: max(1, int(max_apps))]:
        if not isinstance(app, Mapping):
            continue
        number = int(app.get("number") or 0)
        title = _short(app.get("title"), 80)
        category = _short(app.get("category"), 40)
        entry = _short(app.get("entry_point"), 96)
        widget = _short(app.get("widget_class"), 64)
        lines.append(f"- #{number:03d} {title} [{category}] entry={entry} class={widget}")
    extra = max(0, int(row.get("app_count") or len(apps)) - len(lines) + 1)
    if extra:
        lines.append(f"- ... {extra} more apps in app_inventory_memory.jsonl")
    lines.append(f"Receipt: app_count={row.get('app_count')} manifest_hash={row.get('manifest_hash')}")
    return "\n".join(lines)


def refresh_and_format_diary_for_prompt(
    *,
    hours: int = 4,
    state_dir: Path | None = None,
    max_rows: int = 6,
    max_apps: int = 24,
    force: bool = False,
) -> str:
    state = _state_dir(state_dir)
    cache_key = (str(state.resolve()) if state.exists() else str(state), int(hours), int(max_rows), int(max_apps))
    now_ts = time.time()
    if not force and _is_default_state_dir(state):
        cached = _PROMPT_CACHE.get(cache_key)
        if cached and (now_ts - cached[0]) < PROMPT_CACHE_TTL_SECONDS:
            return cached[1]
    if _is_default_state_dir(state):
        refresh_app_inventory_memory(state_dir=state)
    write_episodic_diary(hours=hours, state_dir=state)
    thread_block = ""
    try:
        from System.swarm_episodic_thread_linker import (
            format_latest_threads_for_prompt,
            write_episodic_threads,
        )

        write_episodic_threads(state_dir=state, window_days=14)
        thread_block = format_latest_threads_for_prompt(state_dir=state, max_threads=max_rows)
    except Exception:
        thread_block = ""
    blocks = [
        format_diary_for_prompt(state_dir=state, max_rows=max_rows),
        thread_block,
        format_app_inventory_for_prompt(state_dir=state, max_apps=max_apps),
    ]
    prompt = "\n\n".join(block for block in blocks if block)
    if _is_default_state_dir(state):
        _PROMPT_CACHE[cache_key] = (now_ts, prompt)
    return prompt


__all__ = [
    "DIARY",
    "APP_INVENTORY_LEDGER",
    "APP_INVENTORY_TRUTH_LABEL",
    "TRUTH_LABEL",
    "bucket_key",
    "format_app_inventory_for_prompt",
    "format_diary_for_prompt",
    "read_rows",
    "refresh_app_inventory_memory",
    "refresh_and_format_diary_for_prompt",
    "row_ts",
    "summarize_bucket",
    "write_episodic_diary",
]


if __name__ == "__main__":
    print(json.dumps(write_episodic_diary(), indent=2, ensure_ascii=False))
