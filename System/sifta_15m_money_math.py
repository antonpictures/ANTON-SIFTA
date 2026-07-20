#!/usr/bin/env python3
"""Kalshi money language + dollar-parity STGM scale for Alice 15m paper/body.

Kalshi USD stays OFF. These numbers are HYPOTHETICAL translations so George
can read glass in the same language as Safari cards.

Scale (r1629 owner ask):
  0.0010 STGM ≡ $1  →  body PnL mirrors dollar economics at 1/1000.
"""

from __future__ import annotations

from typing import Any, Optional

# ── Scale ──────────────────────────────────────────────────────────────
STGM_PER_USD = 0.0010  # 0.001 STGM ≡ $1
PAPER_UNIT_USD = 1.0  # one paper ticket ≡ $1 hypothetical


def clamp_price(price: float) -> float:
    try:
        p = float(price)
    except (TypeError, ValueError):
        p = 0.5
    return min(0.99, max(0.01, p))


def gross_multiplier(price: float) -> float:
    """Payout multiple before fees: win pays $1 face per share bought at ``price``."""
    p = clamp_price(price)
    return round(1.0 / p, 4)


def net_multiplier(price: float) -> float:
    """Approximate Kalshi *displayed* net-of-fee multiplier (Safari card x).

    Acceptance fixture (owner screen):
      83¢ favorite → ~1.16x   (gross 1.20x)
      17¢ longshot → ~5.90x   (gross 5.88x)

    Fitted form mult ≈ a/p + b chosen to match those two anchors.
    """
    p = clamp_price(price)
    # Solve a/0.83 + b = 1.16 and a/0.17 + b = 5.90  → a≈1.01335, b≈-0.0609
    mult = 1.01335 / p - 0.0609
    return round(max(1.01, mult), 2)


def fee_drag(price: float) -> float:
    """How much net mult sits below gross (for tooltips)."""
    return round(max(0.0, gross_multiplier(price) - net_multiplier(price)), 4)


def dollar_pnl_if_real(
    price: float,
    *,
    win: bool,
    unit_usd: float = PAPER_UNIT_USD,
    net_of_fees: bool = True,
) -> float:
    """Hypothetical USD PnL for one ticket at entry ``price``.

    Win: +(mult − 1) * unit   Loss: −unit
    Always label HYPOTHETICAL in UI — Kalshi $ OFF.
    """
    unit = float(unit_usd)
    p = clamp_price(price)
    if win:
        mult = net_multiplier(p) if net_of_fees else gross_multiplier(p)
        return round(unit * (mult - 1.0), 4)
    return round(-unit, 4)


def stgm_pnl_from_price(
    price: float,
    *,
    win: bool,
    stake_stgm: float = STGM_PER_USD,
    net_of_fees: bool = True,
) -> float:
    """Body STGM PnL that *mirrors* dollar economics at STGM_PER_USD ≡ $1."""
    # dollars first, then scale — single source of truth
    usd = dollar_pnl_if_real(
        price, win=win, unit_usd=stake_stgm / STGM_PER_USD, net_of_fees=net_of_fees
    )
    # stake_stgm/STGM_PER_USD is how many $1 units this stake represents
    return round(usd * STGM_PER_USD, 9)


def stgm_to_usd(stgm: float) -> float:
    return round(float(stgm) / STGM_PER_USD, 4)


def usd_to_stgm(usd: float) -> float:
    return round(float(usd) * STGM_PER_USD, 9)


def stgm_to_cents(stgm: float) -> int:
    """STGM → integer cents under 0.001 STGM ≡ $1 (100¢)."""
    try:
        return int(round(float(stgm) / STGM_PER_USD * 100.0))
    except (TypeError, ValueError):
        return 0


def is_thin_stake(stgm: float, *, full: float = STGM_PER_USD) -> bool:
    """Rainman THIN half-ticket (~50¢ / 0.0005 STGM)."""
    try:
        s = float(stgm)
        f = float(full)
    except (TypeError, ValueError):
        return False
    if s <= 0 or f <= 0:
        return False
    half = f * 0.5
    return abs(s - half) < f * 0.08 or (s < f * 0.75 and s > 0)


