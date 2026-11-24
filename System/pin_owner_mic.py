#!/usr/bin/env python3
"""pin_owner_mic.py — keep the laptop's mic as the system default input.

Reuses the body's existing mic doctrine from System/audio_ingress.py:
embedded MacBook/FaceTime mic wins; iPhone/Continuity is never the owner's
default. Run once, or from a launchd agent every 30s.

    python3 System/pin_owner_mic.py            # enforce now
    python3 System/pin_owner_mic.py --status   # report only
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from System.audio_ingress import (  # noqa: E402
    is_embedded_owner_microphone,
    default_microphone_rank,
)

SWITCH = "/opt/homebrew/bin/SwitchAudioSource"


def _run(args: list[str]) -> str:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return ""


def inputs() -> list[str]:
    return [line.strip() for line in _run([SWITCH, "-a", "-t", "input"]).splitlines() if line.strip()]


def current() -> str:
    return _run([SWITCH, "-c", "-t", "input"])


def choose(names: list[str]) -> str:
    """Embedded owner mic first (the same ranking the body already uses)."""
    embedded = [n for n in names if is_embedded_owner_microphone(n)]
    if embedded:
        return sorted(embedded, key=lambda n: (default_microphone_rank(n), n))[0]
    return sorted(names, key=lambda n: (default_microphone_rank(n), n))[0] if names else ""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Pin the built-in laptop mic")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args(argv)

    now = current()
    target = choose(inputs())
    if args.status:
        print(f"current={now!r} target={target!r}")
        return 0 if is_embedded_owner_microphone(now) else 1

    if target and now != target:
        out = _run([SWITCH, "-s", target, "-t", "input"])
        print(f"set input -> {target} ({out})")
    else:
        print(f"input already owner mic: {now or target}")
    final = current()
    print(f"verified: {final}")
    return 0 if is_embedded_owner_microphone(final) else 1


if __name__ == "__main__":
    sys.exit(main())
