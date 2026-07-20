#!/usr/bin/env python3
"""swarm_carpenter_pong_stgm.py — Game-local STGM for Carpenter Pong swimmers.

This is a **sandbox hive economy** for the Pong court:
  - each unique swimmer id has a balance
  - settling a directional vote at a signed decision checkpoint costs stake
  - good save pays correct voters; miss taxes wrong voters
  - append-only ledger under .sifta_state/

Honest boundary: this is **not** the spendable body wallet in repair_log /
stgm_economy.py unless a later doctor bridges with a real transfer organ.
Token name: GAME_STGM (rhyme of body STGM, separate books).

Truth label: CARPENTER_PONG_GAME_STGM_V1
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER = "carpenter_pong_game_stgm.jsonl"
_BALANCES = "carpenter_pong_swimmer_balances.json"

TRUTH_LABEL = "CARPENTER_PONG_GAME_STGM_V1"
TOKEN = "GAME_STGM"

GENESIS_BALANCE = 10.0
VOTE_COST = 0.01
SAVE_REWARD = 0.05
MISS_TAX = 0.02


def _state_dir(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return _STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _append(row: dict[str, Any], *, state_dir: Optional[Path | str] = None) -> None:
    root = _state_dir(state_dir)
    try:
        root.mkdir(parents=True, exist_ok=True)
        with (root / _LEDGER).open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


def save_balances(
    balances: dict[str, float],
    *,
    state_dir: Optional[Path | str] = None,
    meta: Optional[dict[str, Any]] = None,
) -> None:
    root = _state_dir(state_dir)
    try:
        root.mkdir(parents=True, exist_ok=True)
        payload = {
            "truth_label": TRUTH_LABEL,
            "token": TOKEN,
            "ts": time.time(),
            "balances": {k: round(float(v), 6) for k, v in balances.items()},
            "meta": meta or {},
            "note": "game sandbox — not body repair_log wallet",
        }
        (root / _BALANCES).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass


def load_balances(*, state_dir: Optional[Path | str] = None) -> dict[str, float]:
    path = _state_dir(state_dir) / _BALANCES
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        raw = data.get("balances") or {}
        return {str(k): float(v) for k, v in raw.items()}
    except Exception:
        return {}


class PongGameStgmEconomy:
    """Per-match sandbox economy: settle votes, reward saves, tax misses."""

    def __init__(
        self,
        *,
        genesis: float = GENESIS_BALANCE,
        vote_cost: float = VOTE_COST,
        save_reward: float = SAVE_REWARD,
        miss_tax: float = MISS_TAX,
        state_dir: Optional[Path | str] = None,
        enabled: bool = True,
    ) -> None:
        self.genesis = float(genesis)
        self.vote_cost = float(vote_cost)
        self.save_reward = float(save_reward)
        self.miss_tax = float(miss_tax)
        self.state_dir = state_dir
        self.enabled = bool(enabled)
        self.balances: dict[str, float] = {}
        self.tx_count = 0
        self.total_spent = 0.0
        self.total_earned = 0.0

    def reset_for_swimmers(self, uids: list[str]) -> None:
        self.balances = {str(u): self.genesis for u in uids}
        self.tx_count = 0
        self.total_spent = 0.0
        self.total_earned = 0.0
        if self.enabled:
            _append(
                {
                    "truth_label": TRUTH_LABEL,
                    "tx_type": "GENESIS_MINT",
                    "ts": time.time(),
                    "receipt_id": str(uuid.uuid4()),
                    "token": TOKEN,
                    "n_swimmers": len(uids),
                    "each": self.genesis,
                    "note": "game sandbox mint",
                },
                state_dir=self.state_dir,
            )
            save_balances(
                self.balances,
                state_dir=self.state_dir,
                meta={"event": "genesis"},
            )

    def can_vote(self, uid: str) -> bool:
        if not self.enabled:
            return True
        return float(self.balances.get(uid, 0.0)) >= self.vote_cost - 1e-12

    def charge_vote(self, uid: str, *, vote: int, tick: int) -> bool:
        """Charge stake for a non-neutral vote. Returns False if broke → forced neutral."""
        if not self.enabled or int(vote) == 0:
            return True
        bal = float(self.balances.get(uid, 0.0))
        if bal < self.vote_cost - 1e-12:
            return False
        self.balances[uid] = round(bal - self.vote_cost, 6)
        self.total_spent += self.vote_cost
        self.tx_count += 1
        return True

    def reward_save(self, correct_uids: list[str], *, side: str, tick: int) -> float:
        if not self.enabled or not correct_uids:
            return 0.0
        paid = 0.0
        for uid in correct_uids:
            self.balances[uid] = round(
                float(self.balances.get(uid, 0.0)) + self.save_reward, 6
            )
            paid += self.save_reward
        self.total_earned += paid
        self.tx_count += 1
        _append(
            {
                "truth_label": TRUTH_LABEL,
                "tx_type": "SAVE_REWARD",
                "ts": time.time(),
                "receipt_id": str(uuid.uuid4()),
                "token": TOKEN,
                "side": side,
                "tick": tick,
                "n": len(correct_uids),
                "amount_each": self.save_reward,
                "paid_total": round(paid, 6),
            },
            state_dir=self.state_dir,
        )
        return paid

    def tax_miss(self, wrong_uids: list[str], *, side: str, tick: int) -> float:
        if not self.enabled or not wrong_uids:
            return 0.0
        taxed = 0.0
        for uid in wrong_uids:
            bal = float(self.balances.get(uid, 0.0))
            take = min(self.miss_tax, bal)
            self.balances[uid] = round(bal - take, 6)
            taxed += take
        self.tx_count += 1
        _append(
            {
                "truth_label": TRUTH_LABEL,
                "tx_type": "MISS_TAX",
                "ts": time.time(),
                "receipt_id": str(uuid.uuid4()),
                "token": TOKEN,
                "side": side,
                "tick": tick,
                "n": len(wrong_uids),
                "taxed_total": round(taxed, 6),
            },
            state_dir=self.state_dir,
        )
        return taxed

    def snapshot(self) -> dict[str, Any]:
        bals = list(self.balances.values())
        return {
            "truth_label": TRUTH_LABEL,
            "token": TOKEN,
            "enabled": self.enabled,
            "n_wallets": len(self.balances),
            "sum": round(sum(bals), 4) if bals else 0.0,
            "mean": round(sum(bals) / len(bals), 4) if bals else 0.0,
            "min": round(min(bals), 4) if bals else 0.0,
            "max": round(max(bals), 4) if bals else 0.0,
            "tx_count": self.tx_count,
            "total_spent": round(self.total_spent, 4),
            "total_earned": round(self.total_earned, 4),
            "vote_cost": self.vote_cost,
            "save_reward": self.save_reward,
            "note": "GAME_STGM sandbox — not body repair_log wallet",
        }


def ask_llm_up_down(
    *,
    ball_y: float,
    paddle_y: float,
    side: str,
    model: str = "",
    timeout_s: float = 2.0,
) -> dict[str, Any]:
    """One swimmer mind: no-thinking binary UP/DOWN. Fail-soft if Ollama offline."""
    import urllib.error
    import urllib.request

    mid = (model or "").strip()
    if not mid:
        try:
            from System.sifta_inference_defaults import resolve_live_local_ollama_default

            mid = str(resolve_live_local_ollama_default() or "ornith:latest")
        except Exception:
            mid = "ornith:latest"
    if mid.startswith("ollama:"):
        mid = mid.split(":", 1)[1]

    rel = "above" if ball_y > paddle_y else "below" if ball_y < paddle_y else "level"
    prompt = (
        f"You are one Carpenter Pong swimmer on the {side} paddle. "
        f"Ball is {rel} your paddle (ball_y={ball_y:.3f}, paddle_y={paddle_y:.3f}). "
        f"Vote only: UP or DOWN. No other words."
    )
    body = {
        "model": mid,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "options": {"temperature": 0.0, "num_predict": 6},
    }
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:11434/api/chat",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        text = str((data.get("message") or {}).get("content") or "").strip().upper()
        # Court y: 0 = top, 1 = bottom. Sim vote: -1 = UP (UI), +1 = DOWN (UI).
        first = (text.split() or [""])[0]
        if first.startswith("UP") or (first == "U"):
            return {"ok": True, "vote": -1, "raw": text[:40], "model": mid}
        if first.startswith("DOWN") or first.startswith("DN") or first == "D":
            return {"ok": True, "vote": 1, "raw": text[:40], "model": mid}
        if "UP" in text and "DOWN" not in text:
            return {"ok": True, "vote": -1, "raw": text[:40], "model": mid}
        if "DOWN" in text:
            return {"ok": True, "vote": 1, "raw": text[:40], "model": mid}
        return {"ok": False, "vote": 0, "raw": text[:40], "model": mid, "reason": "parse"}
    except Exception as exc:
        return {
            "ok": False,
            "vote": 0,
            "model": mid,
            "reason": f"{type(exc).__name__}: {exc}",
        }


__all__ = [
    "TRUTH_LABEL",
    "TOKEN",
    "GENESIS_BALANCE",
    "VOTE_COST",
    "SAVE_REWARD",
    "MISS_TAX",
    "PongGameStgmEconomy",
    "ask_llm_up_down",
    "save_balances",
    "load_balances",
]