def format_stgm_with_cents(stgm: float, *, signed: bool = False) -> str:
    """r1642 glass: five decimals + cents so +0.00035 reads as 35¢ not +0.0003.

    Examples:
      0.00100 → ``0.00100 (100¢)``
      -0.00100 → ``-0.00100 (−100¢)`` when signed
      +0.00035 → ``+0.00035 (+35¢)``
    """
    try:
        v = float(stgm)
    except (TypeError, ValueError):
        return "—"
    cents = stgm_to_cents(v)
    if signed:
        stgm_s = f"{v:+.5f}"
        if cents > 0:
            cent_s = f"+{cents}¢"
        elif cents < 0:
            cent_s = f"−{abs(cents)}¢"
        else:
            cent_s = "0¢"
    else:
        stgm_s = f"{abs(v):.5f}" if v >= 0 else f"{v:.5f}"
        cent_s = f"{abs(cents)}¢"
    return f"{stgm_s} ({cent_s})"


def format_stake_stgm(stgm: float, *, full: float = STGM_PER_USD) -> str:
    """Stake cell: full dollar-parity or THIN half-ticket badge."""
    try:
        v = float(stgm)
    except (TypeError, ValueError):
        return "—"
    if v <= 0:
        return "—"
    base = format_stgm_with_cents(v, signed=False)
    if is_thin_stake(v, full=full):
        return f"½ · {base}"
    return base


def ticket_money_row(
    *,
    price: float,
    win: Optional[bool] = None,
    volume_24h: float = 0.0,
    stake_stgm: float = STGM_PER_USD,
) -> dict[str, Any]:
    """One card's money language for the portfolio glass."""
    p = clamp_price(price)
    mult_g = gross_multiplier(p)
    mult_n = net_multiplier(p)
    stake = float(stake_stgm) if stake_stgm else STGM_PER_USD
    unit_usd = max(0.01, stgm_to_usd(stake))
    thin = is_thin_stake(stake)
    out: dict[str, Any] = {
        "price": p,
        "price_cents": round(p * 100.0, 1),
        "mult_gross": mult_g,
        "mult_net": mult_n,
        "mult_label": f"{mult_n:.2f}x",
        "volume_24h": float(volume_24h or 0.0),
        "stake_stgm": stake,
        "stake_usd_hyp": stgm_to_usd(stake),
        "stake_cents": stgm_to_cents(stake),
        "thin": thin,
        "stake_label": format_stake_stgm(stake),
        "if_win_usd": dollar_pnl_if_real(p, win=True, unit_usd=unit_usd),
        "if_lose_usd": dollar_pnl_if_real(p, win=False, unit_usd=unit_usd),
        "if_win_stgm": stgm_pnl_from_price(p, win=True, stake_stgm=stake),
        "if_lose_stgm": stgm_pnl_from_price(p, win=False, stake_stgm=stake),
        "truth_label": "SIFTA_HYPOTHETICAL_USD_V1",
        "note": "HYPOTHETICAL · Kalshi USD OFF · STGM≡$/1000 · 5dp cents glass r1642",
    }
    if win is not None:
        out["realized_usd_hyp"] = dollar_pnl_if_real(
            p, win=bool(win), unit_usd=unit_usd
        )
        out["realized_stgm"] = stgm_pnl_from_price(
            p, win=bool(win), stake_stgm=stake
        )
        out["realized_stgm_label"] = format_stgm_with_cents(
            float(out["realized_stgm"]), signed=True
        )
    return out


__all__ = [
    "STGM_PER_USD",
    "PAPER_UNIT_USD",
    "clamp_price",
    "gross_multiplier",
    "net_multiplier",
    "fee_drag",
    "dollar_pnl_if_real",
    "stgm_pnl_from_price",
    "stgm_to_usd",
    "usd_to_stgm",
    "stgm_to_cents",
    "is_thin_stake",
    "format_stgm_with_cents",
    "format_stake_stgm",
    "ticket_money_row",
]
