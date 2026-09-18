#!/usr/bin/env python3
"""SIFTA-owned adapter: use the existing Host API, not a fork of the agent loop."""
import sys
from pathlib import Path

# parents[2] == the SIFTA deployment root. This must equal the bridge's own
# import root (parents[1] in System/swarm_dsh_wct_bridge.py); both resolve to
# /Users/ioanganton/Music/ANTON_SIFTA. If either file moves one directory
# level, update the offset here so --root default stays anchored.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from System.swarm_dsh_wct_bridge import main

if __name__ == "__main__":
    raise SystemExit(main())
