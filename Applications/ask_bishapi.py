#!/usr/bin/env python3
"""
Deprecated shim — use Applications/ask_nugget.py (canonical metered-API entrypoint).

History:
  - 2026-04-19 morning:    ask_bishapi.py canonical (sender_agent=BISHAPI).
  - 2026-04-19 afternoon:  Architect renamed BISHAPI → LEFTY (Donnie Brasco doctrine).
  - 2026-04-19 evening:    Architect renamed LEFTY → NUGGET (Nugget Doctrine —
                           every metered call is expected to drop one verified
                           factual nugget into local stigmergic storage).

This shim forwards directly to ask_nugget.py (skipping the also-shimmed
ask_lefty.py) so older docs, shell history, scripts, and historical ledger
lines stay valid. The agent identity is **NUGGET**; BISHAPI and LEFTY are
prior aliases preserved only for backward compatibility.
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

_TARGET = Path(__file__).resolve().parent / "ask_nugget.py"
sys.argv[0] = str(_TARGET)
runpy.run_path(str(_TARGET), run_name="__main__")
