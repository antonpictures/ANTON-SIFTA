#!/usr/bin/env python3
"""r1684 lab — tournament runner, holdout gate, glass (STGM only).

Orchestrates:
  - execution tape capture
  - frozen strategy arms vs KalshiExecutionSim
  - honest grading (EV/window, not raw WR)
  - holdout promote gate (lab promote only — never USD)

Truth: ALICE_15M_SCALP_LAB_V1
Receipts: r1684-d / r1684-e / r1684-f
"""

from __future__ import annotations

import json
import math
import time
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".sifta_state"
TRUTH = "ALICE_15M_SCALP_LAB_V1"
RECEIPT_D = "r1684-d-scalp-strategy-tournament"
RECEIPT_E = "r1684-e-scalp-holdout-gate"
RECEIPT_F = "r1684-f-scalp-glass"
REPORT_JSON = "alice_15m_scalp_lab_report.json"
REPORT_MD = "alice_15m_scalp_lab_report.md"
GLASS_JSON = "alice_15m_scalp_glass.json"
GLASS_MD = "alice_15m_scalp_glass.md"
LAB_LOG = "alice_15m_scalp_lab.jsonl"

# Phase E gates (promote within STGM lab only)
HOLDOUT_MIN_WINDOWS = 300
HOLDOUT_MIN_FILLS = 500
# For early lab progress we still report gate distance


