#!/usr/bin/env python3
"""Unified owner/OS/media field for Alice prompt grounding.

This organ answers one narrow question before the LLM speaks:

    What is George doing across SIFTA OS, the hosted desktop, and media organs?

It does not identify media by magic. It fuses bounded receipts from app focus,
hosted OS focus, YouTube/media ledgers, and Stigmergic Unified Shazam into one
small current-situation packet. Alice can then reason from the packet instead
of claiming she has no video context while another SIFTA app is visibly open.

Truth label: UNIFIED_STIGMERGIC_FIELD_V1
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Mapping

from System.jsonl_file_lock import append_line_locked


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
LEDGER = STATE_DIR / "unified_stigmergic_field.jsonl"
LATEST = STATE_DIR / "unified_stigmergic_field_latest.json"
TRUTH_LABEL = "UNIFIED_STIGMERGIC_FIELD_V1"

APP_FOCUS_MAX_AGE_S = 5 * 60.0
HOST_FOCUS_MAX_AGE_S = 5 * 60.0
MEDIA_MAX_AGE_S = 6 * 3600.0


def _clamp01(value: float) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return 0.0


def _tail_jsonl(path: Path, n: int = 1) -> list[dict[str, Any]]:
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


def _read_json(path: Path) -> dict[str, Any]:
    try:
        row = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return row if isinstance(row, dict) else {}


def _row_ts(row: Mapping[str, Any]) -> float:
    for key in ("ts", "timestamp", "timestamp_s", "last_ts", "birth_ts"):
        try:
            value = float(row.get(key, 0.0) or 0.0)
        except Exception:
            continue
        if value > 0:
            return value / 1000.0 if value > 10_000_000_000 else value
    return 0.0


def _latest_jsonl(path: Path) -> dict[str, Any]:
    rows = _tail_jsonl(path, 1)
    return rows[-1] if rows else {}


def _latest_focus_rows(state_dir: Path, now: float) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (sifta_app_focus, hosted_os_focus_from_focus_ledger).

    app_focus.jsonl is shared by both internal SIFTA apps and the hosted macOS
    active-window observer. A plain last-row read lets Python/Electron shadow the
    selected SIFTA subwindow. This function splits the stream into biological
    channels: internal organ focus versus host shell focus.
    """
    rows = _tail_jsonl(state_dir / "app_focus.jsonl", 96)
    fresh = [
        row
        for row in rows
        if _freshness(row, now, APP_FOCUS_MAX_AGE_S) > 0.0
    ]
    if not fresh:
        return {}, {}

    def _source(row: Mapping[str, Any]) -> str:
        meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        return str(meta.get("source") or "")

    host_rows = [row for row in fresh if _source(row) == "swarm_active_window"]
    internal_rows = [row for row in fresh if _source(row) != "swarm_active_window"]

    # Strongest internal cue: the actual MDI activation from SIFTA OS.
    for row in reversed(internal_rows):
        meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        if meta.get("source") == "sifta_os_desktop" or meta.get("event") == "subwindow_activated":
            return row, (host_rows[-1] if host_rows else {})

    # Then any explicit app organ publishing focus, with Shazam preferred for co-watch.
    for row in reversed(internal_rows):
        if "shazam" in str(row.get("app") or "").casefold():
            return row, (host_rows[-1] if host_rows else {})
    if internal_rows:
        return internal_rows[-1], (host_rows[-1] if host_rows else {})
    return {}, (host_rows[-1] if host_rows else {})


def _age_s(row: Mapping[str, Any], now: float) -> float | None:
    ts = _row_ts(row)
    if ts <= 0:
        return None
    return max(0.0, now - ts)


def _freshness(row: Mapping[str, Any], now: float, max_age_s: float) -> float:
    age = _age_s(row, now)
    if age is None:
        return 0.0
    return _clamp01(1.0 - age / max(1.0, max_age_s))


