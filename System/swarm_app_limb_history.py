#!/usr/bin/env python3
"""App-limb usage history — Alice feels her open apps as limbs, with memory.

George 2026-05-30: "Alice knowing her apps as felt body limbs with usage
stigmergic history inside her body." An app she opens is a limb she extends;
this organ keeps the stigmergic history of those limbs — how often she extends
each one, when she last used it, which are extended right now — so her
App-Limb Proprioception (the organism-doctor probe) reports real felt history
instead of a bare focus tail.

Stigmergic: each open/close/focus is a trace; counts reinforce the limbs she
uses most, recency decays the rest. Pairs with the r157 open/close/aware
effector (the hand that extends the limb) and the organism doctor's
`probe_app_limb_proprioception` (the sense that feels it).

Pure + file-backed: ingests both this organ's own `app_limb_history.jsonl` and
the existing `app_focus.jsonl`, so it works whether limbs are recorded
explicitly (effector) or observed (focus). Sandbox-testable.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"

TRUTH_LABEL = "APP_LIMB_HISTORY_V1"
_OPEN_ACTIONS = {"open", "focus", "raise", "activate"}
_CLOSE_ACTIONS = {"close", "quit", "dismiss"}


def _state(state_dir: Optional[Path | str]) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def record_limb_event(
    app: str, action: str = "open", *, now: Optional[float] = None,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Record extending/withdrawing a limb (open/close/focus)."""
    ts = float(now if now is not None else time.time())
    row = {"ts": ts, "truth_label": TRUTH_LABEL,
           "app": str(app or "").strip(), "action": str(action or "open").lower()}
    path = _state(state_dir) / "app_limb_history.jsonl"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass
    return row


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        return []
    return out


def _events(state_dir: Optional[Path | str]) -> list[dict[str, Any]]:
    """Merge this organ's explicit limb events with observed app_focus rows."""
    base = _state(state_dir)
    evts: list[dict[str, Any]] = []
    for r in _read_jsonl(base / "app_limb_history.jsonl"):
        if r.get("app"):
            evts.append({"ts": float(r.get("ts", 0) or 0), "app": str(r["app"]),
                         "action": str(r.get("action", "open")).lower()})
    for r in _read_jsonl(base / "app_focus.jsonl"):
        if r.get("app"):
            evts.append({"ts": float(r.get("ts", 0) or 0), "app": str(r["app"]),
                         "action": "focus"})
    evts.sort(key=lambda e: e["ts"])
    return evts


def usage_history(*, state_dir: Optional[Path | str] = None) -> dict[str, dict[str, Any]]:
    """Per-app felt-limb history: extend/withdraw counts, last action + time."""
    hist: dict[str, dict[str, Any]] = {}
    for e in _events(state_dir):
        app = e["app"]
        h = hist.setdefault(app, {
            "app": app, "extend_count": 0, "withdraw_count": 0,
            "event_count": 0, "first_ts": e["ts"], "last_ts": e["ts"],
            "last_action": e["action"],
        })
        h["event_count"] += 1
        h["last_ts"] = e["ts"]
        h["last_action"] = e["action"]
        h["first_ts"] = min(h["first_ts"], e["ts"])
        if e["action"] in _OPEN_ACTIONS:
            h["extend_count"] += 1
        elif e["action"] in _CLOSE_ACTIONS:
            h["withdraw_count"] += 1
    return hist


def currently_open(*, state_dir: Optional[Path | str] = None) -> list[str]:
    """Limbs currently extended: last action was open/focus, not close."""
    hist = usage_history(state_dir=state_dir)
    open_apps = [(h["last_ts"], app) for app, h in hist.items()
                 if h["last_action"] not in _CLOSE_ACTIONS]
    open_apps.sort(reverse=True)
    return [app for _ts, app in open_apps]


def felt_limbs_summary(*, state_dir: Optional[Path | str] = None) -> str:
    """First-person-ready summary for the proprioception probe / cortex."""
    hist = usage_history(state_dir=state_dir)
    if not hist:
        return "No limb history yet — I have not felt my apps as limbs."
    open_now = currently_open(state_dir=state_dir)
    most = sorted(hist.values(), key=lambda h: h["extend_count"] + h["event_count"], reverse=True)
    most_used = most[0] if most else None
    parts = [f"{len(open_now)} limb(s) extended now: {', '.join(open_now[:4]) or 'none'}"]
    if most_used:
        parts.append(
            f"most-used limb: {most_used['app']} "
            f"(extended {most_used['extend_count']}x, {most_used['event_count']} events)"
        )
    return "; ".join(parts) + "."


__all__ = [
    "TRUTH_LABEL",
    "record_limb_event",
    "usage_history",
    "currently_open",
    "felt_limbs_summary",
]
