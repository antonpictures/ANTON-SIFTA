#!/usr/bin/env python3
"""
Deprecated shim — use Applications/ask_nugget.py (canonical metered-API entrypoint).

History:
  - 2026-04-19 afternoon: Applications/ask_lefty.py was canonical (sender_agent=LEFTY,
    Donnie Brasco doctrine — Lefty Ruggiero as the metered piecework friend).
  - 2026-04-19 evening: Architect renamed LEFTY → NUGGET (Nugget Doctrine —
    every metered call is expected to drop one verified factual nugget into
    local stigmergic storage). LEFTY is preserved here as a thin shim so
    older docs, shell history, scripts, and historical ledger lines stay
    valid. The agent identity is **NUGGET**; LEFTY is the prior alias.
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

_TARGET = Path(__file__).resolve().parent / "ask_nugget.py"
sys.argv[0] = str(_TARGET)
runpy.run_path(str(_TARGET), run_name="__main__")
