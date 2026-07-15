"""r1684 STGM intrawindow scalp lab — offline tests (no USD, no network)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from System import alice_15m_execution_sim as sim
from System import alice_15m_execution_tape as tape
from System import alice_15m_scalp_lab as lab
from System import alice_15m_scalp_proof_accounting as acct
from System import alice_15m_scalp_strategies as strat


def _state(tmp_path: Path) -> Path:
    s = tmp_path / ".sifta_state"
    s.mkdir(parents=True, exist_ok=True)
    return s


def test_complement_asks_from_bids() -> None:
    out = tape.complement_asks_from_bids(
        [["0.5600", "12.00"]],
        [["0.4300", "8.00"]],
    )
    # yes ask ≈ 1 - no bid = 0.57
    assert float(out["yes_asks"][0][0]) == pytest.approx(0.57)
    # no ask ≈ 1 - yes bid = 0.44
    assert float(out["no_asks"][0][0]) == pytest.approx(0.44)


def test_taker_walk_multi_level() -> None:
    asks = [(0.55, 0.4), (0.56, 0.4), (0.58, 2.0)]
    fills, rem = sim.walk_taker_buy_yes(asks, limit_price=0.56, quantity=1.0)
    assert rem == pytest.approx(0.2)
    assert len(fills) == 2
    assert fills[0]["price"] == 0.55
    assert fills[1]["price"] == 0.56
    # insufficient depth at limit
    fills2, rem2 = sim.walk_taker_buy_yes(asks, limit_price=0.54, quantity=1.0)
    assert fills2 == []
    assert rem2 == 1.0


def test_fok_rejects_partial() -> None:
    s = sim.KalshiExecutionSim(latency_ms=0, persist=False)
    book = {
        "ticker": "KXBTC15M-TEST",
        "yes_bids": [["0.54", "1.00"]],
        "no_bids": [["0.44", "0.30"]],  # yes ask = 0.56, only 0.30 size
        "yes_asks": [["0.56", "0.30"]],
        "recv_ts_ms": 1_000,
    }
    s.on_book(book)
    snap = s.submit(
        {
            "ticker": "KXBTC15M-TEST",
            "side": "yes",
            "action": "buy",
            "price": 0.60,
            "quantity": 1.0,
            "tif": "fok",
            "book_at_arrival": book,
            "latency_ms": 0,
        }
    )
    assert snap["fill_confidence"] == "no_fill"
    assert snap["state"] == "canceled"
    assert s.n_no_fills == 1


def test_ioc_partial_and_fees_reconcile() -> None:
    s = sim.KalshiExecutionSim(latency_ms=0, persist=False)
    book = {
        "ticker": "KXBTC15M-TEST",
        "yes_bids": [["0.54", "5.00"]],
        "yes_asks": [["0.56", "0.5"]],
        "no_bids": [["0.44", "0.5"]],
        "recv_ts_ms": 1_000,
    }
    snap = s.submit(
        {
            "ticker": "KXBTC15M-TEST",
            "side": "yes",
            "action": "buy",
            "price": 0.60,
            "quantity": 1.0,
            "tif": "ioc",
            "book_at_arrival": book,
            "latency_ms": 0,
        }
    )
    assert float(snap["filled_qty"]) == pytest.approx(0.5)
    assert snap["fill_confidence"] in ("partial", "filled")
    rec = s.reconcile()
    assert rec["fees_match"] is True
    assert rec["n_fills"] + rec["n_partial"] >= 1


def test_maker_without_trade_is_fill_unknown_not_filled() -> None:
    s = sim.KalshiExecutionSim(latency_ms=0, persist=False)
    book = {
        "ticker": "KXBTC15M-TEST",
        "yes_bids": [["0.54", "5.00"]],
        "yes_asks": [["0.56", "5.00"]],
        "recv_ts_ms": 1_000,
    }
    snap = s.submit(
        {
            "ticker": "KXBTC15M-TEST",
            "side": "yes",
            "action": "buy",
            "price": 0.55,
            "quantity": 1.0,
            "tif": "gtc",
            "post_only": True,
            "book_at_arrival": book,
            "latency_ms": 0,
        }
    )
    assert snap["state"] == "resting"
    assert snap["fill_confidence"] == "fill_unknown"
    # book update without trade → still not filled
    s.on_book({**book, "recv_ts_ms": 2_000})
    o = s.orders[snap["order_id"]]
    assert o.filled_qty == 0.0


def test_round_trip_pnl_from_ledger() -> None:
    s = sim.KalshiExecutionSim(latency_ms=0, persist=False)
    entry_book = {
        "ticker": "T1",
        "yes_bids": [["0.60", "10"]],
        "yes_asks": [["0.62", "10"]],
        "no_bids": [["0.38", "10"]],
        "recv_ts_ms": 1_000,
    }
    buy = s.submit(
        {
            "ticker": "T1",
            "side": "yes",
            "action": "buy",
            "price": 0.65,
            "quantity": 1.0,
            "tif": "ioc",
            "book_at_arrival": entry_book,
            "latency_ms": 0,
        }
    )
    assert float(buy["filled_qty"]) == 1.0
    exit_book = {
        "ticker": "T1",
        "yes_bids": [["0.72", "10"]],
        "yes_asks": [["0.74", "10"]],
        "no_bids": [["0.26", "10"]],
        "recv_ts_ms": 50_000,
    }
    sell = s.submit(
        {
            "ticker": "T1",
            "side": "yes",
            "action": "sell",
            "price": 0.01,
            "quantity": 1.0,
            "tif": "ioc",
            "reduce_only": True,
            "book_at_arrival": exit_book,
            "latency_ms": 0,
        }
    )
    assert float(sell["filled_qty"]) == 1.0
    # gross ~0.10 minus two fees → still green
    assert s.realized_pnl > 0.05
    rec = s.reconcile()
    assert rec["fees_match"] is True
    assert abs(sum(p["qty"] for p in s.positions_snapshot().values())) < 1e-9 or not s.positions_snapshot()


def test_force_flatten_unflattenable_without_book() -> None:
    s = sim.KalshiExecutionSim(latency_ms=0, persist=False)
    s.positions["T1"] = sim.Position(ticker="T1", side="yes", qty=1.0, avg_entry=0.5)
    out = s.force_flatten("T1", book=None)
    assert out["ok"] is False
    assert s.n_unflattenable == 1


def test_honest_accounting_splits_biased_and_training(tmp_path: Path) -> None:
    state = _state(tmp_path)
    log = state / "alice_15m_scalp.jsonl"
    rows = [
        {
            "event": "scalp_exit",
            "ticker": "A",
            "pnl_usd_fee_true": 0.05,
            "fees_total": 0.02,
            "ts": 1,
        },
        {
            "event": "scalp_exit",
            "ticker": "A",
            "pnl_usd_fee_true": 0.05,
            "fees_total": 0.02,
            "ts": 1,
        },  # dup
        {
            "event": "training_scalp_open",
            "id": "t1",
            "ticker": "B",
            "window_id": "w1",
            "ts": 2,
        },
        {
            "event": "training_scalp_exit",
            "id": "t1",
            "ticker": "B",
            "window_id": "w1",
            "pnl_usd_fee_true": -0.02,
            "fees_total": 0.03,
            "reason": "window_expired_mark",
            "ts": 3,
        },
        {
            "event": "scalp_vs_hold",
            "ticker": "A",
            "scalp_net_usd": 0.05,
            "hold_net_usd": -0.10,
            "delta_scalp_minus_hold": 0.15,
            "result": "no",
        },
    ]
    with log.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    # legacy inflated proof
    (state / "alice_15m_scalp_proof.json").write_text(
        json.dumps({"n_scalps": 99, "n_wins": 99, "n_losses": 0, "win_rate": 1.0, "pnl_usd": 12.9}),
        encoding="utf-8",
    )
    honest = acct.recompute_honest_proof(state_dir=state)
    assert honest["selected_green_exit"]["n"] == 1
    assert honest["selected_green_exit"]["do_not_promote_on_this"] is True
    assert honest["selected_green_exit"]["biased"] is True
    assert honest["training_round_trip"]["n_exits"] == 1
    assert honest["training_round_trip"]["n_losses"] == 1
    assert honest["n_forced_closes"] == 1
    assert honest["hold_counterfactual"]["scalp_beat_hold"] == 1
    # legacy preserved with warning
    legacy = json.loads((state / "alice_15m_scalp_proof.json").read_text(encoding="utf-8"))
    assert legacy["n_wins"] == 99
    assert "selection_bias_warning" in legacy


def test_tape_capture_from_live_marks(tmp_path: Path) -> None:
    state = _state(tmp_path)
    (state / "kalshi_15m_live.json").write_text(
        json.dumps(
            {
                "markets": [
                    {
                        "kalshi_ticker": "KXBTC15M-TEST",
                        "asset": "BTC",
                        "kalshi_yes": 0.62,
                        "yes_bid": 0.61,
                        "yes_ask": 0.63,
                        "seconds_to_close": 400,
                        "kalshi_volume_24h": 9000,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    out = tape.capture_from_live_marks(state_dir=state)
    assert out["ok"] is True
    assert out["n"] == 1
    assert out["usd"] == "NEVER"
    rows = tape.load_tape(state_dir=state)
    assert len(rows) == 1
    assert rows[0]["event"] == "book_snapshot"
    assert rows[0]["yes_bids"]


def test_strategies_frozen_registry() -> None:
    arms = strat.all_strategies()
    ids = {a.strategy_id for a in arms}
    assert ids == {
        "end_of_tape_liquidation",
        "hold_to_settlement",
        "taker_momentum_tp",
        "pullback_continuation",
        "micro_mean_reversion",
        "maker_spread_capture",
        "cross_asset_confirmation",
    }
    ph = strat.policy_hash_for_strategies()
    assert len(ph) == 16
    # no-trade when weird
    book = {
        "asset": "ZEC",
        "yes_mid": 0.6,
        "yes_bids": [["0.59", "2"]],
        "yes_asks": [["0.61", "2"]],
        "no_bids": [["0.39", "2"]],
        "seconds_left": 300,
        "volume_24h": 5000,
        "recv_ts_ms": 1,
    }
    st = strat.ArmState(strategy_id="taker_momentum_tp")
    intent = strat.TakerMomentumTP().decide(book, state=st, field={"mom_yes": 0.05})
    assert intent.action == "no_trade"
    assert intent.reason == "weird_asset"


def test_tournament_ranks_by_ev_not_wr(tmp_path: Path) -> None:
    state = _state(tmp_path)
    # seed a short rising tape so momentum can trade
    now = 1_700_000_000_000
    for i, mid in enumerate([0.55, 0.56, 0.58, 0.60, 0.63, 0.66, 0.68]):
        tape.append_tape_event(
            {
                "event": "book_snapshot",
                "ticker": "KXBTC15M-T",
                "window_id": "KXBTC15M-T",
                "asset": "BTC",
                "recv_ts_ms": now + i * 15_000,
                "yes_mid": mid,
                "yes_bids": [[f"{mid - 0.01:.4f}", "5.00"]],
                "yes_asks": [[f"{mid + 0.01:.4f}", "5.00"]],
                "no_bids": [[f"{1 - (mid + 0.01):.4f}", "5.00"]],
                "seconds_left": 500 - i * 15,
                "volume_24h": 8000,
                "source": "test",
            },
            state_dir=state,
        )
    report = lab.run_live_shadow_tournament(state_dir=state, latency_ms=0)
    assert report["ok"] is True
    assert report["n_arms"] == 7
    assert report["ranking_rule"].startswith("fee_net_ev_per_window")
    assert report["usd_orders"] == "NEVER"
    assert report.get("formula_audit") == "r20260714-grok-scalp-formula-audit"
    gate = report["holdout_gate"]
    assert gate["usd_authorize"] is False
    assert "LCB95" in str(gate.get("promotion_rule") or "")
    # early sample must not lab-promote
    assert gate["any_lab_promote"] is False
    # arms carry bootstrap LCB and do not double-count fills
    for a in report["arms"]:
        assert "lcb95" in a
        assert a.get("n_fills") is not None
        # gate must not add n_exits into fill count
        g = next(x for x in gate["arms"] if x["strategy_id"] == a["strategy_id"])
        assert g["n_fills"] == a["n_fills"]


def test_block_bootstrap_ci() -> None:
    pnls = [0.01, -0.02, 0.03, 0.00, 0.02]
    ci = lab.block_bootstrap_ci(pnls, n_boot=200, seed=1)
    assert ci["n"] == 5
    assert ci["lo"] <= ci["mean"] <= ci["hi"]


def test_tick_scalp_lab_smoke(tmp_path: Path) -> None:
    state = _state(tmp_path)
    (state / "kalshi_15m_live.json").write_text(
        json.dumps(
            {
                "markets": [
                    {
                        "kalshi_ticker": "KXETH15M-T",
                        "asset": "ETH",
                        "kalshi_yes": 0.58,
                        "yes_bid": 0.57,
                        "yes_ask": 0.59,
                        "seconds_to_close": 350,
                        "kalshi_volume_24h": 4000,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    out = lab.tick_scalp_lab(state_dir=state, run_tournament=True)
    assert out["ok"] is True
    assert out["usd"] == "NEVER_FROM_LAB"
    assert (state / "alice_15m_execution_tape.jsonl").exists()
    assert (state / "alice_15m_scalp_glass.json").exists()


# ── r20260714 formula-audit P0 regressions ─────────────────────────────────


def test_p0_latency_uses_book_at_arrival_not_decision_book() -> None:
    """P0.2: 0ms vs positive latency must fill against different arrival books."""
    s = sim.KalshiExecutionSim(latency_ms=0, persist=False)
    t0 = 1_700_000_000_000
    books = []
    for i, mid in enumerate([0.50, 0.55, 0.60]):
        books.append(
            {
                "ticker": "KX-LAT",
                "recv_ts_ms": t0 + i * 1000,
                "yes_bids": [[f"{mid - 0.01:.2f}", "10"]],
                "yes_asks": [[f"{mid + 0.01:.2f}", "10"]],
                "no_bids": [[f"{1 - (mid + 0.01):.2f}", "10"]],
            }
        )
    s.register_tape("KX-LAT", books)
    # decision at first book; 0 latency → fill at 0.51 ask
    snap0 = s.submit(
        {
            "ticker": "KX-LAT",
            "side": "yes",
            "action": "buy",
            "price": 0.99,
            "quantity": 1.0,
            "tif": "ioc",
            "submitted_ts_ms": t0,
            "latency_ms": 0,
        }
    )
    assert float(snap0["avg_fill_price"]) == pytest.approx(0.51)
    s2 = sim.KalshiExecutionSim(latency_ms=1500, persist=False)
    s2.register_tape("KX-LAT", books)
    # 1500ms latency → arrives at third book, ask 0.61
    snap1 = s2.submit(
        {
            "ticker": "KX-LAT",
            "side": "yes",
            "action": "buy",
            "price": 0.99,
            "quantity": 1.0,
            "tif": "ioc",
            "submitted_ts_ms": t0,
            "latency_ms": 1500,
        }
    )
    assert float(snap1["avg_fill_price"]) == pytest.approx(0.61)
    assert float(snap0["avg_fill_price"]) != float(snap1["avg_fill_price"])


def test_p0_pit_majors_no_lookahead() -> None:
    """P0.1: first decision must not see final majors snapshot."""
    by_ticker = {
        "KXBTC": [
            {"ticker": "KXBTC", "asset": "BTC", "recv_ts_ms": 1000, "yes_mid": 0.40},
            {"ticker": "KXBTC", "asset": "BTC", "recv_ts_ms": 5000, "yes_mid": 0.80},
        ],
        "KXETH": [
            {"ticker": "KXETH", "asset": "ETH", "recv_ts_ms": 1000, "yes_mid": 0.42},
            {"ticker": "KXETH", "asset": "ETH", "recv_ts_ms": 5000, "yes_mid": 0.82},
        ],
        "KXSOL": [
            {"ticker": "KXSOL", "asset": "SOL", "recv_ts_ms": 1000, "yes_mid": 0.41},
            {"ticker": "KXSOL", "asset": "SOL", "recv_ts_ms": 5000, "yes_mid": 0.81},
        ],
        "KXXRP": [
            {"ticker": "KXXRP", "asset": "XRP", "recv_ts_ms": 1000, "yes_mid": 0.39},
            {"ticker": "KXXRP", "asset": "XRP", "recv_ts_ms": 5000, "yes_mid": 0.79},
        ],
    }
    mids_t0, _prev, src = lab._pit_majors(by_ticker, 1000)
    assert mids_t0["BTC"] == pytest.approx(0.40)
    assert mids_t0["ETH"] == pytest.approx(0.42)
    assert src["BTC"] == 1000
    # final snapshot not visible at t=1000
    assert mids_t0["BTC"] < 0.5
    mids_end, prev_end, _ = lab._pit_majors(by_ticker, 5000, lookback_ms=4000)
    assert mids_end["BTC"] == pytest.approx(0.80)
    assert prev_end["BTC"] == pytest.approx(0.40)
    field = strat.feature_field_from_books(
        by_ticker["KXBTC"][:1],
        majors_mids=mids_end,
        majors_prev_mids=prev_end,
    )
    # returns-based breadth: all majors up → breadth > 0
    assert field["majors_breadth"] is not None
    assert field["majors_breadth"] > 0.5
    assert field["majors_breadth_complete"] is True


def test_p0_maker_post_only_no_does_not_cross() -> None:
    """P0.8: post-only buy NO priced at no_bid = 1-yes_ask, not no_ask."""
    book = {
        "asset": "BTC",
        "yes_mid": 0.55,
        "yes_bids": [["0.54", "5"]],
        "yes_asks": [["0.56", "5"]],
        "no_bids": [["0.44", "5"]],
        "seconds_left": 400,
        "volume_24h": 8000,
        "recv_ts_ms": 1,
    }
    st = strat.ArmState(strategy_id="maker_spread_capture")
    intent = strat.MakerSpreadCapture().decide(book, state=st, field={})
    assert intent.action == "enter"
    assert intent.post_only is True
    if intent.side == "yes":
        # post_buy_yes <= yes_bid
        assert intent.price <= 0.54 + 1e-9
    else:
        # post_buy_no <= no_bid = 1 - yes_ask = 0.44
        assert intent.price <= 0.44 + 1e-9


def test_p0_partial_exit_keeps_residual_inventory() -> None:
    """P0.4: partial IOC exit must not zero tracked residual qty."""
    s = sim.KalshiExecutionSim(latency_ms=0, persist=False)
    entry_book = {
        "ticker": "KX-RES",
        "recv_ts_ms": 1,
        "yes_bids": [["0.50", "10"]],
        "yes_asks": [["0.51", "10"]],
        "no_bids": [["0.49", "10"]],
    }
    s.on_book(entry_book)
    s.submit(
        {
            "ticker": "KX-RES",
            "side": "yes",
            "action": "buy",
            "price": 0.51,
            "quantity": 2.0,
            "tif": "ioc",
            "book_at_arrival": entry_book,
            "latency_ms": 0,
        }
    )
    assert s.positions["KX-RES"].qty == pytest.approx(2.0)
    # exit book only has 1.0 bid size → partial
    exit_book = {
        "ticker": "KX-RES",
        "recv_ts_ms": 2,
        "yes_bids": [["0.60", "1.0"]],
        "yes_asks": [["0.61", "5"]],
        "no_bids": [["0.39", "5"]],
    }
    snap = s.submit(
        {
            "ticker": "KX-RES",
            "side": "yes",
            "action": "sell",
            "price": 0.01,
            "quantity": 2.0,
            "tif": "ioc",
            "reduce_only": True,
            "book_at_arrival": exit_book,
            "latency_ms": 0,
        }
    )
    assert float(snap["filled_qty"]) == pytest.approx(1.0)
    assert s.positions["KX-RES"].qty == pytest.approx(1.0)
    st = strat.ArmState(strategy_id="t", open_qty=2.0, open_side="yes", open_entry=0.51)
    done = lab._sync_arm_from_sim(
        st, s, "KX-RES", filled=1.0, is_exit=True, book_ts_ms=2
    )
    assert done is False
    assert st.open_qty == pytest.approx(1.0)


def test_p0_hold_controls_are_distinct() -> None:
    eot = strat.EndOfTapeLiquidation()
    hts = strat.HoldToSettlement()
    assert eot.strategy_id == "end_of_tape_liquidation"
    assert hts.strategy_id == "hold_to_settlement"
    assert eot.settle_mode != hts.settle_mode
    book = {
        "asset": "BTC",
        "yes_mid": 0.60,
        "yes_bids": [["0.59", "5"]],
        "yes_asks": [["0.61", "5"]],
        "no_bids": [["0.39", "5"]],
        "seconds_left": 0,
        "volume_24h": 8000,
        "recv_ts_ms": 9,
    }
    st_e = strat.ArmState(
        strategy_id=eot.strategy_id, open_qty=1.0, open_side="yes", open_entry=0.55
    )
    st_h = strat.ArmState(
        strategy_id=hts.strategy_id, open_qty=1.0, open_side="yes", open_entry=0.55
    )
    assert eot.decide(book, state=st_e).action == "flatten"
    assert hts.decide(book, state=st_h).action == "hold"
