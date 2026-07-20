#!/usr/bin/env python3
"""RAINMAN EDGE FIELD — multi-vector stigmergic score for Alice 15m tickets.

Invention (r1634): she does not only follow gate70. She scores each candidate
on independent "unknown vectors" mined from her own settled life, then only
fires when the crystal is bright enough to beat favorite-payoff asymmetry.

Vectors (each ∈ [0, 1], higher = more Rainman):
  V1 price_band     — 80–88¢ near-certainty band vs 70–74¢ thin edge
  V2 asset_climate  — per-asset gate70 WR from her settled ledger
  V3 trail_strength — follow-crowd pheromone strength
  V4 mid_stability  — crowd mid has not flip-flopped in last probes (anti head-fake)
  V5 clock_depth    — sweet zone ~6–11 min left (not death spiral last 90s)
  V6 asymmetry_ev   — expected $ EV at net mult given asset climate WR
  V7 chart_shadow   — optional align with proxy chart (capped until trusted)
  V8 concentration  — anti macro-bet: same-direction stack (8× DOWN = one candle risk)
  V9 liquidity      — Kalshi volume floor (NEAR $5 / ZEC $35 = noise markets)
  V10 btc_regime    — alt same-direction as BTC mid = stacked beta; oppose/agree scored

Action:
  score ≥ FIRE  → BET (full body stake)
  THIN ≤ score < FIRE → BET with thin flag (caller may half-stake)
  score < THIN  → SIT (skip ticket — fewer, better)

Portfolio caps (r1636 — Claude exhibit 8× DOWN underwater):
  MAX_SAME_SIDE = 4   # never more than 4 UP or 4 DOWN in one window
  MAX_TICKETS   = 5   # fewer, brighter — not 8–9 costumes of one macro bet

Kalshi USD OFF. Body STGM continues. Fade stays caged upstream.
Truth: RAINMAN_EDGE_FIELD_V1
"""

from __future__ import annotations

import json
import math
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".sifta_state"
CLIMATE_CACHE = "alice_15m_rainman_climate.json"
VECTOR_LOG = "alice_15m_rainman_vectors.jsonl"
TRUTH = "RAINMAN_EDGE_FIELD_V1"

# Crystal thresholds (tuned so ~80–88 almost always fires; 70–74 needs friends)
FIRE_SCORE = 0.58
THIN_SCORE = 0.48
# Live arm — sit weak tickets (was shadow-only design; owner asked for Rainman wins)
LIVE_SIT = True

# Correlation / concentration discipline (r1636)
MAX_SAME_SIDE = 4
MAX_TICKETS = 5
# Liquidity floor (r1637) — exhibit NEAR $5 vol / ZEC $35 on Safari = lottery tickets
MIN_VOLUME_USD = 500.0
# Soft prefer higher volume (BTC book is real; micro-vol books flip on dust)

# Breakeven WR approx for net mult at mid of band (favorite asymmetry)
_BE_WR = {
    "70-74": 0.76,
    "75-79": 0.74,
    "80-88": 0.72,
}