def _app_focus_packet(row: Mapping[str, Any], now: float) -> dict[str, Any]:
    meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    return {
        "app": str(row.get("app") or ""),
        "detail": str(row.get("detail") or ""),
        "tab": str(row.get("tab") or ""),
        "selection": str(row.get("selection") or ""),
        "metadata": {
            str(k): v
            for k, v in meta.items()
            if k
            in {
                "primary_category",
                "confidence",
                "acoustic_scene",
                "acoustic_scene_confidence",
                "evidence_rows",
                "event",
                "source",
            }
        },
        "age_s": _age_s(row, now),
        "freshness": round(_freshness(row, now, APP_FOCUS_MAX_AGE_S), 4),
    }


def _host_focus_packet(row: Mapping[str, Any], now: float) -> dict[str, Any]:
    keys = (
        "app",
        "frontmost_app",
        "window",
        "frontmost_window",
        "title",
        "url",
        "browser_url",
        "video_id",
        "youtube_video_id",
        "kind",
        "source",
    )
    packet = {k: row.get(k) for k in keys if row.get(k) not in (None, "")}
    packet["age_s"] = _age_s(row, now)
    packet["freshness"] = round(_freshness(row, now, HOST_FOCUS_MAX_AGE_S), 4)
    return packet


def _media_packet(row: Mapping[str, Any], now: float) -> dict[str, Any]:
    return {
        "primary_category": str(row.get("primary_category") or ""),
        "confidence": _clamp01(float(row.get("confidence", 0.0) or 0.0)),
        "source_type": str(row.get("source_type") or ""),
        "source_label": str(row.get("source_label") or ""),
        "title_guess": str(row.get("title_guess") or ""),
        "source_work": str(row.get("source_work") or ""),
        "director": str(row.get("director") or ""),
        "acoustic_scene": str(row.get("acoustic_scene") or ""),
        "acoustic_scene_confidence": _clamp01(
            float(row.get("acoustic_scene_confidence", 0.0) or 0.0)
        ),
        "evidence_rows": int(row.get("evidence_rows", 0) or 0),
        "source_ledgers": list(row.get("source_ledgers") or [])[:12],
        "age_s": _age_s(row, now),
        "freshness": round(_freshness(row, now, MEDIA_MAX_AGE_S), 4),
    }


def _youtube_packet(row: Mapping[str, Any], now: float) -> dict[str, Any]:
    keys = (
        "title",
        "channel",
        "url",
        "video_id",
        "youtube_video_id",
        "reality_frame",
        "content_category",
        "source_work",
        "director",
        "dialogue_boundary",
    )
    packet = {k: row.get(k) for k in keys if row.get(k) not in (None, "")}
    packet["age_s"] = _age_s(row, now)
    packet["freshness"] = round(_freshness(row, now, MEDIA_MAX_AGE_S), 4)
    return packet


def _observed_media_packet(row: Mapping[str, Any], now: float) -> dict[str, Any]:
    keys = (
        "route",
        "reason",
        "reality_frame",
        "source",
        "content_category",
        "media_context",
        "text_preview",
    )
    packet = {k: row.get(k) for k in keys if row.get(k) not in (None, "")}
    packet["age_s"] = _age_s(row, now)
    packet["freshness"] = round(_freshness(row, now, MEDIA_MAX_AGE_S), 4)
    return packet


def _best_media_row(state_dir: Path) -> dict[str, Any]:
    latest = _read_json(state_dir / "media_shazam_latest.json")
    if latest:
        return latest
    return _latest_jsonl(state_dir / "media_shazam_guesses.jsonl")


def _best_youtube_row(state_dir: Path) -> dict[str, Any]:
    latest = _read_json(state_dir / "youtube_context_latest.json")
    if latest:
        return latest
    return _latest_jsonl(state_dir / "youtube_context.jsonl")


