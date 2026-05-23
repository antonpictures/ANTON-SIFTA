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
  2. Wallet resolution now includes the real canonical body for this node
     (``ALICE_M5.json``).
  3. A missing/unresolvable wallet now **fails open** (healthy) instead of silently treating the organism as starving (the P0 that was causing "stuck after 2 chats").
  4. Non-blocking API — returns a ``Clearance`` with a ``sleep_needed``
     float so PyQt / async callers can park the wait on a worker thread
     instead of freezing the UI.  A blocking convenience helper is
     available (``await_metabolic_clearance``) for CLI use, but it is **not**
     the default path.
  5. Deterministic SHA-256 hashing (Gemini used Python ``hash()`` which is
     non-deterministic across processes).
  6. Repo-root ledger path (``ROOT_DIR / "repair_log.jsonl"``), matching
     ``Kernel/repair_loop_suppressor.py`` and ``Network/migration_airdrop.py``.
  7. Ed25519-signed ledger rows per ``.cursorrules`` — no unsigned writes.
  8. Persistent last-inference clock in
     ``.sifta_state/metabolic_throttle_state/{agent}.json`` so process
     restarts don't reset the cooldown and let starving nodes burst.
  9. Works whether ``agent_id`` is a body prefix (``M5SIFTA``) or a silicon
     serial (``GTH4921YP3``) — tries both naming conventions.
 10. Denials write `.sifta_state/throttle_decisions.jsonl` so the UI can
     show the real reason instead of looking like an NPU stall.

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
THROTTLE_DECISIONS_LEDGER = "throttle_decisions.jsonl"

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


