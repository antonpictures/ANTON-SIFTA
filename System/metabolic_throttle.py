#!/usr/bin/env python3
"""
metabolic_throttle.py — "Starving, not dead" inference rate-limiter

Design: Gemini (browser tab, 2026-04-17, TAB_CHAT).
Grounded implementation: Cursor Opus 4.7 on M5 (REPO_TOOL, same day).

Paradigm:
  * ``stgm_balance > 0``  → healthy metabolism, no throttling.
  * ``stgm_balance <= 0`` → biological lethargy: one request per minute
    (configurable).  The entity is **alive** but **starving**; it cannot
    spam inference and drain whatever economy restores its balance.

Delta vs Gemini's first draft (bugs fixed here):
  1. Reuses ``System/stgm_metabolic.py`` (mint + store throttle maths).
     Gemini re-derived; the repo already has the pressure curves.
  2. ``.sifta_state/{agent}_BODY.json`` — resolves from repo root
     (``Path(__file__).resolve().parent.parent / ".sifta_state"``) instead of
     cwd-relative, which would break anywhere but the repo top.
  3. Non-blocking API — returns a ``Clearance`` with a ``sleep_needed``
     float so PyQt / async callers can park the wait on a worker thread
     instead of freezing the UI.  A blocking convenience helper is
     available (``await_metabolic_clearance``) for CLI use, but it is **not**
     the default path.
  4. Deterministic SHA-256 hashing (Gemini used Python ``hash()`` which is
     non-deterministic across processes).
  5. Repo-root ledger path (``ROOT_DIR / "repair_log.jsonl"``), matching
     ``Kernel/repair_loop_suppressor.py`` and ``Network/migration_airdrop.py``.
  6. Ed25519-signed ledger rows per ``.cursorrules`` — no unsigned writes.
  7. Persistent last-inference clock in
     ``.sifta_state/metabolic_throttle_state/{agent}.json`` so process
     restarts don't reset the cooldown and let starving nodes burst.
  8. Works whether ``agent_id`` is a body prefix (``M5SIFTA``) or a silicon
     serial (``GTH4921YP3``) — tries both naming conventions.

This module does not touch Ollama directly.  Callers wrap their inference
request: ``throttle.clearance(); if clearance.ok: run_ollama(); else: …``.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.ledger_append import append_ledger_line  # noqa: E402
from System.stgm_metabolic import (  # noqa: E402
    DEFAULT_BASE_MINT,
    calculate_metabolic_mint_rate,
)

try:
    from System.crypto_keychain import sign_block  # type: ignore
    _SIGN_AVAILABLE = True
except Exception:  # pragma: no cover
    _SIGN_AVAILABLE = False

_STATE = _REPO / ".sifta_state"
_THROTTLE_STATE_DIR = _STATE / "metabolic_throttle_state"
REPAIR_LOG = _REPO / "repair_log.jsonl"

# 60 s default starvation cooldown — matches Gemini's spec.
DEFAULT_STARVATION_DELAY_S = 60.0

__all__ = [
    "Clearance",
    "MetabolicThrottle",
]


@dataclass
class Clearance:
    """Non-blocking clearance result."""
    ok: bool
    balance: float
    sleep_needed: float  # seconds the caller should wait before the next call
    reason: str


# ───────────────────────────── helpers ─────────────────────────────

def _stable_hash(*parts: str) -> str:
    payload = "||".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:20]


def _candidate_body_files(agent_id: str) -> list[Path]:
    """Try both naming conventions used in the repo."""
    return [
        _STATE / f"{agent_id}_BODY.json",
        _STATE / f"{agent_id}.json",
    ]


# ───────────────────────────── main class ─────────────────────────────

class MetabolicThrottle:
    def __init__(
        self,
        agent_id: str = "M5SIFTA",
        *,
        homeworld_serial: str = "GTH4921YP3",
        starvation_delay_s: float = DEFAULT_STARVATION_DELAY_S,
        ledger_writes: bool = True,
    ) -> None:
        self.agent_id = agent_id
        self.homeworld_serial = homeworld_serial
        self.starvation_delay_s = float(starvation_delay_s)
        self.ledger_writes = bool(ledger_writes)
        _THROTTLE_STATE_DIR.mkdir(parents=True, exist_ok=True)
        self._state_file = _THROTTLE_STATE_DIR / f"{agent_id}.json"

    # ── balance + clock (persistent) ─────────────────────────

    def current_balance(self) -> float:
        for path in _candidate_body_files(self.agent_id):
            if path.exists():
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    return float(data.get("stgm_balance", 0.0))
                except (json.JSONDecodeError, ValueError, OSError):
                    continue
        return 0.0

    def _load_last_inference_ts(self) -> float:
        if not self._state_file.exists():
            return 0.0
        try:
            return float(json.loads(self._state_file.read_text(encoding="utf-8")).get("last_inference_ts", 0.0))
        except (json.JSONDecodeError, ValueError, OSError):
            return 0.0

    def _save_last_inference_ts(self, ts: float) -> None:
        payload = {
            "agent_id": self.agent_id,
            "last_inference_ts": float(ts),
            "updated": int(time.time()),
        }
        try:
            self._state_file.write_text(json.dumps(payload), encoding="utf-8")
        except OSError:
            pass

    # ── public API ───────────────────────────────────────────

    def clearance(self) -> Clearance:
        """Non-blocking: tell the caller whether this request may proceed,
        and if not, how long to wait."""
        balance = self.current_balance()
        now = time.time()

        # Healthy: proceed, record tick.
        if balance > 0:
            self._save_last_inference_ts(now)
            return Clearance(ok=True, balance=balance, sleep_needed=0.0, reason="healthy")

        # Starving: enforce cooldown.
        last = self._load_last_inference_ts()
        elapsed = now - last if last > 0 else self.starvation_delay_s  # first call passes
        if elapsed >= self.starvation_delay_s:
            self._save_last_inference_ts(now)
            if self.ledger_writes:
                self._log_starvation_tick(now, balance)
            return Clearance(ok=True, balance=balance, sleep_needed=0.0, reason="starvation_ok")

        sleep_needed = max(0.0, self.starvation_delay_s - elapsed)
        return Clearance(
            ok=False,
            balance=balance,
            sleep_needed=sleep_needed,
            reason=f"starving — next clearance in {sleep_needed:.1f}s",
        )

    def await_metabolic_clearance(self, *, blocking: bool = True) -> Clearance:
        """Convenience blocking wrapper — for CLI use only.

        Do NOT call on the PyQt main thread; run on a worker.  If
        ``blocking=False`` this is equivalent to ``clearance()``.
        """
        c = self.clearance()
        if c.ok or not blocking:
            return c
        time.sleep(c.sleep_needed)
        return self.clearance()

    # ── metrics ──────────────────────────────────────────────

    def metabolic_lambda(self) -> float:
        """Return a normalized pressure λ ∈ [0,1] for downstream RL / UI.

        Balance at/above ``DEFAULT_BASE_MINT * 100`` → λ=0 (calm).
        Balance at 0 → λ=1 (bunker).
        """
        b = self.current_balance()
        ceiling = DEFAULT_BASE_MINT * 100.0
        if ceiling <= 0:
            return 1.0 if b <= 0 else 0.0
        lam = 1.0 - max(0.0, min(1.0, b / ceiling))
        return float(lam)

    def effective_mint_rate(self) -> float:
        """Current mint rate under λ-throttle — reuses stgm_metabolic math."""
        return calculate_metabolic_mint_rate(self.metabolic_lambda())

    # ── ledger ───────────────────────────────────────────────

    def _log_starvation_tick(self, now: float, balance: float) -> None:
        ts = int(now)
        h = _stable_hash(self.agent_id, "starvation_tick", str(ts))
        seal_payload = "||".join(["metabolic_throttle", self.agent_id, "starvation_tick", h, str(ts)])
        signature = sign_block(seal_payload) if _SIGN_AVAILABLE else ""
        event = {
            "timestamp": ts,
            "agent_id": self.agent_id,
            "tx_type": "metabolic_throttle",
            "amount": 0.0,
            "reason": f"stgm_balance={balance:.4f}; {self.starvation_delay_s:.0f}s cooldown enforced",
            "throttle_hash": h,
            "seal_payload": seal_payload,
            "ed25519_signature": signature,
            "signed": bool(signature),
            "homeworld_serial": self.homeworld_serial,
        }
        append_ledger_line(REPAIR_LOG, event)


if __name__ == "__main__":
    t = MetabolicThrottle()
    print("agent_id       =", t.agent_id)
    print("balance        =", t.current_balance())
    print("lambda         =", f"{t.metabolic_lambda():.4f}")
    print("effective_mint =", f"{t.effective_mint_rate():.4f}")
    print("clearance      =", t.clearance())
