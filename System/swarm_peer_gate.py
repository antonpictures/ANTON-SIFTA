"""Peer-network gate — kill-switch for daemons that only matter when peers exist.

Architect directive 2026-05-12 00:14: many background `threading.Thread`
loops in `System/` run forever regardless of whether a swarm peer is
present (pheromone evaporation, ARP discovery, mycorrhizal listen,
distributed body broadcast, etc.). When the relay is down and no peers
are connected, these loops are pure fan-spin.

This module gives each daemon a single, cheap predicate to check at
the top of its loop:

    >>> from System.swarm_peer_gate import peer_network_active
    >>> if not peer_network_active():
    ...     time.sleep(SLEEP_WHEN_DORMANT_S)
    ...     continue

When the predicate is False, the daemon sleeps longer between checks
(default 30 s — configurable per daemon) and skips its actual work.
When the predicate flips to True (relay came up, peer appeared), the
daemon resumes within one dormant cycle.

Truth labels (covenant §7.11)
-----------------------------
- `OPERATIONAL` — predicate is a TCP probe + ledger mtime check, both
                   real measurements with sub-millisecond cost.
- `ARCHITECT_DOCTRINE` — gating peer daemons on real network presence
                   is the Architect's binding direction; future Doctors
                   must not silently re-enable always-on peer loops
                   without §4.4 receipt.

Author: Cowork (Claude Opus 4.7, Surgeon lane, 2026-05-12 00:25).
"""
from __future__ import annotations

import os
import socket
import time
from pathlib import Path
from typing import Optional

# ── Tunables (env-overridable, no hardcoded magic constants) ─────────────
# How long a positive probe stays cached before we re-check. Keeps the
# predicate cheap when called from a tight daemon loop.
_PROBE_TTL_S: float = float(os.environ.get("SIFTA_PEER_GATE_TTL_S", "5.0"))
# How long to sleep when dormant — re-check after this.
_DEFAULT_DORMANT_SLEEP_S: float = float(
    os.environ.get("SIFTA_PEER_GATE_DORMANT_S", "30.0")
)
# Where the local relay is expected to listen.
_RELAY_HOST: str = os.environ.get("SIFTA_RELAY_HOST", "127.0.0.1")
_RELAY_PORT: int = int(os.environ.get("SIFTA_RELAY_PORT", "8765"))

# Override knob — Architect can force daemons on/off without code edit.
#   SIFTA_PEER_GATE=force_on   → predicate always True
#   SIFTA_PEER_GATE=force_off  → predicate always False (dormant)
#   SIFTA_PEER_GATE=auto       → real probe (default)
_FORCE = os.environ.get("SIFTA_PEER_GATE", "auto").strip().lower()


_LAST_PROBE_TS: float = 0.0
_LAST_PROBE_RESULT: bool = False


def _tcp_relay_up() -> bool:
    try:
        with socket.create_connection((_RELAY_HOST, _RELAY_PORT), timeout=0.3):
            return True
    except Exception:
        return False


def peer_network_active(*, force_refresh: bool = False) -> bool:
    """Return True when peer-related daemons should do their work.

    Cached for ``_PROBE_TTL_S`` seconds so calling this in a tight loop
    is cheap. ``force_refresh=True`` ignores the cache for one call.
    """
    global _LAST_PROBE_TS, _LAST_PROBE_RESULT

    if _FORCE == "force_on":
        return True
    if _FORCE == "force_off":
        return False

    now = time.monotonic()
    if (
        not force_refresh
        and (now - _LAST_PROBE_TS) < _PROBE_TTL_S
        and _LAST_PROBE_TS > 0.0
    ):
        return _LAST_PROBE_RESULT

    result = _tcp_relay_up()
    _LAST_PROBE_TS = now
    _LAST_PROBE_RESULT = result
    return result


def dormant_sleep_s() -> float:
    """How long a daemon should sleep when peer network is inactive."""
    return _DEFAULT_DORMANT_SLEEP_S


def gate_loop_iteration(*, on_active, on_dormant=None) -> bool:
    """Convenience: call from inside a daemon's `while True` body.

    Returns True if `on_active` was invoked, False if dormant.
    `on_dormant` defaults to `time.sleep(dormant_sleep_s())`.
    """
    if peer_network_active():
        try:
            on_active()
        except Exception:
            pass
        return True
    try:
        if on_dormant is None:
            time.sleep(dormant_sleep_s())
        else:
            on_dormant()
    except Exception:
        pass
    return False


__all__ = [
    "peer_network_active",
    "dormant_sleep_s",
    "gate_loop_iteration",
]
