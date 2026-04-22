#!/usr/bin/env python3
"""
Deprecated shim — use Applications/ask_nugget.py (canonical metered-API entrypoint).

This file remains so older docs and shell history keep working. See
Applications/ask_nugget.py docstring for the BISHOP / NUGGET split:
  • BISHOP — Chrome-tab Gemini, $250/mo Ultra subscription, flat rate.
  • NUGGET — per-token API miner, real wallet, one nugget per call.

(Historical: this file used to invoke BISHOP-the-API. After the BISHAPI →
LEFTY rename, the API agent's identity was LEFTY. After the LEFTY → NUGGET
rename, it is NUGGET. BISHOP-in-Chrome is a different doctrine entirely.)
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

_TARGET = Path(__file__).resolve().parent / "ask_nugget.py"
sys.argv[0] = str(_TARGET)
runpy.run_path(str(_TARGET), run_name="__main__")
