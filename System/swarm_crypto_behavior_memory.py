#!/usr/bin/env python3
"""Read-only spot-candle behavior memory for Alice's 15-minute predictions.

The organ reads public Coinbase Exchange OHLCV candles, caches them locally,
and turns the recent path into a small, auditable description (returns,
volatility, range position, volume, and regime).  It never places an order and
never mutates STGM.

The directional signal begins in *shadow* mode.  It may veto a body-STGM bet
only after its own out-of-sample ticket ledger has enough observations and a
Wilson lower confidence bound above chance.  Until then it is explanation and
training evidence, not authority.
"""

from __future__ import annotations

import json
import math
import statistics
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Optional


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
TRUTH_LABEL = "ALICE_CRYPTO_BEHAVIOR_MEMORY_V1"
SOURCE_NAME = "Coinbase Exchange public OHLCV (proxy spot behavior)"
SOURCE_BASE = "https://api.exchange.coinbase.com"
GRANULARITY_SECONDS = 300
CACHE_MAX_AGE_SECONDS = 300
ERROR_CACHE_SECONDS = 90
MIN_CANDLES = 36
MIN_TRUSTED_SETTLES = 60
MIN_TRUSTED_HIT_RATE = 0.55
EVAL_LEDGER = "alice_crypto_behavior_eval.jsonl"


def _state_dir(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return STATE_DIR
    root = Path(state_dir)
    return root if root.name == ".sifta_state" else root / ".sifta_state"


def _cache_path(asset: str, state_dir: Optional[Path | str] = None) -> Path:
    clean = "".join(c for c in str(asset or "").upper() if c.isalnum()) or "UNKNOWN"
    return _state_dir(state_dir) / f"alice_crypto_ohlcv_{clean}.json"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def _default_fetch(url: str, timeout: float) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "SIFTA-Alice-CryptoBehavior/1.0 (read-only public candles)",
        },
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def _normalize_candles(raw: Any, *, now: float) -> list[dict[str, float]]:
    """Normalize Coinbase's [time, low, high, open, close, volume] rows."""
    by_ts: dict[int, dict[str, float]] = {}
    if not isinstance(raw, list):
        return []
    for item in raw:
        if not isinstance(item, (list, tuple)) or len(item) < 6:
            continue
        try:
            ts = int(float(item[0]))
            candle = {
                "ts": float(ts),
                "low": float(item[1]),
                "high": float(item[2]),
                "open": float(item[3]),
                "close": float(item[4]),
                "volume": float(item[5]),
            }
        except Exception:
            continue
        if min(candle["low"], candle["high"], candle["open"], candle["close"]) <= 0:
            continue
        # Do not teach from a candle whose five-minute bucket is still open.
        if ts + GRANULARITY_SECONDS > now:
            continue
        by_ts[ts] = candle
    return [by_ts[key] for key in sorted(by_ts)][-300:]


