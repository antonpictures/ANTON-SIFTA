#!/usr/bin/env python3
"""
Deprecated shim — use Applications/ask_bishapi.py (canonical BISHAPI entrypoint).

This file remains so older docs and shell history keep working.
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

_TARGET = Path(__file__).resolve().parent / "ask_bishapi.py"
sys.argv[0] = str(_TARGET)
runpy.run_path(str(_TARGET), run_name="__main__")