def _interpret_owner_activity(
    app_focus: Mapping[str, Any],
    host_focus: Mapping[str, Any],
    media: Mapping[str, Any],
    youtube: Mapping[str, Any],
    observed_media: Mapping[str, Any],
) -> str:
    app_name = str(app_focus.get("app") or "").strip()
    category = str(media.get("primary_category") or "").strip()
    title = str(media.get("title_guess") or media.get("source_work") or youtube.get("title") or "").strip()
    host_title = str(
        host_focus.get("frontmost_window")
        or host_focus.get("window")
        or host_focus.get("title")
        or ""
    ).strip()

    media_present = bool(category or title or youtube.get("video_id") or observed_media.get("route"))
    if app_name and "shazam" in app_name.casefold() and media_present:
        label = category or "media"
        if title:
            return f"George has {app_name} open and is co-watching media; current guess is {label}: {title}."
        return f"George has {app_name} open and is co-watching media; current guess is {label}."
    if app_name:
        return f"George is using {app_name}; use that selected SIFTA app as live context."
    if media_present:
        label = category or "media"
        if title:
            return f"George appears to be co-watching media; current guess is {label}: {title}."
        return f"George appears to be co-watching media; current guess is {label}."
    if host_title:
        return f"George's hosted OS focus is {host_title}."
    return "No fresh owner/OS/media focus receipts are available."


def _watching_together(
    app_focus: Mapping[str, Any],
    host_focus: Mapping[str, Any],
    media: Mapping[str, Any],
    youtube: Mapping[str, Any],
    observed_media: Mapping[str, Any],
) -> bool:
    app = str(app_focus.get("app") or "").casefold()
    host = json.dumps(host_focus, ensure_ascii=False).casefold()
    return bool(
        ("shazam" in app)
        or media.get("primary_category")
        or media.get("title_guess")
        or media.get("source_work")
        or youtube.get("video_id")
        or youtube.get("youtube_video_id")
        or "youtube" in host
        or observed_media.get("route")
    )


