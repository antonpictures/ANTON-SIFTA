#!/usr/bin/env python3
"""CLI wrapper for `System.swarm_edge_unified_verifier`."""
from __future__ import annotations

from pathlib import Path
import sys

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.swarm_edge_unified_verifier import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
