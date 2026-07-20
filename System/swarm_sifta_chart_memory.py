#!/usr/bin/env python3
"""Alice 15m behavior memory — her settles, crowd tape, and public spot candles.

She remembers:
  - per-asset paper outcomes (W/L, unit PnL, follow vs fade)
  - hour-of-day performance (local)
  - recent mid path snapshots (crowd tape)
  - read-only public 5-minute spot OHLCV behavior (shadow-learning first)

Used as a gate/boost on top of the learner — not a crystal ball.
Truth: improves selection; does not guarantee +EV. Kalshi USD still off.
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

REPO = Path(__file__).resolve().parents[1]
STATE = REPO / ".sifta_state"
SETTLED = STATE / "alice_15m_settled.jsonl"
MID_HIST = STATE / "alice_15m_mid_history.jsonl"
MEMORY = STATE / "alice_15m_chart_memory.json"

TRUTH = "ALICE_15M_CHART_MEMORY_V1"

# gates from overnight + ongoing postmortem
# r1720: Alice *uses* chart trail harder — sit bleeds sooner, force prefer side
MIN_ASSET_N = 12
SIT_ASSET_PNL = -6.0  # was -8 — cut chronic losers faster (know the chart)
SIT_ASSET_WR = 0.48  # with enough n
SIT_HOUR_PNL = -6.0
SIT_HOUR_N = 20
CHOP_WINDOW = 8  # last N settles for asset
CHOP_FLIPS = 5  # if result flips this many times → chop sit
MID_SPIKE = 0.18  # yes mid moved >18¢ in recent snapshots → caution
# r1720: when follow beats fade (or reverse) by this much, block wrong strategy
CHART_PREFER_EDGE = 3.0


def _iter_jsonl(path: Path, limit: int = 5000) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []
    for ln in lines[-limit:]:
        if not ln.strip():
            continue
        try:
            o = json.loads(ln)
        except Exception:
            continue
        if isinstance(o, dict):
            rows.append(o)
    return rows


def rebuild_memory(*, state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    root = Path(state_dir) if state_dir else STATE
    if root.name != ".sifta_state":
        root = root / ".sifta_state"
    settled_path = root / "alice_15m_settled.jsonl"
    raw_rows = _iter_jsonl(settled_path, limit=8000)
    # A historical two-writer race duplicated 273 tickers.  Keep the append-only
    # evidence intact, but never let duplicate receipts become duplicate lessons.
    by_ticker: dict[str, dict[str, Any]] = {}
    no_ticker: list[dict[str, Any]] = []
    for row in raw_rows:
        ticker = str(row.get("ticker") or "").strip()
        if ticker:
            by_ticker[ticker] = row  # newest receipt wins
        else:
            no_ticker.append(row)
    rows = sorted(
        [*no_ticker, *by_ticker.values()],
        key=lambda row: float(row.get("ts") or 0.0),
    )

    by_asset: dict[str, dict[str, Any]] = {}
    by_hour: dict[int, dict[str, float]] = defaultdict(
        lambda: {"w": 0.0, "l": 0.0, "pnl": 0.0, "n": 0.0}
    )
    recent_by_asset: dict[str, list[int]] = defaultdict(list)  # 1=win 0=loss order

    for r in rows:
        if r.get("win") is None and r.get("result") not in ("yes", "no"):
            continue
        asset = str(r.get("asset") or "?").upper()
        win = r.get("win")
        if win is None:
            # derive
            side = str(r.get("side") or "")
            res = str(r.get("result") or "")
            win = side == res if side and res in ("yes", "no") else None
        if win is None:
            continue
        pnl = float(r.get("pnl") or 0.0)
        a = by_asset.setdefault(
            asset,
            {
                "n": 0,
                "w": 0,
                "l": 0,
                "pnl": 0.0,
                "follow_pnl": 0.0,
                "fade_pnl": 0.0,
                "last": [],
            },
        )
        a["n"] += 1
        a["pnl"] += pnl
        if win:
            a["w"] += 1
        else:
            a["l"] += 1
        strat = str(r.get("strategy") or "unknown")
        if strat == "follow_crowd":
            a["follow_pnl"] += pnl
        elif strat == "fade_crowd":
            a["fade_pnl"] += pnl
        a["last"].append(1 if win else 0)
        a["last"] = a["last"][-20:]
        recent_by_asset[asset].append(1 if win else 0)
        recent_by_asset[asset] = recent_by_asset[asset][-CHOP_WINDOW:]

        ts = r.get("ts")
        if ts:
            try:
                h = datetime.fromtimestamp(float(ts)).hour
                by_hour[h]["n"] += 1
                by_hour[h]["pnl"] += pnl
                if win:
                    by_hour[h]["w"] += 1
                else:
                    by_hour[h]["l"] += 1
            except Exception:
                pass

    # summarize assets
    assets_out = {}
    for asset, a in by_asset.items():
        n = int(a["n"])
        wr = (a["w"] / n) if n else 0.0
        last = a["last"][-CHOP_WINDOW:]
        flips = 0
        for i in range(1, len(last)):
            if last[i] != last[i - 1]:
                flips += 1
        assets_out[asset] = {
            "n": n,
            "w": int(a["w"]),
            "l": int(a["l"]),
            "wr": round(wr, 4),
            "pnl": round(float(a["pnl"]), 4),
            "follow_pnl": round(float(a["follow_pnl"]), 4),
            "fade_pnl": round(float(a["fade_pnl"]), 4),
            "chop_flips": flips,
            # This is outcome alternation, not a price-chart regime.  Preserve
            # the compatibility key, but do not call it market chop or use it
            # alone as authority to stake/sit.
            "outcome_flip_noise": bool(
                len(last) >= CHOP_WINDOW and flips >= CHOP_FLIPS
            ),
            "chop": bool(len(last) >= CHOP_WINDOW and flips >= CHOP_FLIPS),
            "prefer": (
                "follow"
                if float(a["follow_pnl"]) >= float(a["fade_pnl"])
                else "fade"
            ),
        }

    hours_out = {}
    for h, v in by_hour.items():
        n = int(v["n"])
        hours_out[str(h)] = {
            "n": n,
            "w": int(v["w"]),
            "l": int(v["l"]),
            "wr": round((v["w"] / n) if n else 0.0, 4),
            "pnl": round(float(v["pnl"]), 4),
            "bad": bool(n >= SIT_HOUR_N and float(v["pnl"]) <= SIT_HOUR_PNL),
        }

    mem = {
        "truth_label": TRUTH,
        "ts": time.time(),
        "n_settled_rows": len(rows),
        "n_raw_rows": len(raw_rows),
        "n_duplicate_tickers_ignored": max(0, len(raw_rows) - len(rows)),
        "assets": assets_out,
        "hours": hours_out,
        "note": (
            "Own settlements are deduplicated by ticker. Crowd tape is separate "
            "from public spot OHLCV; spot direction remains shadow-only until calibrated."
        ),
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / "alice_15m_chart_memory.json").write_text(
        json.dumps(mem, indent=2, sort_keys=True), encoding="utf-8"
    )
    return mem


def load_memory(state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    root = Path(state_dir) if state_dir else STATE
    if root.name != ".sifta_state":
        root = root / ".sifta_state"
    path = root / "alice_15m_chart_memory.json"
    if path.exists():
        try:
            # rebuild if stale > 10 min
            age = time.time() - path.stat().st_mtime
            if age > 600:
                return rebuild_memory(state_dir=root)
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return rebuild_memory(state_dir=root)


def record_mid_snapshot(
    markets: list[dict[str, Any]], *, state_dir: Optional[Path | str] = None
) -> None:
    """Append a thin mid snapshot for path/behavior (crowd tape memory)."""
    root = Path(state_dir) if state_dir else STATE
    if root.name != ".sifta_state":
        root = root / ".sifta_state"
    root.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": time.time(),
        "markets": [
            {
                "asset": m.get("asset"),
                "yes": m.get("kalshi_yes"),
                "ticker": m.get("kalshi_ticker") or m.get("ticker"),
                "secs": m.get("seconds_to_close") or m.get("secs"),
            }
            for m in markets
            if m.get("asset")
        ],
    }
    try:
        with (root / "alice_15m_mid_history.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _mid_path_spike(asset: str, *, state_dir: Optional[Path | str] = None) -> Optional[float]:
    root = Path(state_dir) if state_dir else STATE
    if root.name != ".sifta_state":
        root = root / ".sifta_state"
    path = root / "alice_15m_mid_history.jsonl"
    rows = _iter_jsonl(path, limit=40)
    ys: list[float] = []
    for r in rows[-15:]:
        for m in r.get("markets") or []:
            if str(m.get("asset") or "").upper() == asset.upper() and m.get("yes") is not None:
                try:
                    ys.append(float(m["yes"]))
                except Exception:
                    pass
    if len(ys) < 3:
        return None
    return abs(ys[-1] - ys[0])


def behavior_gate(
    asset: str,
    *,
    side: str,
    kalshi_yes: float,
    strategy: str = "follow_crowd",
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Return sit/ok + reasons from chart/behavior memory."""
    mem = load_memory(state_dir)
    asset_u = str(asset or "?").upper()
    a = (mem.get("assets") or {}).get(asset_u) or {}
    hour = datetime.now().hour
    h = (mem.get("hours") or {}).get(str(hour)) or {}

    reasons: list[str] = []
    sit = False

    n = int(a.get("n") or 0)
    pnl = float(a.get("pnl") or 0.0)
    wr = float(a.get("wr") or 0.0)
    if n >= MIN_ASSET_N and pnl <= SIT_ASSET_PNL:
        sit = True
        reasons.append(f"asset_bleed_pnl={pnl:.1f}")
    if n >= MIN_ASSET_N and wr < SIT_ASSET_WR and pnl < 0:
        sit = True
        reasons.append(f"asset_wr={wr:.0%}")
    # Alternating wins/losses are outcome noise, not evidence that the price
    # chart itself is choppy.  Surface it, but do not block a bet on this alone.
    outcome_flip_noise = bool(a.get("outcome_flip_noise") or a.get("chop"))
    if h.get("bad"):
        sit = True
        reasons.append(f"bad_hour_{hour}")

    # r1720: chart memory owns side style — follow vs fade from her trail
    prefer = str(a.get("prefer") or "follow")
    follow_pnl = float(a.get("follow_pnl") or 0)
    fade_pnl = float(a.get("fade_pnl") or 0)
    force_follow = prefer == "follow" and (
        fade_pnl < -5 or (follow_pnl - fade_pnl) >= float(CHART_PREFER_EDGE)
    )
    force_fade = prefer == "fade" and (
        follow_pnl < -5 or (fade_pnl - follow_pnl) >= float(CHART_PREFER_EDGE)
    )
    if force_follow and strategy == "fade_crowd":
        sit = True
        reasons.append("chart_memory_blocks_fade")
    if force_fade and strategy in ("follow_crowd", "follow"):
        sit = True
        reasons.append("chart_memory_blocks_follow")

    spike = _mid_path_spike(asset_u, state_dir=state_dir)
    if spike is not None and spike >= MID_SPIKE:
        # thrashy crowd tape — sit unless strong favorite
        fav = max(float(kalshi_yes), 1.0 - float(kalshi_yes))
        if fav < 0.70:
            sit = True
            reasons.append(f"mid_spike={spike:.2f}")

    # Public spot candle behavior is shadow-learning first.  It can only veto
    # after its own live ticket ledger passes the explicit calibration rule.
    spot: dict[str, Any] = {}
    try:
        from System.swarm_crypto_behavior_memory import behavior_snapshot

        spot = behavior_snapshot(asset_u, state_dir=state_dir)
        spot_side = str(spot.get("predicted_side") or "NEUTRAL")
        bet_side = "UP" if str(side).lower() == "yes" else "DOWN"
        if bool(spot.get("trusted")) and spot_side in ("UP", "DOWN") and spot_side != bet_side:
            sit = True
            reasons.append(f"trusted_spot_disagrees={spot_side}")
    except Exception as exc:
        spot = {
            "available": False,
            "summary": "spot chart unavailable · learner/crowd evidence only",
            "error": f"{type(exc).__name__}:{exc}",
        }

    own_summary = (
        f"own trail {n} bets, {wr:.0%} WR, {pnl:+.1f}u"
        if n
        else "own trail warming"
    )
    crowd_side = "UP" if float(kalshi_yes) >= 0.5 else "DOWN"
    crowd_pct = max(float(kalshi_yes), 1.0 - float(kalshi_yes))
    summary = (
        f"crowd {crowd_pct:.0%} {crowd_side} · {own_summary} · "
        f"{spot.get('summary') or 'spot chart warming'}"
    )

    return {
        "action": "sit_out" if sit else "ok",
        "asset": asset_u,
        "reasons": reasons,
        "memory": {
            "n": n,
            "wr": wr,
            "pnl": pnl,
            "prefer": prefer,
            "outcome_flip_noise": outcome_flip_noise,
            "hour": hour,
            "hour_pnl": h.get("pnl"),
            "mid_spike": spike,
        },
        "spot": spot,
        "summary": summary,
        "truth_label": TRUTH,
    }


def memory_status(state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    mem = load_memory(state_dir)
    assets = mem.get("assets") or {}
    worst = sorted(assets.items(), key=lambda kv: float(kv[1].get("pnl") or 0))[:5]
    best = sorted(assets.items(), key=lambda kv: float(kv[1].get("pnl") or 0), reverse=True)[
        :5
    ]
    return {
        "truth_label": TRUTH,
        "n_assets": len(assets),
        "n_settled_rows": mem.get("n_settled_rows"),
        "worst": [{**{"asset": a}, **v} for a, v in worst],
        "best": [{**{"asset": a}, **v} for a, v in best],
        "ts": mem.get("ts"),
    }


__all__ = [
    "TRUTH",
    "rebuild_memory",
    "load_memory",
    "record_mid_snapshot",
    "behavior_gate",
    "memory_status",
]