def fetch_candles(
    asset: str,
    *,
    state_dir: Optional[Path | str] = None,
    now: Optional[float] = None,
    timeout: float = 1.25,
    fetcher: Optional[Callable[[str, float], Any]] = None,
    force: bool = False,
) -> dict[str, Any]:
    """Return cached public 5m candles, refreshing at most once per five minutes."""
    stamp = float(time.time() if now is None else now)
    asset_u = str(asset or "").upper().strip()
    path = _cache_path(asset_u, state_dir)
    cached = _read_json(path)
    age = stamp - float(cached.get("fetched_ts") or 0.0)
    retry_age = stamp - float(cached.get("error_ts") or 0.0)
    cached_rows = list(cached.get("candles") or [])
    if (
        not force
        and cached_rows
        and age >= 0
        and age <= CACHE_MAX_AGE_SECONDS
    ):
        return {**cached, "ok": True, "cache": "fresh", "age_s": round(age, 1)}
    if (
        not force
        and cached.get("last_error")
        and retry_age >= 0
        and retry_age < ERROR_CACHE_SECONDS
    ):
        return {
            **cached,
            "ok": bool(cached_rows),
            "cache": "stale" if cached_rows else "error",
            "age_s": round(max(0.0, age), 1),
        }

    product = f"{asset_u}-USD"
    query = urllib.parse.urlencode({"granularity": GRANULARITY_SECONDS})
    url = f"{SOURCE_BASE}/products/{product}/candles?{query}"
    try:
        raw = (fetcher or _default_fetch)(url, timeout)
        candles = _normalize_candles(raw, now=stamp)
        if len(candles) < MIN_CANDLES:
            raise ValueError(f"only_{len(candles)}_complete_candles")
        out = {
            "truth_label": TRUTH_LABEL,
            "asset": asset_u,
            "product": product,
            "source": SOURCE_NAME,
            "basis": "proxy_spot_not_kalshi_settlement_index",
            "source_url": url,
            "granularity_s": GRANULARITY_SECONDS,
            "fetched_ts": stamp,
            "n_candles": len(candles),
            "candles": candles,
            "last_error": "",
            "error_ts": 0.0,
        }
        _write_json(path, out)
        return {**out, "ok": True, "cache": "refreshed", "age_s": 0.0}
    except Exception as exc:
        err = f"{type(exc).__name__}:{exc}"
        out = {
            **cached,
            "truth_label": TRUTH_LABEL,
            "asset": asset_u,
            "product": product,
            "source": SOURCE_NAME,
            "basis": "proxy_spot_not_kalshi_settlement_index",
            "source_url": url,
            "last_error": err,
            "error_ts": stamp,
        }
        _write_json(path, out)
        return {
            **out,
            "ok": bool(cached_rows),
            "cache": "stale" if cached_rows else "error",
            "age_s": round(max(0.0, age), 1),
        }


def _pct(value: float) -> float:
    return round(float(value) * 100.0, 4)


def analyze_candles(candles: list[dict[str, Any]]) -> dict[str, Any]:
    """Describe the recent price path without claiming it predicts the future."""
    clean = [c for c in candles if float(c.get("close") or 0.0) > 0]
    if len(clean) < MIN_CANDLES:
        return {"available": False, "reason": f"need_{MIN_CANDLES}_candles"}
    closes = [float(c["close"]) for c in clean]
    volumes = [max(0.0, float(c.get("volume") or 0.0)) for c in clean]
    last = closes[-1]

    def ret(bars: int) -> float:
        if len(closes) <= bars:
            return 0.0
        return last / closes[-1 - bars] - 1.0

    log_returns = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
    recent_logs = log_returns[-12:]
    vol_1h = statistics.pstdev(recent_logs) * math.sqrt(12.0) if len(recent_logs) >= 2 else 0.0
    fast = sum(closes[-6:]) / 6.0
    slow = sum(closes[-18:]) / 18.0
    sma_spread = fast / slow - 1.0
    r5, r15, r60, r4h = ret(1), ret(3), ret(12), ret(48)
    last_4h = closes[-49:]
    lo, hi = min(last_4h), max(last_4h)
    range_pos = (last - lo) / (hi - lo) if hi > lo else 0.5
    recent_volume = sum(volumes[-3:]) / 3.0
    baseline_volume = sum(volumes[-36:-3]) / max(1, len(volumes[-36:-3]))
    volume_ratio = recent_volume / baseline_volume if baseline_volume > 0 else 1.0

    # A fixed shadow signal.  It is intentionally simple so its evaluation is
    # auditable; it receives no authority until the live ticket ledger proves it.
    scale = max(vol_1h, 0.0005)
    score = (0.55 * r15 + 0.30 * r60 + 0.15 * sma_spread) / scale
    if abs(r15) > max(0.006, 2.5 * scale):
        regime = "shock_up" if r15 > 0 else "shock_down"
    elif r15 > 0 and r60 > 0 and sma_spread > 0:
        regime = "trend_up"
    elif r15 < 0 and r60 < 0 and sma_spread < 0:
        regime = "trend_down"
    elif vol_1h >= 0.012:
        regime = "volatile_chop"
    else:
        regime = "mixed"

    if abs(score) < 0.12:
        predicted_side = "NEUTRAL"
    else:
        predicted_side = "UP" if score > 0 else "DOWN"
    strength = min(0.99, max(0.0, abs(score) / 1.5))
    return {
        "available": True,
        "n_candles": len(clean),
        "history_hours": round(len(clean) * GRANULARITY_SECONDS / 3600.0, 1),
        "last_price": last,
        "return_5m_pct": _pct(r5),
        "return_15m_pct": _pct(r15),
        "return_1h_pct": _pct(r60),
        "return_4h_pct": _pct(r4h),
        "volatility_1h_pct": _pct(vol_1h),
        "sma_spread_pct": _pct(sma_spread),
        "range_position_4h": round(range_pos, 4),
        "volume_ratio": round(volume_ratio, 3),
        "regime": regime,
        "predicted_side": predicted_side,
        "signal_strength": round(strength, 4),
        "signal_score": round(score, 4),
    }


