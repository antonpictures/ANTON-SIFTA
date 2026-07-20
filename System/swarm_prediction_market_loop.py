#!/usr/bin/env python3
"""Stigmergic auto-bet loop — watches Kalshi 15-min markets, bets STGM,
monitors ending-soon markets, checks results, and learns.

Loop:
    sync Kalshi → filter short-horizon markets → score each →
    auto-bet with STGM → monitor time-to-close → resolve →
    record outcome → feedback → learn → next round

Truth label: STIGMERGIC_AUTOBET_V1.
Ledger: .sifta_state/autobet_receipts.jsonl
"""
from __future__ import annotations

import json
import math
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
AUTOBET_LEDGER = "autobet_receipts.jsonl"
TRUTH_LABEL = "STIGMERGIC_AUTOBET_V1"

AUTO_BET_AGENT = "autobet:stigmergic"
AUTO_BET_GENESIS = 10.0
AUTO_BET_STAKE = 1.0
AUTO_BET_MIN_EDGE = 0.06
AUTO_BET_MAX_PER_TICK = 3
ENDING_SOON_S = 30 * 60
TIMEFRAME_KEYWORDS = ("15 min", "15min", "15-minute", "1 hour", "1hr", "hourly", "daily")


def _state_dir(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _append(row: dict[str, Any], *, state_dir: Optional[Path | str] = None) -> None:
    root = _state_dir(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    try:
        with (root / AUTOBET_LEDGER).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass


def _read_jsonl(path: Path, *, max_rows: int = 2048) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
    except Exception:
        return []
    return rows[-max(1, int(max_rows)) :]


def _is_short_horizon(market_row: dict[str, Any]) -> bool:
    """Check if a market is a short-horizon (15-min, hourly) type."""
    title = str(market_row.get("title") or "").lower()
    subtitle = str(market_row.get("subtitle") or "").lower()
    timeframe = str(market_row.get("timeframe") or "").lower()
    nav = str(market_row.get("nav_section") or "").lower()
    combined = f"{title} {subtitle} {timeframe} {nav}"
    for kw in TIMEFRAME_KEYWORDS:
        if kw in combined:
            return True
    if "btc" in combined and ("above" in combined or "below" in combined or "at or" in combined):
        if any(t in combined for t in ("today", "hour", "min", "this")):
            return True
    return False


def _score_market(market_row: dict[str, Any]) -> dict[str, Any]:
    """Score a market for auto-betting. Returns edge estimate and confidence."""
    yes_price = float(market_row.get("yes_price") or 0.5)
    kalshi_yes = market_row.get("kalshi_yes")
    field_yes = float(market_row.get("field_yes_share") or 0.5)
    trades = int(market_row.get("trades") or 0)
    vol = float(market_row.get("kalshi_volume_24h") or 0.0)

    if kalshi_yes is not None:
        kalshi_yes = float(kalshi_yes)
        local_vs_kalshi = yes_price - kalshi_yes
    else:
        local_vs_kalshi = 0.0

    field_signal = field_yes - 0.5
    swarm_consensus = 0.55 * field_signal + 0.30 * local_vs_kalshi + 0.15 * (yes_price - 0.5)
    edge = abs(swarm_consensus)
    side = "yes" if swarm_consensus > 0 else "no"

    confidence = 0.5
    if trades >= 5:
        confidence += 0.1
    if vol > 100:
        confidence += 0.1
    if abs(local_vs_kalshi) > 0.05:
        confidence += 0.1
    confidence = min(0.95, confidence)

    return {
        "side": side,
        "edge": round(edge, 4),
        "confidence": round(confidence, 4),
        "yes_price": round(yes_price, 4),
        "kalshi_yes": round(kalshi_yes, 4) if kalshi_yes is not None else None,
        "field_yes_share": round(field_yes, 4),
        "local_vs_kalshi": round(local_vs_kalshi, 4),
        "trades": trades,
        "volume_24h": round(vol, 2),
    }


def auto_bet_cycle(
    *,
    engine: Any,
    state_dir: Optional[Path | str] = None,
    max_bets: int = AUTO_BET_MAX_PER_TICK,
    min_edge: float = AUTO_BET_MIN_EDGE,
    stake: float = AUTO_BET_STAKE,
    now: float | None = None,
) -> dict[str, Any]:
    """Run one auto-bet cycle: pull 15-min Kalshi clocks, score, bet best edges."""
    ts = float(now if now is not None else time.time())
    results: list[dict[str, Any]] = []
    bets_placed = 0

    if AUTO_BET_AGENT not in engine.balances:
        engine.balances[AUTO_BET_AGENT] = AUTO_BET_GENESIS
        engine.display_names[AUTO_BET_AGENT] = "Stigmergic AutoBet"

    try:
        from System.swarm_kalshi_public_feed import fetch_15m_clocks

        feed = fetch_15m_clocks(timeout=12.0)
        clocks = feed.get("clocks") or []
    except Exception:
        clocks = []

    for clock in clocks:
        if bets_placed >= max_bets:
            break
        mid = f"kalshi:{clock.get('ticker', '')}"
        if mid not in engine.markets:
            yes = float(clock.get("yes_price") or 0.5)
            yes_pool, no_pool = engine._pools_for_yes_price(yes)
            from System.swarm_sifta_market import Market
            m = Market(
                id=mid,
                title=clock.get("title", "")[:160],
                subtitle=clock.get("yes_sub_title", ""),
                category=f"Crypto · 15 Minute · {clock.get('asset', '?')}",
                yes_pool=yes_pool,
                no_pool=no_pool,
                field_yes=max(0.2, yes * 3.0),
                field_no=max(0.2, (1.0 - yes) * 3.0),
                bias_yes=yes,
                kalshi_ticker=clock.get("ticker", ""),
                kalshi_yes=yes,
                kalshi_volume_24h=float(clock.get("volume_24h") or 0),
                kalshi_synced_ts=ts,
                nav_section="Crypto",
                timeframe="15 Minute",
                asset=clock.get("asset", ""),
                product="Predictions",
            )
            engine.markets[mid] = m
        else:
            m = engine.markets[mid]
            m.kalshi_yes = float(clock.get("yes_price") or m.kalshi_yes or 0.5)
            m.kalshi_volume_24h = float(clock.get("volume_24h") or 0)
            m.kalshi_synced_ts = ts

        score = _score_market(m.to_row())
        score["market_id"] = mid
        score["title"] = clock.get("title", "")[:80]
        score["asset"] = clock.get("asset", "")
        score["target_price"] = clock.get("target_price", 0)
        score["close_time"] = clock.get("close_time", "")

        if score["edge"] >= min_edge and score["trades"] >= 0:
            side = score["side"]
            r = engine.buy(mid, side, stake, agent_id="autobet:stigmergic")
            if r.get("ok"):
                bets_placed += 1
                results.append({
                    "market_id": mid,
                    "title": score["title"],
                    "asset": score["asset"],
                    "side": side,
                    "stake": stake,
                    "edge": score["edge"],
                    "confidence": score["confidence"],
                    "yes_price": score["yes_price"],
                    "kalshi_yes": score["kalshi_yes"],
                    "target_price": score["target_price"],
                })

    row = {
        "schema": "STIGMERGIC_AUTOBET_CYCLE_V1",
        "kind": "autobet_cycle",
        "truth_label": TRUTH_LABEL,
        "trace_id": str(uuid.uuid4()),
        "ts": ts,
        "bets_placed": bets_placed,
        "markets_scored": len(clocks),
        "bets": results,
        "clocks_fetched": len(clocks),
    }
    _append(row, state_dir=state_dir)
    return row


def monitor_ending_soon(
    *,
    engine: Any,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Check which 15-min markets are ending soon and our position in them."""
    try:
        from System.swarm_kalshi_public_feed import fetch_15m_clocks

        feed = fetch_15m_clocks(timeout=10.0)
        clocks = feed.get("clocks") or []
    except Exception:
        clocks = []

    ending: list[dict[str, Any]] = []
    for clock in clocks:
        mid = f"kalshi:{clock.get('ticker', '')}"
        m = engine.markets.get(mid)
        pos = m.positions.get("autobet:stigmergic", {}) if m else {}
        has_position = (float(pos.get("yes") or 0) + float(pos.get("no") or 0)) > 0

        yes_price = float(clock.get("yes_price") or 0.5)
        kalshi_yes = float(clock.get("yes_price") or 0.5)

        score = _score_market({
            "yes_price": yes_price,
            "kalshi_yes": kalshi_yes,
            "field_yes_share": m.field_yes_share() if m else 0.5,
            "trades": m.trades if m else 0,
            "kalshi_volume_24h": float(clock.get("volume_24h") or 0),
        })

        ending.append({
            "market_id": mid,
            "ticker": clock.get("ticker", ""),
            "title": clock.get("title", "")[:80],
            "asset": clock.get("asset", ""),
            "target_price": clock.get("target_price", 0),
            "close_time": clock.get("close_time", ""),
            "yes_price": yes_price,
            "kalshi_yes": kalshi_yes,
            "edge": score["edge"],
            "side": score["side"],
            "has_autobet_position": has_position,
            "position": pos if has_position else None,
            "volume_24h": float(clock.get("volume_24h") or 0),
        })

    ending.sort(key=lambda x: x["edge"], reverse=True)

    return {
        "schema": "STIGMERGIC_MONITOR_V1",
        "kind": "ending_soon_monitor",
        "truth_label": TRUTH_LABEL,
        "ts": time.time(),
        "open_markets": len(clocks),
        "markets": ending[:15],
        "clocks_source": "kalshi_15m_public",
    }


def check_results(
    *,
    engine: Any,
    state_dir: Optional[Path | str] = None,
    write: bool = True,
) -> dict[str, Any]:
    """Check resolved markets against auto-bet predictions. Learn from outcomes."""
    resolved = [m.to_row() for m in engine.markets.values() if m.status == "resolved"]
    autobet_history = [
        h for h in engine.history
        if h.get("agent_id") == "autobet:stigmergic" and h.get("kind") == "closed"
    ]

    wins = sum(1 for h in autobet_history if (h.get("pnl") or 0) > 0)
    losses = sum(1 for h in autobet_history if (h.get("pnl") or 0) < 0)
    total_pnl = sum(float(h.get("pnl") or 0) for h in autobet_history)
    total = wins + losses

    accuracy = wins / max(1, total)

    try:
        from System.swarm_prediction_feedback import record_outcome, adapt_weights
        for h in autobet_history:
            outcome = h.get("outcome")
            if outcome:
                record_outcome(
                    label=f"autobet_{h.get('side', 'unknown')}_{h.get('market_id', 'unknown')}",
                    ts=h.get("ts"),
                    state_dir=state_dir,
                    source="autobet_resolution",
                )
    except Exception:
        pass

    row = {
        "schema": "STIGMERGIC_AUTOBET_RESULTS_V1",
        "kind": "autobet_results",
        "truth_label": TRUTH_LABEL,
        "trace_id": str(uuid.uuid4()),
        "ts": time.time(),
        "total_resolved": total,
        "wins": wins,
        "losses": losses,
        "accuracy": round(accuracy, 4),
        "total_pnl": round(total_pnl, 4),
        "recent_trades": [
            {
                "market_id": h.get("market_id"),
                "side": h.get("side"),
                "stake": h.get("stake"),
                "pnl": h.get("pnl"),
                "outcome": h.get("outcome"),
            }
            for h in autobet_history[-10:]
        ],
    }

    if write:
        _append(row, state_dir=state_dir)

    return row


def format_autobet_for_alice(
    *,
    engine: Any,
    state_dir: Optional[Path | str] = None,
) -> str:
    """Format auto-bet status for Alice's Talk prompt."""
    monitor = monitor_ending_soon(engine=engine, state_dir=state_dir)
    results = check_results(engine=engine, state_dir=state_dir, write=False)

    lines = ["STIGMERGIC AUTOBET (15-min market watcher):"]

    if results["total_resolved"] > 0:
        lines.append(
            f"- record: {results['wins']}W/{results['losses']}L "
            f"({results['accuracy']:.0%}) · PnL {results['total_pnl']:+.2f} STGM"
        )

    high_edge = [m for m in monitor["markets"] if m["edge"] > AUTO_BET_MIN_EDGE]
    if high_edge:
        lines.append(f"- {len(high_edge)} markets with edge > {AUTO_BET_MIN_EDGE:.0%}:")
        for m in high_edge[:3]:
            edge_pct = m["edge"] * 100
            kalshi = f" (Kalshi {m['kalshi_yes']:.0%})" if m["kalshi_yes"] is not None else ""
            pos = " [AUTOBET IN]" if m["has_autobet_position"] else ""
            lines.append(
                f"  · {m['title'][:60]} → bet {m['side'].upper()} "
                f"edge {edge_pct:+.1f}%{kalshi}{pos}"
            )
    else:
        lines.append("- no high-edge markets right now — watching")

    lines.append(f"- {monitor['open_markets']} open markets monitored")
    lines.append(f"- truth: {TRUTH_LABEL}")
    return "\n".join(lines)


__all__ = [
    "AUTOBET_LEDGER",
    "TRUTH_LABEL",
    "auto_bet_cycle",
    "check_results",
    "format_autobet_for_alice",
    "monitor_ending_soon",
]
