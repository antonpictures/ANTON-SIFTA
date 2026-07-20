"""r1648 — ledger deal caps (3 open, 2 same dir, EV log)."""

from __future__ import annotations

import json
from pathlib import Path

from System import ledger_deal as ld
from System import kalshi_usd_hand as hand
from System import kalshi_usd_lane as lane
from System import kalshi_prod_trade_client as kpt


def test_caps_frozen() -> None:
    c = ld.caps_dict()
    assert c["max_open"] == ld.MAX_OPEN
    assert c["max_same_dir"] == ld.MAX_SAME_DIR
    # r1686 scalp buy-low band
    assert c["usd_band"] == [0.40, 0.65]
    assert c["fire_only_usd"] is False
    assert c["dual_every_paper_bet"] is True
    assert c["max_night_loss_usd"] == 5.0


def test_persist_deal(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    state.mkdir()
    p = ld.persist_deal(state_dir=state)
    raw = json.loads(p.read_text())
    assert raw["max_open"] == ld.MAX_OPEN
    assert raw["owner_yes"] is True


def test_ev_log_and_pnl_math(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    state.mkdir()
    assert ld.paper_unit_pnl(True, 0.80) == 0.25
    assert ld.paper_unit_pnl(False, 0.80) == -1.0
    assert ld.live_contract_pnl(True, 0.80) == 0.2
    assert ld.live_contract_pnl(False, 0.80) == -0.8
    ld.log_ev_row({"event": "test", "x": 1}, state_dir=state)
    lines = (state / ld.EV_LOG).read_text().strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["event"] == "test"


def test_usd_max_open_three(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    state.mkdir()
    (state / "alice_fee_net_tournament.json").write_text(
        json.dumps({"epoch_active": True, "usd_shadow_only": False}),
        encoding="utf-8",
    )
    from System.alice_fee_net_tournament import write_policy_hash
    write_policy_hash(state_dir=state)
    lane.set_usd_lane_armed(True, reason="t", state_dir=state)
    hand.set_hand_live(True, reason="t", state_dir=state)
    kpt.set_kill_switch(False, state_dir=state)
    night = hand.load_night(state)
    night["open"] = [
        {"ticker": f"T{i}", "side": "yes", "cost_usd": 0.55}
        for i in range(int(hand.MAX_OPEN))
    ]
    hand.save_night(night, state_dir=state)
    g = hand.evaluate_ticket(
        entry_price=0.55,
        side="no",
        rainman_action="fire",
        volume=9000,
        ticker="D",
        state_dir=state,
    )
    assert g["ok"] is False and g["reason"] == "max_open"


def test_hand_imports_deal_band() -> None:
    assert hand.MIN_ENTRY == 0.40
    assert hand.MAX_ENTRY == 0.65
    assert hand.MAX_OPEN == ld.MAX_OPEN
    assert hand.MAX_SAME_DIR == ld.MAX_SAME_DIR