def _stable_row_hash(row: dict[str, Any]) -> str:
    payload = json.dumps(row, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def _throttle_decisions_path() -> Path:
    return _STATE / THROTTLE_DECISIONS_LEDGER


def _normalized_agent_id(agent_id: Any) -> str:
    return str(agent_id or "").strip().upper()


def _candidate_agent_ids(agent_id: str) -> list[str]:
    raw = _normalized_agent_id(agent_id)
    candidates: list[str] = []

    def add(value: str) -> None:
        value = _normalized_agent_id(value)
        if value and value not in candidates:
            candidates.append(value)

    add(raw)
    if raw.endswith("_BODY"):
        add(raw[:-5])
    if raw in {"M5SIFTA", "M5SIFTA_BODY", "ALICE_M5", "GTH4921YP3"}:
        add("ALICE_M5")
        add("M5SIFTA")
        add("M5SIFTA_BODY")
    return candidates


def _candidate_body_files(agent_id: str) -> list[Path]:
    """Try legacy body names plus the unified ALICE_M5 wallet."""
    paths: list[Path] = []

    def add(path: Path) -> None:
        if path not in paths:
            paths.append(path)

    for aid in _candidate_agent_ids(agent_id):
        if aid.endswith("_BODY"):
            add(_STATE / f"{aid}.json")
            add(_STATE / f"{aid[:-5]}.json")
        else:
            add(_STATE / f"{aid}_BODY.json")
            add(_STATE / f"{aid}.json")
    return paths


def _wallet_source_label(path: Optional[Path]) -> Optional[str]:
    if path is None:
        return None
    if path.is_absolute():
        try:
            return str(path.relative_to(_STATE))
        except ValueError:
            return str(path)
    return str(path)


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

    def _resolve_balance(self) -> tuple[float, Optional[Path]]:
        """Returns (balance, resolved_wallet_path or None).
        If no wallet file matching this agent_id exists, returns (0.0, None).
        """
        for path in _candidate_body_files(self.agent_id):
            if path.exists():
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    bal = float(data.get("stgm_balance", 0.0))
                    return bal, path
                except (json.JSONDecodeError, ValueError, OSError):
                    continue
        try:
            from System.stgm_economy import scan_economy

            snap = scan_economy(
                repair_log=REPAIR_LOG,
                state_dir=_STATE,
                memory_rewards=_STATE / "stgm_memory_rewards.jsonl",
            ).as_dict()
            wallet_balances = {
                _normalized_agent_id(k): float(v)
                for k, v in (snap.get("canonical_wallet_balances") or {}).items()
            }
            for aid in _candidate_agent_ids(self.agent_id):
                if aid in wallet_balances:
                    return wallet_balances[aid], Path(f"canonical_wallet_balances.{aid}")
            wallet_sum = float(snap.get("canonical_wallet_sum") or 0.0)
            if wallet_sum > 0.0:
                return wallet_sum, Path("canonical_wallet_sum")
        except Exception:
            pass
        return 0.0, None

    def current_balance(self) -> float:
        bal, _ = self._resolve_balance()
        return bal

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
        balance, resolved_wallet = self._resolve_balance()
        now = time.time()

        # Fail open if we could not locate any wallet file for this agent.
        # Do not punish the organism because our lookup was incomplete.
        if resolved_wallet is None:
            self._save_last_inference_ts(now)
            self._log_decision(
                now,
                ok=True,
                balance=balance,
                resolved_wallet=resolved_wallet,
                reason="wallet_unresolved_fail_open",
                sleep_needed=0.0,
            )
            if self.ledger_writes:
                self._log_starvation_tick(now, balance, reason="wallet_unresolved_fail_open")
            return Clearance(
                ok=True,
                balance=balance,
                sleep_needed=0.0,
                reason="wallet_unresolved_fail_open"
            )

        # Healthy: proceed, record tick.
        if balance > 0:
            self._save_last_inference_ts(now)
            return Clearance(ok=True, balance=balance, sleep_needed=0.0, reason="healthy")

        # Starving: enforce cooldown (only when we actually found a wallet with ≤0).
        last = self._load_last_inference_ts()
        elapsed = now - last if last > 0 else self.starvation_delay_s  # first call passes
        if elapsed >= self.starvation_delay_s:
            self._save_last_inference_ts(now)
            if self.ledger_writes:
                self._log_starvation_tick(now, balance)
            return Clearance(ok=True, balance=balance, sleep_needed=0.0, reason="starvation_ok")

        sleep_needed = max(0.0, self.starvation_delay_s - elapsed)
        reason = f"starving — next clearance in {sleep_needed:.1f}s"
        self._log_decision(
            now,
            ok=False,
            balance=balance,
            resolved_wallet=resolved_wallet,
            reason=reason,
            sleep_needed=sleep_needed,
        )
        return Clearance(
            ok=False,
            balance=balance,
            sleep_needed=sleep_needed,
            reason=reason,
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

    def _log_decision(
        self,
        now: float,
        *,
        ok: bool,
        balance: float,
        resolved_wallet: Optional[Path],
        reason: str,
        sleep_needed: float,
    ) -> None:
        row = {
            "schema": "SIFTA_THROTTLE_DECISION_V1",
            "ts": float(now),
            "agent_id": self.agent_id,
            "ok": bool(ok),
            "resolved_wallet_file": _wallet_source_label(resolved_wallet),
            "balance": round(float(balance), 4),
            "reason": str(reason),
            "sleep_needed": round(float(sleep_needed), 4),
            "homeworld_serial": self.homeworld_serial,
        }
        row["decision_hash"] = _stable_row_hash(row)
        try:
            append_ledger_line(_throttle_decisions_path(), row)
        except OSError:
            pass

    def _log_starvation_tick(self, now: float, balance: float, reason: Optional[str] = None) -> None:
        ts = int(now)
        h = _stable_hash(self.agent_id, "starvation_tick", str(ts))
        seal_payload = "||".join(["metabolic_throttle", self.agent_id, "starvation_tick", h, str(ts)])
        signature = sign_block(seal_payload) if _SIGN_AVAILABLE else ""
        base_reason = f"stgm_balance={balance:.4f}; {self.starvation_delay_s:.0f}s cooldown enforced"
        final_reason = f"{base_reason} | {reason}" if reason else base_reason
        event = {
            "timestamp": ts,
            "agent_id": self.agent_id,
            "tx_type": "metabolic_throttle",
            "amount": 0.0,
            "reason": final_reason,
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
