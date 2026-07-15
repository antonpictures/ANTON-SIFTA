#!/usr/bin/env python3
"""Alice 15m SCALP learner — fee-true cash-out (STGM/paper + shadow training).

Owner ask 2026-07-13: stop bag-holding; scalp when mark covers
**entry fee + exit fee + min edge** (same math as US$ take-profit).

r1706 owner: **exact same scalp strategy as US$** on live STGM paper book:
  • band 40–65¢ · hunt until 7:30 left · force flat ≤7:30 left
  • fee-true TP executes paper close (learns by doing)
  • fees = estimate_taker_fee (Kalshi-style) — shared with alice_usd_take_profit

Shadow Alice (training book): extra virtual scalps only — never real USD.
Same fee formula, same band, same force-flat clock.

Truth: ALICE_15M_SCALP_LEARNER_V1
"""

from __future__ import annotations

import json
import math
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".sifta_state"

TRUTH = "ALICE_15M_SCALP_LEARNER_V1"
LOG_NAME = "alice_15m_scalp.jsonl"
PROOF_NAME = "alice_15m_scalp_proof.json"
CF_NAME = "alice_15m_scalp_counterfactual.json"  # ticker → scalp row awaiting resolve
MD_NAME = "alice_15m_scalp.md"

# Gates — r1706: match US$ take-profit / hunt clock (exact copy for learning)
# Keep numeric twins of paper_loop (avoid circular import at module load).
MIN_EDGE_USD = 0.02  # alice_usd_take_profit.MIN_EDGE_USD
EARLY_BURST_MIN_EDGE_USD = 0.01
MIN_HOLD_SECS = 25.0
SCALP_MIN_ENTRY = 0.20  # r1710 STGM burst (paper/train); US$ stays separate
SCALP_MAX_ENTRY = 0.80
SCALP_ENTRY_SECS_MAX = 15 * 60
SCALP_ENTRY_SECS_MIN = 7 * 60 + 30.0  # = DEFAULT_MIN_SECS / FORCE_FLAT_SECS
FORCE_FLAT_SECS = 7 * 60 + 30.0
MIN_SECS_LEFT = 45.0
MAX_SECS_LEFT = float(SCALP_ENTRY_SECS_MAX)
MAX_ENTRY_AGE_FOR_SCALP_S = 14 * 60.0
SCALP_MIN_VOLUME_USD = 500.0
# Shadow Alice: extra virtual scalps (training only — never USD)
TRAINING_BOOK = "alice_15m_scalp_training_book.json"
TRAINING_SCALPS_PER_WINDOW = 9  # r1710: denser shadow train alongside paper burst
TRAINING_CONTRACTS = 2.0  # match AMMO $2 = 2 contracts for fee scaling
TRAINING_MAJORS = ("BTC", "ETH", "SOL", "XRP", "BNB", "DOGE")
TRAINING_OPEN_SECS_MAX = 15 * 60
TRAINING_OPEN_SECS_MIN = SCALP_ENTRY_SECS_MIN


