#!/usr/bin/env python3
"""Kalshi Pro tape dirt — liquidity / microstructure lessons (r1661).

Owner pasted Pro Active Markets (Crypto). Encode what matters for Alice:
  • 15m clocks with huge 5min vol = tradeable (fills + cash-out)
  • Daily strike ladders = high 24h, often dead 5min tape
  • 1–3¢ lottery tails = sit
  • Fields: 24H vol, 5min vol, spread, yes|no, sizes, yes taker %

Truth: KALSHI_PRO_TAPE_DIRT_V1
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".sifta_state"
DIRT_JSON = "kalshi_pro_tape_dirt.json"
TRUTH = "KALSHI_PRO_TAPE_DIRT_V1"

# Soft floors from owner Pro paste + Alice practice
MIN_5M_VOL_HINT_USD = 500.0
TIGHT_SPREAD_CENTS = 2


def load_dirt(*, state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    root = Path(state_dir) if state_dir else STATE
    if root.name != ".sifta_state":
        root = root / ".sifta_state"
    p = root / DIRT_JSON
    if not p.exists():
        return {"truth_label": TRUTH, "ok": False, "reason": "no_dirt_file"}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"truth_label": TRUTH, "ok": False, "reason": str(exc)}


def liquidity_score(
    *,
    vol_5m_usd: float = 0.0,
    vol_24h_usd: float = 0.0,
    spread_cents: float = 99.0,
    yes_size: float = 0.0,
    no_size: float = 0.0,
) -> dict[str, Any]:
    """0–1 score: can we fill and cash out without fantasy marks?"""
    v5 = float(vol_5m_usd or 0.0)
    v24 = float(vol_24h_usd or 0.0)
    # Prefer 5min; fall back to 24h/20 as crude now-proxy
    v = v5 if v5 > 0 else v24 / 20.0
    if v >= 50_000:
        vol_s = 1.0
    elif v >= 5_000:
        vol_s = 0.8
    elif v >= 500:
        vol_s = 0.55
    elif v >= 100:
        vol_s = 0.25
    else:
        vol_s = 0.05
    sp = float(spread_cents)
    spread_s = 1.0 if sp <= 1 else (0.7 if sp <= 2 else (0.4 if sp <= 5 else 0.1))
    size = min(float(yes_size or 0), float(no_size or 0))
    size_s = 1.0 if size >= 50 else (0.6 if size >= 10 else (0.3 if size >= 1 else 0.05))
    score = round(0.5 * vol_s + 0.25 * spread_s + 0.25 * size_s, 4)
    tradeable = score >= 0.45 and v >= MIN_5M_VOL_HINT_USD
    return {
        "score": score,
        "tradeable": tradeable,
        "vol_proxy_usd": round(v, 2),
        "truth_label": TRUTH,
        "note": "tradeable ≈ can take profit via API without pure hope",
    }


def is_lottery_premium(yes_price: float) -> bool:
    """1–5¢ or 95–99¢ = coupon / poster, not scalp meat."""
    p = float(yes_price)
    return p <= 0.05 or p >= 0.95


__all__ = [
    "TRUTH",
    "load_dirt",
    "liquidity_score",
    "is_lottery_premium",
    "MIN_5M_VOL_HINT_USD",
]
