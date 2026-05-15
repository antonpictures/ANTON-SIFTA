#!/usr/bin/env python3
"""Global stigmergic segment index for Alice.

This organ fuses already-written receipts into one countable segment ledger.
It does not invent phone contacts, speech identity, or location. It counts only
what local ledgers already contain: owner dialogue, media/YouTube receipts,
desktop focus, voice exemplars, schedule/body rows, per-turn physical substrate
snapshots (serial + GPS cache age + frontmost app), GPS latest, and RLHS rows.
"""
from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

from System.jsonl_file_lock import append_line_locked


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
LEDGER = STATE_DIR / "global_segment_index.jsonl"
LATEST = STATE_DIR / "global_segment_index_latest.json"
TRUTH_LABEL = "GLOBAL_STIGMERGIC_SEGMENT_INDEX_V1"

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9'_-]{2,}")
_STOP = {
    "about",
    "active",
    "alice",
    "already",
    "and",
    "are",
    "audio",
    "camera",
    "context",
    "direct",
    "from",
    "george",
    "has",
    "media",
    "now",
    "owner",
    "python",
    "receipt",
    "source",
    "that",
    "the",
    "this",
    "truth",
    "with",
    "youtube",
}


def _state_dir(state_dir: Path | str | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else STATE_DIR


def _tail_jsonl(path: Path, n: int = 256, *, max_bytes: int = 1024 * 1024) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        with path.open("rb") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            start = max(0, size - max_bytes)
            handle.seek(start)
            lines = handle.read().splitlines()
    except OSError:
        return []
    if start > 0 and lines:
        lines = lines[1:]
    rows: list[dict[str, Any]] = []
    for raw in lines[-max(1, int(n)) :]:
        try:
            row = json.loads(raw.decode("utf-8", errors="replace"))
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _row_ts(row: Mapping[str, Any]) -> float:
    for key in ("ts", "timestamp", "created", "ts_captured", "last_alive_ts"):
        try:
            value = float(row.get(key, 0.0) or 0.0)
        except Exception:
            continue
        if value > 0:
            return value / 1000.0 if value > 10_000_000_000 else value
    return 0.0


def _local_day(ts: float) -> str:
    if ts <= 0:
        return "unknown_day"
    return time.strftime("%Y-%m-%d", time.localtime(ts))


def _hour_bucket(ts: float) -> str:
    if ts <= 0:
        return "unknown_hour"
    return time.strftime("%Y-%m-%dT%H:00", time.localtime(ts))


def _compact(value: Any, limit: int = 220) -> str:
    return " ".join(str(value or "").split())[:limit]


def _terms(*texts: Any, limit: int = 12) -> list[str]:
    counts: Counter[str] = Counter()
    for text in texts:
        for token in _TOKEN_RE.findall(str(text or "")):
            low = token.lower()
            if low in _STOP:
                continue
            counts[low[:40]] += 1
    return [term for term, _count in counts.most_common(limit)]


def _segment(
    *,
    source_kind: str,
    source_file: str,
    row: Mapping[str, Any],
    source_label: str = "",
    category: str = "",
    text: str = "",
    confidence: float | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    ts = _row_ts(row)
    seg: dict[str, Any] = {
        "source_kind": source_kind,
        "source_file": source_file,
        "source_label": _compact(source_label or source_kind, 80),
        "category": _compact(category or source_label or source_kind, 120),
        "row_ts": ts,
        "local_day": _local_day(ts),
        "hour_bucket": _hour_bucket(ts),
        "text_preview": _compact(text, 260),
        "terms": _terms(text),
    }
    if confidence is not None:
        try:
            seg["confidence"] = round(max(0.0, min(1.0, float(confidence))), 3)
        except Exception:
            pass
    if extra:
        for key, value in extra.items():
            if value not in (None, "", [], {}):
                seg[str(key)] = value
    return seg


def _youtube_category(row: Mapping[str, Any]) -> str:
    frame = row.get("reality_frame")
    if isinstance(frame, Mapping):
        return str(frame.get("content_category") or frame.get("reality_frame") or "youtube")
    direct = row.get("content_category") or frame
    if direct:
        return str(direct)
    return "youtube"


def _iter_segments(state: Path, *, max_rows_per_ledger: int) -> Iterable[dict[str, Any]]:
    for row in _tail_jsonl(state / "memory_ledger.jsonl", max_rows_per_ledger):
        tags = row.get("semantic_tags") if isinstance(row.get("semantic_tags"), list) else []
        yield _segment(
            source_kind="owner_dialogue",
            source_file="memory_ledger.jsonl",
            row=row,
            source_label=str(row.get("app_context") or "talk_to_alice"),
            category=str(tags[0]) if tags else "owner_dialogue",
            text=str(row.get("raw_text") or ""),
            extra={"semantic_tags": tags[:8]},
        )

    for row in _tail_jsonl(state / "media_ingress_gate.jsonl", max_rows_per_ledger):
        fp = row.get("acoustic_fingerprint") if isinstance(row.get("acoustic_fingerprint"), Mapping) else {}
        yield _segment(
            source_kind="audio_media_gate",
            source_file="media_ingress_gate.jsonl",
            row=row,
            source_label=str(row.get("route") or "audio"),
            category=str(row.get("reason") or row.get("route") or "audio"),
            text=str(row.get("text_preview") or row.get("focus_preview") or ""),
            confidence=float(row.get("confidence", row.get("stt_confidence", 0.0)) or 0.0),
            extra={
                "stt_confidence": row.get("stt_confidence"),
                "channel_cue": fp.get("channel_cue"),
            },
        )

    for filename, source_kind in (
        ("youtube_context.jsonl", "youtube_context"),
        ("youtube_watch_memory.jsonl", "youtube_watch"),
    ):
        for row in _tail_jsonl(state / filename, max_rows_per_ledger):
            title = row.get("title") or row.get("source_work") or ""
            yield _segment(
                source_kind=source_kind,
                source_file=filename,
                row=row,
                source_label=str(row.get("video_id") or row.get("youtube_video_id") or "youtube"),
                category=_youtube_category(row),
                text=str(title),
                extra={
                    "video_id": row.get("video_id") or row.get("youtube_video_id"),
                    "title": _compact(title, 180),
                    "url": _compact(row.get("url"), 260),
                    "caption_status": row.get("caption_status") or row.get("status"),
                },
            )

    for row in _tail_jsonl(state / "app_focus.jsonl", max_rows_per_ledger):
        meta = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
        yield _segment(
            source_kind="desktop_focus",
            source_file="app_focus.jsonl",
            row=row,
            source_label=str(row.get("app") or "focus"),
            category=str(meta.get("source") or row.get("app") or "focus"),
            text=f"{row.get('detail') or ''} {row.get('selection') or ''}",
            extra={"tab": row.get("tab"), "selection": _compact(row.get("selection"), 180)},
        )

    for row in _tail_jsonl(state / "voice_identity_ledger.jsonl", max_rows_per_ledger):
        label = str(row.get("source_label") or "unknown")
        yield _segment(
            source_kind="voice_exemplar",
            source_file="voice_identity_ledger.jsonl",
            row=row,
            source_label=label,
            category=f"voice_label:{label}",
            text=str(row.get("note") or row.get("display") or ""),
            extra={"display": row.get("display"), "duration_s": (row.get("features") or {}).get("duration_s") if isinstance(row.get("features"), Mapping) else None},
        )

    for row in _tail_jsonl(state / "stigmergic_schedule.jsonl", max_rows_per_ledger):
        yield _segment(
            source_kind="schedule",
            source_file="stigmergic_schedule.jsonl",
            row=row,
            source_label=str(row.get("source") or "schedule"),
            category="schedule",
            text=str(row.get("text") or ""),
            extra={"done": row.get("done"), "priority": row.get("priority")},
        )

    for row in _tail_jsonl(state / "architect_day_segments.jsonl", max_rows_per_ledger):
        yield _segment(
            source_kind="day_segment",
            source_file="architect_day_segments.jsonl",
            row=row,
            source_label=str(row.get("label") or "day_segment"),
            category=str(row.get("media_context") or row.get("location") or row.get("label") or "day_segment"),
            text=str(row.get("context_note") or row.get("raw_text") or ""),
            extra={
                "location": row.get("location"),
                "duration_minutes": row.get("duration_minutes"),
            },
        )

    for row in _tail_jsonl(state / "owner_body_events.jsonl", max_rows_per_ledger):
        yield _segment(
            source_kind="owner_body",
            source_file="owner_body_events.jsonl",
            row=row,
            source_label=str(row.get("event_type") or "body_event"),
            category=str(row.get("event_type") or "body_event"),
            text=str(row.get("note") or ""),
            extra={"status": row.get("status")},
        )

    for row in _tail_jsonl(state / "rlhs_events.jsonl", max_rows_per_ledger):
        yield _segment(
            source_kind="rlhs_turn",
            source_file="rlhs_events.jsonl",
            row=row,
            source_label=str(row.get("event_type") or "rlhs"),
            category=str(row.get("failure_mode") or row.get("event_type") or "rlhs"),
            text=f"{row.get('trigger') or ''} {row.get('result') or row.get('bad_response_pattern') or ''}",
            confidence=float(row.get("stt_conf", 0.0) or 0.0),
        )

    for row in _tail_jsonl(state / "architect_physical_substrate.jsonl", max_rows_per_ledger):
        gps_part = row.get("iphone_gps_latest") if isinstance(row.get("iphone_gps_latest"), Mapping) else {}
        focus = row.get("frontmost_app_focus") if isinstance(row.get("frontmost_app_focus"), Mapping) else {}
        parts = [
            f"channel={row.get('input_channel') or ''}",
            f"model={row.get('ollama_model') or ''}",
        ]
        if focus.get("app"):
            parts.append(f"front={focus.get('app')}")
        age = gps_part.get("age_s")
        if age is not None:
            parts.append(f"gps_age_s={age}")
        yield _segment(
            source_kind="physical_substrate",
            source_file="architect_physical_substrate.jsonl",
            row=row,
            source_label=str(row.get("homeworld_serial") or "substrate"),
            category="architect_physical_substrate",
            text=" ".join(parts),
            extra={
                "homeworld_serial": row.get("homeworld_serial"),
                "input_channel": row.get("input_channel"),
                "ollama_model": row.get("ollama_model"),
                "gps_age_s": age,
                "front_app": focus.get("app"),
            },
        )

    gps = _read_json(state / "iphone_gps_latest.json")
    if gps:
        payload = gps.get("payload") if isinstance(gps.get("payload"), Mapping) else {}
        yield _segment(
            source_kind="location_latest",
            source_file="iphone_gps_latest.json",
            row=gps,
            source_label=str(gps.get("carrier") or "iphone_gps"),
            category="location_fix",
            text=f"iphone_gps accuracy={payload.get('accuracy')}",
            extra={
                "location_available": bool(payload.get("latitude") and payload.get("longitude")),
                "accuracy_m": payload.get("accuracy"),
                "channel": gps.get("channel"),
            },
        )


def build_global_segment_index(
    *,
    state_dir: Path | str | None = None,
    max_rows_per_ledger: int = 240,
    write: bool = False,
) -> dict[str, Any]:
    """Build a countable cross-ledger segment index from local receipts."""
    state = _state_dir(state_dir)
    now_ts = time.time()
    segments = sorted(
        _iter_segments(state, max_rows_per_ledger=max_rows_per_ledger),
        key=lambda row: float(row.get("row_ts", 0.0) or 0.0),
    )

    source_counts = Counter(str(s.get("source_kind") or "unknown") for s in segments)
    category_counts = Counter(str(s.get("category") or "unknown") for s in segments)
    hour_counts = Counter(str(s.get("hour_bucket") or "unknown_hour") for s in segments)
    voice_counts = Counter(
        str(s.get("source_label") or "unknown")
        for s in segments
        if s.get("source_kind") == "voice_exemplar"
    )
    title_counts = Counter(
        str(s.get("title") or s.get("text_preview") or "")
        for s in segments
        if s.get("source_kind") in {"youtube_context", "youtube_watch"}
    )
    term_counts: Counter[str] = Counter()
    for seg in segments:
        for term in seg.get("terms") or []:
            term_counts[str(term)] += 1

    gps_seg = next((s for s in reversed(segments) if s.get("source_kind") == "location_latest"), {})
    unknowns = []
    if voice_counts.get("phone", 0) and not (state / "phone_call_segments.jsonl").exists():
        unknowns.append("phone_contact_identity_not_wired")
    if not (state / "architect_day_segments.jsonl").exists():
        unknowns.append("architect_day_segments_absent")
    if not (state / "architect_physical_substrate.jsonl").exists():
        unknowns.append("physical_substrate_ledger_absent")
    if not gps_seg:
        unknowns.append("live_location_not_available")
    else:
        unknowns.append("location_is_latest_fix_not_attached_to_every_segment")
    if not (state / "phone_call_segments.jsonl").exists():
        unknowns.append("speakerphone_call_metadata_not_wired")

    row = {
        "ts": now_ts,
        "truth_label": TRUTH_LABEL,
        "segment_count": len(segments),
        "source_counts": dict(source_counts.most_common()),
        "category_counts": dict(category_counts.most_common(20)),
        "hour_counts": dict(hour_counts.most_common(24)),
        "voice_label_counts": dict(voice_counts.most_common()),
        "top_youtube_titles": [
            {"title": title, "receipts": count}
            for title, count in title_counts.most_common(8)
            if title
        ],
        "top_terms": [
            {"term": term, "count": count}
            for term, count in term_counts.most_common(16)
        ],
        "latest_location": gps_seg,
        "last_segments": segments[-12:],
        "unknowns": unknowns,
        "source_ledgers": sorted(
            {
                str(seg.get("source_file"))
                for seg in segments
                if seg.get("source_file")
            }
        ),
    }

    if write:
        state.mkdir(parents=True, exist_ok=True)
        append_line_locked(
            state / "global_segment_index.jsonl",
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n",
        )
        try:
            (state / "global_segment_index_latest.json").write_text(
                json.dumps(row, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        except OSError:
            pass
    return row


def summary_for_prompt(
    *,
    state_dir: Path | str | None = None,
    max_rows_per_ledger: int = 240,
    write: bool = True,
) -> str:
    row = build_global_segment_index(
        state_dir=state_dir,
        max_rows_per_ledger=max_rows_per_ledger,
        write=write,
    )
    if int(row.get("segment_count") or 0) <= 0:
        return ""

    def _fmt_counts(counts: Mapping[str, Any], limit: int = 8) -> str:
        return ", ".join(f"{k}={v}" for k, v in list(counts.items())[:limit]) or "none"

    top_titles = row.get("top_youtube_titles") if isinstance(row.get("top_youtube_titles"), list) else []
    titles = " / ".join(
        f"{item.get('title')} receipts={item.get('receipts')}"
        for item in top_titles[:4]
        if isinstance(item, Mapping)
    )
    latest_location = row.get("latest_location") if isinstance(row.get("latest_location"), Mapping) else {}
    location_line = "none"
    if latest_location:
        location_line = (
            f"source={latest_location.get('source_label')} "
            f"accuracy_m={latest_location.get('accuracy_m')} "
            f"hour={latest_location.get('hour_bucket')}"
        )
    unknowns = ", ".join(str(x) for x in (row.get("unknowns") or [])[:6]) or "none"
    return "\n".join(
        [
            "GLOBAL STIGMERGIC SEGMENT INDEX:",
            f"- truth_label={TRUTH_LABEL}; segment_count={row.get('segment_count')}",
            f"- sources: {_fmt_counts(row.get('source_counts') or {})}",
            f"- categories: {_fmt_counts(row.get('category_counts') or {})}",
            f"- voice_labels: {_fmt_counts(row.get('voice_label_counts') or {})}",
            f"- youtube_titles: {titles or 'none'}",
            f"- latest_location: {location_line}",
            f"- unknowns: {unknowns}",
            "- rule=count only receipts; phone_contact_identity and per_segment_location stay unknown until those ledgers exist.",
        ]
    )


__all__ = [
    "TRUTH_LABEL",
    "build_global_segment_index",
    "summary_for_prompt",
]


if __name__ == "__main__":
    print(summary_for_prompt())