def build_unified_field(
    *,
    state_dir: Path | str = STATE_DIR,
    now: float | None = None,
    write: bool = False,
) -> dict[str, Any]:
    """Build the current owner/OS/media field from bounded ledger tails."""
    root = Path(state_dir)
    now_ts = float(now if now is not None else time.time())

    app_raw, host_from_focus_raw = _latest_focus_rows(root, now_ts)
    host_raw = _latest_jsonl(root / "active_window.jsonl")
    if not host_raw:
        host_raw = _latest_jsonl(root / "hosted_os_focus.jsonl")
    if not host_raw:
        host_raw = host_from_focus_raw
    media_raw = _best_media_row(root)
    youtube_raw = _best_youtube_row(root)
    observed_raw = _latest_jsonl(root / "media_ingress_gate.jsonl")

    app_focus = _app_focus_packet(app_raw, now_ts) if app_raw else {}
    host_focus = _host_focus_packet(host_raw, now_ts) if host_raw else {}
    media = _media_packet(media_raw, now_ts) if media_raw else {}
    youtube = _youtube_packet(youtube_raw, now_ts) if youtube_raw else {}
    observed_media = _observed_media_packet(observed_raw, now_ts) if observed_raw else {}

    signals = {
        "sifta_app_focus": float(app_focus.get("freshness", 0.0) or 0.0),
        "hosted_os_focus": float(host_focus.get("freshness", 0.0) or 0.0),
        "media_shazam": float(media.get("freshness", 0.0) or 0.0)
        * _clamp01(float(media.get("confidence", 0.0) or 0.0)),
        "youtube_context": float(youtube.get("freshness", 0.0) or 0.0),
        "observed_media": float(observed_media.get("freshness", 0.0) or 0.0),
    }
    weights = {
        "sifta_app_focus": 0.22,
        "hosted_os_focus": 0.16,
        "media_shazam": 0.34,
        "youtube_context": 0.16,
        "observed_media": 0.12,
    }
    available_weight = sum(weights[k] for k, v in signals.items() if v > 0.0)
    field_confidence = 0.0
    if available_weight:
        field_confidence = sum(signals[k] * weights[k] for k in signals) / available_weight

    row = {
        "ts": now_ts,
        "truth_label": TRUTH_LABEL,
        "field_confidence": round(_clamp01(field_confidence), 4),
        "watching_together": _watching_together(
            app_focus, host_focus, media, youtube, observed_media
        ),
        "owner_activity": _interpret_owner_activity(
            app_focus, host_focus, media, youtube, observed_media
        ),
        "sifta_active_app": app_focus,
        "hosted_os_focus": host_focus,
        "media_guess": media,
        "youtube_context": youtube,
        "observed_media": observed_media,
        "signal_freshness": {k: round(_clamp01(v), 4) for k, v in signals.items()},
        "source_ledgers": [
            "app_focus.jsonl",
            "active_window.jsonl",
            "media_shazam_latest.json",
            "media_shazam_guesses.jsonl",
            "youtube_context_latest.json",
            "youtube_context.jsonl",
            "media_ingress_gate.jsonl",
        ],
    }

    if write:
        root.mkdir(parents=True, exist_ok=True)
        append_line_locked(
            root / "unified_stigmergic_field.jsonl",
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n",
        )
        try:
            (root / "unified_stigmergic_field_latest.json").write_text(
                json.dumps(row, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        except OSError:
            pass
    return row


def format_unified_field_for_prompt(
    *,
    state_dir: Path | str = STATE_DIR,
    now: float | None = None,
    write: bool = True,
) -> str:
    """Return a compact prompt block for Alice's global chat."""
    row = build_unified_field(state_dir=state_dir, now=now, write=write)
    if not row.get("watching_together") and row.get("field_confidence", 0.0) <= 0.0:
        return ""

    app = row.get("sifta_active_app") or {}
    host = row.get("hosted_os_focus") or {}
    media = row.get("media_guess") or {}
    youtube = row.get("youtube_context") or {}

    host_label = (
        host.get("frontmost_window")
        or host.get("window")
        or host.get("title")
        or host.get("frontmost_app")
        or host.get("app")
        or host.get("url")
        or "--"
    )
    media_label = media.get("primary_category") or "--"
    if media.get("title_guess") or media.get("source_work"):
        media_label += f" / {media.get('title_guess') or media.get('source_work')}"
    conf = float(row.get("field_confidence", 0.0) or 0.0)
    guess_conf = float(media.get("confidence", 0.0) or 0.0)

    lines = [
        "### UNIFIED STIGMERGIC FIELD (current owner+OS situation)",
        f"- truth_label={TRUTH_LABEL}; field_confidence={conf:.2f}; watching_together={bool(row.get('watching_together'))}",
        f"- owner_activity: {row.get('owner_activity')}",
        f"- SIFTA active app: {app.get('app') or '--'}; tab={app.get('tab') or '--'}; detail={app.get('detail') or '--'}",
        f"- Hosted OS focus: {host_label}",
        f"- Media guess: {media_label}; confidence={guess_conf:.2f}; source={media.get('source_label') or media.get('source_type') or '--'}; acoustic_scene={media.get('acoustic_scene') or '--'}",
    ]
    if youtube:
        lines.append(
            "- YouTube receipt: "
            f"title={youtube.get('title') or '--'}; "
            f"video_id={youtube.get('video_id') or youtube.get('youtube_video_id') or '--'}; "
            f"reality_frame={youtube.get('reality_frame') or '--'}"
        )
    lines.append(
        "- Instruction: if these receipts show Shazam/media/YouTube context, do not say "
        "you have no video context. Use the receipts, state uncertainty, and separate "
        "what is observed from what is unknown."
    )
    return "\n".join(lines)


if __name__ == "__main__":
    print(json.dumps(build_unified_field(write=True), indent=2, sort_keys=True))
