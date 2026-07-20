#!/usr/bin/env python3
"""Co-direction ticker picker — best-of-3 same way, avoid contrarians (r1660).

Owner: pick tickers that go ONE direction (all three). Avoid ones that might
go the other way (last on list). STGM-first; US$ they arm themselves.

Board mids are the pheromone: majority UP/DOWN is the field. Assets aligned
with majority + strong favorite + volume rank first. Contrarians sit.

Truth: ALICE_15M_CO_DIRECTION_V1
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".sifta_state"
TRUTH = "ALICE_15M_CO_DIRECTION_V1"
# Majority must be this clear before we force-align / skip contrarians
MIN_MAJORITY_FRAC = 0.55  # > half of readable clocks
MIN_MAJORITY_N = 4  # at least 4 assets speaking
# Soft: never pick more than this many against the field
MAX_CONTRARIAN = 0  # owner: avoid other direction entirely when field is clear
# Power-max eligible floor (Pro liquidity_score 0–1). ~0.25 ≈ thin-but-tradeable.
MIN_LIQUIDITY_SCORE = 0.25
# Owner 2026-07-13: unusual/fragile behavior is evidence for shadow study,
# not a moral ban. Weird assets stay out of live selection.
# r1720: HYPE back on live strip (liquid charts); ZEC/NEAR remain shadow dust
WEIRD_15M_ASSETS = frozenset({"ZEC", "NEAR"})


def is_weird_15m_asset(asset: str) -> bool:
    return str(asset or "").upper() in WEIRD_15M_ASSETS


def _state(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def board_field(*, state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    """Read live strip → majority direction + per-asset ranks."""
    root = _state(state_dir)
    path = root / "kalshi_15m_live.json"
    assets: list[dict[str, Any]] = []
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for m in data.get("markets") or []:
                if not isinstance(m, dict):
                    continue
                a = str(m.get("asset") or "").upper()
                if not a or a in WEIRD_15M_ASSETS:
                    continue
                yes = m.get("kalshi_yes")
                if yes is None:
                    yes = m.get("yes_price")
                if yes is None:
                    continue
                try:
                    ky = float(yes)
                except (TypeError, ValueError):
                    continue
                vol = float(m.get("kalshi_volume_24h") or m.get("volume") or 0.0)
                fav = max(ky, 1.0 - ky)
                side = "yes" if ky >= 0.5 else "no"
                assets.append(
                    {
                        "asset": a,
                        "ticker": str(m.get("kalshi_ticker") or m.get("ticker") or ""),
                        "yes": ky,
                        "side": side,
                        "fav": fav,
                        "volume": vol,
                        "secs": m.get("seconds_to_close"),
                    }
                )
        except Exception:
            pass

    n_up = sum(1 for x in assets if x["side"] == "yes")
    n_dn = sum(1 for x in assets if x["side"] == "no")
    n = len(assets)
    if n_up > n_dn:
        majority = "yes"
        maj_n = n_up
    elif n_dn > n_up:
        majority = "no"
        maj_n = n_dn
    else:
        majority = "split"
        maj_n = n_up
    maj_frac = (maj_n / n) if n else 0.0
    clear = majority in ("yes", "no") and maj_frac >= MIN_MAJORITY_FRAC and maj_n >= MIN_MAJORITY_N

    # Score alignment with majority (or with BTC if split)
    btc = next((x for x in assets if x["asset"] == "BTC"), None)
    anchor_side = majority if clear else (btc["side"] if btc else "yes")

    ranked: list[dict[str, Any]] = []
    for x in assets:
        align = 1.0 if x["side"] == anchor_side else 0.0
        # strength: how hard mid leans
        lean = abs(x["yes"] - 0.5) * 2.0  # 0–1
        # volume soft (log-ish)
        vol = x["volume"]
        # Pro tape liquidity (r1661) — 24h vol proxy when 5min unknown
        try:
            from System.kalshi_pro_tape_dirt import liquidity_score, is_lottery_premium

            liq = liquidity_score(vol_24h_usd=vol, spread_cents=1.0)
            vsc = float(liq.get("score") or 0.0)
            lottery = is_lottery_premium(x["yes"])
        except Exception:
            if vol >= 50_000:
                vsc = 1.0
            elif vol >= 5_000:
                vsc = 0.75
            elif vol >= 1_000:
                vsc = 0.5
            elif vol >= 200:
                vsc = 0.3
            else:
                vsc = 0.05
            lottery = x["yes"] <= 0.05 or x["yes"] >= 0.95
        # path slope + flip noise from mid history (minute grid)
        path = _path_features(x["asset"], root)
        slope = float(path.get("slope") or 0.0)
        flips = int(path.get("flips") or 0)
        # path aligns with side: rising YES good for UP
        path_align = slope if x["side"] == "yes" else -slope
        # contrarian penalty
        contrarian = x["side"] != anchor_side
        score = (
            0.40 * align
            + 0.20 * min(1.0, lean)
            + 0.20 * vsc
            + 0.15 * max(0.0, min(1.0, 0.5 + path_align * 2.0))
            + 0.05 * max(0.0, 1.0 - flips / 4.0)
        )
        if contrarian:
            score *= 0.15  # bury at bottom of list
        if vol < 200:
            score *= 0.4
        if lottery:
            score *= 0.2  # 95%+ / 5¢ posters last
        ranked.append(
            {
                **x,
                "align": align,
                "contrarian": contrarian,
                "lottery": lottery,
                "anchor_side": anchor_side,
                "path_slope": slope,
                "path_flips": flips,
                "liq_score": vsc,
                "co_dir_score": round(score, 4),
            }
        )
    ranked.sort(
        key=lambda r: (
            -float(r["co_dir_score"]),
            -float(r["liq_score"]),
            -float(r["fav"]),
            -float(r["volume"]),
        )
    )
    eligible = [
        r
        for r in ranked
        if not r.get("contrarian")
        and not r.get("lottery")
        and float(r.get("liq_score") or 0.0) >= MIN_LIQUIDITY_SCORE
    ]
    # r1664: best PAIR (2) same direction — can still be 1 if only one qualifies
    CLUSTER_N = 2
    best_pair = eligible[:CLUSTER_N]
    best_names = {r["asset"] for r in best_pair}

    return {
        "truth_label": TRUTH,
        "ts": time.time(),
        "n": n,
        "n_up": n_up,
        "n_down": n_dn,
        "majority": majority,
        "majority_n": maj_n,
        "majority_frac": round(maj_frac, 3),
        "field_clear": clear,
        "anchor_side": anchor_side,
        "label": "UP" if anchor_side == "yes" else "DOWN",
        "ranked": ranked,
        "cluster_n": CLUSTER_N,
        "best2": [r["asset"] for r in best_pair],
        "best3": [r["asset"] for r in best_pair],  # compat alias → pair
        "best3_side": "UP" if anchor_side == "yes" else "DOWN",
        "best_pair_side": "UP" if anchor_side == "yes" else "DOWN",
        "avoid": [r["asset"] for r in ranked if r["asset"] not in best_names],
        "mind_blowers": [
            f"{r['asset']} {('UP' if r['side'] == 'yes' else 'DOWN')} "
            f"score={float(r['co_dir_score']):.3f} liq={float(r['liq_score']):.3f}"
            for r in best_pair
        ],
    }


def _path_features(asset: str, root: Path) -> dict[str, Any]:
    """Recent mid path: slope + flip count (stigmergic minute-grid proxy)."""
    path = root / "alice_15m_mid_history.jsonl"
    if not path.exists():
        return {"slope": 0.0, "flips": 0, "n": 0, "by_minute": {}}
    try:
        raw = path.read_text(encoding="utf-8", errors="replace").splitlines()[-60:]
        ys: list[float] = []
        by_minute: dict[int, float] = {}
        for line in raw:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            for m in row.get("markets") or []:
                if str(m.get("asset") or "").upper() != asset.upper():
                    continue
                try:
                    y = float(m.get("yes"))
                except (TypeError, ValueError):
                    break
                ys.append(y)
                secs = m.get("secs")
                if secs is not None:
                    try:
                        by_minute[int(secs) // 60] = y
                    except (TypeError, ValueError):
                        pass
                break
        if len(ys) < 3:
            return {"slope": 0.0, "flips": 0, "n": len(ys), "by_minute": by_minute}
        flips = 0
        for i in range(1, len(ys)):
            if (ys[i] - 0.5) * (ys[i - 1] - 0.5) < 0:
                flips += 1
        return {
            "slope": float(ys[-1] - ys[0]),
            "flips": flips,
            "n": len(ys),
            "by_minute": {str(k): v for k, v in sorted(by_minute.items(), reverse=True)},
        }
    except Exception:
        return {"slope": 0.0, "flips": 0, "n": 0, "by_minute": {}}


def _path_slope(asset: str, root: Path) -> float:
    return float(_path_features(asset, root).get("slope") or 0.0)


def rank_candidates(
    candidates: list[dict[str, Any]],
    *,
    state_dir: Optional[Path | str] = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Sort bet candidates by co-direction score; tag skips for contrarians.

    Each candidate needs: asset, side (yes/no), and optional fav/volume.
    """
    field = board_field(state_dir=state_dir)
    score_by = {r["asset"]: r for r in field.get("ranked") or []}
    anchor = field.get("anchor_side") or "yes"
    clear = bool(field.get("field_clear"))

    enriched: list[dict[str, Any]] = []
    for c in candidates:
        a = str(c.get("asset") or "").upper()
        if is_weird_15m_asset(a):
            row = dict(c)
            row["co_dir_score"] = 0.0
            row["co_dir_contrarian"] = True
            row["co_dir_weird"] = True
            row["co_dir_anchor"] = anchor
            row["co_dir_field"] = field.get("label")
            enriched.append(row)
            continue
        side = str(c.get("side") or "").lower()
        meta = score_by.get(a) or {}
        contrarian = bool(clear and side and side != anchor)
        sc = float(meta.get("co_dir_score") or 0.0)
        if contrarian:
            sc = min(sc, 0.05)
        row = dict(c)
        row["co_dir_score"] = sc
        row["co_dir_contrarian"] = contrarian
        row["co_dir_weird"] = False
        row["co_dir_anchor"] = anchor
        row["co_dir_field"] = field.get("label")
        enriched.append(row)

    # non-contrarian first by score, contrarians last
    enriched.sort(
        key=lambda r: (
            1 if r.get("co_dir_contrarian") else 0,
            -float(r.get("co_dir_score") or 0),
        )
    )
    return enriched, field


