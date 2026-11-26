#!/usr/bin/env python3
"""swarm_speak_toggle.py — flip the body's speak on/off master switch.

Shared by the Talk window and OpenCode. State: .sifta_state/speak_enabled
Usage:
  python3 System/swarm_speak_toggle.py          # toggle, print new state
  python3 System/swarm_speak_toggle.py on       # force on
  python3 System/swarm_speak_toggle.py off      # force off
  python3 System/swarm_speak_toggle.py status   # print current state
"""
from __future__ import annotations
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STATE = REPO / ".sifta_state" / "speak_enabled"


def current() -> bool:
    try:
        if STATE.exists():
            return STATE.read_text().strip().lower() not in ("0", "false", "off", "no")
    except Exception:
        pass
    return True


def set_state(on: bool) -> bool:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text("1" if on else "0")
    return on


def main() -> int:
    arg = (sys.argv[1].lower() if len(sys.argv) > 1 else "toggle")
    if arg == "status":
        print("ON" if current() else "OFF")
        return 0
    if arg == "on":
        on = True
    elif arg == "off":
        on = False
    elif arg == "toggle":
        on = not current()
    else:
        print(f"unknown arg: {arg}", file=sys.stderr)
        return 2
    set_state(on)
    print("Speak:", "ON" if on else "OFF")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
PY