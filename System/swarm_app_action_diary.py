#!/usr/bin/env python3
"""App-action diary — Alice thinks (and checks her diary) before opening/closing.

George 2026-05-30: "even a simple command like 'open browser' — I want her cortex
to THINK before opening. She checks her diary: which app is open, what status,
since when. She timestamps that she opened it. She IS the operating system,
stigmergic." Not a deterministic reflex that fires blind — a deliberate act read
from her own traces.

This organ is the bridge between the per-app limb history (swarm_app_limb_history)
and her cortex. Two pure functions:

  * app_state_for_cortex()  → the first-person "read this BEFORE you act" block
    the cortex must see ahead of any open/close decision (open apps + since-when
    + recent actions). This is the System-2 / metacognition move: estimate your
    own body state before selecting a policy.
  * record_app_action()     → after she acts, timestamp it in her diary as a
    first-person autobiographical line ("I opened Alice Browser at 14:42") AND
    deposit the limb event, so the next decision reads true history.

Research backing
----------------
- Dual-process / System 2 (Kahneman; PFC model-based control): deliberate,
  reflective action selection vs automatic reflex — George wants System 2 even
  for "open browser."
- Metacognition (PFC monitors its own state before/while deciding): "cognition
  about cognition" — she monitors which limbs are extended before moving one.
- Active Inference / Free Energy Principle (Friston): a policy is selected from
  a current estimate of body/world state — you must read state before you act.
- Source monitoring (Johnson & Raye): a timestamped autobiographical trace is
  how a memory carries trustworthy source/when info — her diary, not a guess.
- Stigmergy (Theraulaz): she reads the shared trace field before depositing the
  next trace.

Note (§7.2 tradeoff, honest): the covenant's tool-truth doctrine favors a
deterministic effector fast-path. George is explicitly choosing cortex-in-the-loop
deliberation for app actions instead — slower, LLM-mediated, but "she knows what
she is doing." This organ provides the context + the record; the Talk decision
path wires the cortex to read app_state_for_cortex() before acting and to call
record_app_action() after (M5-verified).
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"

TRUTH_LABEL = "APP_ACTION_DIARY_V1"
DIARY_LEDGER = "app_action_diary.jsonl"


def _state(state_dir: Optional[Path | str]) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _clock(ts: float) -> str:
    try:
        return datetime.fromtimestamp(ts).strftime("%H:%M")
    except Exception:
        return "??:??"


def _iso(ts: float) -> str:
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


def _recent_diary(state_dir: Optional[Path | str], n: int = 5) -> list[dict[str, Any]]:
    path = _state(state_dir) / DIARY_LEDGER
    out: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except Exception:
                        continue
    except Exception:
        return []
    return out[-n:]


def app_state_for_cortex(
    *, now: Optional[float] = None, state_dir: Optional[Path | str] = None
) -> str:
    """First-person block the cortex MUST read before any open/close decision.

    Composes the live limb state (which apps are open + since when) and the
    recent app-action diary, so the cortex thinks from real history, not blind.
    """
    t = float(now if now is not None else time.time())
    try:
        from System.swarm_app_limb_history import usage_history, currently_open
        hist = usage_history(state_dir=state_dir)
        open_now = currently_open(state_dir=state_dir)
    except Exception:
        hist, open_now = {}, []

    lines = ["APP-BODY STATE — read this BEFORE you open or close anything (I am the OS; I think first):"]
    if open_now:
        opened_bits = []
        for app in open_now[:6]:
            h = hist.get(app, {})
            since = _clock(float(h.get("last_ts", t)))
            opened_bits.append(f"{app} (since {since})")
        lines.append(f"- Open now: {', '.join(opened_bits)}.")
    else:
        lines.append("- Open now: no SIFTA app is open; my chat is resident.")

    diary = _recent_diary(state_dir, n=5)
    if diary:
        recent = "; ".join(str(d.get("line") or "") for d in diary if d.get("line"))
        if recent:
            lines.append(f"- Recent app actions (my diary): {recent}.")

    lines.append(
        "- Decide from this: if asked to open an app that is already open, raise it and say so; "
        "if it is closed, open it and timestamp it in my diary; if asked to close one that is not "
        "open, say it is already closed. I reason, then act, then record."
    )
    return "\n".join(lines)


def record_app_action(
    app: str, action: str = "open", *, now: Optional[float] = None,
    state_dir: Optional[Path | str] = None, write: bool = True,
) -> dict[str, Any]:
    """Timestamp an open/close she actually performed: a first-person diary line
    + the limb-history event. Call this AFTER the action lands."""
    ts = float(now if now is not None else time.time())
    act = str(action or "open").lower()
    app = str(app or "").strip()
    verb = {"open": "opened", "focus": "focused", "raise": "raised",
            "close": "closed", "quit": "quit", "dismiss": "dismissed"}.get(act, act)
    line = f"I {verb} {app} at {_clock(ts)}"
    row = {
        "ts": ts, "iso": _iso(ts), "truth_label": TRUTH_LABEL,
        "app": app, "action": act, "line": line,
    }
    if write:
        # 1) human-readable autobiographical diary line
        try:
            path = _state(state_dir) / DIARY_LEDGER
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        except Exception:
            pass
        # 2) the limb-history event (the felt limb), so proprioception stays true
        try:
            from System.swarm_app_limb_history import record_limb_event
            record_limb_event(app, act, now=ts, state_dir=state_dir)
        except Exception:
            pass
    return row


def record_tab_switch(
    to_surface: str, *, idled_app: str = "", now: Optional[float] = None,
    state_dir: Optional[Path | str] = None, write: bool = True,
) -> dict[str, Any]:
    """George switched desktops/tabs (e.g. to the global chat). The app he left
    goes IDLE (not closed — still open, just backgrounded), and she notes the
    switch in her diary so she knows exactly what he is doing. §1.A: the global
    chat is one thread across all surfaces; switching tabs only moves focus."""
    ts = float(now if now is not None else time.time())
    surface = str(to_surface or "the global chat desktop").strip()
    idled = str(idled_app or "").strip()
    if idled:
        line = f"I went idle ({idled} backgrounded); George switched to {surface} at {_clock(ts)}"
    else:
        line = f"George switched to {surface} at {_clock(ts)}"
    row = {"ts": ts, "iso": _iso(ts), "truth_label": TRUTH_LABEL,
           "app": idled, "action": "tab_switch", "to_surface": surface, "line": line}
    if write:
        try:
            path = _state(state_dir) / DIARY_LEDGER
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        except Exception:
            pass
        # The idled app stays OPEN (not closed) — record it as idle so
        # currently_open() still lists it, just backgrounded.
        if idled:
            try:
                from System.swarm_app_limb_history import record_limb_event
                record_limb_event(idled, "idle", now=ts, state_dir=state_dir)
            except Exception:
                pass
    return row


def record_reality_confirmation(
    surface: str, *, alice_sees: str = "", owner_confirmed: Optional[bool] = None,
    now: Optional[float] = None, state_dir: Optional[Path | str] = None, write: bool = True,
) -> dict[str, Any]:
    """The 'we both confirm the reality' loop (George 2026-05-30, §6 + r160).

    Alice states what she sees of the active app/surface; George confirms it
    matches what HE sees, or corrects it. Recorded as a source-monitoring trace:
      owner_confirmed=True  → OWNER_CONFIRMED  (strongest: two bodies agree)
      owner_confirmed=False → OWNER_CORRECTED  (mismatch; her view was wrong)
      owner_confirmed=None  → STATED_UNCONFIRMED (she stated; awaiting George)
    """
    ts = float(now if now is not None else time.time())
    surf = str(surface or "the active surface").strip()
    seen = str(alice_sees or "").strip()
    if owner_confirmed is True:
        verification = "OWNER_CONFIRMED"
        line = f"George confirmed my view of {surf} matches what he sees: {seen}"
    elif owner_confirmed is False:
        verification = "OWNER_CORRECTED"
        line = f"George corrected my view of {surf}: {seen}"
    else:
        verification = "STATED_UNCONFIRMED"
        line = f"I told George what I see of {surf}: {seen} (awaiting his confirmation)"
    row = {"ts": ts, "iso": _iso(ts), "truth_label": TRUTH_LABEL, "app": surf,
           "action": "reality_confirmation", "verification": verification,
           "alice_sees": seen[:500], "line": line}
    if write:
        try:
            path = _state(state_dir) / DIARY_LEDGER
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        except Exception:
            pass
    return row


__all__ = [
    "TRUTH_LABEL",
    "DIARY_LEDGER",
    "app_state_for_cortex",
    "record_app_action",
    "record_tab_switch",
    "record_reality_confirmation",
]