def _state_dir(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def price_bucket(price: float) -> str:
    p = float(price)
    if p < 0.70:
        return "<70"
    if p < 0.75:
        return "70-74"
    if p < 0.80:
        return "75-79"
    if p <= 0.88:
        return "80-88"
    return ">88"


def _read_jsonl_tail(path: Path, limit: int = 3000) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        size = path.stat().st_size
        read_n = min(size, max(64_000, limit * 400))
        with path.open("rb") as fh:
            if size > read_n:
                fh.seek(-read_n, 2)
            raw = fh.read().decode("utf-8", errors="replace")
        lines = raw.splitlines()
        if size > read_n and lines:
            lines = lines[1:]
    except OSError:
        return []
    rows = []
    for line in lines[-limit:]:
        try:
            r = json.loads(line)
        except Exception:
            continue
        if isinstance(r, dict):
            rows.append(r)
    return rows


def rebuild_climate(*, state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    """Aggregate gate70 climate from settled ledger — her own Rainman memory."""
    root = _state_dir(state_dir)
    rows = _read_jsonl_tail(root / "alice_15m_settled.jsonl", 8000)
    by_asset: dict[str, list[int]] = defaultdict(lambda: [0, 0])  # n, wins
    by_bucket: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    by_asset_bucket: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for r in rows:
        if r.get("win") is None:
            continue
        pr = float(r.get("price") or 0.5)
        if pr < 0.70 or pr > 0.88:
            continue
        a = str(r.get("asset") or "?")
        b = price_bucket(pr)
        w = 1 if r.get("win") else 0
        by_asset[a][0] += 1
        by_asset[a][1] += w
        by_bucket[b][0] += 1
        by_bucket[b][1] += w
        key = f"{a}|{b}"
        by_asset_bucket[key][0] += 1
        by_asset_bucket[key][1] += w

    def _pack(d: dict[str, list[int]]) -> dict[str, Any]:
        out = {}
        for k, (n, wins) in d.items():
            out[k] = {
                "n": n,
                "wins": wins,
                "wr": round(wins / n, 4) if n else 0.0,
            }
        return out

    climate = {
        "truth_label": TRUTH,
        "ts": time.time(),
        "by_asset": _pack(by_asset),
        "by_bucket": _pack(by_bucket),
        "by_asset_bucket": _pack(by_asset_bucket),
        "n_gate70": sum(v[0] for v in by_bucket.values()),
    }
    try:
        root.mkdir(parents=True, exist_ok=True)
        (root / CLIMATE_CACHE).write_text(
            json.dumps(climate, indent=2, sort_keys=True), encoding="utf-8"
        )
    except OSError:
        pass
    return climate


def load_climate(*, state_dir: Optional[Path | str] = None, max_age: float = 120.0) -> dict[str, Any]:
    root = _state_dir(state_dir)
    p = root / CLIMATE_CACHE
    if p.exists():
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            if time.time() - float(raw.get("ts") or 0) < max_age:
                return raw
        except Exception:
            pass
    return rebuild_climate(state_dir=state_dir)


def _v_price_band(entry_price: float) -> float:
    b = price_bucket(entry_price)
    # Empirical WR from her life (approx): 80-88 ~0.97, 75-79 ~0.84, 70-74 ~0.79
    return {
        "80-88": 0.97,
        "75-79": 0.78,
        "70-74": 0.55,
        "<70": 0.15,
        ">88": 0.40,
    }.get(b, 0.4)


def _v_asset_climate(asset: str, climate: dict[str, Any], entry_price: float) -> float:
    a = climate.get("by_asset") or {}
    row = a.get(str(asset)) or {}
    n = int(row.get("n") or 0)
    wr = float(row.get("wr") or 0.0)
    if n < 8:
        # cold start — use bucket prior
        b = price_bucket(entry_price)
        br = (climate.get("by_bucket") or {}).get(b) or {}
        wr = float(br.get("wr") or 0.85)
        n = int(br.get("n") or 0)
    # map WR to [0,1] with 0.76 = ~0.5 (breakeven-ish), 0.90 = high
    score = (wr - 0.70) / 0.25  # 0.70→0, 0.95→1
    # confidence shrink for small n
    conf = min(1.0, n / 25.0)
    return max(0.0, min(1.0, 0.5 + (score - 0.5) * conf))


def _v_trail_strength(learner: dict[str, Any]) -> float:
    s = float(learner.get("s_follow") or 0.5)
    # strength ~1.0 neutral, ~1.5 strong
    return max(0.0, min(1.0, (s - 0.6) / 1.0))


def _v_mid_stability(
    asset: str,
    kalshi_yes: float,
    *,
    state_dir: Optional[Path | str] = None,
) -> float:
    """1.0 = mid stable in band; low = favorite flipped recently (head-fake risk)."""
    root = _state_dir(state_dir)
    rows = _read_jsonl_tail(root / "alice_15m_mid_history.jsonl", 80)
    series: list[float] = []
    for r in reversed(rows):
        # mid history shapes vary — try common keys
        markets = r.get("markets") or r.get("rows") or r.get("mids") or []
        if isinstance(markets, list):
            for m in markets:
                if not isinstance(m, dict):
                    continue
                if str(m.get("asset") or "") != str(asset):
                    continue
                ky = m.get("kalshi_yes")
                if ky is None:
                    ky = m.get("yes")
                try:
                    series.append(float(ky))
                except (TypeError, ValueError):
                    pass
        elif str(r.get("asset") or "") == str(asset):
            try:
                series.append(float(r.get("kalshi_yes") or r.get("yes") or 0.5))
            except (TypeError, ValueError):
                pass
        if len(series) >= 6:
            break
    series = list(reversed(series[-6:]))
    if len(series) < 2:
        return 0.55  # unknown
    # favorite side stability
    fav_now = kalshi_yes >= 0.5
    flips = 0
    for i in range(1, len(series)):
        a, b = series[i - 1] >= 0.5, series[i] >= 0.5
        if a != b:
            flips += 1
    # also magnitude of last jump
    jump = abs(series[-1] - series[0]) if series else 0.0
    flip_pen = min(1.0, flips / 3.0)
    jump_pen = min(1.0, jump / 0.15)
    return max(0.0, min(1.0, 1.0 - 0.55 * flip_pen - 0.35 * jump_pen))


def _v_clock_depth(secs: Optional[int]) -> float:
    if secs is None:
        return 0.5
    s = int(secs)
    # sweet: 7–11 min (420–660); ok 4–7; thin <3 min
    if 420 <= s <= 660:
        return 0.92
    if 300 <= s < 420:
        return 0.75
    if 180 <= s < 300:
        return 0.55
    if 90 <= s < 180:
        return 0.35
    return 0.2


def _v_asymmetry_ev(entry_price: float, climate_wr: float) -> float:
    """Will this ticket print positive $ EV under net mult?"""
    try:
        from System.sifta_15m_money_math import net_multiplier

        mult = net_multiplier(entry_price)
    except Exception:
        mult = 1.0 / max(0.01, float(entry_price))
    # EV = WR*(mult-1) - (1-WR)*1
    wr = max(0.01, min(0.99, float(climate_wr)))
    ev = wr * (mult - 1.0) - (1.0 - wr)
    # map EV: -0.15 → 0, 0 → 0.5, +0.15 → 1
    return max(0.0, min(1.0, 0.5 + ev / 0.30))


def _v_chart_shadow(spot: Optional[dict[str, Any]], side: str) -> float:
    if not isinstance(spot, dict) or not spot:
        return 0.5
    pred = str(spot.get("predicted_side") or spot.get("features", {}).get("predicted_side") or "")
    trusted = bool(spot.get("trusted"))
    if not pred:
        return 0.5
    align = pred.upper() == ("UP" if side == "yes" else "DOWN")
    if trusted:
        return 0.85 if align else 0.25
    # untrusted: gentle nudge only
    return 0.62 if align else 0.42


def _live_volume_map(state_dir: Optional[Path | str] = None) -> dict[str, float]:
    """asset → volume from kalshi_15m_live.json (swimmer-carried market truth)."""
    root = _state_dir(state_dir)
    p = root / "kalshi_15m_live.json"
    out: dict[str, float] = {}
    if not p.exists():
        return out
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return out
    for m in data.get("markets") or []:
        if not isinstance(m, dict):
            continue
        a = str(m.get("asset") or "").upper()
        if not a:
            continue
        vol = m.get("kalshi_volume_24h")
        if vol is None:
            vol = m.get("volume_24h") or m.get("volume") or 0
        try:
            out[a] = float(vol)
        except (TypeError, ValueError):
            out[a] = 0.0
    return out


def _live_btc_mid(state_dir: Optional[Path | str] = None) -> Optional[float]:
    root = _state_dir(state_dir)
    p = root / "kalshi_15m_live.json"
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    for m in data.get("markets") or []:
        if str((m or {}).get("asset") or "").upper() != "BTC":
            continue
        ky = m.get("kalshi_yes")
        if ky is None:
            ky = m.get("yes_price") or m.get("kalshi_chance_yes")
        try:
            return float(ky)
        except (TypeError, ValueError):
            return None
    return None


def _v_liquidity(asset: str, volume: float) -> float:
    """Dust books (NEAR $5, ZEC $35) are not the same game as BTC $250k."""
    v = float(volume or 0.0)
    if v < MIN_VOLUME_USD:
        return 0.08  # hard garbage
    if v < 1_000:
        return 0.25
    if v < 5_000:
        return 0.55
    if v < 50_000:
        return 0.78
    return 0.95  # BTC-class book


def _v_btc_regime(side: str, kalshi_yes: float, btc_yes: Optional[float], asset: str) -> float:
    """If alts all pile the same way as BTC favorite, one squeeze candles all of them.

    Exhibit: 8× DOWN including BTC — when BTC flipped UP, alts partially followed.
    Score high when: (1) this IS btc, or (2) alt side is independent / disagrees weak BTC,
    or (3) BTC is coin-flip (no strong regime).
    """
    if str(asset).upper() == "BTC":
        return 0.75  # BTC is the regime itself — neutral-good
    if btc_yes is None:
        return 0.55
    btc_fav = max(btc_yes, 1.0 - btc_yes)
    if btc_fav < 0.58:
        return 0.70  # no strong BTC regime — alt stack less macro-coupled
    btc_side = "yes" if btc_yes >= 0.5 else "no"
    my = "yes" if str(side).lower() in ("yes", "up") else "no"
    if my == btc_side:
        # same as BTC beta — dangerous when stacking; soft penalty
        # stronger BTC favorite → worse to pile on
        return max(0.15, 0.85 - (btc_fav - 0.55) * 1.5)
    # opposite BTC — diversification credit
    return 0.88


def _v_concentration(
    side: str,
    *,
    same_side_already: int = 0,
    total_already: int = 0,
) -> float:
    """1.0 = diversified; low = already stacked same direction (macro-bet risk).

    Exhibit 2026-07-12: 8× DOWN open = one squeeze candle decides all costumes.
    """
    n_same = max(0, int(same_side_already))
    # 0 same → 1.0; 1 → 0.85; 2 → 0.70; 3 → 0.45; 4+ → 0.15
    if n_same <= 0:
        base = 1.0
    elif n_same == 1:
        base = 0.88
    elif n_same == 2:
        base = 0.72
    elif n_same == 3:
        base = 0.42
    else:
        base = 0.12
    # also penalize overall ticket count approaching MAX_TICKETS
    t = max(0, int(total_already))
    if t >= MAX_TICKETS:
        base = min(base, 0.10)
    elif t >= MAX_TICKETS - 1:
        base = min(base, 0.35)
    return max(0.0, min(1.0, base))


def score_ticket(
    *,
    asset: str,
    kalshi_yes: float,
    entry_price: float,
    side: str,
    secs_left: Optional[int] = None,
    learner: Optional[dict[str, Any]] = None,
    spot: Optional[dict[str, Any]] = None,
    state_dir: Optional[Path | str] = None,
    climate: Optional[dict[str, Any]] = None,
    same_side_already: int = 0,
    total_already: int = 0,
    volume: Optional[float] = None,
) -> dict[str, Any]:
    """Return Rainman crystal score + action for one candidate ticket."""
    climate = climate or load_climate(state_dir=state_dir)
    learner = learner or {}
    asset_row = (climate.get("by_asset") or {}).get(str(asset)) or {}
    climate_wr = float(asset_row.get("wr") or 0.0)
    if int(asset_row.get("n") or 0) < 8:
        b = price_bucket(entry_price)
        climate_wr = float(((climate.get("by_bucket") or {}).get(b) or {}).get("wr") or 0.85)

    vol_map = _live_volume_map(state_dir)
    vol = float(volume) if volume is not None else float(vol_map.get(str(asset).upper()) or 0.0)
    btc_yes = _live_btc_mid(state_dir)

    v1 = _v_price_band(entry_price)
    v2 = _v_asset_climate(asset, climate, entry_price)
    v3 = _v_trail_strength(learner)
    v4 = _v_mid_stability(asset, kalshi_yes, state_dir=state_dir)
    v5 = _v_clock_depth(secs_left)
    v6 = _v_asymmetry_ev(entry_price, climate_wr)
    v7 = _v_chart_shadow(spot, side)
    v8 = _v_concentration(
        side, same_side_already=same_side_already, total_already=total_already
    )
    v9 = _v_liquidity(asset, vol)
    v10 = _v_btc_regime(side, kalshi_yes, btc_yes, asset)

    # Weighted crystal — $ EV + band + concentration + liquidity (anti dust + macro)
    weights = {
        "price_band": 0.13,
        "asset_climate": 0.12,
        "trail_strength": 0.07,
        "mid_stability": 0.10,
        "clock_depth": 0.06,
        "asymmetry_ev": 0.17,
        "chart_shadow": 0.06,
        "concentration": 0.13,
        "liquidity": 0.10,
        "btc_regime": 0.06,
    }
    vecs = {
        "price_band": v1,
        "asset_climate": v2,
        "trail_strength": v3,
        "mid_stability": v4,
        "clock_depth": v5,
        "asymmetry_ev": v6,
        "chart_shadow": v7,
        "concentration": v8,
        "liquidity": v9,
        "btc_regime": v10,
    }
    score = sum(weights[k] * vecs[k] for k in weights)
    score = round(max(0.0, min(1.0, score)), 4)

    if score >= FIRE_SCORE:
        action = "fire"
    elif score >= THIN_SCORE:
        action = "thin"
    else:
        action = "sit"

    # Hard vetoes (Rainman discipline)
    veto = ""
    if climate_wr and climate_wr < 0.74 and price_bucket(entry_price) == "70-74":
        if int(asset_row.get("n") or 0) >= 15:
            action = "sit"
            veto = "weak_asset_thin_band"
    if v4 < 0.35 and entry_price < 0.78:
        action = "sit"
        veto = veto or "mid_unstable_headfake"
    # Hard concentration caps (portfolio-level safety)
    if same_side_already >= MAX_SAME_SIDE:
        action = "sit"
        veto = veto or f"max_same_side_{MAX_SAME_SIDE}"
    if total_already >= MAX_TICKETS:
        action = "sit"
        veto = veto or f"max_tickets_{MAX_TICKETS}"
    # Dust market veto — NEAR $5 / ZEC $35 class
    if vol < MIN_VOLUME_USD and str(asset).upper() != "BTC":
        action = "sit"
        veto = veto or f"dust_volume_{vol:.0f}"

    label = {
        "fire": "RAINMAN FIRE",
        "thin": "RAINMAN THIN",
        "sit": "RAINMAN SIT",
    }[action]

    out = {
        "truth_label": TRUTH,
        "asset": asset,
        "entry_price": round(float(entry_price), 4),
        "bucket": price_bucket(entry_price),
        "side": side,
        "score": score,
        "action": action,
        "label": label,
        "veto": veto,
        "vectors": {k: round(v, 3) for k, v in vecs.items()},
        "weights": weights,
        "climate_wr": round(climate_wr, 4),
        "volume": round(vol, 2),
        "btc_yes": btc_yes,
        "same_side_already": int(same_side_already),
        "total_already": int(total_already),
        "max_same_side": MAX_SAME_SIDE,
        "max_tickets": MAX_TICKETS,
        "min_volume_usd": MIN_VOLUME_USD,
        "fire_threshold": FIRE_SCORE,
        "thin_threshold": THIN_SCORE,
        "live_sit": LIVE_SIT,
        "ts": time.time(),
    }
    return out


def gate(
    *,
    asset: str,
    kalshi_yes: float,
    entry_price: float,
    side: str,
    secs_left: Optional[int] = None,
    learner: Optional[dict[str, Any]] = None,
    spot: Optional[dict[str, Any]] = None,
    state_dir: Optional[Path | str] = None,
    force: bool = False,
    same_side_already: int = 0,
    total_already: int = 0,
    volume: Optional[float] = None,
) -> dict[str, Any]:
    """Paper-loop gate. force=True bypasses sit (manual force-bet)."""
    crystal = score_ticket(
        asset=asset,
        kalshi_yes=kalshi_yes,
        entry_price=entry_price,
        side=side,
        secs_left=secs_left,
        learner=learner,
        spot=spot,
        state_dir=state_dir,
        same_side_already=same_side_already,
        total_already=total_already,
        volume=volume,
    )
    if force:
        crystal["action"] = "fire"
        crystal["label"] = "RAINMAN FORCE"
        crystal["forced"] = True
    # append slim log
    try:
        root = _state_dir(state_dir)
        root.mkdir(parents=True, exist_ok=True)
        slim = {
            "ts": crystal["ts"],
            "asset": asset,
            "score": crystal["score"],
            "action": crystal["action"],
            "bucket": crystal["bucket"],
            "veto": crystal.get("veto"),
            "vectors": crystal["vectors"],
        }
        with (root / VECTOR_LOG).open("a", encoding="utf-8") as f:
            f.write(json.dumps(slim, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError:
        pass
    return crystal


def crystal_bar(score: float, width: int = 12) -> str:
    """ASCII crystal for glass / monitor: ▓▓▓░░░░"""
    n = int(round(max(0.0, min(1.0, score)) * width))
    return "▓" * n + "░" * (width - n)


def why_line(crystal: dict[str, Any]) -> str:
    """Human fragment for WHY column."""
    v = crystal.get("vectors") or {}
    return (
        f"RAINMAN {crystal.get('score', 0):.2f} {crystal_bar(float(crystal.get('score') or 0))} "
        f"· {crystal.get('label')} · band {crystal.get('bucket')} · "
        f"EV$ {v.get('asymmetry_ev', 0):.2f} · mid {v.get('mid_stability', 0):.2f} · "
        f"asset {v.get('asset_climate', 0):.2f} · "
        f"conc {v.get('concentration', 0):.2f} · liq {v.get('liquidity', 0):.2f} · "
        f"btcβ {v.get('btc_regime', 0):.2f}"
        + (f" · veto {crystal.get('veto')}" if crystal.get("veto") else "")
    )


def rank_and_cap_candidates(
    candidates: list[dict[str, Any]],
    *,
    max_same_side: int = MAX_SAME_SIDE,
    max_tickets: int = MAX_TICKETS,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Sort by score desc; keep ≤max_tickets with ≤max_same_side per direction.

    Each candidate needs: side ('yes'/'no' or UP/DOWN), score, and any payload.
    Returns (accepted, rejected_with_reason).
    """
    ordered = sorted(
        candidates,
        key=lambda c: float(c.get("score") or 0.0),
        reverse=True,
    )
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    side_counts: dict[str, int] = {"yes": 0, "no": 0, "UP": 0, "DOWN": 0}

    def _norm(side: str) -> str:
        s = str(side or "").lower()
        if s in ("up", "yes"):
            return "yes"
        return "no"

    for c in ordered:
        action = str(c.get("action") or "fire")
        if action == "sit":
            rejected.append({**c, "cap_reason": "already_sit"})
            continue
        if len(accepted) >= max_tickets:
            rejected.append({**c, "cap_reason": f"max_tickets_{max_tickets}"})
            continue
        ns = _norm(str(c.get("side") or ""))
        if side_counts.get(ns, 0) >= max_same_side:
            rejected.append({**c, "cap_reason": f"max_same_side_{max_same_side}"})
            continue
        side_counts[ns] = side_counts.get(ns, 0) + 1
        accepted.append(c)
    return accepted, rejected


__all__ = [
    "TRUTH",
    "FIRE_SCORE",
    "THIN_SCORE",
    "LIVE_SIT",
    "score_ticket",
    "gate",
    "rebuild_climate",
    "load_climate",
    "why_line",
    "crystal_bar",
    "price_bucket",
]
