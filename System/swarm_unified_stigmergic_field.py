#!/usr/bin/env python3
"""Unified owner/OS/media field for Alice prompt grounding.

This organ answers one narrow question before the LLM speaks:

    What is the primary operator doing across SIFTA OS, the hosted desktop, and media organs?

It does not identify media by magic. It fuses bounded receipts from app focus,
hosted OS focus, YouTube/media ledgers, and Stigmergic Unified Shazam into one
small current-situation packet. Alice can then reason from the packet instead
of claiming she has no video context while another SIFTA app is visibly open.

Truth label: UNIFIED_STIGMERGIC_FIELD_V1
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Mapping

from System.jsonl_file_lock import append_line_locked


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
LEDGER = STATE_DIR / "unified_stigmergic_field.jsonl"
LATEST = STATE_DIR / "unified_stigmergic_field_latest.json"
TRUTH_LABEL = "UNIFIED_STIGMERGIC_FIELD_V1"
APP_HABIT_TRUTH_LABEL = "SIFTA_APP_HABIT_UNIFIED_FIELD_V1"
APP_HABIT_CHAIN_LEDGER = "app_habit_unified_field_chain.jsonl"

APP_FOCUS_MAX_AGE_S = 5 * 60.0
HOST_FOCUS_MAX_AGE_S = 5 * 60.0
MEDIA_MAX_AGE_S = 6 * 3600.0
PREDICTION_MAX_AGE_S = 30 * 60.0


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


def _prediction_packet(row: Mapping[str, Any], now: float) -> dict[str, Any]:
    """Compact owner schedule prediction packet for the unified field."""
    if not row:
        return {}
    return {
        "truth_label": row.get("truth_label"),
        "next_likely_segment": row.get("next_likely_segment"),
        "confidence": row.get("confidence"),
        "expected_start_min": row.get("expected_start_min"),
        "expected_start_time": row.get("expected_start_time"),
        "basis_days": row.get("basis_days"),
        "basis_event_count": row.get("basis_event_count"),
        "age_s": _age_s(row, now),
        "freshness": round(_freshness(row, now, PREDICTION_MAX_AGE_S), 4),
    }


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
    try:
        from System.swarm_kernel_identity import owner_display_name

        who = owner_display_name("the primary operator")
    except Exception:
        who = "the primary operator"
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
            return f"{who} has {app_name} open and is co-watching media; current guess is {label}: {title}."
        return f"{who} has {app_name} open and is co-watching media; current guess is {label}."
    if app_name:
        return f"{who} is using {app_name}; use that selected SIFTA app as live context."
    if media_present:
        label = category or "media"
        if title:
            return f"{who} appears to be co-watching media; current guess is {label}: {title}."
        return f"{who} appears to be co-watching media; current guess is {label}."
    if host_title:
        return f"{who}'s hosted OS focus is {host_title}."
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


def _safe_slug(value: str) -> str:
    cleaned = re.sub(r"[^\w\-]+", "_", (value or "unknown")).strip("_")
    return cleaned.lower() or "unknown"


def _canonical_hash(payload: Mapping[str, Any]) -> str:
    body = {
        k: v
        for k, v in payload.items()
        if k not in {"packet_sha256", "chain_event_id", "chain_hash", "chain_seq"}
    }
    blob = json.dumps(body, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _clearance_summary(row: Mapping[str, Any]) -> dict[str, Any]:
    body = row.get("body") if isinstance(row.get("body"), dict) else {}
    return {
        "truth_label": row.get("truth_label"),
        "process_kind": row.get("process_kind"),
        "allowed": bool(row.get("allowed")),
        "action": row.get("action"),
        "reasons": list(row.get("reasons") or [])[:6],
        "rest_seconds": row.get("rest_seconds"),
        "receipt_hash": row.get("receipt_hash"),
        "body": {
            "thermal_warning_level": body.get("thermal_warning_level"),
            "thermal_pressure": body.get("thermal_pressure"),
            "allostatic_load_norm": body.get("allostatic_load_norm"),
            "budget_multiplier": body.get("budget_multiplier"),
            "metabolic_mode": body.get("metabolic_mode"),
        },
    }


def _app_habit_field_packet(
    app_focus: Mapping[str, Any],
    *,
    state_dir: Path,
    now: float,
    write: bool,
) -> dict[str, Any]:
    """Build the active app's habit/skill lane behind a body-clearance gate."""
    app_name = str(app_focus.get("app") or "").strip()
    if not app_name:
        return {}

    gate_payload = {
        "active_app": app_name,
        "app_focus_age_s": app_focus.get("age_s"),
        "app_focus_freshness": app_focus.get("freshness"),
        "requested_lane": "app_focus_habits_skills_to_unified_field",
    }
    try:
        from System.swarm_processing_thermodynamic_gate import request_processing_clearance

        clearance = request_processing_clearance(
            "app_habit_unified_field_merge",
            expected_value=0.58,
            emergency=False,
            payload=gate_payload,
            state_dir=state_dir,
            write_ledger=write,
            now=now,
        )
    except Exception as exc:
        clearance = {
            "truth_label": "PROCESSING_THERMODYNAMIC_GATE_UNAVAILABLE",
            "process_kind": "app_habit_unified_field_merge",
            "allowed": False,
            "action": "defer",
            "reasons": [f"gate_unavailable:{type(exc).__name__}"],
            "rest_seconds": 30.0,
            "receipt_hash": "",
            "body": {},
        }

    packet: dict[str, Any] = {
        "ts": now,
        "truth_label": APP_HABIT_TRUTH_LABEL,
        "active_app": app_name,
        "status": "allowed" if clearance.get("allowed") else "deferred_by_thermodynamic_gate",
        "app_focus_age_s": app_focus.get("age_s"),
        "app_focus_freshness": app_focus.get("freshness"),
        "thermodynamic_clearance": _clearance_summary(clearance),
        "help_doc_path": str(REPO_ROOT / "Documents" / "app_help" / f"{_safe_slug(app_name)}.md"),
        "help_skills": [],
        "capability_habits": [],
        "source_ledgers": [
            "app_focus.jsonl",
            "app_health.jsonl",
            "skill_ingest.jsonl",
            "work_receipts.jsonl",
            "processing_thermodynamic_gate.jsonl",
        ],
    }

    if clearance.get("allowed"):
        try:
            from System.swarm_app_help_skills import effective_skills_for_app

            effective = effective_skills_for_app(app_name)
            packet["help_skills"] = [
                {
                    "name": str(skill),
                    "source": (
                        "stigmergic"
                        if skill in getattr(effective, "stigmergic", [])
                        else "seed"
                        if skill in getattr(effective, "static_seed", [])
                        else "unknown"
                    ),
                    "last_seen_ts": getattr(effective, "last_seen_ts", {}).get(skill),
                }
                for skill in list(getattr(effective, "merged", []) or [])[:16]
            ]
        except Exception as exc:
            packet["help_skill_error"] = f"{type(exc).__name__}: {exc}"

        try:
            from System.swarm_capability_registry import app_habit_field_summary

            summary = app_habit_field_summary(app_name, limit=8)
            packet["capability_habits"] = list(summary.get("habits") or [])[:8]
            packet["capability_returned"] = int(summary.get("returned") or 0)
        except Exception as exc:
            packet["capability_habit_error"] = f"{type(exc).__name__}: {exc}"

    packet["packet_sha256"] = _canonical_hash(packet)

    if write:
        try:
            from System.stigmergic_ledger_chain import append_linked_row

            chain_row = append_linked_row(
                {
                    "truth_label": APP_HABIT_TRUTH_LABEL,
                    "active_app": app_name,
                    "status": packet.get("status"),
                    "packet_sha256": packet["packet_sha256"],
                    "thermodynamic_receipt_hash": (
                        packet.get("thermodynamic_clearance", {}).get("receipt_hash")
                    ),
                    "help_skill_count": len(packet.get("help_skills") or []),
                    "capability_habit_count": len(packet.get("capability_habits") or []),
                },
                path=state_dir / APP_HABIT_CHAIN_LEDGER,
                ts=now,
            )
            packet["chain_event_id"] = chain_row.get("event_id")
            packet["chain_hash"] = chain_row.get("chain_hash")
            packet["chain_seq"] = chain_row.get("chain_seq")
        except Exception as exc:
            packet["chain_error"] = f"{type(exc).__name__}: {exc}"

    return packet


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
    prediction_raw = _read_json(root / "stigmergic_prediction.json")

    app_focus = _app_focus_packet(app_raw, now_ts) if app_raw else {}
    host_focus = _host_focus_packet(host_raw, now_ts) if host_raw else {}
    media = _media_packet(media_raw, now_ts) if media_raw else {}
    youtube = _youtube_packet(youtube_raw, now_ts) if youtube_raw else {}
    observed_media = _observed_media_packet(observed_raw, now_ts) if observed_raw else {}
    schedule_prediction = _prediction_packet(prediction_raw, now_ts) if prediction_raw else {}
    app_habit_field = _app_habit_field_packet(
        app_focus,
        state_dir=root,
        now=now_ts,
        write=write,
    ) if app_focus else {}

    signals = {
        "sifta_app_focus": float(app_focus.get("freshness", 0.0) or 0.0),
        "app_habit_field": float(app_habit_field.get("app_focus_freshness", 0.0) or 0.0)
        if app_habit_field.get("status") == "allowed"
        else 0.0,
        "hosted_os_focus": float(host_focus.get("freshness", 0.0) or 0.0),
        "media_shazam": float(media.get("freshness", 0.0) or 0.0)
        * _clamp01(float(media.get("confidence", 0.0) or 0.0)),
        "youtube_context": float(youtube.get("freshness", 0.0) or 0.0),
        "observed_media": float(observed_media.get("freshness", 0.0) or 0.0),
        "schedule_prediction": float(schedule_prediction.get("freshness", 0.0) or 0.0)
        * _clamp01(float(schedule_prediction.get("confidence", 0.0) or 0.0)),
    }
    weights = {
        "sifta_app_focus": 0.22,
        "app_habit_field": 0.14,
        "hosted_os_focus": 0.16,
        "media_shazam": 0.34,
        "youtube_context": 0.16,
        "observed_media": 0.12,
        "schedule_prediction": 0.10,
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
        "schedule_prediction": schedule_prediction,
        "app_habit_field": app_habit_field,
        "signal_freshness": {k: round(_clamp01(v), 4) for k, v in signals.items()},
        "source_ledgers": [
            "app_focus.jsonl",
            APP_HABIT_CHAIN_LEDGER,
            "processing_thermodynamic_gate.jsonl",
            "active_window.jsonl",
            "media_shazam_latest.json",
            "media_shazam_guesses.jsonl",
            "youtube_context_latest.json",
            "youtube_context.jsonl",
            "media_ingress_gate.jsonl",
            "stigmergic_prediction.json",
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
    prediction = row.get("schedule_prediction") or {}
    app_habit = row.get("app_habit_field") or {}

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
    if prediction:
        lines.append(
            "- Schedule prediction: "
            f"next={prediction.get('next_likely_segment') or '--'}; "
            f"confidence={float(prediction.get('confidence') or 0.0):.2f}; "
            f"expected_in_min={prediction.get('expected_start_min') or '--'}; "
            f"expected_time={prediction.get('expected_start_time') or '--'}"
        )
    if youtube:
        lines.append(
            "- YouTube receipt: "
            f"title={youtube.get('title') or '--'}; "
            f"video_id={youtube.get('video_id') or youtube.get('youtube_video_id') or '--'}; "
            f"reality_frame={youtube.get('reality_frame') or '--'}"
        )
    if app_habit:
        clearance = app_habit.get("thermodynamic_clearance") or {}
        receipt = str(clearance.get("receipt_hash") or "")[:12] or "--"
        help_skills = [
            str(item.get("name") or "")
            for item in (app_habit.get("help_skills") or [])
            if isinstance(item, dict) and item.get("name")
        ][:8]
        habit_names = [
            str(item.get("name") or "")
            for item in (app_habit.get("capability_habits") or [])
            if isinstance(item, dict) and item.get("name")
        ][:6]
        lines.append(
            "- App habit lane: "
            f"truth_label={APP_HABIT_TRUTH_LABEL}; "
            f"active_app={app_habit.get('active_app') or '--'}; "
            f"status={app_habit.get('status') or '--'}; "
            f"thermo_action={clearance.get('action') or '--'}; "
            f"thermo_receipt={receipt}; "
            f"packet_sha256={str(app_habit.get('packet_sha256') or '')[:12] or '--'}"
        )
        if help_skills:
            lines.append("- App help skills to load now: " + ", ".join(help_skills))
        if habit_names:
            lines.append("- Scoped app habits to prefer now: " + ", ".join(habit_names))
        lines.append(
            "- App-habit instruction: treat the active app's help file, health trace, "
            "and scoped skills as the current field lane before falling back to generic chat."
        )
    lines.append(
        "- Instruction: if these receipts show Shazam/media/YouTube context, do not say "
        "you have no video context. Use the receipts, state uncertainty, and separate "
        "what is observed from what is unknown."
    )
    return "\n".join(lines)


if __name__ == "__main__":
    print(json.dumps(build_unified_field(write=True), indent=2, sort_keys=True))
