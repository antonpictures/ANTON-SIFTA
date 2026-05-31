#!/usr/bin/env python3
"""Co-watch media visual sense.

When the existing co-watch field says George and Alice are watching media
together, this organ takes a throttled desktop screenshot, fingerprints it like
other visual events, and deposits an ``OBSERVED_MEDIA`` row. The provenance line
is strict: this is screen media, not room camera sight and not generated image
sight.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

from System.jsonl_file_lock import append_line_locked, read_text_locked

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_VISUAL_STIGMERGY = _STATE / "visual_stigmergy.jsonl"
_AUDIT_LEDGER = _STATE / "cowatch_media_visual.jsonl"
_FRAME_DIR = _STATE / "cowatch_frames"
_YOUTUBE_LATEST = _STATE / "youtube_context_latest.json"
_YOUTUBE_LEDGER = _STATE / "youtube_context.jsonl"

DEFAULT_MIN_INTERVAL_S = 25.0
YOUTUBE_TTL_S = 10 * 60.0

VisualWriter = Callable[[dict[str, Any]], None]
CaptureFn = Callable[[Path], Mapping[str, Any]]
ContextFn = Callable[[], str]


def _state_dir(state_dir: Path | str | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else _STATE


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _tail_jsonl(path: Path, limit: int = 12) -> list[dict[str, Any]]:
    try:
        text = read_text_locked(path, encoding="utf-8", errors="replace")
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    for line in text.splitlines()[-max(1, int(limit)):]:
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _row_hash(row: Mapping[str, Any]) -> str:
    body = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


def _youtube_context_hash(row: Mapping[str, Any]) -> str:
    payload = {
        "title": row.get("title") or "",
        "url": row.get("url") or "",
        "video_id": row.get("video_id") or row.get("youtube_video_id") or "",
    }
    return _row_hash(payload)


def _latest_youtube_context(*, state_dir: Path | str | None = None, now: float | None = None) -> dict[str, Any]:
    state = _state_dir(state_dir)
    now_ts = float(now if now is not None else time.time())
    latest = _read_json(state / "youtube_context_latest.json")
    try:
        if latest and (now_ts - float(latest.get("ts", 0.0))) <= YOUTUBE_TTL_S:
            return latest
    except Exception:
        pass
    for row in reversed(_tail_jsonl(state / "youtube_context.jsonl", 24)):
        try:
            if (now_ts - float(row.get("ts", 0.0))) <= YOUTUBE_TTL_S:
                return row
        except Exception:
            continue
    return latest if latest else {}


def _extract_media_title(context_block: str, youtube_row: Mapping[str, Any]) -> str:
    title = str(
        youtube_row.get("title")
        or youtube_row.get("media_title")
        or youtube_row.get("source_work")
        or ""
    ).strip()
    if title:
        return title[:240]
    for marker in ('[YouTube]', '[YouTube via organ]', '[Title guess]'):
        if marker not in context_block:
            continue
        line = context_block.split(marker, 1)[1].splitlines()[0].strip()
        return line.strip(' "').strip()[:240]
    return ""


def _cowatch_is_active(context_block: str, youtube_row: Mapping[str, Any], *, now: float) -> bool:
    if not context_block.strip():
        return False
    title = _extract_media_title(context_block, youtube_row)
    if not title:
        return False
    low = context_block.lower()
    return "youtube" in low or "media" in low or "co-watch" in low or "cowatch" in low


def _last_capture_ts(state: Path) -> float:
    for row in reversed(_tail_jsonl(state / "cowatch_media_visual.jsonl", 16)):
        if row.get("ok") is False:
            continue
        try:
            return float(row.get("ts", 0.0))
        except Exception:
            continue
    return 0.0


def _default_capture(path: Path) -> Mapping[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run(
            ["screencapture", "-x", "-C", str(path)],
            capture_output=True,
            text=True,
            timeout=8.0,
        )
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    ok = proc.returncode == 0 and path.exists() and path.stat().st_size > 0
    return {
        "ok": ok,
        "path": str(path),
        "error": "" if ok else (proc.stderr or proc.stdout or f"rc={proc.returncode}")[:500],
        "capture_method": "macos_screencapture_fullscreen_with_cursor",
    }


def _append_visual_direct(state: Path, row: dict[str, Any]) -> None:
    append_line_locked(state / "visual_stigmergy.jsonl", json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")


def _audit(state: Path, row: dict[str, Any]) -> None:
    append_line_locked(state / "cowatch_media_visual.jsonl", json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")


def _min_interval(default: float = DEFAULT_MIN_INTERVAL_S) -> float:
    raw = os.environ.get("SIFTA_COWATCH_MEDIA_VISUAL_INTERVAL_S", "").strip()
    if not raw:
        return default
    try:
        return max(5.0, float(raw))
    except ValueError:
        return default


def build_observed_media_row(
    *,
    ts: float,
    image_path: Path,
    youtube_row: Mapping[str, Any],
    context_block: str,
    fingerprint: Mapping[str, Any],
) -> dict[str, Any]:
    title = _extract_media_title(context_block, youtube_row) or "current co-watch media"
    row: dict[str, Any] = {
        "ts": ts,
        "t": ts,
        "kind": "COWATCH_MEDIA_FRAME",
        "truth": "OBSERVED_MEDIA",
        "source": "co_watch_desktop",
        "stigmergic_label": "OBSERVED_MEDIA",
        "media_title": title,
        "youtube_video_id": str(youtube_row.get("video_id") or youtube_row.get("youtube_video_id") or ""),
        "url": str(youtube_row.get("url") or ""),
        "youtube_context_hash": _youtube_context_hash(youtube_row),
        "image_path": str(image_path),
        "frame_path": str(image_path),
        "capture_method": "macos_screencapture_fullscreen_with_cursor",
        "provenance_note": (
            "Co-watched media frame from George's screen. Not webcam sight, "
            "not a real-room scene, and not generated image sight."
        ),
        **dict(fingerprint),
    }
    row["row_hash"] = _row_hash(row)
    return row


def maybe_capture_cowatch_frame(
    *,
    write_visual_stigmergy_row: Optional[VisualWriter] = None,
    now: float | None = None,
    state_dir: Path | str | None = None,
    min_interval_s: float | None = None,
    capture_fn: Optional[CaptureFn] = None,
    cowatch_context_fn: Optional[ContextFn] = None,
) -> dict[str, Any]:
    """Capture one co-watch media frame if the field is active and unthrottled."""
    state = _state_dir(state_dir)
    now_ts = float(now if now is not None else time.time())
    interval = _min_interval(min_interval_s if min_interval_s is not None else DEFAULT_MIN_INTERVAL_S)

    if cowatch_context_fn is None:
        try:
            from System.swarm_unified_cowatch_field import get_unified_cowatch_context

            cowatch_context_fn = get_unified_cowatch_context
        except Exception:
            cowatch_context_fn = lambda: ""

    context_block = ""
    try:
        context_block = str(cowatch_context_fn() or "")
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "skipped": True, "reason": f"cowatch_context_error:{type(exc).__name__}"}

    youtube_row = _latest_youtube_context(state_dir=state, now=now_ts)
    if not _cowatch_is_active(context_block, youtube_row, now=now_ts):
        return {"ok": False, "skipped": True, "reason": "cowatch_not_active", "next_check_s": 10.0}

    last_ts = _last_capture_ts(state)
    age = now_ts - last_ts if last_ts else None
    if last_ts and age is not None and age < interval:
        return {
            "ok": False,
            "skipped": True,
            "reason": "throttled",
            "age_s": round(age, 3),
            "next_check_s": max(1.0, interval - age),
        }

    frame_dir = state / "cowatch_frames"
    frame_path = frame_dir / f"cowatch_media_{int(now_ts * 1000)}.png"
    capture = (capture_fn or _default_capture)(frame_path)
    if not capture.get("ok"):
        audit = {
            "ts": now_ts,
            "schema": "COWATCH_MEDIA_VISUAL_V1",
            "ok": False,
            "reason": "capture_failed",
            "error": str(capture.get("error") or "unknown capture error")[:1000],
            "media_title": _extract_media_title(context_block, youtube_row),
            "youtube_context_hash": _youtube_context_hash(youtube_row),
        }
        audit["row_hash"] = _row_hash(audit)
        _audit(state, audit)
        return {**audit, "skipped": False, "next_check_s": interval}

    try:
        from System.swarm_bonsai_image_organ import _visual_fingerprint

        fingerprint = _visual_fingerprint(str(frame_path))
    except Exception as exc:  # noqa: BLE001
        fingerprint = {
            "sha8": hashlib.sha256(frame_path.read_bytes()).hexdigest()[:8] if frame_path.exists() else "",
            "fingerprint_note": f"fallback hash-only after {type(exc).__name__}",
        }

    visual_row = build_observed_media_row(
        ts=now_ts,
        image_path=frame_path,
        youtube_row=youtube_row,
        context_block=context_block,
        fingerprint=fingerprint,
    )
    if write_visual_stigmergy_row is not None:
        write_visual_stigmergy_row(visual_row)
    else:
        _append_visual_direct(state, visual_row)

    audit = {
        "ts": now_ts,
        "schema": "COWATCH_MEDIA_VISUAL_V1",
        "ok": True,
        "visual_row_hash": visual_row["row_hash"],
        "media_title": visual_row["media_title"],
        "youtube_video_id": visual_row.get("youtube_video_id", ""),
        "youtube_context_hash": visual_row["youtube_context_hash"],
        "image_path": str(frame_path),
        "source": "co_watch_desktop",
        "stigmergic_label": "OBSERVED_MEDIA",
        "capture_method": visual_row["capture_method"],
        "provenance_note": visual_row["provenance_note"],
    }
    audit["row_hash"] = _row_hash(audit)
    _audit(state, audit)
    return {
        "ok": True,
        "skipped": False,
        "visual_row": visual_row,
        "audit_row": audit,
        "next_check_s": interval,
    }


__all__ = [
    "DEFAULT_MIN_INTERVAL_S",
    "build_observed_media_row",
    "maybe_capture_cowatch_frame",
]
