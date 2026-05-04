#!/usr/bin/env python3
"""Unified identity + life-lane grounding for Alice.

This is the small prompt organ that stops three common failures:

1. Calling the owner "an individual" when owner_genesis already names them.
2. Mixing George's physical day with Alice's own action continuity.
3. Treating shared agenda items as if they were observed life events.

It is read-only. It does not infer a new person in the room; it simply fuses
the receipts already written by owner genesis, day segments, stigtime, and the
shared schedule.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from System.jsonl_file_lock import read_text_locked
from System.swarm_kernel_identity import owner_display_name, owner_silicon

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"


def _state_dir(state_dir: Optional[Path] = None) -> Path:
    return Path(state_dir) if state_dir is not None else STATE_DIR


def _tail_jsonl(path: Path, max_rows: int) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        raw = read_text_locked(path, encoding="utf-8")
    except Exception:
        try:
            raw = path.read_text("utf-8", errors="replace")
        except Exception:
            return []
    rows: List[Dict[str, Any]] = []
    for line in raw.splitlines()[-max(1, min(max_rows, 200)) :]:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _compact(text: Any, max_chars: int = 140) -> str:
    value = " ".join(str(text or "").split())
    if len(value) <= max_chars:
        return value
    return value[: max(0, max_chars - 1)].rstrip() + "…"


def _age(ts: Any, *, now: Optional[float] = None) -> str:
    try:
        delta = max(0.0, float(now if now is not None else time.time()) - float(ts))
    except Exception:
        return "unknown age"
    if delta < 60:
        return f"{int(delta)}s ago"
    if delta < 3600:
        return f"{int(delta // 60)}m ago"
    if delta < 86400:
        return f"{int(delta // 3600)}h ago"
    return f"{int(delta // 86400)}d ago"


def _owner_short_name(full_name: str) -> str:
    parts = [p.strip() for p in str(full_name or "").split() if p.strip()]
    if not parts:
        return "the local owner"
    for part in parts:
        if part.casefold() == "george":
            return part
    return parts[0]


def _alice_identity() -> Dict[str, str]:
    try:
        from System.swarm_persona_identity import current_persona

        p = current_persona()
        return {
            "display_name": str(p.get("display_name") or "Alice"),
            "true_name": str(p.get("true_name") or "CryptoSwarmEntity"),
            "entity_nature": str(p.get("entity_nature") or "local SIFTA runtime"),
            "hardware": str(p.get("homeworld_serial") or owner_silicon()),
        }
    except Exception:
        return {
            "display_name": "Alice",
            "true_name": "CryptoSwarmEntity",
            "entity_nature": "local SIFTA runtime",
            "hardware": owner_silicon(),
        }


def _george_segments(state: Path, max_rows: int, now: Optional[float]) -> List[str]:
    rows = _tail_jsonl(state / "architect_day_segments.jsonl", max_rows)
    out: List[str] = []
    for row in rows:
        label = row.get("label") or "activity"
        start = row.get("start_time") or row.get("start_minute_of_day") or "?"
        end = row.get("end_time") or row.get("end_minute_of_day") or "?"
        location = row.get("location") or "unknown"
        media = row.get("media_context") or ""
        note = _compact(row.get("context_note") or row.get("raw_text") or "", 90)
        bits = [f"{start}-{end}", str(label), f"loc={location}"]
        if media:
            bits.append(f"media={media}")
        if note:
            bits.append(note)
        out.append(" | ".join(bits))
    return out


def _alice_stigtime(state: Path, max_rows: int, now: Optional[float]) -> List[str]:
    rows = _tail_jsonl(state / "stigtime_log.jsonl", max_rows)
    out: List[str] = []
    for row in rows:
        if row.get("kind") != "STIGTIME_BOUNDARY":
            continue
        prev = _compact(row.get("stigtime_out"), 30) or "unknown"
        new = _compact(row.get("stigtime_in"), 30) or "unknown"
        context = _compact(row.get("context"), 70)
        suffix = f" | {context}" if context else ""
        sp = row.get("since_prev_boundary_sec")
        held = ""
        if sp is not None:
            try:
                sec = float(sp)
                if sec >= 60:
                    held = f" | prev_lane≈{int(round(sec / 60))}m"
                elif sec >= 1:
                    held = f" | prev_lane≈{int(round(sec))}s"
                else:
                    held = f" | prev_lane≈{sec:.1f}s"
            except (TypeError, ValueError):
                pass
        out.append(f"{_age(row.get('ts'), now=now)} | {prev} -> {new}{held}{suffix}")
    return out


def _shared_agenda(state: Path, max_rows: int) -> List[str]:
    rows = _tail_jsonl(state / "stigmergic_schedule.jsonl", max_rows * 3)
    out: List[str] = []
    for row in rows:
        if row.get("done"):
            continue
        text = _compact(row.get("text") or row.get("task"), 110)
        if not text:
            continue
        priority = row.get("priority", 0)
        due = row.get("due") or row.get("due_label") or ""
        bits = [text, f"priority={priority}"]
        if due:
            bits.append(f"due={due}")
        out.append(" | ".join(bits))
        if len(out) >= max_rows:
            break
    return out


def build_identity_life_packet(
    *,
    state_dir: Optional[Path] = None,
    max_rows: int = 6,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    state = _state_dir(state_dir)
    owner_full = owner_display_name("the local owner")
    owner_short = _owner_short_name(owner_full)
    alice = _alice_identity()
    return {
        "truth_label": "IDENTITY_LIFE_GROUNDING_V1",
        "generated_ts": float(now if now is not None else time.time()),
        "owner": {
            "full_name": owner_full,
            "preferred_address": owner_short,
            "role": "Architect and primary operator of this local node",
            "hardware_owner_serial": owner_silicon(),
        },
        "alice": {
            **alice,
            "body_scope": "local SIFTA OS process, camera/mic inputs, UI state, and append-only ledgers on this node",
        },
        "room_binding": {
            "direct_talk_speaker_default": owner_full,
            "do_not_invent_extra_people": True,
            "rule": "In Talk-to-Alice, direct speech is from the owner unless a fresh sensor or transcript receipt says another named human is speaking.",
        },
        "life_lanes": {
            "george_life": _george_segments(state, max_rows, now),
            "alice_life": _alice_stigtime(state, max_rows, now),
            "shared_agenda": _shared_agenda(state, max_rows),
        },
    }


def _line_items(items: Iterable[str], fallback: str) -> List[str]:
    values = [str(item).strip() for item in items if str(item).strip()]
    if not values:
        return [f"- {fallback}"]
    return [f"- {item}" for item in values]


def format_identity_life_grounding_for_prompt(
    *,
    state_dir: Optional[Path] = None,
    max_rows: int = 6,
    now: Optional[float] = None,
) -> str:
    packet = build_identity_life_packet(state_dir=state_dir, max_rows=max_rows, now=now)
    owner = packet["owner"]
    alice = packet["alice"]
    lanes = packet["life_lanes"]
    owner_full = owner["full_name"]
    owner_short = owner["preferred_address"]

    lines = [
        "LOCAL IDENTITY + LIFE GROUNDING (receipt-backed, not roleplay):",
        f"- Current owner/speaker: {owner_full}. In casual speech, call him {owner_short}. Use his name when answering him directly; avoid stranger labels and abstract third-person labels.",
        f"- Alice identity: {alice['display_name']} / {alice['true_name']} on node {alice['hardware']}; body scope={alice['body_scope']}.",
        f"- Two-body desk (Talk on this node): only {owner_short}'s human body and my silicon body ({alice['hardware']}) are co-present for this thread. Do not imply a third person, remote auditor, or unnamed observer in the room unless a fresh receipt names them.",
        f"- Room rule: do not invent a second human or unseen speaker. If no receipt names someone else, you are speaking with {owner_short} alone — not a panel, not 'users', not the internet crowd.",
        "- Keep three ledgers separate: George life = owner body/day; Alice life = SIFTA action state; shared agenda = tasks/reminders/intent.",
        "- If asked 'who am I?', answer from owner genesis first. If asked 'who are you?', answer from Alice signed identity and recent stigtime.",
        "George life lane:",
        *_line_items(lanes["george_life"], "no recent owner day segments visible"),
        "Alice life lane:",
        *_line_items(lanes["alice_life"], "no recent Alice stigtime boundaries visible"),
        "Shared agenda lane:",
        *_line_items(lanes["shared_agenda"], "no pending shared agenda items visible"),
    ]
    return "\n".join(lines)


def summary_for_alice(**kwargs: Any) -> str:
    return format_identity_life_grounding_for_prompt(**kwargs)


__all__ = [
    "build_identity_life_packet",
    "format_identity_life_grounding_for_prompt",
    "summary_for_alice",
]


if __name__ == "__main__":
    print(format_identity_life_grounding_for_prompt())