def should_skip_contrarian(
    asset: str,
    side: str,
    *,
    state_dir: Optional[Path | str] = None,
    field: Optional[dict[str, Any]] = None,
) -> tuple[bool, str]:
    """True if weird/shadow-only, or ticket fights a clear majority field."""
    if is_weird_15m_asset(asset):
        return True, "weird_asset"
    field = field or board_field(state_dir=state_dir)
    anchor = field.get("anchor_side")
    side_l = str(side or "").lower()
    if side_l not in ("yes", "no"):
        return False, ""
    row = next(
        (
            r
            for r in field.get("ranked") or []
            if str(r.get("asset") or "").upper() == str(asset or "").upper()
        ),
        {},
    )
    if row and (row.get("lottery") or float(row.get("liq_score") or 0.0) < MIN_LIQUIDITY_SCORE):
        return True, "illiquid_or_lottery"
    best3 = {str(a).upper() for a in (field.get("best3") or [])}
    if not best3:
        return True, "no_eligible_top3"
    if best3 and str(asset or "").upper() not in best3:
        return True, "not_top3_cluster"
    if field.get("field_clear") and side_l != anchor:
        return True, (
            f"contrarian_to_field_{field.get('label')}_"
            f"{field.get('majority_n')}/{field.get('n')}"
        )
    return False, ""


__all__ = [
    "TRUTH",
    "WEIRD_15M_ASSETS",
    "is_weird_15m_asset",
    "board_field",
    "rank_candidates",
    "should_skip_contrarian",
]