def _state(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def _log(row: dict[str, Any], *, root: Path) -> None:
    row = dict(row)
    row.setdefault("ts", time.time())
    row.setdefault("truth_label", TRUTH)
    try:
        with (root / LAB_LOG).open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError:
        pass


def tick_scalp_lab(
    *,
    state_dir: Optional[Path | str] = None,
    run_tournament: bool = True,
) -> dict[str, Any]:
    """Monitor hook: capture tape + optional micro tournament on latest books."""
    from System.alice_15m_execution_tape import capture_from_live_marks
    from System.alice_15m_scalp_proof_accounting import (
        annotate_legacy_proof_md,
        recompute_honest_proof,
    )

    root = _state(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    tape = capture_from_live_marks(state_dir=root)
    honest = None
    try:
        honest = recompute_honest_proof(state_dir=root)
        annotate_legacy_proof_md(state_dir=root)
    except Exception as exc:
        honest = {"ok": False, "reason": f"{type(exc).__name__}:{exc}"}

    tourney = None
    if run_tournament:
        try:
            tourney = run_live_shadow_tournament(state_dir=root, max_ticks_per_ticker=40)
        except Exception as exc:
            tourney = {"ok": False, "reason": f"{type(exc).__name__}:{exc}"}

    glass = build_glass(state_dir=root, tourney=tourney, honest=honest)
    out = {
        "ok": True,
        "event": "scalp_lab_tick",
        "tape": {
            "n": tape.get("n"),
            "gap": tape.get("gap"),
            "n_snapshots_total": tape.get("n_snapshots_total"),
        },
        "honest": {
            "n_round_trips": (honest or {}).get("n_round_trips"),
            "training_pnl": ((honest or {}).get("training_round_trip") or {}).get("pnl_usd"),
            "selected_biased_wr": ((honest or {}).get("selected_green_exit") or {}).get(
                "win_rate_biased"
            ),
        },
        "tourney": {
            "ok": (tourney or {}).get("ok"),
            "n_arms": (tourney or {}).get("n_arms"),
            "best_arm": (tourney or {}).get("best_arm"),
        },
        "glass_path": GLASS_JSON,
        "truth_label": TRUTH,
        "usd": "NEVER_FROM_LAB",
        "ts": time.time(),
    }
    _log(out, root=root)
    return out


def _book_ts_ms(book: dict[str, Any]) -> int:
    return int(
        book.get("exchange_ts_ms")
        or book.get("recv_ts_ms")
        or book.get("ts_ms")
        or 0
    )


def _round_id_from_book(book: dict[str, Any], ticker: str = "") -> str:
    """Canonical 15m round id (shared across co-expiring assets when available)."""
    for key in ("round_id", "window_id", "expiration_ts", "close_time", "event_ticker"):
        v = book.get(key)
        if v is not None and str(v).strip():
            return str(v)
    # derive from ticker stem (strip asset-specific prefix when possible)
    t = str(book.get("ticker") or ticker or "")
    if "-" in t:
        # e.g. KXBTC15M-26JUL141530 → round key from suffix
        return t.split("-", 1)[-1] if t.count("-") >= 1 else t
    return t or "unknown_round"


def _tape_hash(by_ticker: dict[str, list[dict[str, Any]]]) -> str:
    import hashlib

    parts: list[str] = []
    for t in sorted(by_ticker):
        hist = by_ticker[t]
        if not hist:
            continue
        first, last = hist[0], hist[-1]
        parts.append(
            f"{t}:{_book_ts_ms(first)}:{_book_ts_ms(last)}:{len(hist)}:"
            f"{last.get('yes_mid')}"
        )
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def _pit_majors(
    by_ticker: dict[str, list[dict[str, Any]]],
    decision_ts_ms: int,
    *,
    lookback_ms: int = 60_000,
) -> tuple[dict[str, float], dict[str, float], dict[str, int]]:
    """Point-in-time majors mids at t and t-lookback (no lookahead).

    Returns (majors_mids, majors_prev_mids, majors_source_ts).
    """
    # asset → list of (ts, mid) ascending
    by_asset: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for _t, hist in by_ticker.items():
        for b in hist:
            asset = str(b.get("asset") or "").upper()
            mid = b.get("yes_mid")
            if not asset or mid is None:
                continue
            ts = _book_ts_ms(b)
            if ts <= 0:
                continue
            by_asset[asset].append((ts, float(mid)))

    mids: dict[str, float] = {}
    prev: dict[str, float] = {}
    src_ts: dict[str, int] = {}
    for asset, series in by_asset.items():
        series.sort(key=lambda x: x[0])
        last_t: Optional[float] = None
        last_ts = 0
        prev_t: Optional[float] = None
        target_prev = decision_ts_ms - lookback_ms
        for ts, mid in series:
            if ts > decision_ts_ms:
                break
            last_t, last_ts = mid, ts
            if ts <= target_prev:
                prev_t = mid
        if last_t is not None:
            mids[asset] = last_t
            src_ts[asset] = last_ts
            if prev_t is not None:
                prev[asset] = prev_t
    return mids, prev, src_ts


def _sync_arm_from_sim(
    st: "ArmState",
    sim: Any,
    ticker: str,
    *,
    intent_side: str = "",
    filled: float = 0.0,
    avg_px: float = 0.0,
    order_id: str = "",
    is_entry: bool = False,
    is_exit: bool = False,
    book_ts_ms: int = 0,
) -> bool:
    """P0.4: sync ArmState from sim inventory. Returns True if round-trip completed."""
    pos = sim.positions.get(ticker)
    remaining = float(pos.qty) if pos and pos.qty > 1e-12 else 0.0
    prev_qty = float(st.open_qty)
    round_trip_complete = False
    if is_entry and filled > 0:
        st.open_side = (pos.side if pos and remaining > 0 else intent_side) or intent_side
        st.open_qty = remaining if remaining > 0 else float(filled)
        st.open_entry = float(avg_px or (pos.avg_entry if pos else 0) or 0)
        st.open_ts_ms = book_ts_ms
        st.trail_best = st.open_entry
        if order_id and remaining <= 1e-12 and filled <= 0:
            pass
        # resting maker: track order without inventory yet
    if is_exit and filled > 0:
        st.open_qty = remaining
        if prev_qty > 1e-12 and remaining <= 1e-12:
            round_trip_complete = True
            st.n_round_trips += 1
            st.open_side = ""
            st.open_entry = 0.0
            st.trail_best = 0.0
            st.cooldown_until_ms = book_ts_ms + 30_000
            st.open_order_id = ""
            st.open_order_action = ""
            st.open_order_price = 0.0
            st.open_order_qty = 0.0
            st.queue_state = ""
        else:
            # residual remains open
            if pos and remaining > 0:
                st.open_side = pos.side
                st.open_entry = float(pos.avg_entry or st.open_entry)
    elif not is_entry and not is_exit:
        st.open_qty = remaining
        if remaining <= 1e-12:
            st.open_side = ""
    return round_trip_complete


def run_live_shadow_tournament(
    *,
    state_dir: Optional[Path | str] = None,
    max_ticks_per_ticker: int = 40,
    latency_ms: int = 500,
) -> dict[str, Any]:
    """Run all frozen arms on recent tape books (shadow, STGM sim only).

    P0 fixes: PIT majors (no lookahead), book-at-arrival after latency,
    residual inventory sync, round-level denominator + bootstrap LCB,
    epoch manifest, hold_to_settlement vs end_of_tape_liquidation.
    """
    from System.alice_15m_execution_sim import KalshiExecutionSim
    from System.alice_15m_execution_tape import load_tape
    from System.alice_15m_scalp_strategies import (
        ArmState,
        all_strategies,
        feature_field_from_books,
        policy_hash_for_strategies,
        STRATEGY_VERSION,
    )

    root = _state(state_dir)
    tape = load_tape(state_dir=root, limit=8000)
    snaps = [r for r in tape if str(r.get("event")) == "book_snapshot"]
    if not snaps:
        return {"ok": False, "reason": "no_tape", "n_arms": 0}

    # group by ticker, keep last N
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for s in snaps:
        t = str(s.get("ticker") or "")
        if t:
            by_ticker[t].append(s)
    for t in list(by_ticker):
        hist = by_ticker[t]
        hist.sort(key=lambda b: (_book_ts_ms(b), int(b.get("seq") or 0)))
        by_ticker[t] = hist[-max_ticks_per_ticker:]

    # P0.5: canonical rounds (not one ticker = one independent window)
    round_ids: set[str] = set()
    for t, hist in by_ticker.items():
        for b in hist:
            round_ids.add(_round_id_from_book(b, t))
    n_rounds = max(1, len(round_ids))
    th = _tape_hash(by_ticker)

    ph = policy_hash_for_strategies()
    epoch = f"lab-{datetime.now().strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:6]}"
    # P0.6: immutable epoch manifest (append-only)
    manifest = {
        "epoch_id": epoch,
        "policy_hash": ph,
        "tape_hash": th,
        "round_ids": sorted(round_ids),
        "n_rounds": n_rounds,
        "n_tickers": len(by_ticker),
        "latency_ms": latency_ms,
        "max_ticks_per_ticker": max_ticks_per_ticker,
        "created_ts": time.time(),
        "note": "overlapping partial windows are not independent holdouts",
    }
    try:
        with (root / "alice_15m_scalp_epoch_manifest.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(manifest, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError:
        pass

    arm_results: list[dict[str, Any]] = []

    for strat in all_strategies():
        settle_mode = str(getattr(strat, "settle_mode", "scalp") or "scalp")
        sim = KalshiExecutionSim(
            run_id=f"{epoch}-{strat.strategy_id}",
            latency_ms=latency_ms,
            state_dir=root,
            strategy_id=strat.strategy_id,
            policy_hash=ph,
            persist=True,
        )
        states: dict[str, ArmState] = {}
        n_no_trade = 0
        n_entries = 0
        n_exits = 0
        n_round_trips = 0
        n_settlements = 0
        n_incomplete_settlement = 0
        round_pnls: dict[str, float] = defaultdict(float)
        pnl_before = 0.0

        for ticker, hist in by_ticker.items():
            st = ArmState(strategy_id=strat.strategy_id, ticker=ticker)
            states[ticker] = st
            # P0.2: preload full hist so arrival can see future books
            sim.register_tape(ticker, hist)
            for i, book in enumerate(hist):
                sim.on_book(book)
                decision_ts = _book_ts_ms(book)
                st.window_id = _round_id_from_book(book, ticker)
                # P0.1: majors as-of decision time only
                maj_mids, maj_prev, maj_ts = _pit_majors(by_ticker, decision_ts)
                field = feature_field_from_books(
                    hist[: i + 1],
                    majors_mids=maj_mids,
                    majors_prev_mids=maj_prev,
                    majors_ts=maj_ts,
                )
                intent = strat.decide(book, state=st, field=field)
                # r1711: double-check regime on enter (strategies also gate inside _enter)
                if intent.action == "enter":
                    try:
                        from System.alice_15m_scalp_strategies import regime_gate

                        mid = book.get("yes_mid")
                        if mid is None:
                            mid = (field or {}).get("mom_yes")  # unused fallback
                        _rg = regime_gate(
                            side=str(intent.side or "yes"),
                            yes_mid=book.get("yes_mid"),
                            field=field,
                        )
                        if _rg:
                            n_no_trade += 1
                            st.no_trade_reasons.append(_rg)
                            continue
                    except Exception:
                        pass
                if intent.action == "no_trade":
                    n_no_trade += 1
                    continue
                if intent.action == "hold":
                    mid = book.get("yes_mid")
                    if mid is not None and st.open_qty > 0:
                        if st.open_side == "yes":
                            sim.mark_excursions(ticker, float(mid))
                        else:
                            sim.mark_excursions(ticker, 1.0 - float(mid))
                    continue
                if intent.action == "enter":
                    snap = sim.submit(
                        {
                            "ticker": ticker,
                            "side": intent.side,
                            "action": "buy",
                            "price": intent.price,
                            "quantity": intent.quantity,
                            "tif": intent.tif,
                            "post_only": intent.post_only,
                            # P0.2: do NOT inject decision book — sim uses tape@arrival
                            "submitted_ts_ms": decision_ts,
                            "window_id": st.window_id,
                            "strategy_id": strat.strategy_id,
                            "latency_ms": latency_ms,
                        }
                    )
                    filled = float(snap.get("filled_qty") or 0)
                    if intent.post_only or str(intent.tif).lower() == "gtc":
                        # P0.8: record resting order so strategy does not spam
                        st.open_order_id = str(snap.get("order_id") or "")
                        st.open_order_price = float(intent.price)
                        st.open_order_qty = float(intent.quantity)
                        st.open_order_action = "buy"
                        st.queue_state = "resting"
                    if filled > 0:
                        n_entries += 1
                        _sync_arm_from_sim(
                            st,
                            sim,
                            ticker,
                            intent_side=intent.side,
                            filled=filled,
                            avg_px=float(snap.get("avg_fill_price") or intent.price),
                            order_id=str(snap.get("order_id") or ""),
                            is_entry=True,
                            book_ts_ms=decision_ts,
                        )
                        if st.open_order_id and st.open_qty > 1e-12:
                            st.open_order_id = ""
                            st.queue_state = "filled"
                    continue
                if intent.action in ("exit", "flatten"):
                    if st.open_qty <= 0:
                        continue
                    sell_px = float(intent.price) if intent.price and intent.price > 0 else 0.01
                    snap = sim.submit(
                        {
                            "ticker": ticker,
                            "side": intent.side or st.open_side or "yes",
                            "action": "sell",
                            "price": sell_px,
                            "quantity": st.open_qty,
                            "tif": intent.tif or "ioc",
                            "post_only": bool(intent.post_only),
                            "reduce_only": True,
                            "submitted_ts_ms": decision_ts,
                            "window_id": st.window_id,
                            "strategy_id": strat.strategy_id,
                            "latency_ms": latency_ms,
                        }
                    )
                    filled = float(snap.get("filled_qty") or 0)
                    if intent.post_only or str(intent.tif).lower() == "gtc":
                        st.open_order_id = str(snap.get("order_id") or "")
                        st.open_order_price = sell_px
                        st.open_order_qty = float(st.open_qty)
                        st.open_order_action = "sell"
                        st.queue_state = "resting"
                    if filled > 0:
                        n_exits += 1
                        pnl_after = float(sim.realized_pnl)
                        delta = pnl_after - pnl_before
                        pnl_before = pnl_after
                        done = _sync_arm_from_sim(
                            st,
                            sim,
                            ticker,
                            filled=filled,
                            avg_px=float(snap.get("avg_fill_price") or 0),
                            is_exit=True,
                            book_ts_ms=decision_ts,
                        )
                        if done:
                            n_round_trips += 1
                            round_pnls[st.window_id] += delta
                    continue

            # end of ticker hist: residual handling depends on settle_mode
            if st.open_qty > 1e-12 and hist:
                last = hist[-1]
                rid = _round_id_from_book(last, ticker)
                if settle_mode == "hold_to_settlement":
                    # P0.3: only settle with canonical resolved outcome
                    resolved = last.get("resolved_side") or last.get("result") or last.get(
                        "settlement"
                    )
                    if resolved in ("yes", "no", "YES", "NO", 0, 1, "0", "1"):
                        rs = str(resolved).lower()
                        if rs in ("1", "yes"):
                            rs = "yes"
                        elif rs in ("0", "no"):
                            rs = "no"
                        won = st.open_side == rs
                        payoff = 1.0 if won else 0.0
                        entry = float(st.open_entry)
                        qty = float(st.open_qty)
                        from System.alice_15m_execution_sim import estimate_taker_fee

                        fee_in = estimate_taker_fee(entry, contracts=qty)
                        # settlement: no exit trade/fee
                        net = round(qty * (payoff - entry) - fee_in, 4)
                        sim.realized_pnl = round(sim.realized_pnl + net, 4)
                        sim.cash = round(sim.cash + qty * payoff, 6)
                        pos = sim.positions.get(ticker)
                        if pos:
                            pos.qty = 0.0
                            pos.realized_pnl = round(pos.realized_pnl + net, 4)
                        st.open_qty = 0.0
                        st.open_side = ""
                        st.n_round_trips += 1
                        n_round_trips += 1
                        n_settlements += 1
                        round_pnls[rid] += net
                        pnl_before = float(sim.realized_pnl)
                    else:
                        # incomplete window — do not substitute last quote
                        n_incomplete_settlement += 1
                        sim.n_unflattenable += 1
                        sim._ledger(
                            {
                                "event": "incomplete_settlement",
                                "ticker": ticker,
                                "qty": st.open_qty,
                                "side": st.open_side,
                                "reason": "no_resolved_outcome",
                                "state": "incomplete_settlement",
                            }
                        )
                else:
                    # end_of_tape_liquidation / scalp arms: force flatten at last bid
                    pnl_before_flat = float(sim.realized_pnl)
                    flat = sim.force_flatten(
                        ticker, book=last, reason="end_of_tape_flatten"
                    )
                    pos = sim.positions.get(ticker)
                    remaining = float(pos.qty) if pos and pos.qty > 1e-12 else 0.0
                    if float((flat.get("snap") or {}).get("filled_qty") or 0) > 0:
                        n_exits += 1
                    st.open_qty = remaining
                    if remaining <= 1e-12:
                        st.open_side = ""
                        st.n_round_trips += 1
                        n_round_trips += 1
                        delta = float(sim.realized_pnl) - pnl_before_flat
                        round_pnls[rid] += delta
                        pnl_before = float(sim.realized_pnl)
                    # else residual stays open + unflattenable already counted

        rec = sim.reconcile()
        pnl = float(rec.get("realized_pnl") or 0)
        # ensure every round key present for bootstrap (0 if untouched)
        for rid in round_ids:
            round_pnls.setdefault(rid, 0.0)
        round_pnl_list = [float(round_pnls[r]) for r in sorted(round_pnls)]
        # If arm only attributes deltas to some rounds, total may not match —
        # prefer explicit round list; if empty activity, use single total block.
        if abs(sum(round_pnl_list) - pnl) > 1e-3 and n_round_trips == 0:
            round_pnl_list = [pnl]
        ci = block_bootstrap_ci(round_pnl_list, n_boot=500, seed=42)
        residual = float(rec.get("residual_qty") or 0)
        n_fills = int(rec.get("n_fills") or 0)  # unique filled orders, not +exits
        arm_results.append(
            {
                "strategy_id": strat.strategy_id,
                "version": getattr(strat, "version", STRATEGY_VERSION),
                "shadow_only": bool(getattr(strat, "shadow_only", False)),
                "settle_mode": settle_mode,
                "n_entries": n_entries,
                "n_exits": n_exits,
                "n_round_trips": n_round_trips,
                "n_settlements": n_settlements,
                "n_incomplete_settlement": n_incomplete_settlement,
                "n_no_trade": n_no_trade,
                "n_fills": n_fills,
                "n_partial": rec.get("n_partial"),
                "n_no_fills": rec.get("n_no_fills"),
                "n_no_arrival_book": rec.get("n_no_arrival_book"),
                "n_unflattenable": rec.get("n_unflattenable"),
                "residual_qty": residual,
                "fee_net_pnl": pnl,
                "fees_total": rec.get("fees_total"),
                "ev_per_window": round(pnl / n_rounds, 6),
                "ev_per_round": round(pnl / n_rounds, 6),
                "ev_per_round_trip": (
                    round(pnl / n_round_trips, 6) if n_round_trips else None
                ),
                "lcb95": ci.get("lo"),
                "ucb95": ci.get("hi"),
                "bootstrap_mean": ci.get("mean"),
                "zero_trade_rate": round(
                    sum(1 for _t, s in states.items() if s.n_round_trips == 0)
                    / max(1, len(states)),
                    4,
                ),
                "n_tickers": len(states),
                "n_windows": n_rounds,
                "n_windows_proxy": n_rounds,  # legacy key
                "n_rounds": n_rounds,
                "run_id": sim.run_id,
                "rank_metric": "fee_net_ev_per_round_lcb",
            }
        )

    # rank by fee-net EV/round; prefer higher LCB when EV ties
    arm_results.sort(
        key=lambda r: (
            float(r.get("ev_per_window") or -1e9),
            float(r.get("lcb95") or -1e9),
        ),
        reverse=True,
    )
    best = arm_results[0]["strategy_id"] if arm_results else None
    report = {
        "ok": True,
        "event": "scalp_lab_tournament",
        "epoch": epoch,
        "epoch_manifest": {
            "epoch_id": epoch,
            "policy_hash": ph,
            "tape_hash": th,
            "n_rounds": n_rounds,
        },
        "policy_hash": ph,
        "strategy_version": STRATEGY_VERSION,
        "latency_ms": latency_ms,
        "n_arms": len(arm_results),
        "n_tickers": len(by_ticker),
        "n_rounds": n_rounds,
        "arms": arm_results,
        "best_arm": best,
        "ranking_rule": "fee_net_ev_per_window_desc_not_win_rate",
        "receipt_id": RECEIPT_D,
        "truth_label": TRUTH,
        "usd_orders": "NEVER",
        "formula_audit": "r20260714-grok-scalp-formula-audit",
        "ts": time.time(),
    }
    report["holdout_gate"] = evaluate_holdout_gate(arm_results)
    _save_report(report, state_dir=root)
    _log({"event": "tournament_done", "best_arm": best, "epoch": epoch}, root=root)
    return report


def evaluate_holdout_gate(arm_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Phase E: lab promote only. Does NOT authorize USD.

    P0.5: LCB95 > 0, no residual inventory, fills not double-counted with exits.
    """
    gates = []
    for a in arm_results:
        n_win = int(a.get("n_rounds") or a.get("n_windows") or a.get("n_windows_proxy") or 0)
        n_fills = int(a.get("n_fills") or 0)  # do NOT add n_exits
        ev = float(a.get("ev_per_window") or a.get("ev_per_round") or 0)
        lcb = a.get("lcb95")
        lcb_f = float(lcb) if lcb is not None else None
        residual = float(a.get("residual_qty") or 0)
        unflat = int(a.get("n_unflattenable") or 0)
        incomplete = int(a.get("n_incomplete_settlement") or 0)
        pass_size = n_win >= HOLDOUT_MIN_WINDOWS and n_fills >= HOLDOUT_MIN_FILLS
        pass_ev = ev > 0
        pass_lcb = lcb_f is not None and lcb_f > 0
        pass_inventory = residual <= 1e-12 and unflat == 0 and incomplete == 0
        lab_promote = bool(pass_size and pass_ev and pass_lcb and pass_inventory)
        gates.append(
            {
                "strategy_id": a.get("strategy_id"),
                "n_windows": n_win,
                "n_rounds": n_win,
                "n_fills": n_fills,
                "n_fills_proxy": n_fills,  # legacy name; no longer double-counts exits
                "ev_per_window": ev,
                "lcb95": lcb_f,
                "residual_qty": residual,
                "need_windows": HOLDOUT_MIN_WINDOWS,
                "need_fills": HOLDOUT_MIN_FILLS,
                "pass_sample_size": pass_size,
                "pass_ev_positive": pass_ev,
                "pass_lcb95_positive": pass_lcb,
                "pass_unflattenable_ok": unflat == 0,
                "pass_no_residual": residual <= 1e-12,
                "pass_inventory_clean": pass_inventory,
                "lab_promote": lab_promote,
                "usd_authorize": False,  # hard no
                "distance": {
                    "windows_short": max(0, HOLDOUT_MIN_WINDOWS - n_win),
                    "fills_short": max(0, HOLDOUT_MIN_FILLS - n_fills),
                },
            }
        )
    any_promote = any(g["lab_promote"] for g in gates)
    return {
        "receipt_id": RECEIPT_E,
        "any_lab_promote": any_promote,
        "usd_authorize": False,
        "promotion_rule": "LCB95>0 AND residual==0 AND sample_size AND EV>0",
        "note": (
            "Passing lab promote means promote within STGM laboratory only. "
            "It does not authorize live USD. Block-bootstrap LCB95 required."
        ),
        "arms": gates,
    }


def block_bootstrap_ci(
    window_pnls: list[float],
    *,
    n_boot: int = 500,
    alpha: float = 0.05,
    seed: int = 42,
) -> dict[str, float]:
    """Block bootstrap mean CI (each window is one block)."""
    if not window_pnls:
        return {"mean": 0.0, "lo": 0.0, "hi": 0.0, "n": 0}
    import random

    rng = random.Random(seed)
    n = len(window_pnls)
    means = []
    for _ in range(n_boot):
        sample = [window_pnls[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo_i = int(alpha / 2 * n_boot)
    hi_i = int((1 - alpha / 2) * n_boot) - 1
    hi_i = max(0, min(n_boot - 1, hi_i))
    return {
        "mean": round(sum(window_pnls) / n, 6),
        "lo": round(means[lo_i], 6),
        "hi": round(means[hi_i], 6),
        "n": n,
    }


def build_glass(
    *,
    state_dir: Optional[Path | str] = None,
    tourney: Optional[dict[str, Any]] = None,
    honest: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Owner glass: strategy, entry, exit mark, fees, hold CF, no-trade reasons."""
    root = _state(state_dir)
    if tourney is None:
        try:
            p = root / REPORT_JSON
            tourney = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        except Exception:
            tourney = {}
    if honest is None:
        try:
            p = root / "alice_15m_scalp_proof_honest.json"
            honest = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        except Exception:
            honest = {}

    # live USD open marks for cash-out awareness (read-only)
    usd_opens: list[dict[str, Any]] = []
    try:
        night_path = root / "kalshi_usd_night.json"
        if night_path.exists():
            night = json.loads(night_path.read_text(encoding="utf-8"))
            for o in night.get("open") or []:
                if isinstance(o, dict):
                    usd_opens.append(
                        {
                            "asset": o.get("asset"),
                            "ticker": o.get("ticker"),
                            "side": o.get("side"),
                            "price": o.get("price"),
                            "note": "live_usd_open_read_only",
                        }
                    )
    except Exception:
        pass

    # training book open
    training_open: list[dict[str, Any]] = []
    try:
        tb = root / "alice_15m_scalp_training_book.json"
        if tb.exists():
            book = json.loads(tb.read_text(encoding="utf-8"))
            for o in book.get("open") or []:
                if isinstance(o, dict):
                    training_open.append(
                        {
                            "asset": o.get("asset"),
                            "ticker": o.get("ticker"),
                            "side": o.get("side"),
                            "entry": o.get("price") or o.get("entry"),
                            "window_id": o.get("window_id"),
                        }
                    )
    except Exception:
        pass

    arms = (tourney or {}).get("arms") or []
    glass = {
        "truth_label": TRUTH,
        "receipt_id": RECEIPT_F,
        "ts": time.time(),
        "stamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "doctrine": {
            "bank_greens_mid_window": True,
            "hold_to_end_not_required": True,
            "owner_lesson": (
                "Alice cash-out organ banks fee-true greens inside the 15m window. "
                "Glass can show red (direction) while USD/STGM booked green via TP. "
                "Repeat fee-true take-profit pattern; discover more via lab arms."
            ),
        },
        "usd_opens_readonly": usd_opens,
        "training_open": training_open,
        "honest_accounting": {
            "selected_green_biased_wr": ((honest or {}).get("selected_green_exit") or {}).get(
                "win_rate_biased"
            ),
            "training_pnl": ((honest or {}).get("training_round_trip") or {}).get("pnl_usd"),
            "training_n": ((honest or {}).get("training_round_trip") or {}).get("n_exits"),
            "scalp_beat_hold": ((honest or {}).get("hold_counterfactual") or {}).get(
                "scalp_beat_hold"
            ),
            "scalp_lost_to_hold": ((honest or {}).get("hold_counterfactual") or {}).get(
                "scalp_lost_to_hold"
            ),
            "disclaimer": (honest or {}).get("disclaimer"),
        },
        "tournament": {
            "best_arm": (tourney or {}).get("best_arm"),
            "policy_hash": (tourney or {}).get("policy_hash"),
            "arms": [
                {
                    "strategy_id": a.get("strategy_id"),
                    "ev_per_window": a.get("ev_per_window"),
                    "fee_net_pnl": a.get("fee_net_pnl"),
                    "n_entries": a.get("n_entries"),
                    "n_exits": a.get("n_exits"),
                    "zero_trade_rate": a.get("zero_trade_rate"),
                    "n_no_fills": a.get("n_no_fills"),
                }
                for a in arms
            ],
            "holdout_gate": (tourney or {}).get("holdout_gate"),
            "ranking_rule": (tourney or {}).get("ranking_rule"),
        },
        "usd_orders_from_lab": "NEVER",
    }
    try:
        (root / GLASS_JSON).write_text(
            json.dumps(glass, indent=2, sort_keys=True), encoding="utf-8"
        )
    except OSError:
        pass
    _write_glass_md(glass, root=root)
    return glass


def _write_glass_md(glass: dict[str, Any], *, root: Path) -> None:
    arms = (glass.get("tournament") or {}).get("arms") or []
    honest = glass.get("honest_accounting") or {}
    lines = [
        f"# Alice scalp lab glass · {glass.get('stamp')}",
        "",
        f"**Receipt:** `{RECEIPT_F}`",
        "",
        "## Doctrine",
        f"- {((glass.get('doctrine') or {}).get('owner_lesson') or '')}",
        "",
        "## Honest accounting",
        f"- selected green WR (BIASED): **{honest.get('selected_green_biased_wr')}**",
        f"- training RT n/pnl: **{honest.get('training_n')}** / "
        f"**${float(honest.get('training_pnl') or 0):+.4f}**",
        f"- scalp beat/lost hold: **{honest.get('scalp_beat_hold')}** / "
        f"**{honest.get('scalp_lost_to_hold')}**",
        "",
        "## Tournament (rank = fee-net EV/window, not WR)",
        f"- best arm: **{(glass.get('tournament') or {}).get('best_arm')}**",
        "",
    ]
    for a in arms:
        lines.append(
            f"- `{a.get('strategy_id')}` EV/win **{a.get('ev_per_window')}** · "
            f"pnl ${float(a.get('fee_net_pnl') or 0):+.4f} · "
            f"entries {a.get('n_entries')} exits {a.get('n_exits')} · "
            f"zero-trade {a.get('zero_trade_rate')}"
        )
    lines += [
        "",
        f"- training open: {len(glass.get('training_open') or [])}",
        f"- usd opens (read-only): {len(glass.get('usd_opens_readonly') or [])}",
        "",
        "Lab never places USD. Live cash-out is `alice_usd_take_profit` organ.",
        "",
    ]
    try:
        (root / GLASS_MD).write_text("\n".join(lines), encoding="utf-8")
    except OSError:
        pass


def _save_report(report: dict[str, Any], *, state_dir: Path) -> None:
    try:
        (state_dir / REPORT_JSON).write_text(
            json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
        )
        arms = report.get("arms") or []
        lines = [
            f"# Scalp lab tournament · {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            f"epoch `{report.get('epoch')}` · policy `{report.get('policy_hash')}`",
            f"rank: **{report.get('ranking_rule')}**",
            f"best: **{report.get('best_arm')}**",
            "",
        ]
        for a in arms:
            lines.append(
                f"- `{a.get('strategy_id')}` EV/w **{a.get('ev_per_window')}** "
                f"pnl ${float(a.get('fee_net_pnl') or 0):+.4f} "
                f"in {a.get('n_entries')} out {a.get('n_exits')}"
            )
        gate = report.get("holdout_gate") or {}
        lines += [
            "",
            f"## Holdout gate (`{RECEIPT_E}`)",
            f"- any_lab_promote: **{gate.get('any_lab_promote')}**",
            f"- usd_authorize: **{gate.get('usd_authorize')}** (always false here)",
            f"- {gate.get('note')}",
            "",
        ]
        (state_dir / REPORT_MD).write_text("\n".join(lines), encoding="utf-8")
    except OSError:
        pass


if __name__ == "__main__":
    print(json.dumps(tick_scalp_lab(), indent=2, default=str)[:3500])
