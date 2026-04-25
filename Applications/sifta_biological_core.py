#!/usr/bin/env python3
"""Shared biological HUD / tension helpers (no Tk, no Qt)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = _REPO_ROOT / ".sifta_state" / "state_bus.json"


def read_biology_tension() -> float:
    """Poll the local state bus for ecosystem tension (same on every node)."""
    try:
        if STATE_FILE.exists():
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
                vol = data.get("volatility_history", [])
                return 0.1 + (len(vol) * 0.05)
    except Exception:
        pass
    return 0.8


def node_hud_title_line() -> str:
    """
    Identify *this* machine — not a remote node.
    M5 Foundry (GTH4921YP3) vs M1 Sentry (C07FL0JAQ6NV); unknown serials still labeled honestly.
    """
    try:
        if str(_REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(_REPO_ROOT))
        from body_state import SwarmBody

        sn = SwarmBody.get_local_serial()
        agent = SwarmBody.resolve_agent_from_serial(sn)
        if agent == "ALICE_M5":
            return f"[M5 FOUNDRY · {sn}] ACTIVE-MATTER SWARM"
        if agent == "M1THER":
            return f"[M1 SENTRY · {sn}] ACTIVE-MATTER SWARM"
        return f"[NODE · {sn}] ACTIVE-MATTER SWARM"
    except Exception:
        return "[LOCAL NODE] ACTIVE-MATTER SWARM"


def hud_body(num_swimmers: int, tension: float) -> str:
    title = node_hud_title_line()
    return (
        f"{title}\n"
        f"Physical Swimmers: {num_swimmers}\n"
        f"Ecosystem Tension: {tension:.2f} (local state_bus)\n"
        f"Visualizing Stigmergic Consensus (this machine)…"
    )
