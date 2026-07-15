"""STGM scalp learner — fee-true virtual cash-out (offline)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from System import alice_15m_scalp_learner as scalp


def _state(tmp_path: Path) -> Path:
    s = tmp_path / ".sifta_state"
    s.mkdir(parents=True, exist_ok=True)
    return s


def test_taker_fee_matches_live_fill_scale() -> None:
    # From exchange fills: 0.74 → ~0.0135, 0.87 → ~0.008, 0.66 → ~0.0158
    assert scalp.estimate_taker_fee(0.74) == pytest.approx(0.0135, abs=0.0005)
    assert scalp.estimate_taker_fee(0.87) == pytest.approx(0.008, abs=0.0005)
    assert scalp.estimate_taker_fee(0.66) == pytest.approx(0.0158, abs=0.0005)


def test_evaluate_scalp_needs_move_past_both_fees() -> None:
    # entry 0.70, exit 0.71 → tiny gross, fees kill it
    thin = scalp.evaluate_scalp(side="yes", entry_price=0.70, yes_mid=0.71, contracts=1.0)
    assert thin["scalp_ok"] is False
    # entry 0.70 → mark/exit ~0.80 after haircut 0.79
    fat = scalp.evaluate_scalp(
        side="yes",
        entry_price=0.70,
        yes_mid=0.80,
        yes_bid=0.79,
        contracts=1.0,
        min_edge=0.03,
    )
    assert fat["net_usd"] > 0.03
    assert fat["scalp_ok"] is True
    # NO side: entry 0.74, mark no rises to ~0.84 (yes mid 0.16)
    no = scalp.evaluate_scalp(
        side="no",
        entry_price=0.74,
        yes_mid=0.16,
        yes_ask=0.17,
        contracts=1.0,
    )
    # exit no = 1-0.17 = 0.83; gross 0.09 - fees
    assert no["exit_px"] == pytest.approx(0.83)
    assert no["scalp_ok"] is True


def test_tick_scalps_exits_green_ticket(tmp_path: Path) -> None:
    state = _state(tmp_path)
    # open ticket YES @ 0.70, live yes 0.82 → should scalp
    book = {
        "open": [
            {
                "asset": "XRP",
                "ticker": "KXXRP15M-TEST-SCALP",
                "side": "yes",
                "label": "UP",
                "price": 0.70,
                "stake": 1.0,
                "ts": __import__("time").time() - 120,
                "secs_left_at_entry": 600,
                "strategy": "follow_crowd",
                "body_stgm": {"ok": True, "stake": 0.001},
            }
        ],
        "n_open": 1,
    }
    (state / "alice_15m_open_book.json").write_text(json.dumps(book), encoding="utf-8")
    (state / "kalshi_15m_live.json").write_text(
        json.dumps(
            {
                "markets": [
                    {
                        "kalshi_ticker": "KXXRP15M-TEST-SCALP",
                        "asset": "XRP",
                        "kalshi_yes": 0.82,
                        "yes_bid": 0.81,
                        "yes_ask": 0.83,
                        "seconds_to_close": 300,
                        "kalshi_volume_24h": 5000.0,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (state / "alice_15m_paper_proof.json").write_text(
        json.dumps({"n_settled": 0, "n_wins": 0, "n_losses": 0, "pnl": 0.0}),
        encoding="utf-8",
    )
    # body stgm budget stub so settle doesn't blow up hard
    (state / "alice_15m_body_stgm_budget.json").write_text(
        json.dumps(
            {
                "open_tickets": {},
                "realized_pnl_stgm": 0.0,
                "n_settled": 0,
                "n_wins": 0,
                "n_losses": 0,
            }
        ),
        encoding="utf-8",
    )

    out = scalp.tick_scalps(state_dir=state, engine=None)
    assert out["n_scalped"] == 1
    # r1706: fee-true green executes STGM paper close (learns by doing)
    assert out["n_open"] == 0
    still_open = json.loads((state / "alice_15m_open_book.json").read_text())["open"]
    assert still_open == []
    proof = scalp.load_proof(state)
    assert proof["n_scalps"] == 1
    assert float(proof["pnl_usd"]) > 0.03
    # counterfactual + executed flag
    cf = json.loads((state / "alice_15m_scalp_counterfactual.json").read_text())
    assert "KXXRP15M-TEST-SCALP" in cf
    assert cf["KXXRP15M-TEST-SCALP"].get("executed") is True


def test_inert_reduce_only_cashout_builder_never_transmits() -> None:
    from System.kalshi_prod_trade_client import CapRejected, build_reduce_only_cashout_order

    yes_exit = build_reduce_only_cashout_order(
        ticker="KXBTC15M-TEST", hold_side="yes", exit_yes_price=0.82
    )
    assert yes_exit["inert"] is True
    assert yes_exit["transmits"] is False
    assert yes_exit["body"]["side"] == "ask"
    assert yes_exit["body"]["reduce_only"] is True
    assert yes_exit["body"]["time_in_force"] == "immediate_or_cancel"

    no_exit = build_reduce_only_cashout_order(
        ticker="KXXRP15M-TEST", hold_side="no", exit_yes_price=0.20
    )
    assert no_exit["body"]["side"] == "bid"  # buy YES to close NO
    assert no_exit["body"]["reduce_only"] is True
    with pytest.raises(CapRejected):
        build_reduce_only_cashout_order(
            ticker="KXXRP15M-TEST", hold_side="maybe", exit_yes_price=0.20
        )


def test_scalp_banks_green_early_not_only_last_five_minutes(tmp_path: Path) -> None:
    """r1685: minute-14 scalping — fee-true green exits with 10m left (not m5-only)."""
    state = _state(tmp_path)
    ticker = "KXBTC15M-TEST-EARLY"
    (state / "alice_15m_open_book.json").write_text(
        json.dumps(
            {
                "open": [
                    {
                        "asset": "BTC",
                        "ticker": ticker,
                        "side": "yes",
                        "label": "UP",
                        "price": 0.70,
                        "stake": 1.0,
                        "ts": __import__("time").time() - 120,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (state / "kalshi_15m_live.json").write_text(
        json.dumps(
            {
                "markets": [
                    {
                        "kalshi_ticker": ticker,
                        "kalshi_yes": 0.82,
                        "yes_bid": 0.81,
                        "yes_ask": 0.83,
                        "seconds_to_close": 10 * 60,  # early/mid window
                        "kalshi_volume_24h": 5000,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (state / "alice_15m_paper_proof.json").write_text(
        json.dumps({"n_settled": 0, "n_wins": 0, "n_losses": 0, "pnl": 0.0}),
        encoding="utf-8",
    )
    out = scalp.tick_scalps(state_dir=state)
    assert out["n_scalped"] >= 1
    # r1685/r1706: open-bell through full 15m strip (not m14-only)
    assert scalp.TRAINING_OPEN_SECS_MAX == 15 * 60


def test_training_scalps_arm_every_window_stgm_only(tmp_path: Path) -> None:
    """r1674: few STGM training scalps per 15m; never USD; Kalshi fee-sim."""

    def _write_marks(state: Path, secs_left: int, *, n: int = 3) -> None:
        markets = []
        for asset in ("BTC", "ETH", "SOL", "XRP")[:n]:
            markets.append(
                {
                    "kalshi_ticker": f"KX{asset}15M-TEST-TRAIN",
                    "asset": asset,
                    "kalshi_yes": 0.52,
                    "yes_bid": 0.51,
                    "yes_ask": 0.53,
                    "seconds_to_close": secs_left,
                    "kalshi_volume_24h": 8000.0,
                }
            )
        (state / "kalshi_15m_live.json").write_text(
            json.dumps({"markets": markets}),
            encoding="utf-8",
        )

    # near expiry: refuse
    dead = _state(tmp_path / "dead")
    _write_marks(dead, secs_left=20)
    assert scalp.open_training_scalps_for_window(state_dir=dead)["opened"] == 0

    # r1685: minute-14 / early window — not m7/m11-only
    early = _state(tmp_path / "early_m14")
    _write_marks(early, secs_left=14 * 60, n=4)
    out_early = scalp.open_training_scalps_for_window(state_dir=early)
    assert 1 <= out_early["opened"] <= min(4, scalp.TRAINING_SCALPS_PER_WINDOW)
    assert out_early["usd"] == "NEVER"
    for t in out_early.get("tickets") or []:
        assert float(t["fee_in"]) > 0
        assert scalp.SCALP_MIN_ENTRY <= float(t["entry"]) <= scalp.SCALP_MAX_ENTRY
        # P0.7: training taker entry uses executable ask (0.53 for YES @ yes_ask)
        assert float(t["entry"]) == 0.53

    # mid window still works
    in_zone = _state(tmp_path / "in_zone")
    _write_marks(in_zone, secs_left=8 * 60, n=4)
    out_mid = scalp.open_training_scalps_for_window(state_dir=in_zone)
    assert 1 <= out_mid["opened"] <= min(4, scalp.TRAINING_SCALPS_PER_WINDOW)

    # same window idempotent
    assert scalp.open_training_scalps_for_window(state_dir=in_zone)["opened"] == 0


def test_hold_counterfactual_grades_beat_or_miss(tmp_path: Path) -> None:
    state = _state(tmp_path)
    (state / "alice_15m_scalp_counterfactual.json").write_text(
        json.dumps(
            {
                "T1": {
                    "scalp_net_usd": 0.05,
                    "entry": 0.70,
                    "side": "yes",
                    "contracts": 1.0,
                    "asset": "BTC",
                }
            }
        ),
        encoding="utf-8",
    )
    # market went yes → hold would have paid ~0.30 - fee
    r = scalp.grade_hold_counterfactuals(
        [{"ticker": "T1", "result": "yes", "owner_side": "yes", "price": 0.70}],
        state_dir=state,
    )
    assert r["n"] == 1
    proof = scalp.load_proof(state)
    assert proof.get("scalp_lost_to_hold", 0) + proof.get("scalp_beat_hold", 0) >= 1