def _state(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def clamp_price(price: float) -> float:
    try:
        p = float(price)
    except (TypeError, ValueError):
        p = 0.5
    if not math.isfinite(p):
        p = 0.5
    return min(0.99, max(0.01, p))


def estimate_taker_fee(price: float, *, contracts: float = 1.0) -> float:
    """Kalshi-style variable taker fee ≈ 0.07 · C · p · (1−p).

    Checked against live fills (0.74→1.35¢, 0.87→0.8¢, 0.66→1.58¢).
    """
    p = clamp_price(price)
    c = max(0.01, float(contracts))
    raw = 0.07 * c * p * (1.0 - p)
    # July 2026 schedule: round UP so fee + position cost lands on a centicent.
    return round(max(0.0001, math.ceil(raw * 10_000.0 - 1e-12) / 10_000.0), 4)


def side_exit_price(
    side: str,
    yes_mid: float,
    *,
    yes_bid: Optional[float] = None,
    yes_ask: Optional[float] = None,
    haircut: float = 0.01,
) -> float:
    """Conservative exit: hit the bid of the side we hold."""
    side_l = "yes" if str(side).lower() in ("yes", "up") else "no"
    ym = clamp_price(yes_mid)
    if side_l == "yes":
        if yes_bid is not None and float(yes_bid) > 0:
            return clamp_price(float(yes_bid))
        return clamp_price(ym - haircut)
    # long NO → sell NO ≈ buy YES at ask → no_bid = 1 - yes_ask
    if yes_ask is not None and float(yes_ask) > 0:
        return clamp_price(1.0 - float(yes_ask))
    return clamp_price((1.0 - ym) - haircut)


def evaluate_scalp(
    *,
    side: str,
    entry_price: float,
    yes_mid: float,
    contracts: float = 1.0,
    yes_bid: Optional[float] = None,
    yes_ask: Optional[float] = None,
    min_edge: float = MIN_EDGE_USD,
) -> dict[str, Any]:
    """Return fee-true mark-to-market and scalp_ok flag."""
    side_l = "yes" if str(side).lower() in ("yes", "up") else "no"
    entry = clamp_price(entry_price)
    # mark on our side
    if side_l == "yes":
        mark_mid = clamp_price(yes_mid)
    else:
        mark_mid = clamp_price(1.0 - float(yes_mid))
    exit_px = side_exit_price(
        side_l, yes_mid, yes_bid=yes_bid, yes_ask=yes_ask
    )
    c = max(0.01, float(contracts))
    fee_in = estimate_taker_fee(entry, contracts=c)
    fee_out = estimate_taker_fee(exit_px, contracts=c)
    gross = round((exit_px - entry) * c, 4)
    net = round(gross - fee_in - fee_out, 4)
    # mid mark without spread haircut (optimistic glass)
    gross_mid = round((mark_mid - entry) * c, 4)
    net_mid = round(gross_mid - fee_in - estimate_taker_fee(mark_mid, contracts=c), 4)
    be_move = round((fee_in + fee_out) / c + float(min_edge) / c, 4)
    return {
        "side": side_l,
        "entry": entry,
        "mark_mid": mark_mid,
        "exit_px": exit_px,
        "contracts": c,
        "fee_in": fee_in,
        "fee_out": fee_out,
        "fees_total": round(fee_in + fee_out, 4),
        "gross_usd": gross,
        "net_usd": net,
        "net_mid_usd": net_mid,
        "break_even_move": be_move,
        "min_edge": float(min_edge),
        "scalp_ok": net >= float(min_edge) - 1e-9,
        "truth_label": TRUTH,
    }


def _load_live_marks(state_dir: Path) -> dict[str, dict[str, Any]]:
    """ticker → {yes, yes_bid, yes_ask, secs, asset, target}."""
    out: dict[str, dict[str, Any]] = {}
    live_path = state_dir / "kalshi_15m_live.json"
    try:
        if live_path.exists():
            data = json.loads(live_path.read_text(encoding="utf-8"))
            now = time.time()
            for row in data.get("markets") or []:
                if not isinstance(row, dict):
                    continue
                t = str(row.get("kalshi_ticker") or row.get("ticker") or "").strip()
                if not t:
                    continue
                yes = row.get("kalshi_yes")
                if yes is None:
                    yes = row.get("yes_price")
                if yes is None:
                    continue
                secs = row.get("seconds_to_close")
                if secs is None and row.get("close_ts"):
                    try:
                        secs = max(0, int(float(row["close_ts"]) - now))
                    except Exception:
                        secs = None
                vol = row.get("kalshi_volume_24h")
                if vol is None:
                    vol = row.get("volume_24h") or row.get("volume") or 0
                try:
                    vol_f = float(vol)
                except (TypeError, ValueError):
                    vol_f = 0.0
                out[t] = {
                    "yes": float(yes),
                    "yes_bid": row.get("yes_bid"),
                    "yes_ask": row.get("yes_ask"),
                    "secs": secs,
                    "asset": row.get("asset"),
                    "target_price": row.get("target_price"),
                    "volume": vol_f,
                }
    except Exception:
        pass
    return out


def _contracts_from_ticket(b: dict[str, Any]) -> float:
    stake = float(b.get("stake") or 1.0)
    # thin STGM half-ticket ≈ 0.5 contracts
    stgm = 0.0
    try:
        stgm = float(b.get("stgm_stake") or 0.0)
        if stgm <= 0 and b.get("body_stgm"):
            stgm = float((b.get("body_stgm") or {}).get("stake") or 0.0)
    except Exception:
        stgm = 0.0
    if stgm > 0:
        # 0.001 STGM ≡ $1 ≡ 1 contract face unit
        return max(0.25, round(stgm / 0.001, 4))
    return max(0.25, min(3.0, stake))


def _append_log(row: dict[str, Any], *, state_dir: Path) -> None:
    path = state_dir / LOG_NAME
    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError:
        pass


def load_proof(state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    p = _state(state_dir) / PROOF_NAME
    if not p.exists():
        return {
            "truth_label": TRUTH,
            "n_scalps": 0,
            "n_hold": 0,
            "n_wins": 0,
            "n_losses": 0,
            "pnl_usd": 0.0,
            "fees_paid_usd": 0.0,
            "hold_cf_pnl_usd": 0.0,
            "scalp_beat_hold": 0,
            "scalp_lost_to_hold": 0,
        }
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"truth_label": TRUTH}


def save_proof(proof: dict[str, Any], *, state_dir: Optional[Path | str] = None) -> None:
    root = _state(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    proof = dict(proof)
    proof["ts"] = time.time()
    proof["truth_label"] = TRUTH
    n = int(proof.get("n_scalps") or 0)
    if n > 0:
        proof["ev_per_scalp"] = round(float(proof.get("pnl_usd") or 0) / n, 4)
        proof["win_rate"] = round(int(proof.get("n_wins") or 0) / n, 4)
    (root / PROOF_NAME).write_text(json.dumps(proof, indent=2, sort_keys=True), encoding="utf-8")
    _write_md(proof, state_dir=root)


def _write_md(proof: dict[str, Any], *, state_dir: Path) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    n = int(proof.get("n_scalps") or 0)
    lines = [
        f"# Alice SCALP learner · {stamp}",
        "",
        f"- scalps **{n}** · {proof.get('n_wins', 0)}W/{proof.get('n_losses', 0)}L",
        f"- net PnL **${float(proof.get('pnl_usd') or 0):+.4f}** · fees ${float(proof.get('fees_paid_usd') or 0):.4f}",
        f"- EV/scalp **{proof.get('ev_per_scalp', 'n/a')}** · WR {float(proof.get('win_rate') or 0):.0%}",
        f"- hold-CF sum ${float(proof.get('hold_cf_pnl_usd') or 0):+.4f} · "
        f"beat hold {proof.get('scalp_beat_hold', 0)} · lost to hold {proof.get('scalp_lost_to_hold', 0)}",
        "",
        "Rule: cash out (virtual) when `exit − entry − fee_in − fee_out ≥ $0.03`.",
        "USD orders OFF — paper/STGM learning only.",
        "",
        "> ⚠️ r1684: green-only exit WR is **selection-biased** (exits fire after a "
        "fee-true green quote). See `alice_15m_scalp_proof_honest.md` for unbiased "
        "training round-trips + opportunity counts. Do not promote on this headline WR.",
        "",
    ]
    (state_dir / MD_NAME).write_text("\n".join(lines), encoding="utf-8")


def _load_cf(state_dir: Path) -> dict[str, Any]:
    p = state_dir / CF_NAME
    if not p.exists():
        return {}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save_cf(cf: dict[str, Any], *, state_dir: Path) -> None:
    try:
        (state_dir / CF_NAME).write_text(
            json.dumps(cf, indent=2, sort_keys=True), encoding="utf-8"
        )
    except OSError:
        pass


def tick_scalps(
    *,
    state_dir: Optional[Path | str] = None,
    engine: Any = None,
    min_edge: float = MIN_EDGE_USD,
    force: bool = False,
    any_profit: bool = False,
) -> dict[str, Any]:
    """Scan open paper book; virtual cash-out fee-true winners. No real USD.

    force=True: ignore hold-time / secs-left gates (owner: SCALP NOW).
    any_profit=True: min_edge = 0 (owner: any profit counts).
    Never locks a fee-true loss unless future flag says so.
    """
    from System.swarm_sifta_paper_loop import load_open_book, save_open_book

    root = _state(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    book = load_open_book(root)
    opens = list(book.get("open") or [])
    if not opens:
        proof = load_proof(root)
        save_proof(proof, state_dir=root)  # refresh md for monitor
        return {
            "ok": True,
            "event": "scalp_tick",
            "n_open": 0,
            "n_watched": 0,
            "n_scalped": 0,
            "proof": {
                "n_scalps": proof.get("n_scalps"),
                "pnl_usd": proof.get("pnl_usd"),
                "ev_per_scalp": proof.get("ev_per_scalp"),
            },
            "truth_label": TRUTH,
            "usd": "HALTED_LEARN_ONLY",
        }

    marks = _load_live_marks(root)
    # fill from engine if missing
    if engine is not None:
        try:
            for m in engine.markets.values():
                t = str(getattr(m, "kalshi_ticker", "") or "")
                if not t or t in marks:
                    continue
                ky = getattr(m, "kalshi_yes", None)
                if ky is None:
                    try:
                        ky = m.yes_price()
                    except Exception:
                        continue
                marks[t] = {
                    "yes": float(ky),
                    "yes_bid": getattr(m, "yes_bid", None),
                    "yes_ask": getattr(m, "yes_ask", None),
                    "secs": None,
                    "asset": getattr(m, "asset", None),
                    "target_price": getattr(m, "target_price", None),
                }
                try:
                    row = m.to_row()
                    marks[t]["secs"] = row.get("seconds_to_close")
                    if row.get("yes_bid"):
                        marks[t]["yes_bid"] = row.get("yes_bid")
                    if row.get("yes_ask"):
                        marks[t]["yes_ask"] = row.get("yes_ask")
                except Exception:
                    pass
        except Exception:
            pass

    now = time.time()
    still: list[dict[str, Any]] = []
    scalped: list[dict[str, Any]] = []
    watched: list[dict[str, Any]] = []
    proof = load_proof(root)
    cf = _load_cf(root)

    for b in opens:
        kt = str(b.get("ticker") or "").strip()
        if not kt:
            still.append(b)
            continue
        mk = marks.get(kt)
        if not mk:
            still.append(b)
            continue
        side = str(b.get("side") or ("yes" if str(b.get("label")).upper() == "UP" else "no"))
        entry = float(b.get("price") or 0.5)
        contracts = _contracts_from_ticket(b)
        entry_ts = float(b.get("ts") or 0.0)
        age = now - entry_ts if entry_ts > 0 else 999.0
        secs = mk.get("secs")
        try:
            secs_f = float(secs) if secs is not None else None
        except (TypeError, ValueError):
            secs_f = None

        # r1706: same edge schedule as US$ take_profit (early 1¢ · base 2¢ · flat 0)
        danger_flat = bool(
            force
            or (
                secs_f is not None
                and secs_f <= float(FORCE_FLAT_SECS) + 1e-9
            )
        )
        if danger_flat or any_profit:
            edge = 0.0
        elif secs_f is not None and secs_f >= float(FORCE_FLAT_SECS) - 1e-9:
            edge = min(float(min_edge), float(EARLY_BURST_MIN_EDGE_USD))
        else:
            edge = float(min_edge)
        ev = evaluate_scalp(
            side=side,
            entry_price=entry,
            yes_mid=float(mk["yes"]),
            contracts=contracts,
            yes_bid=float(mk["yes_bid"]) if mk.get("yes_bid") not in (None, "") else None,
            yes_ask=float(mk["yes_ask"]) if mk.get("yes_ask") not in (None, "") else None,
            min_edge=edge,
        )
        # force-flat zone: always attempt cash-out (even small red) — same as US$
        if danger_flat or any_profit:
            ev = dict(ev)
            ev["scalp_ok"] = True
            ev["force_flat"] = bool(danger_flat)
            ev["min_edge"] = edge
        # r1712: salvage residual when held side is dead vs live field
        salvage = False
        salvage_imp = None
        try:
            from System.alice_15m_scalp_strategies import (
                SALVAGE_COHORT,
                SALVAGE_EXIT_REASON,
                salvage_exit_should_fire,
                side_implied_prob,
            )

            salvage = salvage_exit_should_fire(
                side=side,
                yes_mid=float(mk["yes"]),
                secs_left=secs_f,
            )
            if salvage:
                salvage_imp = side_implied_prob(side, float(mk["yes"]))
                ev = dict(ev)
                ev["scalp_ok"] = True  # allow execute path (may be red)
                ev["salvage"] = True
                ev["salvage_side_implied"] = salvage_imp
        except Exception:
            salvage = False
        watch = {
            "ticker": kt,
            "asset": b.get("asset") or mk.get("asset"),
            "label": b.get("label"),
            "age_s": round(age, 1),
            "secs_left": secs_f,
            "force": bool(force),
            "danger_flat": danger_flat,
            "salvage": salvage,
            **{k: ev[k] for k in ("entry", "exit_px", "fee_in", "fee_out", "net_usd", "scalp_ok")},
        }
        watched.append(watch)

        # r1706: EXECUTE paper/STGM on fee-true green or force-flat (learn by scalping)
        # r1712: also salvage dead side vs field (cut residual, don't ride to zero)
        execute = bool(
            danger_flat or any_profit or force or ev.get("scalp_ok") or salvage
        )

        if not execute and kt in cf:
            watch["virtual_exit_recorded"] = True
            still.append(b)
            continue

        # gates — bank fee-true green after min hold; force-flat / salvage ignore hold
        if not danger_flat and not force and not salvage:
            if age < MIN_HOLD_SECS:
                still.append(b)
                continue
            if age > MAX_ENTRY_AGE_FOR_SCALP_S + 60.0:
                still.append(b)
                continue
        vol = float(mk.get("volume") or 0.0)
        vol_floor = 100.0 if (danger_flat or force or salvage) else SCALP_MIN_VOLUME_USD
        if vol < vol_floor:
            watch["skip"] = "dust_volume"
            watch["volume"] = vol
            still.append(b)
            continue
        if not ev["scalp_ok"] and not danger_flat and not salvage:
            watch["skip"] = "not_green_fee_true"
            still.append(b)
            continue
        watch["volume"] = vol

        net = float(ev["net_usd"])
        win = net >= 0.0
        unit_pnl = round(net / max(0.25, contracts), 4) if contracts else net
        label = str(b.get("label") or ("UP" if side == "yes" else "DOWN"))
        strategy = str(b.get("strategy") or "follow_crowd")
        if salvage:
            why_reason = "salvage_exit_red_field"
        elif danger_flat:
            why_reason = "force_flat_7m30"
        elif win:
            why_reason = "fee_true_green"
        else:
            why_reason = "scalp_exit"
        row = {
            "event": "scalp_exit",
            "mode": "scalp_execute" if execute else "scalp_shadow",
            "asset": b.get("asset"),
            "ticker": kt,
            "side": side,
            "label": label,
            "price": entry,
            "exit_price": ev["exit_px"],
            "mark_mid": ev["mark_mid"],
            "win": win,
            "pnl": unit_pnl,
            "pnl_usd_fee_true": net,
            "fee_in": ev["fee_in"],
            "fee_out": ev["fee_out"],
            "fees_total": ev["fees_total"],
            "contracts": contracts,
            "stake": b.get("stake"),
            "strategy": strategy,
            "explored": bool(b.get("explored")),
            "decision_evidence": b.get("decision_evidence") or {},
            "entry_ts": entry_ts,
            "secs_left_at_entry": b.get("secs_left_at_entry") or b.get("secs"),
            "entry_clock": b.get("entry_clock") or "",
            "secs_left_at_exit": secs_f,
            "age_s": round(age, 1),
            "force_flat": bool(ev.get("force_flat") or danger_flat),
            "salvage": bool(salvage),
            "salvage_side_implied": salvage_imp,
            "why": why_reason,
            "cohort": "salvage_exit_red_field" if salvage else "selected_green_or_flat",
            "result": "scalp_execute" if execute else "virtual_scalp",
            "ts": now,
            "truth_label": TRUTH,
            "fee_model": "kalshi_taker_0.07_p_1minus_p",
            "note": (
                "SALVAGE cut dead side vs field · residual banked · not ride-to-zero"
                if salvage
                else (
                    "EXECUTED STGM paper cash-out · fee-true same as US$ · no real $"
                    if execute
                    else "SHADOW virtual cash-out · training only"
                )
            ),
        }

        # scalp proof
        proof["n_scalps"] = int(proof.get("n_scalps") or 0) + 1
        if win:
            proof["n_wins"] = int(proof.get("n_wins") or 0) + 1
        else:
            proof["n_losses"] = int(proof.get("n_losses") or 0) + 1
        proof["pnl_usd"] = round(float(proof.get("pnl_usd") or 0.0) + net, 4)
        proof["fees_paid_usd"] = round(
            float(proof.get("fees_paid_usd") or 0.0) + float(ev["fees_total"]), 4
        )

        cf[kt] = {
            "scalp_net_usd": net,
            "entry": entry,
            "side": side,
            "contracts": contracts,
            "asset": b.get("asset"),
            "label": label,
            "executed": execute,
            "ts": now,
        }

        scalped.append(row)
        _append_log(row, state_dir=root)

        if not execute:
            still.append(b)
            continue

        # ── EXECUTE: close paper/STGM ticket now ──────────────────────
        try:
            from System.swarm_sifta_paper_loop import (
                SETTLED_LOG,
                load_proof as load_paper_proof,
                load_settled_tickers,
                save_proof as save_paper_proof,
                save_settled_tickers,
            )
            from System.swarm_sifta_paper_loop import _learner

            paper = load_paper_proof(root)
            paper["n_settled"] = int(paper.get("n_settled") or 0) + 1
            if win:
                paper["n_wins"] = int(paper.get("n_wins") or 0) + 1
            else:
                paper["n_losses"] = int(paper.get("n_losses") or 0) + 1
            paper["pnl"] = round(float(paper.get("pnl") or 0.0) + unit_pnl, 4)
            hist = list(paper.get("history") or [])
            hist.append(
                {
                    "asset": row.get("asset"),
                    "ticker": kt,
                    "win": win,
                    "pnl": unit_pnl,
                    "price": entry,
                    "mode": "scalp_execute",
                    "pnl_usd_fee_true": net,
                    "ts": now,
                }
            )
            paper["history"] = hist[-40:]
            paper["last_event"] = (
                f"SCALP {row.get('asset')} {label} net ${net:+.3f} (fee-true)"
            )
            save_paper_proof(paper, state_dir=root)
            # r1710: log scalp close but ALLOW re-entry same clock (18/round STGM)
            # Do not permanently mark ticker settled — that blocked multi-scalp.
            try:
                from System.swarm_sifta_paper_loop import (
                    record_stgm_scalp,
                    release_settled_ticker_for_restake,
                )

                release_settled_ticker_for_restake(kt, state_dir=root)
                record_stgm_scalp(
                    ticker=kt,
                    asset=str(row.get("asset") or ""),
                    state_dir=root,
                )
            except Exception:
                pass
            try:
                with (root / SETTLED_LOG).open("a", encoding="utf-8") as f:
                    f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            except Exception:
                pass
            if _learner is not None:
                try:
                    _learner.learn(
                        str(b.get("asset") or "?"),
                        strategy,
                        win,
                        unit_pnl,
                        explored=bool(b.get("explored")),
                        ticker=kt,
                        state_dir=root,
                    )
                except Exception:
                    pass
        except Exception as exc:
            row["paper_settle_error"] = f"{type(exc).__name__}:{exc}"
            _append_log(
                {"event": "scalp_execute_paper_fault", "ticker": kt, "err": row["paper_settle_error"]},
                state_dir=root,
            )

        try:
            stgm_stake = float(b.get("stgm_stake") or 0.0)
            if stgm_stake <= 0 and b.get("body_stgm"):
                stgm_stake = float((b.get("body_stgm") or {}).get("stake") or 0.0)
            if stgm_stake > 0:
                from System.alice_15m_body_stgm import settle_body_stgm

                row["body_stgm_settle"] = settle_body_stgm(
                    ticker=kt,
                    asset=str(b.get("asset") or ""),
                    label=label,
                    price=entry,
                    win=bool(win),
                    stake=stgm_stake,
                    state_dir=root,
                )
        except Exception as exc:
            row["body_stgm_settle"] = {"ok": False, "reason": f"{type(exc).__name__}:{exc}"}
        # r1710: clear engine stake so same ticker can re-arm after scalp
        if engine is not None:
            try:
                for _m in getattr(engine, "markets", {}).values():
                    if str(getattr(_m, "kalshi_ticker", "") or "") != kt:
                        continue
                    pos = (_m.positions or {}).pop("owner", None)
                    if pos is None:
                        (_m.positions or {}).clear()
                    break
            except Exception:
                pass
        # executed → do NOT re-append to still

    book["open"] = still
    book["n_open"] = len(still)
    book["last_scalp_tick"] = now
    save_open_book(book, state_dir=root)
    save_proof(proof, state_dir=root)
    _save_cf(cf, state_dir=root)

    out = {
        "ok": True,
        "event": "scalp_tick",
        "ts": now,
        "n_open": len(still),
        "n_watched": len(watched),
        "n_scalped": len(scalped),
        "scalped": scalped,
        "watched": watched[:12],
        "proof": {
            "n_scalps": proof.get("n_scalps"),
            "pnl_usd": proof.get("pnl_usd"),
            "ev_per_scalp": proof.get("ev_per_scalp"),
            "win_rate": proof.get("win_rate"),
        },
        "truth_label": TRUTH,
        "usd": "HALTED_LEARN_ONLY",
    }
    _append_log({"event": "scalp_tick_summary", **{k: out[k] for k in out if k != "scalped"}}, state_dir=root)
    return out


def _load_training_book(state_dir: Path) -> dict[str, Any]:
    p = state_dir / TRAINING_BOOK
    if not p.exists():
        return {"truth_label": TRUTH, "open": [], "windows": {}}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(d, dict):
            d.setdefault("open", [])
            d.setdefault("windows", {})
            return d
    except Exception:
        pass
    return {"truth_label": TRUTH, "open": [], "windows": {}}


def _save_training_book(book: dict[str, Any], *, state_dir: Path) -> None:
    book = dict(book)
    book["ts"] = time.time()
    book["truth_label"] = TRUTH
    book["n_open"] = len(book.get("open") or [])
    book["note"] = (
        "Shadow Alice training scalps · same fee model + band + 7:30 flat as US$/STGM · never real USD"
    )
    p = state_dir / TRAINING_BOOK
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(book, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(p)


def _window_id_from_live(marks: dict[str, dict[str, Any]]) -> str:
    for t, mk in marks.items():
        parts = str(t).split("-")
        if len(parts) >= 2:
            return parts[1]
    return datetime.now().strftime("%Y%m%d%H%M")


def open_training_scalps_for_window(
    *,
    state_dir: Optional[Path | str] = None,
    n: int = TRAINING_SCALPS_PER_WINDOW,
) -> dict[str, Any]:
    """Open up to N virtual STGM training tickets on liquid co-dir majors.

    Simulates a Kalshi taker buy at mid: cost_basis = price + fee_in.
    Never places USD. Idempotent per window_id.
    """
    root = _state(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    marks = _load_live_marks(root)
    if not marks:
        return {"ok": False, "reason": "no_marks", "opened": 0}

    book = _load_training_book(root)
    wid = _window_id_from_live(marks)
    windows = dict(book.get("windows") or {})
    if windows.get(wid, {}).get("opened"):
        return {
            "ok": True,
            "opened": 0,
            "reason": "window_already_armed",
            "window_id": wid,
            "n_open": len(book.get("open") or []),
        }

    # co-dir preference
    try:
        from System.alice_15m_co_direction import board_field

        field = board_field(state_dir=root)
        anchor = str(field.get("anchor_side") or "yes")
        ranked = [
            str(r.get("asset") or "").upper()
            for r in (field.get("ranked") or [])
            if not r.get("contrarian")
        ]
    except Exception:
        anchor = "yes"
        ranked = list(TRAINING_MAJORS)

    def _skip_asset(a: str) -> bool:
        a_u = str(a or "").upper()
        try:
            from System.alice_15m_co_direction import is_weird_15m_asset

            if is_weird_15m_asset(a_u):
                return True
        except Exception:
            if a_u in ("HYPE", "ZEC", "NEAR"):
                return True
        try:
            from System.alice_fee_net_tournament import asset_trade_class

            return asset_trade_class(a_u) in ("weird", "banned")
        except Exception:
            return False

    # map asset → best mark row
    by_asset: dict[str, tuple[str, dict[str, Any]]] = {}
    for t, mk in marks.items():
        a = str(mk.get("asset") or "").upper()
        if not a:
            # ticker parse KXBTC15M-...
            for maj in TRAINING_MAJORS:
                if maj in t.upper():
                    a = maj
                    break
        if not a or a not in TRAINING_MAJORS:
            continue
        if _skip_asset(a):
            continue
        secs = mk.get("secs")
        try:
            secs_i = int(secs) if secs is not None else None
        except (TypeError, ValueError):
            secs_i = None
        if secs_i is None:
            continue
        # r1685/r1690: open from minute-14 / full strip; prefer early mid-price
        if secs_i < int(SCALP_ENTRY_SECS_MIN) or secs_i > int(SCALP_ENTRY_SECS_MAX):
            continue
        vol = float(mk.get("volume") or 0.0)
        if vol < SCALP_MIN_VOLUME_USD * 0.4:  # slightly softer for training
            continue
        yes = float(mk["yes"])
        # side = co-dir anchor when clear, else mid favorite
        side = anchor if anchor in ("yes", "no") else ("yes" if yes >= 0.5 else "no")
        # P0.7: taker entry at executable ask — never mid
        # ask_yes = yes_ask; ask_no = 1 - yes_bid
        yes_bid = mk.get("yes_bid")
        yes_ask = mk.get("yes_ask")
        try:
            yb = float(yes_bid) if yes_bid not in (None, "") else None
        except (TypeError, ValueError):
            yb = None
        try:
            ya = float(yes_ask) if yes_ask not in (None, "") else None
        except (TypeError, ValueError):
            ya = None
        if side == "yes":
            if ya is None or ya <= 0:
                continue  # no_entry_quote
            entry = clamp_price(ya)
        else:
            if yb is None or yb <= 0:
                continue  # no_entry_quote — need yes_bid to form no ask
            entry = clamp_price(1.0 - yb)
        # r1689: buy low sell high — skip expensive side premiums
        if entry < SCALP_MIN_ENTRY or entry > SCALP_MAX_ENTRY:
            continue
        early_sweet = 12 * 60 <= secs_i <= 15 * 60
        # prefer early cheaper + liquid (executable ask, not mid)
        score = (
            (3.0 if early_sweet else 0.0)
            + (SCALP_MAX_ENTRY - entry) * 3.0  # cheaper = better
            + min(1.0, vol / 50_000.0)
            + abs(yes - 0.5) * 0.5
        )
        prev = by_asset.get(a)
        if prev is None or score > float(prev[1].get("_score") or 0):
            mk2 = dict(mk)
            mk2["_score"] = score
            mk2["_side"] = side
            mk2["_entry"] = entry
            mk2["_entry_quote"] = "ask"
            by_asset[a] = (t, mk2)

    # order by co-dir rank then score
    order = [a for a in ranked if a in by_asset]
    for a in sorted(by_asset.keys(), key=lambda x: -float(by_asset[x][1].get("_score") or 0)):
        if a not in order:
            order.append(a)

    opened: list[dict[str, Any]] = []
    open_rows = list(book.get("open") or [])
    have_assets = {str(r.get("asset") or "").upper() for r in open_rows}
    now = time.time()
    for a in order:
        if len(opened) >= int(n):
            break
        if a in have_assets:
            continue
        t, mk = by_asset[a]
        side = str(mk["_side"])
        entry = float(mk["_entry"])
        fee_in = estimate_taker_fee(entry, contracts=TRAINING_CONTRACTS)
        # exact Kalshi-style cash outlay for 1 contract buy
        cash_cost = round(entry * TRAINING_CONTRACTS + fee_in, 4)
        row = {
            "id": f"stgm-train-{wid}-{a}-{int(now)}",
            "window_id": wid,
            "asset": a,
            "ticker": t,
            "side": side,
            "label": "UP" if side == "yes" else "DOWN",
            "entry": entry,
            "entry_quote": "ask",
            "yes_bid_at_entry": mk.get("yes_bid"),
            "yes_ask_at_entry": mk.get("yes_ask"),
            "fee_in": fee_in,
            "cash_cost_usd_sim": cash_cost,
            "contracts": TRAINING_CONTRACTS,
            "ts": now,
            "secs_at_entry": mk.get("secs"),
            "volume": mk.get("volume"),
            "mode": "stgm_training_only",
            "kalshi_fee_model": "taker_0.07_p_(1-p)_ceil_centicent",
            "usd": False,
            "note": "Training scalp · taker ask entry · fee-true Kalshi sim · never real USD",
        }
        open_rows.append(row)
        opened.append(row)
        have_assets.add(a)
        _append_log({"event": "training_scalp_open", **row}, state_dir=root)

    book["open"] = open_rows
    windows[wid] = {
        "opened": True,
        "n": len(opened),
        "assets": [r["asset"] for r in opened],
        "ts": now,
    }
    # prune old window keys
    if len(windows) > 80:
        for k in sorted(windows.keys())[:-60]:
            windows.pop(k, None)
    book["windows"] = windows
    _save_training_book(book, state_dir=root)
    return {
        "ok": True,
        "opened": len(opened),
        "window_id": wid,
        "tickets": [
            {"asset": r["asset"], "side": r["side"], "entry": r["entry"], "fee_in": r["fee_in"]}
            for r in opened
        ],
        "n_open": len(open_rows),
        "truth_label": TRUTH,
        "usd": "NEVER",
    }


def tick_training_scalps(
    *,
    state_dir: Optional[Path | str] = None,
    min_edge: float = MIN_EDGE_USD,
) -> dict[str, Any]:
    """Mark training book; virtual exit when fee-true net ≥ min_edge (Kalshi sim)."""
    root = _state(state_dir)
    book = _load_training_book(root)
    opens = list(book.get("open") or [])
    if not opens:
        # still try arm new window tickets
        armed = open_training_scalps_for_window(state_dir=root)
        return {
            "ok": True,
            "event": "training_scalp_tick",
            "n_open": 0,
            "n_exited": 0,
            "armed": armed,
            "usd": "NEVER",
        }

    marks = _load_live_marks(root)
    now = time.time()
    still: list[dict[str, Any]] = []
    exited: list[dict[str, Any]] = []
    proof = load_proof(root)

    for b in opens:
        kt = str(b.get("ticker") or "")
        mk = marks.get(kt)
        if not mk:
            still.append(b)
            continue
        side = str(b.get("side") or "yes")
        entry = float(b.get("entry") or 0.5)
        contracts = float(b.get("contracts") or TRAINING_CONTRACTS)
        age = now - float(b.get("ts") or now)
        secs = mk.get("secs")
        try:
            secs_f = float(secs) if secs is not None else None
        except (TypeError, ValueError):
            secs_f = None

        # r1706: same edge + force-flat clock as US$ / live STGM paper
        danger_flat = secs_f is not None and secs_f <= float(FORCE_FLAT_SECS) + 1e-9
        if danger_flat:
            edge = 0.0
        elif secs_f is not None and secs_f >= float(FORCE_FLAT_SECS) - 1e-9:
            edge = min(float(min_edge), float(EARLY_BURST_MIN_EDGE_USD))
        else:
            edge = float(min_edge)
        ev = evaluate_scalp(
            side=side,
            entry_price=entry,
            yes_mid=float(mk["yes"]),
            contracts=contracts,
            yes_bid=float(mk["yes_bid"]) if mk.get("yes_bid") not in (None, "") else None,
            yes_ask=float(mk["yes_ask"]) if mk.get("yes_ask") not in (None, "") else None,
            min_edge=edge,
        )
        expired = secs_f is not None and secs_f <= 0
        do_exit = False
        reason = ""
        if danger_flat:
            do_exit = True
            reason = "force_flat_7m30"
        elif age >= MIN_HOLD_SECS and ev.get("scalp_ok"):
            do_exit = True
            reason = "fee_true_green"
        if expired:
            do_exit = True
            reason = "window_expired_mark"
        if do_exit:
            net = float(ev["net_usd"])
            # if expired and not green, still book mark-to-mid fee-true (training truth)
            if reason == "window_expired_mark" and not ev.get("scalp_ok"):
                # settle-style: use mid mark with exit fee only path already in evaluate
                pass
            row = {
                "event": "training_scalp_exit",
                "mode": "stgm_training_only",
                "id": b.get("id"),
                "window_id": b.get("window_id"),
                "asset": b.get("asset"),
                "ticker": kt,
                "side": side,
                "label": b.get("label"),
                "entry": entry,
                "exit_price": ev["exit_px"],
                "fee_in": ev["fee_in"],
                "fee_out": ev["fee_out"],
                "fees_total": ev["fees_total"],
                "cash_cost_usd_sim": b.get("cash_cost_usd_sim"),
                "pnl_usd_fee_true": net,
                "win": net >= 0,
                "reason": reason,
                "secs_left": secs_f,
                "age_s": round(age, 1),
                "contracts": contracts,
                "kalshi_fee_model": "taker_0.07_p_(1-p)_ceil_centicent",
                "usd": False,
                "ts": now,
                "truth_label": TRUTH,
            }
            proof["n_scalps"] = int(proof.get("n_scalps") or 0) + 1
            proof["n_training_scalps"] = int(proof.get("n_training_scalps") or 0) + 1
            if net >= 0:
                proof["n_wins"] = int(proof.get("n_wins") or 0) + 1
            else:
                proof["n_losses"] = int(proof.get("n_losses") or 0) + 1
            proof["pnl_usd"] = round(float(proof.get("pnl_usd") or 0.0) + net, 4)
            proof["fees_paid_usd"] = round(
                float(proof.get("fees_paid_usd") or 0.0) + float(ev["fees_total"]), 4
            )
            proof["training_pnl_usd"] = round(
                float(proof.get("training_pnl_usd") or 0.0) + net, 4
            )
            exited.append(row)
            _append_log(row, state_dir=root)
        else:
            still.append(b)

    book["open"] = still
    _save_training_book(book, state_dir=root)
    save_proof(proof, state_dir=root)

    # arm next window tickets if book thin and clock in open band
    armed = {"opened": 0}
    if len(still) < TRAINING_SCALPS_PER_WINDOW:
        armed = open_training_scalps_for_window(state_dir=root)

    return {
        "ok": True,
        "event": "training_scalp_tick",
        "n_open": len(still),
        "n_exited": len(exited),
        "exited": exited[:6],
        "armed": armed,
        "proof": {
            "n_scalps": proof.get("n_scalps"),
            "n_training_scalps": proof.get("n_training_scalps"),
            "training_pnl_usd": proof.get("training_pnl_usd"),
            "pnl_usd": proof.get("pnl_usd"),
        },
        "truth_label": TRUTH,
        "usd": "NEVER",
        "note": "STGM training scalps · Kalshi fee-sim · real USD one-ticker path untouched",
    }


def grade_hold_counterfactuals(
    settled_rows: list[dict[str, Any]],
    *,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """After market resolve: compare scalp net vs what hold-to-settle would have paid."""
    root = _state(state_dir)
    cf = _load_cf(root)
    if not cf or not settled_rows:
        return {"ok": True, "n": 0}
    proof = load_proof(root)
    graded = 0
    for s in settled_rows:
        kt = str(s.get("ticker") or "")
        if kt not in cf:
            continue
        meta = cf.pop(kt)
        # hold PnL fee-true: win +(1-p)-fee_in, lose -p-fee_in (already paid entry fee)
        side = str(meta.get("side") or s.get("owner_side") or "")
        entry = float(meta.get("entry") or s.get("price") or 0.5)
        contracts = float(meta.get("contracts") or 1.0)
        fee_in = estimate_taker_fee(entry, contracts=contracts)
        result = str(s.get("result") or "").lower()
        if result not in ("yes", "no"):
            continue
        win_hold = side == result
        if win_hold:
            hold_net = round((1.0 - entry) * contracts - fee_in, 4)
        else:
            hold_net = round(-entry * contracts - fee_in, 4)
        scalp_net = float(meta.get("scalp_net_usd") or 0.0)
        delta = round(scalp_net - hold_net, 4)
        proof["hold_cf_pnl_usd"] = round(
            float(proof.get("hold_cf_pnl_usd") or 0.0) + hold_net, 4
        )
        if delta > 0:
            proof["scalp_beat_hold"] = int(proof.get("scalp_beat_hold") or 0) + 1
        elif delta < 0:
            proof["scalp_lost_to_hold"] = int(proof.get("scalp_lost_to_hold") or 0) + 1
        graded += 1
        _append_log(
            {
                "event": "scalp_vs_hold",
                "ticker": kt,
                "asset": meta.get("asset"),
                "scalp_net_usd": scalp_net,
                "hold_net_usd": hold_net,
                "delta_scalp_minus_hold": delta,
                "hold_win": win_hold,
                "result": result,
                "ts": time.time(),
                "truth_label": TRUTH,
            },
            state_dir=root,
        )
    _save_cf(cf, state_dir=root)
    save_proof(proof, state_dir=root)
    return {"ok": True, "n": graded, "remaining_cf": len(cf)}


__all__ = [
    "TRUTH",
    "estimate_taker_fee",
    "evaluate_scalp",
    "tick_scalps",
    "tick_training_scalps",
    "open_training_scalps_for_window",
    "grade_hold_counterfactuals",
    "load_proof",
    "MIN_EDGE_USD",
    "TRAINING_SCALPS_PER_WINDOW",
]
