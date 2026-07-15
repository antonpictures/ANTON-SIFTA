#!/usr/bin/env python3
"""r20260714-dual-lag-harness — STGM↔US$ decision/submit/arrival instrumentation.

Joinable stream: candidate → sit/reject → submit → partial/fill → exit-reason.
Default is **shadow-safe**: works with kill switch on / dry_run / lane off.

Truth: ALICE_USD_DUAL_LAG_HARNESS_V1
Receipt: r20260714-dual-lag-harness
"""

from __future__ import annotations

import json
import statistics
import time
import uuid
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".sifta_state"
TRUTH = "ALICE_USD_DUAL_LAG_HARNESS_V1"
RECEIPT = "r20260714-dual-lag-harness"
STREAM = "alice_usd_dual_lag_stream.jsonl"
REPORT = "alice_usd_dual_lag_report.json"
SHADOW_N_DEFAULT = 20


def _state(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def _now_ms() -> int:
    return int(time.time() * 1000)


def _append(row: dict[str, Any], *, state_dir: Path) -> None:
    row = dict(row)
    row.setdefault("ts", time.time())
    row.setdefault("ts_ms", _now_ms())
    row.setdefault("truth_label", TRUTH)
    row.setdefault("receipt_id", RECEIPT)
    row.setdefault("usd_orders", "NEVER_FROM_HARNESS_ALONE")
    state_dir.mkdir(parents=True, exist_ok=True)
    try:
        with (state_dir / STREAM).open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError:
        pass


def stamp_decision(
    *,
    phase: str,
    bet: dict[str, Any],
    mark: Optional[dict[str, Any]] = None,
    secs_left: Optional[float] = None,
    dry_run: bool = True,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Stamp decision-time book (before submit)."""
    root = _state(state_dir)
    mid = None
    if mark:
        mid = mark.get("yes") or mark.get("kalshi_yes") or mark.get("yes_mid")
    row = {
        "event": "dual_lag_decision",
        "phase": phase,
        "decision_ts_ms": _now_ms(),
        "asset": bet.get("asset"),
        "ticker": bet.get("ticker"),
        "side": bet.get("side"),
        "entry": bet.get("entry_price") or bet.get("price") or bet.get("entry"),
        "book_at_decision": {
            "yes_mid": mid,
            "yes_bid": (mark or {}).get("yes_bid"),
            "yes_ask": (mark or {}).get("yes_ask"),
            "secs_left": secs_left,
        },
        "dry_run": bool(dry_run),
        "attempt_id": str(bet.get("attempt_id") or f"a-{uuid.uuid4().hex[:10]}"),
    }
    if not bet.get("attempt_id"):
        bet["attempt_id"] = row["attempt_id"]
    _append(row, state_dir=root)
    return row


def stamp_submit_result(
    *,
    phase: str,
    bet: dict[str, Any],
    result: dict[str, Any],
    decision_ts_ms: int,
    dry_run: bool = True,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Stamp submit/ack after place attempt; compute RTT from decision."""
    root = _state(state_dir)
    ack_ms = _now_ms()
    rtt = max(0, ack_ms - int(decision_ts_ms or ack_ms))
    fill_px = result.get("avg_fill_price") or result.get("fill_price") or result.get("price")
    row = {
        "event": "dual_lag_submit",
        "phase": phase,
        "decision_ts_ms": int(decision_ts_ms),
        "submit_ack_ts_ms": ack_ms,
        "rtt_ms": rtt,
        "asset": bet.get("asset"),
        "ticker": bet.get("ticker"),
        "side": bet.get("side"),
        "entry_intent": bet.get("entry_price") or bet.get("price"),
        "result_event": result.get("event"),
        "reason": result.get("reason"),
        "filled": bool(result.get("filled")),
        "fill_count": result.get("fill_count"),
        "fill_price": fill_px,
        "order_id": result.get("order_id"),
        "fee_paid_usd": result.get("fee_paid_usd"),
        "dry_run": bool(dry_run),
        "attempt_id": bet.get("attempt_id"),
        "kill_or_cap": str(result.get("reason") or "")
        in ("kill_switch", "cap_rejected", "not_provisioned"),
    }
    # fee model delta estimate vs paper
    try:
        from System.alice_15m_scalp_learner import estimate_taker_fee

        px = float(fill_px or bet.get("entry_price") or bet.get("price") or 0.5)
        cnt = float(result.get("fill_count") or 1.0)
        model = estimate_taker_fee(px, contracts=cnt)
        live = result.get("fee_paid_usd")
        if live is not None:
            row["fee_model_usd"] = model
            row["fee_live_usd"] = float(live)
            row["fee_delta_usd"] = round(float(live) - model, 4)
    except Exception:
        pass
    _append(row, state_dir=root)
    return row


def stamp_exit_attempt(
    *,
    open_row: dict[str, Any],
    mark: dict[str, Any],
    ev: dict[str, Any],
    secs_left: Optional[float],
    dry_run: bool = True,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    root = _state(state_dir)
    row = {
        "event": "dual_lag_exit_intent",
        "decision_ts_ms": _now_ms(),
        "asset": open_row.get("asset"),
        "ticker": open_row.get("ticker"),
        "side": open_row.get("side"),
        "entry": ev.get("entry"),
        "exit_side": ev.get("exit_side"),
        "net_usd": ev.get("net_usd"),
        "take_profit": ev.get("take_profit"),
        "salvage": ev.get("salvage"),
        "soft_adverse": ev.get("soft_adverse"),
        "force_flat_7m": ev.get("force_flat_7m"),
        "exit_why": ev.get("exit_why")
        or (
            "force_flat_7m"
            if ev.get("force_flat_7m")
            else (
                "salvage"
                if ev.get("salvage")
                else ("soft_adverse" if ev.get("soft_adverse") else "green_tp")
            )
        ),
        "book_at_decision": {
            "yes": mark.get("yes"),
            "yes_bid": mark.get("yes_bid"),
            "yes_ask": mark.get("yes_ask"),
            "secs_left": secs_left,
        },
        "dry_run": bool(dry_run),
    }
    _append(row, state_dir=root)
    return row


def load_stream(
    *, state_dir: Optional[Path | str] = None, limit: int = 5000
) -> list[dict[str, Any]]:
    root = _state(state_dir)
    p = root / STREAM
    if not p.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
        for ln in lines[-limit:]:
            try:
                rows.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    return rows


def run_dual_shadow_suite(
    *,
    state_dir: Optional[Path | str] = None,
    n: int = SHADOW_N_DEFAULT,
) -> dict[str, Any]:
    """Simulate n dual-shadow decision stamps from live marks (no USD place).

    Uses the **same** regime_gate as paper/US$ for side selection; records
    decision books only — kill switch / lane may stay OFF.
    """
    root = _state(state_dir)
    live_path = root / "kalshi_15m_live.json"
    if not live_path.exists():
        return {"ok": False, "reason": "no_live_marks", "n": 0}

    try:
        data = json.loads(live_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"ok": False, "reason": f"live_read:{exc}", "n": 0}

    markets = [m for m in (data.get("markets") or []) if isinstance(m, dict)]
    if not markets:
        return {"ok": False, "reason": "empty_markets", "n": 0}

    try:
        from System.alice_15m_scalp_strategies import (
            regime_gate,
            regime_preferred_side,
        )
        from System.alice_15m_co_direction import board_field

        field = board_field(state_dir=root)
    except Exception:
        field = {}
        regime_gate = None  # type: ignore
        regime_preferred_side = None  # type: ignore

    field_rg = {
        "anchor_side": field.get("anchor_side"),
        "majors_breadth": field.get("breadth") or field.get("majors_breadth"),
    }
    stamped = 0
    sits = 0
    for i in range(int(n)):
        m = markets[i % len(markets)]
        asset = str(m.get("asset") or "").upper()
        yes = float(m.get("kalshi_yes") or m.get("yes") or 0.5)
        side = str(field_rg.get("anchor_side") or ("yes" if yes >= 0.5 else "no"))
        entry = yes if side == "yes" else (1.0 - yes)
        if regime_gate is not None:
            rg = regime_gate(side=side, yes_mid=yes, field=field_rg)
            if rg:
                pref = (
                    regime_preferred_side(yes, field=field_rg)
                    if regime_preferred_side
                    else None
                )
                if pref and pref != side:
                    side = pref
                    entry = yes if side == "yes" else (1.0 - yes)
                else:
                    sits += 1
                    _append(
                        {
                            "event": "dual_lag_shadow_sit",
                            "reason": rg,
                            "asset": asset,
                            "yes_mid": yes,
                            "shadow_i": i,
                        },
                        state_dir=root,
                    )
                    continue
        bet = {
            "asset": asset,
            "ticker": m.get("kalshi_ticker") or m.get("ticker"),
            "side": side,
            "entry_price": entry,
            "price": entry,
            "attempt_id": f"shadow-{i}-{uuid.uuid4().hex[:6]}",
        }
        mark = {
            "yes": yes,
            "yes_bid": m.get("yes_bid"),
            "yes_ask": m.get("yes_ask"),
            "secs": m.get("seconds_to_close"),
        }
        stamp_decision(
            phase="dual_shadow",
            bet=bet,
            mark=mark,
            secs_left=m.get("seconds_to_close"),
            dry_run=True,
            state_dir=root,
        )
        # shadow "submit" is a no-op with synthetic RTT 0 (no API)
        stamp_submit_result(
            phase="dual_shadow_noop",
            bet=bet,
            result={
                "event": "shadow_no_submit",
                "reason": "dual_shadow_only",
                "filled": False,
            },
            decision_ts_ms=_now_ms(),
            dry_run=True,
            state_dir=root,
        )
        stamped += 1

    report = summarize_stream(state_dir=root)
    report["shadow_suite"] = {
        "n_requested": int(n),
        "n_stamped": stamped,
        "n_sits": sits,
        "note": "shadow only — no US$ orders transmitted",
    }
    report["ok"] = True
    try:
        (root / REPORT).write_text(
            json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
        )
    except OSError:
        pass
    return report


def summarize_stream(
    *, state_dir: Optional[Path | str] = None, limit: int = 5000
) -> dict[str, Any]:
    rows = load_stream(state_dir=state_dir, limit=limit)
    rtts = [
        float(r["rtt_ms"])
        for r in rows
        if r.get("event") == "dual_lag_submit" and r.get("rtt_ms") is not None
    ]
    fee_deltas = [
        float(r["fee_delta_usd"])
        for r in rows
        if r.get("fee_delta_usd") is not None
    ]
    decisions = [r for r in rows if r.get("event") == "dual_lag_decision"]
    submits = [r for r in rows if r.get("event") == "dual_lag_submit"]
    exits = [r for r in rows if r.get("event") == "dual_lag_exit_intent"]
    sits = [r for r in rows if r.get("event") == "dual_lag_shadow_sit"]
    filled = [r for r in submits if r.get("filled")]

    def _pct(xs: list[float], p: float) -> Optional[float]:
        if not xs:
            return None
        xs = sorted(xs)
        i = min(len(xs) - 1, max(0, int(p * (len(xs) - 1))))
        return round(xs[i], 2)

    return {
        "truth_label": TRUTH,
        "receipt_id": RECEIPT,
        "n_rows": len(rows),
        "n_decisions": len(decisions),
        "n_submits": len(submits),
        "n_exits": len(exits),
        "n_sits": len(sits),
        "n_filled": len(filled),
        "rtt_ms": {
            "n": len(rtts),
            "p50": _pct(rtts, 0.50),
            "p95": _pct(rtts, 0.95),
            "mean": round(statistics.mean(rtts), 2) if rtts else None,
        },
        "fee_delta_usd": {
            "n": len(fee_deltas),
            "mean": round(statistics.mean(fee_deltas), 4) if fee_deltas else None,
            "abs_max": round(max(abs(x) for x in fee_deltas), 4) if fee_deltas else None,
        },
        "targets_f29": {
            "fee_net_sum_gt_0": "measure after live fills",
            "max_dd_le_2_50": "measure after live fills",
            "fill_gap_median_le_3c": "needs filled dual pairs",
            "note": "shadow suite stamps decision/submit only until lane ON",
        },
        "usd_orders_from_harness": "NEVER",
        "ts": time.time(),
    }


__all__ = [
    "TRUTH",
    "RECEIPT",
    "STREAM",
    "REPORT",
    "stamp_decision",
    "stamp_submit_result",
    "stamp_exit_attempt",
    "load_stream",
    "run_dual_shadow_suite",
    "summarize_stream",
]
