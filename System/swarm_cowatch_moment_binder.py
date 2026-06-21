#!/usr/bin/env python3
"""Bind co-watch sound to sparse two-eye visual evidence.

r1027: Alice should answer shared-media questions from converging body evidence,
not from being told what is on screen. This organ fuses an STT media fragment
with the nearest world-eye blink, the latest owner-eye blink, and YouTube/media
context. It persists compact meaning only; it never writes or copies raw frames.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Mapping

try:
    from System.jsonl_file_lock import append_line_locked, read_text_locked
except Exception:  # pragma: no cover
    append_line_locked = None  # type: ignore[assignment]
    read_text_locked = None  # type: ignore[assignment]


_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

TRUTH_LABEL = "SIFTA_COWATCH_MOMENT_V1"
LEDGER_NAME = "co_watch_moments.jsonl"
WORLD_FEED_LEDGER_NAME = "latent_world_model_cowatch_feed.jsonl"

_COWATCH_SCENE_QUERY_RE = re.compile(
    r"\b(?:"
    r"what\s+(?:are|r)\s+(?:we|you|u|i)\s+watching|"
    r"what\s+(?:am|is)\s+(?:i|on\s+(?:the\s+)?(?:screen|tv|television|browser|video))\s+watching|"
    r"what\s+is\s+(?:this|that|the|on\s+(?:the\s+)?)\s*(?:video|movie|clip|show|screen|tv|youtube|tiktok|reel|post)?|"
    r"what\s+(?:is|['’]s)\s+(?:playing|on\s+(?:the\s+)?(?:screen|tv|television|browser|video))|"
    r"what\s+do\s+(?:you|u)\s+see\s+on\s+(?:the\s+)?(?:screen|tv|television|browser|video)|"
    r"are\s+(?:you|u)\s+watching\s+(?:this|that|the)\s+(?:video|movie|clip|show|screen|youtube|tiktok|reel|post)|"
    r"can\s+(?:you|u)\s+(?:tell|see)\s+what\s+(?:we|i)\s+(?:are|am|['’]re|['’]m)\s+watching|"
    r"do\s+(?:you|u)\s+know\s+what\s+(?:we|i)\s+(?:are|am|['’]re|['’]m)\s+watching"
    r")\b",
    re.IGNORECASE,
)


def _state_dir(state_dir: Path | str | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else _STATE


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(dict(row), ensure_ascii=False, sort_keys=True, default=str) + "\n"
    if append_line_locked is not None:
        append_line_locked(path, line, encoding="utf-8")
    else:  # pragma: no cover
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        value = json.loads(text)
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _read_jsonl_tail(path: Path, limit: int = 80, max_bytes: int = 256_000) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        if read_text_locked is not None and path.stat().st_size <= max_bytes:
            text = read_text_locked(path, encoding="utf-8", errors="replace")
        else:
            with path.open("rb") as handle:
                handle.seek(0, 2)
                size = handle.tell()
                handle.seek(max(0, size - max_bytes))
                text = handle.read().decode("utf-8", errors="replace")
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    for line in text.splitlines()[-max(1, int(limit)):]:
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except Exception:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _compact_text(value: Any, limit: int = 360) -> str:
    return " ".join(str(value or "").split())[:limit]


def _age(now: float, row: Mapping[str, Any]) -> float | None:
    try:
        ts = float(row.get("ts") or 0.0)
    except Exception:
        return None
    if ts <= 0:
        return None
    return max(0.0, now - ts)


def _latest_media_context(state: Path, now: float, max_age_s: float = 6 * 3600.0) -> dict[str, Any]:
    latest = _read_json(state / "youtube_context_latest.json")
    try:
        if latest and 0 <= now - float(latest.get("ts") or 0.0) <= max_age_s:
            return latest
    except Exception:
        pass
    for path_name in ("youtube_context.jsonl", "youtube_watch_memory.jsonl"):
        for row in reversed(_read_jsonl_tail(state / path_name, 48)):
            try:
                if 0 <= now - float(row.get("ts") or 0.0) <= max_age_s:
                    return row
            except Exception:
                continue
    # P2 (r1036): do NOT fall back to `latest` here — it already failed the age
    # gate at the top of this function. Returning it would attach stale
    # youtube_context_latest.json past the freshness window and make Alice answer
    # about the old video. Honest empty context instead; the visible answer then
    # routes to OWNER_DECLARED / UNAVAILABLE through the cortex, never a stale title.
    return {}


def is_cowatch_scene_question(text: str) -> bool:
    """Detect direct co-watch scene/media questions, not owner-camera presence."""
    clean = " ".join(str(text or "").split())
    if not clean:
        return False
    if re.search(r"\b(?:watching|seeing|looking(?:\s+at)?)\s+(?:me|us)\b", clean, re.IGNORECASE):
        return False
    return bool(_COWATCH_SCENE_QUERY_RE.search(clean))


def _latest_cowatch_moment(state: Path, now: float, max_age_s: float = 10 * 60.0) -> dict[str, Any]:
    for row in reversed(_read_jsonl_tail(state / LEDGER_NAME, 80)):
        try:
            ts = float(row.get("ts") or 0.0)
        except Exception:
            continue
        if ts <= 0 or now - ts < 0 or now - ts > max_age_s:
            continue
        if str(row.get("truth_label") or row.get("schema") or "") not in ("", TRUTH_LABEL):
            continue
        return row
    return {}


def cowatch_truth_context_for_prompt(
    owner_text: str = "",
    *,
    state_dir: Path | str | None = None,
    now: float | None = None,
    max_age_s: float = 10 * 60.0,
) -> str:
    """Return a compact cortex prompt gate for "what are we watching?" turns.

    This helper never composes Alice's visible answer. It exposes the latest
    receipts and the allowed epistemic status so the cortex can answer without
    inventing a title, character, or optical claim.
    """
    state = _state_dir(state_dir)
    ts = float(now if now is not None else time.time())
    direct_question = is_cowatch_scene_question(owner_text)
    moment = _latest_cowatch_moment(state, ts, max_age_s=max_age_s)
    media = {}
    if moment and isinstance(moment.get("media_context"), Mapping):
        media = dict(moment.get("media_context") or {})
    if not media:
        media = _latest_media_context(state, ts, max_age_s=max(max_age_s, 6 * 3600.0))
    if not direct_question and not moment:
        return ""

    visual_status = str(moment.get("visual_observation_status") or "").strip().upper()
    if not visual_status:
        visual_status = "OWNER_DECLARED" if media else "UNAVAILABLE"
    if visual_status not in {"OBSERVED", "OWNER_DECLARED", "UNAVAILABLE"}:
        visual_status = "UNAVAILABLE"

    scene = _compact_text(moment.get("world_eye_scene_label"), 500) if moment else ""
    provenance = moment.get("world_eye_object_provenance") if isinstance(moment.get("world_eye_object_provenance"), list) else []
    media_title = _compact_text(media.get("title") or media.get("media_title"), 240)
    media_url = _compact_text(media.get("url"), 260)
    media_video_id = _compact_text(media.get("video_id") or media.get("youtube_video_id"), 80)
    lines = [
        "CO-WATCH MOMENT TRUTH GATE (r1034, receipt-only):",
        f"direct_scene_question={str(direct_question).lower()}",
        f"visual_observation_status={visual_status}",
        f"moment_status={str(moment.get('status') or 'NO_RECENT_COWATCH_MOMENT')}",
        f"moment_id={str(moment.get('moment_id') or '')}",
    ]
    if moment:
        lines.extend(
            [
                f"world_eye_age_s={moment.get('world_eye_age_s')}",
                f"world_eye_scene_label={scene or 'empty'}",
                f"world_eye_provenance_depth={moment.get('world_eye_provenance_depth', 0)}",
                "world_eye_object_provenance="
                + _compact_text(json.dumps(provenance[:6], ensure_ascii=False, default=str), 700),
                f"owner_eye_presence={_compact_text(json.dumps(moment.get('owner_eye_presence') or {}, ensure_ascii=False, default=str), 220)}",
            ]
        )
    if media_title or media_url or media_video_id:
        lines.extend(
            [
                f"media_title_receipt={media_title}",
                f"media_url_receipt={media_url}",
                f"media_video_id_receipt={media_video_id}",
                f"media_context_ts={media.get('context_ts') or media.get('ts')}",
            ]
        )
    if visual_status == "OBSERVED":
        rule = (
            "Answer rule: the world-eye receipt permits a brief 'I see...' answer from "
            "world_eye_scene_label/provenance, but do not invent a title, character, or plot not in receipts."
        )
    elif visual_status == "OWNER_DECLARED":
        rule = (
            "Answer rule: speak as media/owner-declared context, not optical sight. "
            "Do not say 'I see' or identify a title from vision unless the world-eye receipt says OBSERVED."
        )
    else:
        rule = (
            "Answer rule: say there is no fresh world-eye co-watch receipt; do not guess what is playing."
        )
    lines.append(rule)
    return "\n".join(lines)


def _nearest_blink(
    state: Path,
    *,
    now: float,
    eye_role: str,
    max_age_s: float,
) -> dict[str, Any]:
    best: dict[str, Any] = {}
    best_distance = float("inf")
    for row in _read_jsonl_tail(state / "saccadic_blink_vision.jsonl", 240):
        if str(row.get("eye_role") or row.get("eye_id") or "") != eye_role:
            continue
        try:
            ts = float(row.get("ts") or 0.0)
        except Exception:
            continue
        distance = abs(now - ts)
        if distance > max_age_s:
            continue
        if distance < best_distance:
            best = row
            best_distance = distance
    return best


def _scene_label(blink: Mapping[str, Any]) -> str:
    desc = blink.get("semantic_description") if isinstance(blink.get("semantic_description"), Mapping) else {}
    text = _compact_text(desc.get("description"), 420)
    if text:
        return text
    labels = blink.get("semantic_labels") if isinstance(blink.get("semantic_labels"), list) else []
    return _compact_text("; ".join(str(x) for x in labels[:10]), 420)


def _owner_presence(blink: Mapping[str, Any]) -> dict[str, Any]:
    face = blink.get("face") if isinstance(blink.get("face"), Mapping) else {}
    return {
        "faces_detected": int(face.get("faces_detected") or 0),
        "audience": str(face.get("audience") or ""),
        "confidence": face.get("confidence"),
    }


def _row_id(payload: Mapping[str, Any]) -> str:
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return "cowatch_" + hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


def _feed_latent_world_model(state: Path, row: Mapping[str, Any]) -> dict[str, Any]:
    try:
        from System.swarm_latent_world_model import LatentWorldModel

        model = LatentWorldModel(state_dir=state)
        media = row.get("media_context") if isinstance(row.get("media_context"), Mapping) else {}
        prev_state = json.dumps(
            {
                "media_title": media.get("title") or media.get("media_title") or "",
                "owner_presence": row.get("owner_eye_presence"),
            },
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        next_state = json.dumps(
            {
                "transcript": row.get("transcript_fragment"),
                "world_scene": row.get("world_eye_scene_label"),
                "world_object_provenance": row.get("world_eye_object_provenance", []),
                "provenance_depth": row.get("world_eye_provenance_depth", 0),
            },
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        model.observe_reality(prev_state, "co_watch_moment", next_state, 0.75)
        model.save()
        feed = {
            "ts": row.get("ts") or time.time(),
            "truth_label": "LATENT_WORLD_MODEL_COWATCH_FEED_V1",
            "source": TRUTH_LABEL,
            "moment_id": row.get("moment_id"),
            "transition_count": len(model.transitions),
        }
        _append_jsonl(state / WORLD_FEED_LEDGER_NAME, feed)
        return {"ok": True, "ledger": WORLD_FEED_LEDGER_NAME, "transition_count": len(model.transitions)}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _feed_youtube_watch_memory(state: Path, row: Mapping[str, Any]) -> dict[str, Any]:
    media = row.get("media_context") if isinstance(row.get("media_context"), Mapping) else {}
    if not (media.get("title") or media.get("url") or media.get("video_id")):
        return {"ok": False, "skipped": True, "reason": "no_youtube_context"}
    try:
        from System.swarm_youtube_watch_memory import remember_youtube_watch

        out = remember_youtube_watch(
            {
                "title": media.get("title") or media.get("media_title") or "co-watch media",
                "url": media.get("url") or "",
                "video_id": media.get("video_id") or media.get("youtube_video_id") or "",
                "status": "co_watch_moment_bound",
                "content_kind": "co_watch_moment",
                "context_route": "two_eye_co_watch_moment",
                "page_context": (
                    f"world_eye={row.get('world_eye_scene_label')}; "
                    f"owner_eye={row.get('owner_eye_presence')}; "
                    f"transcript={row.get('transcript_fragment')}; "
                    f"provenance_depth={row.get('world_eye_provenance_depth', 0)}"
                ),
                "ask_panel_answer_excerpt": row.get("transcript_fragment") or "",
                "caption_chars": len(str(row.get("transcript_fragment") or "")),
                # P7 (r1036): carry the STRUCTURED world-eye object provenance into the
                # co-watch memory, matching what already reaches the latent feed. The
                # string page_context alone dropped the list; downstream "what are we
                # watching?" can now cite provenance, not just a depth integer. No pixels.
                "object_provenance": row.get("world_eye_object_provenance", []),
                "provenance_depth": row.get("world_eye_provenance_depth", 0),
            },
            state_dir=state,
        )
        return {"ok": True, "memory_id": out.get("memory_id"), "ledger": "youtube_watch_memory.jsonl"}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def bind_cowatch_moment(
    transcript_fragment: str,
    *,
    source_row: Mapping[str, Any] | None = None,
    state_dir: Path | str | None = None,
    now: float | None = None,
    max_blink_age_s: float = 90.0,
    write: bool = True,
    feed_memory: bool = True,
) -> dict[str, Any]:
    """Bind one media/STT fragment to nearest world-eye and owner-eye blinks."""
    state = _state_dir(state_dir)
    ts = float(now if now is not None else time.time())
    source = dict(source_row or {})
    fragment = _compact_text(transcript_fragment, 420)
    media = _latest_media_context(state, ts)
    world = _nearest_blink(state, now=ts, eye_role="world_eye", max_age_s=max_blink_age_s)
    owner = _nearest_blink(state, now=ts, eye_role="owner_eye", max_age_s=max_blink_age_s)
    status = "BOUND" if world else "OPEN_NO_WORLD_EYE_BLINK"
    payload_for_id = {
        "ts": round(ts, 3),
        "fragment": fragment,
        "source_ts": source.get("ts"),
        "world_blink_id": world.get("blink_id"),
        "media": {k: media.get(k) for k in ("title", "url", "video_id", "youtube_video_id")},
    }
    row: dict[str, Any] = {
        "ts": ts,
        "truth_label": TRUTH_LABEL,
        "schema": TRUTH_LABEL,
        "moment_id": _row_id(payload_for_id),
        "status": status,
        "transcript_fragment": fragment,
        "source_route": source.get("route"),
        "source_reason": source.get("reason"),
        "source_class": (
            source.get("external_consciousness", {}).get("source_class")
            if isinstance(source.get("external_consciousness"), Mapping)
            else source.get("source_class")
        ),
        "world_eye_blink_id": world.get("blink_id"),
        "world_eye_age_s": _age(ts, world) if world else None,
        "world_eye_scene_label": _scene_label(world) if world else "",
        "world_eye_object_provenance": world.get("object_provenance") if world else [],
        "world_eye_provenance_depth": world.get("provenance_depth") if world else 0,
        "owner_eye_blink_id": owner.get("blink_id"),
        "owner_eye_age_s": _age(ts, owner) if owner else None,
        "owner_eye_presence": _owner_presence(owner) if owner else {},
        "media_context": {
            "title": media.get("title") or media.get("media_title") or "",
            "url": media.get("url") or "",
            "video_id": media.get("video_id") or media.get("youtube_video_id") or "",
            "context_ts": media.get("ts"),
        },
        "privacy_policy": "pixels_die_information_lives_no_frame_archive",
        "raw_frame_archived": False,
        "raw_audio_logged": False,
        "visual_observation_status": (
            "OBSERVED" if (world and world.get("semantic_description", {}).get("status") == "ok" and not world.get("idle_decimated"))
            else "OWNER_DECLARED" if media or source
            else "UNAVAILABLE"
        ),
    }
    if feed_memory and status == "BOUND":
        row["latent_world_model"] = _feed_latent_world_model(state, row)
        row["youtube_watch_memory"] = _feed_youtube_watch_memory(state, row)
    else:
        row["latent_world_model"] = {"ok": False, "skipped": True, "reason": status}
        row["youtube_watch_memory"] = {"ok": False, "skipped": True, "reason": status}
    if write:
        _append_jsonl(state / LEDGER_NAME, row)
        media_title = str(
            (row.get("media_context") or {}).get("title")
            or (row.get("media_context") or {}).get("media_title")
            or ""
        ).strip()
        if media_title:
            try:
                from System.swarm_human_identity_constants import ingest_media_context

                ingest_media_context(
                    media_title,
                    state_dir=state,
                    now=ts,
                    evidence_ref=f"{LEDGER_NAME}:{row.get('moment_id')}",
                )
            except Exception:
                pass
    return row


__all__ = [
    "LEDGER_NAME",
    "TRUTH_LABEL",
    "WORLD_FEED_LEDGER_NAME",
    "bind_cowatch_moment",
    "cowatch_truth_context_for_prompt",
    "is_cowatch_scene_question",
]


if __name__ == "__main__":  # pragma: no cover
    print(json.dumps(bind_cowatch_moment("manual co-watch probe"), indent=2, ensure_ascii=False))
