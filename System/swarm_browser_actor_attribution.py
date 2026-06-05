#!/usr/bin/env python3
"""
System/swarm_browser_actor_attribution.py — who moved the browser: Alice (self) or George (owner)?

Finding (Cowork r460, probe-before-claim from a live session 2026-06-03 ~14:51): a DuckDuckGo
search for "pale light-colored top woman outdoors green foliage" appeared in Alice's browser
during an eval. George said *Alice* ran it; Alice's own receipts said *George* ran it
(`owner_browser_behaviour`, "my owner's hands moving inside me"). Both can't be right — and the
reason they conflict is a real bug: `sifta_alice_browser_widget.py` calls
`log_owner_browser_behaviour(...)` on EVERY navigate / load / DOM change, hard-asserting that the
owner did it (r222 Lane B comment: "George is now here doing this"). There is no actor check. So
when Alice's OWN agent drives the browser, it is silently relabeled as George's hands.

For an organism aiming at autonomy that exceeds human-designed bounds (§0), this matters: an agent
must know which actions are its own. This is the effector-side twin of the typed-vs-spoken input
provenance work — there it was "did George type or speak this?"; here it is "did Alice or George
move the browser?"

This organ does NOT decide for the widget; it returns an honest attribution the widget can record
instead of hard-coding the owner. The key correction: when there is NO positive evidence of owner
presence, do not claim "George's hands" — record `unattributed`. Only claim `owner` with an owner
signal (keystroke/click/typed turn), and `self` with an Alice browser-effector receipt.

Truth label: BROWSER_ACTOR_ATTRIBUTION_V1. Read-only; best-effort field reader; no network.
For the Swarm. 🐜⚡
"""
from __future__ import annotations

import json
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

# Ledgers that would carry positive evidence of an ALICE-initiated browser action.
_ALICE_EFFECTOR_LEDGERS = (
    "app_action_diary.jsonl",
    "tool_router_trace.jsonl",
    "work_receipts.jsonl",
    "agent_arm_receipts.jsonl",
)
# Ledgers that would carry positive evidence of OWNER presence at the moment.
_OWNER_SIGNAL_LEDGERS = ("alice_conversation.jsonl", "active_window.jsonl", "owner_body_events.jsonl")

_WINDOW_S = 20.0  # an action is "explained" by a signal within this many seconds


def _recent_hit(
    ledgers,
    *,
    now: float,
    needles,
    window_s: float = _WINDOW_S,
    state_dir: Path | str | None = None,
) -> bool:
    """True if any of `ledgers` has a row within window_s whose text contains any needle."""
    state = Path(state_dir) if state_dir is not None else _STATE
    cut = now - window_s
    for name in ledgers:
        p = state / name
        if not p.exists():
            continue
        try:
            with p.open("rb") as f:
                f.seek(0, 2)
                size = f.tell()
                f.seek(max(0, size - 200_000))
                raw = f.read()
            lines = raw.decode("utf-8", errors="replace").splitlines()[-300:]
        except OSError:
            continue
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            try:
                ts = float(row.get("ts") or row.get("timestamp") or 0.0)
            except Exception:
                ts = 0.0
            if ts and ts < cut:
                continue
            blob = json.dumps(row, ensure_ascii=False).lower()
            if any(n in blob for n in needles):
                return True
    return False


def attribute_browser_action(
    url: str = "",
    *,
    now: float | None = None,
    alice_effector: bool | None = None,
    owner_input: bool | None = None,
    state_dir: Path | str | None = None,
) -> dict:
    """Return {actor, confidence, reason} for a browser action.

    actor: 'self' (Alice's own agent) | 'owner' (George) | 'unattributed' (no evidence either way).
    Callers may pass alice_effector / owner_input directly; otherwise a best-effort field read fills
    them. The correction vs the old hard-coded owner assumption: default to 'unattributed', never a
    false 'owner'.
    """
    now = time.time() if now is None else float(now)
    state = Path(state_dir) if state_dir is not None else _STATE
    if alice_effector is None:
        alice_effector = _recent_hit(
            _ALICE_EFFECTOR_LEDGERS,
            now=now,
            needles=(
                "open_browser_url",
                "alice browser",
                "browser_action",
                "browser",
                "navigate",
                "duckduckgo",
                "web_search",
                "open_url",
            ),
            state_dir=state,
        )
    if owner_input is None:
        owner_input = _recent_hit(
            _OWNER_SIGNAL_LEDGERS,
            now=now,
            needles=("typed", "keystroke", "input_source", "owner"),
            state_dir=state,
        )

    if alice_effector:
        actor = "self"
        conf = 0.75 if owner_input else 0.85
        reason = (
            "an Alice browser-effector receipt fired near this action; "
            "a recent owner signal may be the trigger, but the browser hand was Alice's effector"
            if owner_input
            else "an Alice browser-effector receipt fired near this action; no owner signal"
        )
    elif owner_input and not alice_effector:
        actor, conf, reason = "owner", 0.8, "an owner input/presence signal fired near this action; no Alice effector"
    else:
        actor, conf, reason = "unattributed", 0.5, "no Alice-effector and no owner signal — do NOT assert owner's hands"
    return {
        "truth_label": "BROWSER_ACTOR_ATTRIBUTION_V1",
        "ts": round(now, 3),
        "url": (url or "")[:300],
        "actor": actor,
        "confidence": conf,
        "reason": reason,
        "alice_effector_recent": bool(alice_effector),
        "owner_signal_recent": bool(owner_input),
        "doctrine": "Alice must know her own hands from George's; never claim 'owner' without an owner signal",
        "source": "swarm_browser_actor_attribution",
    }


def main() -> int:
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else "https://duckduckgo.com/?q=test"
    print(json.dumps(attribute_browser_action(url), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
