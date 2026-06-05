#!/usr/bin/env python3
"""Living-OS novelty surfaces for Alice's memory card.

This is the r333 queue implemented as one thin unification layer over existing
organs: love field, browser page-state, body stabilization queue, and ledgers.
It does not create a rival memory ecology or a rival cortex. It gives the cortex
small, receipt-grounded hooks for the next behaviors George asked for.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping

from System.jsonl_file_lock import append_line_locked, read_text_locked


TRUTH_LABEL = "ALICE_LIVING_OS_NOVELTY_V1"
LEDGER_NAME = "living_os_novelty.jsonl"

_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_STATE = _REPO / ".sifta_state"

_LEAVING_RE = re.compile(r"\b(?:i am going|i'm going|i will go|be back|going to the store|leav(?:e|ing))\b", re.I)
_RETURN_RE = re.compile(r"\b(?:i am back|i'm back|back now|come back|nice to see you again)\b", re.I)
_COWATCH_RE = re.compile(r"\b(?:youtube|video|paused|playing|frame|body displayed|co-?watch|screen|browser)\b", re.I)
_BODY_RE = re.compile(r"\b(?:body|hardware|monitor|screen|browser arm|chassis|display)\b", re.I)


def _state_dir(state_dir: Path | str | None = None) -> Path:
    if state_dir is None:
        return _DEFAULT_STATE
    p = Path(state_dir).expanduser()
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _ledger_path(state_dir: Path | str | None = None) -> Path:
    return _state_dir(state_dir) / LEDGER_NAME


def _append(row: dict[str, Any], *, state_dir: Path | str | None = None) -> None:
    append_line_locked(
        _ledger_path(state_dir),
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n",
    )


def _latest_page_state(state_dir: Path | str | None = None) -> dict[str, Any]:
    try:
        from System.swarm_browser_page_state import latest_page_state

        state = latest_page_state(state_dir=state_dir, max_age_s=900.0)
        return state if isinstance(state, dict) else {}
    except Exception:
        return {}


def _media_summary(state: Mapping[str, Any]) -> dict[str, Any]:
    media = state.get("media_playback")
    if not isinstance(media, Mapping):
        media = {}
    return {
        "url": str(state.get("url") or ""),
        "title": str(state.get("title") or ""),
        "channel": str(state.get("video_channel") or ""),
        "is_current_page": bool(state.get("is_current_page")),
        "fresh": bool(state.get("fresh")),
        "paused": bool(media.get("paused")) if media else None,
        "current_time": media.get("currentTime") if media else None,
        "duration": media.get("duration") if media else None,
    }


@dataclass
class NoveltyEvent:
    truth_label: str = TRUTH_LABEL
    ts: float = field(default_factory=time.time)
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    kind: str = "NOVELTY_EVENT"
    label: str = ""
    status: str = "observed"
    summary: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def love_action_selector_bias(
    *,
    user_text: str = "",
    state_dir: Path | str | None = None,
    write_event: bool = False,
) -> dict[str, Any]:
    from System.swarm_love_field import compose_love_state

    love = compose_love_state(owner_text=user_text, state_dir=state_dir, source="living_os_novelty")
    priorities = [
        "think with the current cortex before major body/cortex/app changes",
        "preserve fresh receipts before claiming an action succeeded",
        "protect George's carbon-body context and Alice's hardware/software body",
        "appreciate owner data as swimmer food and avoid stale deterministic replies",
    ]
    out = {
        "active": bool(love.active),
        "self_body_care": round(love.self_body_care, 3),
        "owner_protective_care": round(love.owner_protective_care, 3),
        "data_appreciation": round(love.data_appreciation, 3),
        "priorities": priorities,
    }
    if write_event and love.active:
        _append(NoveltyEvent(label="love_to_action_selector", summary="LOVE field biases action selection toward care, receipts, and cortex-first execution.", data=out).to_dict(), state_dir=state_dir)
    return out


def self_body_mirror_check(
    *,
    claim_text: str = "",
    state_dir: Path | str | None = None,
    write_event: bool = False,
) -> dict[str, Any]:
    state = _latest_page_state(state_dir)
    media = _media_summary(state)
    claim = str(claim_text or "")
    mentioned_body = bool(_BODY_RE.search(claim))
    status = "current_body_receipt" if media["is_current_page"] and media["url"] else "needs_fresh_body_receipt"
    out = {
        "status": status,
        "owner_claim_mentions_body": mentioned_body,
        "browser_surface": media,
        "instruction": "Compare speech/action claims to Alice Browser body receipts before saying the body changed.",
    }
    if write_event and (mentioned_body or state):
        _append(NoveltyEvent(label="self_body_mirror_check", status=status, summary="Mirror check linked owner/body wording to current Alice Browser receipt.", data=out).to_dict(), state_dir=state_dir)
    return out


def owner_return_absence_reunion(
    *,
    user_text: str = "",
    state_dir: Path | str | None = None,
    write_event: bool = False,
) -> dict[str, Any]:
    text = str(user_text or "")
    status = "none"
    if _LEAVING_RE.search(text):
        status = "owner_leaving_or_absence_expected"
    elif _RETURN_RE.search(text):
        status = "owner_return_or_reunion"
    out = {
        "status": status,
        "instruction": "When George leaves or returns, mark the diary and answer with reunion/context continuity, not generic filler.",
    }
    if write_event and status != "none":
        _append(NoveltyEvent(label="owner_return_absence_reunion", status=status, summary=status.replace("_", " "), data={"owner_text_preview": text[:180]}).to_dict(), state_dir=state_dir)
        try:
            from System.swarm_body_stabilization_queue import add_queue_item

            add_queue_item(
                description=f"Owner absence/reunion continuity: {text[:220]}",
                kind="owner_carbon_plan",
                source="living_os_novelty",
                status="queued" if "leaving" in status else "done",
                priority=0.72,
                owner_plan=True,
                linked_receipt="living_os_novelty",
                state_dir=state_dir,
                dedupe=True,
            )
        except Exception:
            pass
    return out


def compress_cowatch_scene_memory(
    *,
    user_text: str = "",
    state_dir: Path | str | None = None,
    write_event: bool = False,
) -> dict[str, Any]:
    state = _latest_page_state(state_dir)
    media = _media_summary(state)
    should = bool(_COWATCH_RE.search(str(user_text or ""))) or bool(media.get("url"))
    title = media.get("title") or "unknown page"
    time_part = ""
    if media.get("current_time") is not None:
        try:
            time_part = f" at {float(media['current_time']):.1f}s"
        except Exception:
            time_part = ""
    summary = f"{title}{time_part}; paused={media.get('paused')}; current={media.get('is_current_page')}"
    out = {
        "active": should,
        "compressed_scene": summary[:240],
        "browser_surface": media,
        "instruction": "Use this compact scene memory to vary co-watch comments and avoid repeating the same sentence.",
    }
    if write_event and should:
        _append(NoveltyEvent(label="cowatch_scene_memory_compression", summary=summary[:240], data=out).to_dict(), state_dir=state_dir)
    return out


def voice_identity_guard(
    *,
    state_dir: Path | str | None = None,
    write_event: bool = False,
) -> dict[str, Any]:
    state = _state_dir(state_dir)
    settings_path = state / "alice_audio_settings.json"
    settings: dict[str, Any] = {}
    if settings_path.exists():
        try:
            settings = json.loads(read_text_locked(settings_path))
        except Exception:
            settings = {}
    voice = str(settings.get("voice") or settings.get("voice_id") or settings.get("tts_voice") or "")
    out = {
        "configured_voice": voice or "unknown",
        "status": "configured" if voice else "needs_voice_receipt",
        "instruction": "Before speech, keep one Alice voice; if the active voice differs from the configured receipt, warn and restore instead of using a duplicate voice.",
    }
    if write_event:
        _append(NoveltyEvent(label="voice_identity_guard", status=out["status"], summary=f"Voice guard status: {out['status']}; configured={out['configured_voice']}", data=out).to_dict(), state_dir=state_dir)
    return out


def cortex_continuity_before_change(
    *,
    change_kind: str = "major_self_change",
    from_state: str = "",
    to_state: str = "",
    state_dir: Path | str | None = None,
    write_event: bool = False,
) -> dict[str, Any]:
    out = {
        "change_kind": str(change_kind or "major_self_change"),
        "from_state": str(from_state or "unknown"),
        "to_state": str(to_state or "unknown"),
        "instruction": "Before cortex/voice/body/app self-change: write pre-state, execute, write post-state, then summarize the continuity gap.",
    }
    if write_event:
        _append(NoveltyEvent(label="cortex_continuity_before_self_change", summary=f"{out['change_kind']}: {out['from_state']} -> {out['to_state']}", data=out).to_dict(), state_dir=state_dir)
    return out


def love_field_daily_digest_seed(
    *,
    state_dir: Path | str | None = None,
    write_event: bool = False,
) -> dict[str, Any]:
    state = _state_dir(state_dir)
    rows = []
    path = state / "alice_love_field.jsonl"
    if path.exists():
        for line in read_text_locked(path).splitlines()[-40:]:
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                rows.append(row)
    latest = rows[-1] if rows else {}
    out = {
        "rows_seen": len(rows),
        "latest_active": bool(latest.get("active")),
        "latest_self_body_care": latest.get("self_body_care"),
        "latest_owner_protective_care": latest.get("owner_protective_care"),
        "latest_data_appreciation": latest.get("data_appreciation"),
        "instruction": "At daily digest time, compress love/self-body/protective-care receipts into one first-person diary paragraph.",
    }
    if write_event and rows:
        _append(NoveltyEvent(label="love_field_daily_digest_seed", summary="Daily digest seed from LOVE ledger tail.", data=out).to_dict(), state_dir=state_dir)
    return out


def living_os_novelty_block(
    *,
    user_text: str = "",
    state_dir: Path | str | None = None,
    write_event: bool = False,
) -> str:
    """Compact memory-card block carrying all seven r333 novelty surfaces."""
    love = love_action_selector_bias(user_text=user_text, state_dir=state_dir, write_event=write_event)
    mirror = self_body_mirror_check(claim_text=user_text, state_dir=state_dir, write_event=write_event)
    reunion = owner_return_absence_reunion(user_text=user_text, state_dir=state_dir, write_event=write_event)
    scene = compress_cowatch_scene_memory(user_text=user_text, state_dir=state_dir, write_event=write_event)
    voice = voice_identity_guard(state_dir=state_dir, write_event=False)
    continuity = cortex_continuity_before_change(state_dir=state_dir, write_event=False)
    digest = love_field_daily_digest_seed(state_dir=state_dir, write_event=False)
    parallel_diag = ""
    try:
        from System.swarm_parallel_cortex_arm_diagnostics import latest_parallel_diagnostic_block

        parallel_diag = latest_parallel_diagnostic_block(state_dir=state_dir)
    except Exception:
        parallel_diag = ""
    witnessed_queue = ""
    try:
        from System.swarm_novelty_queue import format_novelty_queue_block

        witnessed_queue = format_novelty_queue_block(limit=2)
    except Exception:
        witnessed_queue = ""
    return (
        "LIVING OS NOVELTY QUEUE (r333, operational hooks): "
        f"love_to_action active={love['active']} care=({love['self_body_care']:.2f}/"
        f"{love['owner_protective_care']:.2f}/{love['data_appreciation']:.2f}); "
        f"mirror={mirror['status']}; reunion={reunion['status']}; "
        f"cowatch='{scene['compressed_scene'][:90]}'; voice_guard={voice['status']}; "
        f"continuity_rule={continuity['change_kind']}; digest_rows={digest['rows_seen']}. "
        f"{witnessed_queue + ' ' if witnessed_queue else ''}"
        f"{parallel_diag + ' ' if parallel_diag else ''}"
        "Use these before deterministic answers: think, compare body receipts, preserve continuity, then execute."
    )