def _eval_rows(state_dir: Optional[Path | str] = None) -> list[dict[str, Any]]:
    path = _state_dir(state_dir) / EVAL_LEDGER
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []
    seen: set[str] = set()
    for line in reversed(lines[-5000:]):
        try:
            row = json.loads(line)
        except Exception:
            continue
        ticker = str(row.get("ticker") or "")
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        rows.append(row)
    rows.reverse()
    return rows


def _wilson_lower(wins: int, total: int, z: float = 1.96) -> float:
    if total <= 0:
        return 0.0
    p = wins / total
    denom = 1.0 + z * z / total
    center = p + z * z / (2.0 * total)
    margin = z * math.sqrt((p * (1.0 - p) + z * z / (4.0 * total)) / total)
    return max(0.0, (center - margin) / denom)


def calibration(asset: str, *, state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    asset_u = str(asset or "").upper()
    rows = [
        row
        for row in _eval_rows(state_dir)
        if str(row.get("asset") or "").upper() == asset_u
        and row.get("predicted_side") in ("UP", "DOWN")
        and row.get("actual_side") in ("UP", "DOWN")
    ]
    n = len(rows)
    wins = sum(1 for row in rows if row.get("predicted_side") == row.get("actual_side"))
    hit_rate = wins / n if n else 0.0
    lower = _wilson_lower(wins, n)
    trusted = bool(
        n >= MIN_TRUSTED_SETTLES
        and hit_rate >= MIN_TRUSTED_HIT_RATE
        and lower > 0.50
    )
    return {
        "asset": asset_u,
        "n": n,
        "correct": wins,
        "hit_rate": round(hit_rate, 4),
        "wilson_lower": round(lower, 4),
        "trusted": trusted,
        "mode": "trusted_veto" if trusted else "shadow_learning",
        "prove_rule": (
            f"n>={MIN_TRUSTED_SETTLES}, hit_rate>={MIN_TRUSTED_HIT_RATE:.0%}, "
            "95% Wilson lower>50%"
        ),
    }


def behavior_snapshot(
    asset: str,
    *,
    state_dir: Optional[Path | str] = None,
    now: Optional[float] = None,
    fetcher: Optional[Callable[[str, float], Any]] = None,
    force: bool = False,
    timeout: float = 1.25,
) -> dict[str, Any]:
    fetched = fetch_candles(
        asset,
        state_dir=state_dir,
        now=now,
        fetcher=fetcher,
        force=force,
        timeout=timeout,
    )
    analysis = analyze_candles(list(fetched.get("candles") or []))
    cal = calibration(asset, state_dir=state_dir)
    if not analysis.get("available"):
        return {
            "truth_label": TRUTH_LABEL,
            "asset": str(asset or "").upper(),
            "available": False,
            "source": SOURCE_NAME,
            "basis": "proxy_spot_not_kalshi_settlement_index",
            "error": fetched.get("last_error") or analysis.get("reason"),
            "calibration": cal,
            "summary": "spot chart unavailable · learner/crowd evidence only",
        }
    regime = str(analysis.get("regime") or "mixed").replace("_", " ")
    side = str(analysis.get("predicted_side") or "NEUTRAL")
    summary = (
        f"spot {regime} · 15m {float(analysis.get('return_15m_pct') or 0):+.2f}% · "
        f"1h {float(analysis.get('return_1h_pct') or 0):+.2f}% · chart {side} "
        f"({cal['mode'].replace('_', ' ')}, {cal['correct']}/{cal['n']})"
    )
    return {
        "truth_label": TRUTH_LABEL,
        "asset": str(asset or "").upper(),
        "available": True,
        "source": SOURCE_NAME,
        "basis": "proxy_spot_not_kalshi_settlement_index",
        "source_product": fetched.get("product"),
        "cache": fetched.get("cache"),
        "age_s": fetched.get("age_s"),
        "features": analysis,
        "predicted_side": side,
        "trusted": bool(cal.get("trusted")),
        "calibration": cal,
        "summary": summary,
    }


def record_settlement(
    *,
    asset: str,
    ticker: str,
    actual_side: str,
    spot_snapshot: dict[str, Any],
    state_dir: Optional[Path | str] = None,
    now: Optional[float] = None,
) -> dict[str, Any]:
    """Score one immutable shadow prediction once; duplicate tickers are ignored."""
    ticker_s = str(ticker or "").strip()
    predicted = str(spot_snapshot.get("predicted_side") or "").upper()
    actual = str(actual_side or "").upper()
    if not ticker_s or predicted not in ("UP", "DOWN") or actual not in ("UP", "DOWN"):
        return {"ok": False, "reason": "unscorable_signal"}
    if any(str(row.get("ticker") or "") == ticker_s for row in _eval_rows(state_dir)):
        return {"ok": True, "duplicate": True, "ticker": ticker_s}
    row = {
        "truth_label": TRUTH_LABEL,
        "ts": float(time.time() if now is None else now),
        "asset": str(asset or "").upper(),
        "ticker": ticker_s,
        "predicted_side": predicted,
        "actual_side": actual,
        "correct": predicted == actual,
        "signal_strength": (spot_snapshot.get("features") or {}).get("signal_strength"),
        "regime": (spot_snapshot.get("features") or {}).get("regime"),
        "source": spot_snapshot.get("source") or SOURCE_NAME,
        "basis": "proxy_spot_not_kalshi_settlement_index",
        "note": "shadow chart signal evaluation; no wallet mutation",
    }
    root = _state_dir(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    with (root / EVAL_LEDGER).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return {"ok": True, "row": row, "calibration": calibration(asset, state_dir=root)}


def cached_coverage_status(*, state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    root = _state_dir(state_dir)
    assets: list[str] = []
    candles = 0
    for path in root.glob("alice_crypto_ohlcv_*.json"):
        raw = _read_json(path)
        if raw.get("candles"):
            assets.append(str(raw.get("asset") or path.stem.rsplit("_", 1)[-1]))
            candles += int(raw.get("n_candles") or len(raw.get("candles") or []))
    eval_rows = _eval_rows(root)
    return {
        "truth_label": TRUTH_LABEL,
        "assets_cached": sorted(set(assets)),
        "n_assets_cached": len(set(assets)),
        "n_candles_cached": candles,
        "n_shadow_settles": len(eval_rows),
        "n_trusted_assets": sum(
            1 for asset in set(assets) if calibration(asset, state_dir=root).get("trusted")
        ),
    }


__all__ = [
    "TRUTH_LABEL",
    "SOURCE_NAME",
    "analyze_candles",
    "behavior_snapshot",
    "cached_coverage_status",
    "calibration",
    "fetch_candles",
    "record_settlement",
]
