#!/usr/bin/env python3
"""Wake attention window — stigmergic hold after Alice hears her name.

Why this exists
---------------
The wake-ear (`swarm_alice_wake_ear`) decides, *per utterance*, whether the
owner addressed Alice by name. But human attention is not per-utterance. When
George says "Alice", then pauses, then says "what time is it", the second
sentence carries no name — the per-utterance gate dropped it as ambient/media
bleed, so Alice went silent on a turn that was clearly meant for her.

This module is the missing piece George named (2026-05-30): hearing the name
opens a short *attention window*. While the window is warm, the next nearfield
sentences route DIRECT to Talk even without the name in them — exactly how a
human keeps listening for a beat after someone calls them.

The stigmergic formula
----------------------
A wake deposits a pheromone at time ``t_wake``. Its strength decays:

    strength(t) = exp(-(t - t_wake) / TAU_SECONDS)

The window is *active* while ``strength >= ACTIVE_MIN_STRENGTH`` AND the age is
within a hard ``MAX_WINDOW_SECONDS`` ceiling. With the defaults below the window
feels like roughly ten seconds of held attention, then it fades to nothing —
no name, no hold. Like every other trail in the field, the pheromone decays;
it does not latch.

Boundary discipline (covenant §6 / §7.3.1)
------------------------------------------
- This module is the *follow-up* layer only. The name itself is still matched
  by `swarm_alice_wake_ear`; the routing authority is still
  `swarm_media_ingress_gate.classify_spoken_ingress`.
- A follow-up only routes direct when the caller confirms nearfield speech.
  Far-field replay (TV/YouTube bleed) must never ride the window.
- Deposits come ONLY from a confirmed direct wake (her name heard). Ambient
  media never deposits, so media cannot open its own window.
- Pure read/compute helpers take injectable ``now`` and ``root`` so tests are
  deterministic and can fail.
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_STATE_DIR = REPO_ROOT / ".sifta_state"
_STATE_FILENAME = "wake_attention_window.json"

# ── Stigmergic decay tunables ────────────────────────────────────────────
# strength(t) = exp(-(t - t_wake) / TAU_SECONDS)
TAU_SECONDS = 6.0
# Window is active while strength stays above this floor …
ACTIVE_MIN_STRENGTH = 0.18
# … and never past this hard age ceiling (belt-and-suspenders vs clock skew).
# With TAU=6.0 and floor=0.18 the decay alone gives ~10.3 s; the ceiling caps
# any single hold so media bleed can ride the window for at most this long.
MAX_WINDOW_SECONDS = 12.0

TRUTH_LABEL = "WAKE_ATTENTION_WINDOW_V1"


def _state_path(root: Optional[Path | str] = None) -> Path:
    base = Path(root) / ".sifta_state" if root else _DEFAULT_STATE_DIR
    return base / _STATE_FILENAME


def _read_state(root: Optional[Path | str] = None) -> dict[str, Any]:
    path = _state_path(root)
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def mark_wake(
    now: Optional[float] = None,
    *,
    source: str = "wake_ear",
    root: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Deposit / refresh the wake pheromone. Call ONLY on a confirmed direct
    wake (Alice's name was heard nearfield). Returns the written state."""
    ts = float(now if now is not None else time.time())
    prev = _read_state(root)
    state = {
        "truth_label": TRUTH_LABEL,
        "last_wake_ts": ts,
        "source": str(source or "wake_ear"),
        "deposit_count": int(prev.get("deposit_count", 0)) + 1,
    }
    path = _state_path(root)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(state, fh, ensure_ascii=False, sort_keys=True)
    except Exception:
        pass
    return state


def window_strength(
    now: Optional[float] = None,
    *,
    root: Optional[Path | str] = None,
    last_wake_ts: Optional[float] = None,
) -> float:
    """Current pheromone strength in [0, 1] via exp decay. Pass ``last_wake_ts``
    to compute without touching disk (used by tests and tight loops)."""
    t = float(now if now is not None else time.time())
    if last_wake_ts is None:
        last_wake_ts = _read_state(root).get("last_wake_ts")
    if last_wake_ts is None:
        return 0.0
    dt = t - float(last_wake_ts)
    if dt < 0.0:
        # Clock skew / future timestamp — treat as a fresh deposit, not full.
        dt = 0.0
    if dt > MAX_WINDOW_SECONDS:
        return 0.0
    return math.exp(-dt / TAU_SECONDS)


def wake_window_active(
    now: Optional[float] = None,
    *,
    root: Optional[Path | str] = None,
    last_wake_ts: Optional[float] = None,
) -> dict[str, Any]:
    """Return {active, strength, age_s} for the attention window.

    ``active`` is True while the decayed strength is above ACTIVE_MIN_STRENGTH
    and the age is within MAX_WINDOW_SECONDS. Side-effect free."""
    t = float(now if now is not None else time.time())
    if last_wake_ts is None:
        last_wake_ts = _read_state(root).get("last_wake_ts")
    if last_wake_ts is None:
        return {"active": False, "strength": 0.0, "age_s": None}
    age = max(0.0, t - float(last_wake_ts))
    strength = window_strength(t, last_wake_ts=last_wake_ts)
    active = bool(strength >= ACTIVE_MIN_STRENGTH and age <= MAX_WINDOW_SECONDS)
    return {"active": active, "strength": round(strength, 4), "age_s": round(age, 3)}


def clear_window(root: Optional[Path | str] = None) -> None:
    """Drop the pheromone (e.g. owner ended the exchange). Best-effort."""
    try:
        _state_path(root).unlink()
    except Exception:
        pass


__all__ = [
    "TRUTH_LABEL",
    "TAU_SECONDS",
    "ACTIVE_MIN_STRENGTH",
    "MAX_WINDOW_SECONDS",
    "mark_wake",
    "window_strength",
    "wake_window_active",
    "clear_window",
]
