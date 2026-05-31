#!/usr/bin/env python3
"""App-action deliberation diary for Alice's OS limbs.

Every open/close/switch app action should be preceded by a fresh state estimate:
what is open, what the owner asked for, what action is intended, and why that
action is coherent. The diary is a stigmergic trace, not a private chat; later
cortex turns can read it to know what the body did and when.
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
TRUTH_LABEL = "APP_ACTION_DELIBERATION_V1"
DIARY_NAME = "app_action_diary.jsonl"


def _state_dir(state_dir: str | Path | None = None) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def _read_jsonl(path: Path, *, limit: int = 20) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        return []
    return rows[-limit:]


def _open_apps(state: Mapping[str, Any] | None) -> list[str]:
    raw = (state or {}).get("open_apps") or []
    if not isinstance(raw, list):
        return []
    return [str(x) for x in raw if str(x or "").strip()]


def _active_app(state: Mapping[str, Any] | None) -> str:
    return str((state or {}).get("active_app") or "").strip()


def _desktop_mode(state: Mapping[str, Any] | None) -> str:
    return str((state or {}).get("desktop_mode") or "").strip()


def deliberate_app_action(
    *,
    action: str,
    app_name: str = "",
    url: str = "",
    owner_text: str = "",
    before_state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the pre-action cortex context packet from the body state."""
    action = str(action or "").strip()
    app_name = str(app_name or "").strip()
    url = str(url or "").strip()
    open_before = _open_apps(before_state)
    active_before = _active_app(before_state)

    target = app_name or url or "current app"
    already_open = bool(app_name and any(a.casefold() == app_name.casefold() for a in open_before))
    if action.startswith("open") and already_open:
        decision = "raise_existing_limb"
        rationale = f"{app_name} is already open; raise/focus it instead of opening a second copy."
    elif action.startswith("open"):
        decision = "extend_limb"
        rationale = f"{target} is not the active open limb; open it through the SIFTA desktop."
    elif action.startswith("close") and open_before:
        decision = "withdraw_limb"
        rationale = f"Current open limbs are {open_before}; close the requested limb and return to resident chat."
    elif action.startswith("close"):
        decision = "noop_no_limb"
        rationale = "No open SIFTA app limb is visible; do not invent a close action."
    elif action.startswith("switch"):
        decision = "switch_territory"
        rationale = "Switching desktop territory changes focus, not Alice identity."
    else:
        decision = "observe_only"
        rationale = "No app-limb mutation required."

    return {
        "truth_label": TRUTH_LABEL,
        "action": action,
        "app_name": app_name,
        "url": url,
        "owner_text": owner_text,
        "decision": decision,
        "rationale": rationale,
        "before_open_apps": open_before,
        "before_active_app": active_before,
        "before_desktop_mode": _desktop_mode(before_state),
        "single_app_policy": bool((before_state or {}).get("single_app_policy", True)),
    }


def record_app_action_diary(
    *,
    phase: str,
    action: str,
    app_name: str = "",
    url: str = "",
    owner_text: str = "",
    before_state: Mapping[str, Any] | None = None,
    after_state: Mapping[str, Any] | None = None,
    decision: str = "",
    rationale: str = "",
    receipt_id: str = "",
    ok: bool | None = None,
    state_dir: str | Path | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Append one timestamped app-action diary row."""
    ts = float(time.time() if now is None else now)
    if not decision or not rationale:
        packet = deliberate_app_action(
            action=action,
            app_name=app_name,
            url=url,
            owner_text=owner_text,
            before_state=before_state,
        )
        decision = decision or str(packet.get("decision") or "")
        rationale = rationale or str(packet.get("rationale") or "")

    row: dict[str, Any] = {
        "ts": ts,
        "trace_id": str(uuid.uuid4()),
        "truth_label": TRUTH_LABEL,
        "phase": phase,
        "action": action,
        "app_name": app_name,
        "url": url,
        "owner_text": owner_text,
        "decision": decision,
        "rationale": rationale,
        "receipt_id": receipt_id,
        "ok": ok,
        "before_open_apps": _open_apps(before_state),
        "before_active_app": _active_app(before_state),
        "before_desktop_mode": _desktop_mode(before_state),
        "after_open_apps": _open_apps(after_state),
        "after_active_app": _active_app(after_state),
        "after_desktop_mode": _desktop_mode(after_state),
    }

    sd = _state_dir(state_dir)
    try:
        sd.mkdir(parents=True, exist_ok=True)
        with (sd / DIARY_NAME).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass
    return row


def recent_app_action_diary(
    *, state_dir: str | Path | None = None, limit: int = 6
) -> list[dict[str, Any]]:
    return _read_jsonl(_state_dir(state_dir) / DIARY_NAME, limit=limit)


def current_app_action_context_block(
    *, state_dir: str | Path | None = None, limit: int = 4
) -> str:
    """Prompt block for the cortex: read before open/close/switch actions."""
    sd = _state_dir(state_dir)
    current: dict[str, Any] = {}
    try:
        p = sd / "sifta_desktop_app_state.json"
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            current = data if isinstance(data, dict) else {}
    except Exception:
        current = {}

    try:
        from System.swarm_app_limb_history import currently_open, felt_limbs_summary

        open_now = currently_open(state_dir=sd)
        felt = felt_limbs_summary(state_dir=sd)
    except Exception:
        open_now = _open_apps(current)
        felt = ""

    lines = [
        "APP-LIMB CORTEX CONTEXT (read before any app action):",
        f"- current desktop mode: {_desktop_mode(current) or 'unknown'}",
        f"- active app: {_active_app(current) or 'none'}",
        f"- open app limbs: {', '.join(open_now) if open_now else 'none'}",
    ]
    if felt:
        lines.append(f"- felt limb history: {felt}")

    diary = recent_app_action_diary(state_dir=sd, limit=limit)
    if diary:
        lines.append("- recent app action diary:")
        for row in diary[-limit:]:
            ts = row.get("ts")
            app = row.get("app_name") or row.get("url") or "current"
            decision = row.get("decision") or row.get("action")
            phase = row.get("phase") or "?"
            lines.append(f"  - {ts}: {phase} {row.get('action')} {app} -> {decision}")
    else:
        lines.append("- recent app action diary: none yet")
    return "\n".join(lines)


__all__ = [
    "TRUTH_LABEL",
    "DIARY_NAME",
    "current_app_action_context_block",
    "deliberate_app_action",
    "recent_app_action_diary",
    "record_app_action_diary",
]
