import json
from pathlib import Path

import pytest

from System import alice_15m_body_stgm as body
from System import swarm_sifta_paper_loop as paper


def _state(tmp_path: Path, *, total: float = 1145.0, m5: float = 97.0) -> Path:
    state = tmp_path / ".sifta_state"
    state.mkdir()
    (state / "stgm_economy_cache.json").write_text(
        json.dumps(
            {
                "spendable_total_stgm": total,
                "alice_m5_spendable_stgm": m5,
                "canonical_wallet_balances": {"ALICE_M5": m5},
            }
        ),
        encoding="utf-8",
    )
    return state


def test_stake_reserves_without_touching_repair_log(tmp_path: Path) -> None:
    state = _state(tmp_path)
    repair = tmp_path / "repair_log.jsonl"
    out = body.stake_body_stgm(
        ticker="BTC-1", asset="BTC", label="UP", price=0.6, state_dir=state
    )
    assert out["ok"] and out["stake"] == pytest.approx(body.STGM_STAKE)
    assert not repair.exists()
    budget = json.loads((state / body.BUDGET_NAME).read_text())
    assert budget["open_staked_stgm"] == pytest.approx(body.STGM_STAKE)


def test_duplicate_stake_and_settlement_are_idempotent(monkeypatch, tmp_path: Path) -> None:
    state = _state(tmp_path)
    repair = tmp_path / "repair_log.jsonl"
    first = body.stake_body_stgm(
        ticker="ETH-1", asset="ETH", label="DOWN", price=0.4, state_dir=state
    )
    second = body.stake_body_stgm(
        ticker="ETH-1", asset="ETH", label="DOWN", price=0.4, state_dir=state
    )
    assert first["ok"] and second["duplicate"]
    calls = []
    monkeypatch.setattr(
        body,
        "_burn_loss",
        lambda **kwargs: calls.append(kwargs) or {"spent_stgm": body.STGM_STAKE, "signed": True},
    )
    one = body.settle_body_stgm(
        ticker="ETH-1", asset="ETH", label="DOWN", price=0.4, win=False,
        state_dir=state, repair_log=repair,
    )
    two = body.settle_body_stgm(
        ticker="ETH-1", asset="ETH", label="DOWN", price=0.4, win=False,
        state_dir=state, repair_log=repair,
    )
    assert one["pnl_stgm"] == pytest.approx(-body.STGM_STAKE)
    assert two["duplicate"] is True
    assert len(calls) == 1


def test_win_uses_existing_receipted_work_lane(monkeypatch, tmp_path: Path) -> None:
    state = _state(tmp_path)
    # r1629: use in-band 74¢ so dollar-parity mult applies
    body.stake_body_stgm(
        ticker="SOL-1", asset="SOL", label="UP", price=0.74, state_dir=state
    )
    monkeypatch.setattr(
        body,
        "_reward_win",
        lambda ticker, amount_stgm=None, **kw: {
            "minted_stgm": amount_stgm if amount_stgm is not None else body.STGM_WIN_REWARD,
            "source_receipt_id": ticker,
        },
    )
    out = body.settle_body_stgm(
        ticker="SOL-1", asset="SOL", label="UP", price=0.74, win=True,
        state_dir=state, repair_log=tmp_path / "repair_log.jsonl",
    )
    # Asymmetric: win < full stake at 74¢
    assert out["ok"] and 0 < float(out["pnl_stgm"]) < body.STGM_STAKE


def test_floors_and_open_cap_fail_closed(tmp_path: Path) -> None:
    low = _state(tmp_path, total=1099.0, m5=97.0)
    ok, reason = body.can_stake_body_stgm(state_dir=low)
    assert not ok and reason.startswith("floor_total_")


def test_night_loss_cap_halts_before_overspend(monkeypatch, tmp_path: Path) -> None:
    state = _state(tmp_path)
    budget = body._fresh_budget()
    budget["realized_pnl_stgm"] = -body.STGM_NIGHT_MAX_LOSS + body.STGM_STAKE / 2
    body._save_budget(budget, state)
    ok, reason = body.can_stake_body_stgm(state_dir=state)
    assert not ok and reason.startswith("night_max_loss_")


def test_existing_paper_ticket_is_upgraded_with_body_stake(tmp_path: Path) -> None:
    state = _state(tmp_path)
    paper.save_open_book(
        {"open": [{"ticker": "BTC-OLD", "asset": "BTC", "stake": 1.0}]},
        state_dir=state,
    )
    added = paper.register_open_bets(
        [{
            "ok": True,
            "ticker": "BTC-OLD",
            "asset": "BTC",
            "stgm_stake": body.STGM_STAKE,
            "body_stgm": {"ok": True, "stake": body.STGM_STAKE},
        }],
        state_dir=state,
    )
    assert added == 0
    row = paper.load_open_book(state)["open"][0]
    assert row["stgm_stake"] == pytest.approx(body.STGM_STAKE)
    assert row["body_stgm"]["ok"] is True


def test_reconcile_releases_settled_and_stale_reservations_without_wallet_write(
    monkeypatch, tmp_path: Path
) -> None:
    state = _state(tmp_path)
    budget = body._fresh_budget()
    budget["open_tickets"] = {
        "SETTLED": {"stake": body.STGM_STAKE, "reserved_ts": 10.0},
        "STALE": {"stake": body.STGM_STAKE, "reserved_ts": 10.0},
        "ACTIVE": {"stake": body.STGM_STAKE, "reserved_ts": 10.0},
    }
    budget["open_staked_stgm"] = body.STGM_STAKE * 3
    body._save_budget(budget, state)
    body._append_event(
        {"truth_label": body.TRUTH, "kind": "win", "ticker": "SETTLED"}, state
    )
    out = body.reconcile_reservations(
        {"ACTIVE"}, state_dir=state, now=4000.0, stale_after_s=100.0
    )
    assert out["released"] == 2
    assert out["wallet_mutation"] is False
    after = body._load_budget(state)
    assert set(after["open_tickets"]) == {"ACTIVE"}
    assert after["open_staked_stgm"] == pytest.approx(body.STGM_STAKE)
