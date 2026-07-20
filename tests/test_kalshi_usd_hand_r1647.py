"""r1647 — real-USD hand gates (offline). No network orders."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from System import kalshi_prod_trade_client as kpt
from System import kalshi_usd_hand as hand
from System import kalshi_usd_lane as lane


def _state(tmp_path: Path) -> Path:
    s = tmp_path / ".sifta_state"
    s.mkdir(parents=True, exist_ok=True)
    # r1686 live dual: tests need USD not shadow-only
    (s / "alice_fee_net_tournament.json").write_text(
        __import__("json").dumps(
            {"epoch_active": True, "usd_shadow_only": False, "usd_owner_override": True}
        ),
        encoding="utf-8",
    )
    from System.alice_fee_net_tournament import write_policy_hash
    write_policy_hash(state_dir=s)
    return s


def test_demo_host_forbidden_in_prod_client() -> None:
    with pytest.raises(kpt.DemoHostForbidden):
        kpt.assert_prod_url("https://external-api.demo.kalshi.co/trade-api/v2")


def test_prod_url_ok() -> None:
    assert "kalshi.com" in kpt.assert_prod_url(kpt.PROD_BASE)


@pytest.mark.parametrize(
    "url",
    [
        "http://external-api.kalshi.com/trade-api/v2",
        "https://evilkalshi.com/trade-api/v2",
        "https://kalshi.attacker.example/trade-api/v2",
    ],
)
def test_prod_url_rejects_non_exact_https_host(url: str) -> None:
    with pytest.raises(kpt.DemoHostForbidden):
        kpt.assert_prod_url(url)


def test_corrupt_kill_switch_fails_closed(tmp_path: Path) -> None:
    state = _state(tmp_path)
    (state / kpt.KILL_SWITCH).write_text("{truncated", encoding="utf-8")
    assert kpt.kill_switch_active(state_dir=state) is True


def test_kill_switch_blocks_place(tmp_path: Path) -> None:
    state = _state(tmp_path)
    kpt.set_kill_switch(True, reason="test", state_dir=state)
    c = kpt.KalshiProdTradeClient(state_dir=state)
    with pytest.raises(kpt.KillSwitchActive):
        c.place_limit_order(ticker="T", side="yes", price=0.52, dry_run=True)


def test_band_rejects_expensive_scalp_chase(tmp_path: Path) -> None:
    """r1691: field winners up to 65¢; above still refused."""
    state = _state(tmp_path)
    kpt.set_kill_switch(False, state_dir=state)
    c = kpt.KalshiProdTradeClient(state_dir=state)
    with pytest.raises(kpt.CapRejected):
        c.place_limit_order(ticker="T", side="yes", price=0.70, dry_run=True)
    with pytest.raises(kpt.CapRejected):
        c.place_limit_order(ticker="T", side="yes", price=0.66, dry_run=True)
    r = c.place_limit_order(ticker="T", side="yes", price=0.62, dry_run=True)
    assert r["ok"] is True
    r = c.place_limit_order(ticker="T", side="yes", price=0.52, dry_run=True)
    assert r["ok"] is True


def test_dry_run_in_band(tmp_path: Path) -> None:
    state = _state(tmp_path)
    kpt.set_kill_switch(False, state_dir=state)
    c = kpt.KalshiProdTradeClient(state_dir=state)
    r = c.place_limit_order(
        ticker="KXTEST", side="yes", price=0.52, volume=5000, dry_run=True
    )
    assert r["ok"] and r["dry_run"] is True
    assert r["cost_usd"] == pytest.approx(0.52)


def test_prod_client_normalizes_v2_fill_receipt(tmp_path: Path, monkeypatch) -> None:
    state = _state(tmp_path)
    kpt.set_kill_switch(False, state_dir=state)
    from System import kalshi_credentials as creds

    monkeypatch.setattr(creds, "credentials_status", lambda: {"ready": True})
    client = kpt.KalshiProdTradeClient(state_dir=state)
    monkeypatch.setattr(
        client,
        "_request",
        lambda *args, **kwargs: {
            "order_id": "order-1",
            "client_order_id": "client-1",
            "fill_count": "1.00",
            "remaining_count": "0.00",
            "average_fill_price": "0.5200",
            "average_fee_paid": "0.0100",
        },
    )
    row = client.place_limit_order(
        ticker="KXTEST", side="yes", price=0.52, volume=5000
    )
    assert row["filled"] is True
    assert row["fill_count"] == pytest.approx(1.0)
    assert row["price"] == pytest.approx(0.52)
    assert row["fee_paid_usd"] == pytest.approx(0.01)
    assert row["cost_usd"] == pytest.approx(0.53)


def test_prod_client_no_side_uses_one_minus_yes_book_fill(tmp_path: Path, monkeypatch) -> None:
    """V2 average_fill_price is YES-book; buy NO via ask costs (1 - yes_fill)."""
    state = _state(tmp_path)
    kpt.set_kill_switch(False, state_dir=state)
    from System import kalshi_credentials as creds

    monkeypatch.setattr(creds, "credentials_status", lambda: {"ready": True})
    client = kpt.KalshiProdTradeClient(state_dir=state)
    # Intended NO @ 0.87; YES-book fill @ 0.13 → real NO premium 0.87
    monkeypatch.setattr(
        client,
        "_request",
        lambda *args, **kwargs: {
            "order_id": "order-no-1",
            "client_order_id": "client-no-1",
            "fill_count": "1.00",
            "remaining_count": "0.00",
            "average_fill_price": "0.1300",
            "average_fee_paid": "0.0080",
        },
    )
    row = client.place_limit_order(
        ticker="KXXRP15M", side="no", price=0.52, volume=5000
    )
    assert row["filled"] is True
    assert row["side"] == "no"
    assert row["yes_fill_price"] == pytest.approx(0.13)
    assert row["price"] == pytest.approx(0.87)
    assert row["side_price"] == pytest.approx(0.87)
    assert row["premium_usd"] == pytest.approx(0.87)
    assert row["fee_paid_usd"] == pytest.approx(0.008)
    assert row["cost_usd"] == pytest.approx(0.878)
    # Win on that contract: +(1-0.87) - fee = +0.122
    from System.ledger_deal import live_contract_pnl

    assert live_contract_pnl(True, row["price"]) - row["fee_paid_usd"] == pytest.approx(0.122)


def test_heal_open_no_premiums_fixes_understated_exposure(tmp_path: Path) -> None:
    state = _state(tmp_path)
    night = {
        "day": "2026-07-13",
        "realized_pnl_usd": 0.0,
        "open": [
            {
                "asset": "BTC",
                "side": "no",
                "label": "DOWN",
                "price": 0.23,
                "limit_price": 0.73,
                "fill_count": 1.0,
                "count": 1.0,
                "premium_usd": 0.23,
                "fee_paid_usd": 0.0124,
                "cost_usd": 0.2424,
                "ticker": "KXBTC15M-TEST",
            }
        ],
        "n_placed": 1,
        "n_settled": 0,
        "halted": False,
        "halt_reason": "",
        "truth_label": "KALSHI_USD_HAND_V1",
    }
    (state / "kalshi_usd_night.json").write_text(
        json.dumps(night), encoding="utf-8"
    )
    out = hand.heal_open_no_premiums(state_dir=state)
    assert out["n_healed"] == 1
    fixed = json.loads((state / "kalshi_usd_night.json").read_text())["open"][0]
    assert fixed["price"] == pytest.approx(0.77)
    assert fixed["premium_usd"] == pytest.approx(0.77)
    assert fixed["cost_usd"] == pytest.approx(0.7824)


def test_prod_client_rejects_invalid_count_action_and_unknown_volume(tmp_path: Path) -> None:
    state = _state(tmp_path)
    kpt.set_kill_switch(False, state_dir=state)
    client = kpt.KalshiProdTradeClient(state_dir=state)
    with pytest.raises(kpt.CapRejected):
        client.place_limit_order(
            ticker="KX", side="yes", price=0.52, count=0, volume=5000, dry_run=True
        )
    with pytest.raises(kpt.CapRejected):
        client.place_limit_order(
            ticker="KX", side="yes", price=0.52, action="sell", volume=5000, dry_run=True
        )
    # r1649: volume optional when MIN_VOLUME is 0
    r = client.place_limit_order(ticker="KX", side="yes", price=0.52, dry_run=True)
    assert r["ok"] is True


def test_raw_create_order_request_cannot_bypass_caps(tmp_path: Path) -> None:
    state = _state(tmp_path)
    kpt.set_kill_switch(False, state_dir=state)
    client = kpt.KalshiProdTradeClient(state_dir=state)
    with pytest.raises(kpt.CapRejected):
        client._request(
            "POST",
            "/portfolio/events/orders",
            body={"ticker": "KX", "side": "bid", "count": "9.00", "price": "0.01"},
            write=True,
        )


def test_string_false_session_does_not_arm_hand(tmp_path: Path) -> None:
    state = _state(tmp_path)
    (state / hand.SESSION_FILE).write_text('{"live":"false"}', encoding="utf-8")
    assert hand.is_hand_live(state) is False


def test_repo_root_state_path_normalizes_to_dot_state(tmp_path: Path) -> None:
    hand.set_hand_live(False, state_dir=tmp_path)
    assert (tmp_path / ".sifta_state" / hand.SESSION_FILE).exists()


def test_evaluate_requires_arm(tmp_path: Path) -> None:
    state = _state(tmp_path)
    lane.set_usd_lane_armed(False, reason="test", state_dir=state)
    hand.set_hand_live(False, state_dir=state)
    g = hand.evaluate_ticket(
        entry_price=0.52, side="yes", rainman_action="fire", state_dir=state
    )
    assert g["ok"] is False and g["reason"] == "lane_off"


def test_evaluate_fire_only_and_band(tmp_path: Path) -> None:
    state = _state(tmp_path)
    lane.set_usd_lane_armed(True, reason="test", state_dir=state)
    hand.set_hand_live(True, reason="test", state_dir=state)
    kpt.set_kill_switch(False, state_dir=state)
    # r1691 scalp band 40–65¢
    g = hand.evaluate_ticket(
        entry_price=0.52, side="yes", rainman_action="thin", state_dir=state
    )
    assert g["ok"] is True
    g = hand.evaluate_ticket(
        entry_price=0.62, side="yes", rainman_action="fire", state_dir=state
    )
    assert g["ok"] is True
    g = hand.evaluate_ticket(
        entry_price=0.65, side="yes", rainman_action="fire", state_dir=state
    )
    assert g["ok"] is True
    g = hand.evaluate_ticket(
        entry_price=0.70,
        side="yes",
        rainman_action="fire",
        volume=5000,
        ticker="KX1",
        state_dir=state,
    )
    assert g["ok"] is False and g["reason"] == "band"
    g = hand.evaluate_ticket(
        entry_price=0.48,
        side="yes",
        rainman_action="fire",
        volume=5000,
        ticker="KX1",
        state_dir=state,
    )
    assert g["ok"] is True
def test_max_same_dir(tmp_path: Path, monkeypatch) -> None:
    state = _state(tmp_path)
    lane.set_usd_lane_armed(True, reason="test", state_dir=state)
    hand.set_hand_live(True, reason="test", state_dir=state)
    kpt.set_kill_switch(False, state_dir=state)
    # room for open slots but same-dir cap = 1
    monkeypatch.setattr(hand, "MAX_OPEN", 3)
    monkeypatch.setattr(hand, "MAX_SAME_DIR", 1)
    night = hand.load_night(state)
    night["open"] = [
        {"ticker": "A", "side": "no", "cost_usd": 0.55},
    ]
    hand.save_night(night, state_dir=state)
    g = hand.evaluate_ticket(
        entry_price=0.52,
        side="no",
        rainman_action="fire",
        volume=9000,
        ticker="C",
        state_dir=state,
    )
    assert g["ok"] is False and g["reason"] == "max_same_dir"


def test_mirror_skip_when_idle(tmp_path: Path) -> None:
    state = _state(tmp_path)
    lane.set_usd_lane_armed(False, reason="test", state_dir=state)
    r = hand.maybe_mirror_paper_bet(
        {
            "ticker": "KX",
            "asset": "BTC",
            "side": "yes",
            "kalshi_yes": 0.58,
            "rainman": {"action": "fire"},
            "volume": 9000,
        },
        state_dir=state,
    )
    assert r["ok"] is False
    assert r["event"] == "usd_skip"


def _arm_test_hand(state: Path) -> None:
    lane.set_usd_lane_armed(True, reason="test", state_dir=state)
    hand.set_hand_live(True, reason="test", state_dir=state)
    kpt.set_kill_switch(False, state_dir=state)


def _paper_bet() -> dict:
    return {
        "ticker": "KX-FILL",
        "asset": "BTC",
        "side": "yes",
        "entry_price": 0.52,
        "price": 0.52,
        "rainman": {"action": "fire", "score": 0.91, "bucket": "55-65"},
        "volume": 9000,
    }


def test_ioc_zero_fill_never_books_position(tmp_path: Path, monkeypatch) -> None:
    state = _state(tmp_path)
    _arm_test_hand(state)
    monkeypatch.setattr(
        kpt.KalshiProdTradeClient,
        "place_limit_order",
        lambda self, **kwargs: {
            "ok": True,
            "dry_run": False,
            "order_id": "unfilled-1",
            "client_order_id": "client-unfilled",
            "fill_count": 0.0,
            "remaining_count": 0.0,
            "price": 0.52,
            "cost_usd": 0.0,
        },
    )
    row = hand.maybe_mirror_paper_bet(_paper_bet(), state_dir=state)
    assert row["event"] == "usd_no_fill"
    assert row["filled"] is False
    assert row["rainman_score"] == pytest.approx(0.91)
    assert hand.load_night(state)["open"] == []


def test_missing_rainman_score_never_reaches_order_client(tmp_path: Path, monkeypatch) -> None:
    state = _state(tmp_path)
    _arm_test_hand(state)
    called = {"value": False}

    def _should_not_place(self, **kwargs):
        called["value"] = True
        raise AssertionError("order client must not run")

    monkeypatch.setattr(kpt.KalshiProdTradeClient, "place_limit_order", _should_not_place)
    bet = _paper_bet()
    bet["rainman"].pop("score")
    row = hand.maybe_mirror_paper_bet(bet, state_dir=state)
    assert row["event"] == "usd_skip"
    assert row["reason"] == "rainman_score_unknown"
    assert called["value"] is False


def test_verified_fill_books_actual_price_fee_and_settles_net(tmp_path: Path, monkeypatch) -> None:
    state = _state(tmp_path)
    _arm_test_hand(state)
    monkeypatch.setattr(
        kpt.KalshiProdTradeClient,
        "place_limit_order",
        lambda self, **kwargs: {
            "ok": True,
            "dry_run": False,
            "order_id": "fill-1",
            "client_order_id": "client-fill",
            "fill_count": 1.0,
            "remaining_count": 0.0,
            "average_fill_price": 0.52,
            "average_fee_paid": 0.01,
            "premium_usd": 0.52,
            "fee_paid_usd": 0.01,
            "cost_usd": 0.59,
            "price": 0.52,
            "filled": True,
        },
    )
    placed = hand.maybe_mirror_paper_bet(_paper_bet(), state_dir=state)
    assert placed["event"] == "usd_place"
    assert placed["filled"] is True
    assert placed["price"] == pytest.approx(0.52)
    assert placed["rainman_score"] == pytest.approx(0.91)
    open_row = hand.load_night(state)["open"][0]
    assert open_row["cost_usd"] == pytest.approx(0.53)
    settled = hand.note_settle_from_paper(
        ticker="KX-FILL", win=True, entry_price=0.52, state_dir=state
    )
    assert settled["pnl_before_fee_usd"] == pytest.approx(0.48)
    assert settled["fee_paid_usd"] == pytest.approx(0.01)
    assert settled["pnl_usd"] == pytest.approx(0.47)
    assert settled["live_unit_pnl"] == pytest.approx(0.47 / 0.53, abs=0.0001)


def test_corrupt_night_state_and_worst_case_loss_fail_closed(tmp_path: Path) -> None:
    state = _state(tmp_path)
    _arm_test_hand(state)
    (state / hand.NIGHT_FILE).write_text("{bad", encoding="utf-8")
    corrupt = hand.evaluate_ticket(
        entry_price=0.52,
        side="yes",
        rainman_action="fire",
        volume=9000,
        ticker="KX-CORRUPT",
        state_dir=state,
    )
    assert corrupt["reason"] == "night_halted"

    # worst-case: day must match today or load_night resets PnL
    from datetime import date

    night = hand.load_night(state)
    night["day"] = date.today().isoformat()
    night["halted"] = False
    night["open"] = []
    night["realized_pnl_usd"] = -4.6
    hand.save_night(night, state_dir=state)
    blocked = hand.evaluate_ticket(
        entry_price=0.52,
        side="yes",
        rainman_action="fire",
        volume=9000,
        ticker="KX-WORST",
        state_dir=state,
    )
    assert blocked["reason"] in ("night_loss_worst_case", "night_loss_stop")


def test_arm_from_owner_go(tmp_path: Path) -> None:
    state = _state(tmp_path)
    out = hand.arm_from_owner_go(
        owner_phrase="YES GREEN — real dollars REAL",
        state_dir=state,
    )
    assert out["ok"] is True
    assert lane.is_usd_lane_armed(state)
    assert hand.is_hand_live(state)
    assert kpt.kill_switch_active(state_dir=state) is False
    sess = json.loads((state / "kalshi_usd_hand_session.json").read_text())
    assert sess["caps"]["band"] == [hand.MIN_ENTRY, hand.MAX_ENTRY]
    assert sess["caps"]["max_open"] == hand.MAX_OPEN
