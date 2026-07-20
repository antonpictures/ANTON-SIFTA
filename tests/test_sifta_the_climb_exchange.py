"""THE CLIMB accepts only strict Alice-linked exchange reconciliation."""

from __future__ import annotations

import json
import time
from pathlib import Path

from System import sifta_the_climb as climb


def _state(tmp_path: Path) -> Path:
    state = tmp_path / ".sifta_state"
    state.mkdir(parents=True, exist_ok=True)
    return state


def _cache(state: Path, rows: list[dict], *, complete: bool = True) -> None:
    state.joinpath("kalshi_portfolio_cache.json").write_text(
        json.dumps(
            {
                "balance_usd": 100.0,
                "history_ts": time.time(),
                "history_stale_after_seconds": 90,
                "history_source": "KALSHI_PROD_GET_/portfolio/fills+GET_/portfolio/settlements",
                "exchange_reconciliation": {
                    "source": "alice_order_id_exchange_reconciliation",
                    "rows": rows,
                    "complete": complete,
                    "n_local_orders_missing_exchange_fill": 0,
                    "n_unsettled_fills": 0,
                },
            }
        ),
        encoding="utf-8",
    )


def _clean_audit() -> dict:
    return {"verdict": "CLEAN", "findings": [], "n_graded_settles": 100}


def test_broad_exchange_argument_cannot_unlock_ladder(tmp_path: Path) -> None:
    state = _state(tmp_path)
    result = climb.evaluate(
        audit_data=_clean_audit(),
        exchange_truth={
            "n_settlements": 1000,
            "live_ev_per_ticket": 0.99,
            "total_realized_usd": 990,
        },
        state_dir=state,
    )
    assert result["gates_to_next"]["fills"] == "0/100"
    assert result["gates_to_next"]["ev"] is None
    assert result["promotion_earned"] is False


def test_negative_alice_receipts_block_promotion(tmp_path: Path) -> None:
    state = _state(tmp_path)
    rows = [
        {"pnl_usd": -0.07, "won": False, "count": 1.0}
        for _ in range(100)
    ]
    _cache(state, rows)
    result = climb.evaluate(audit_data=_clean_audit(), state_dir=state)
    gates = result["gates_to_next"]
    assert gates["fills_ok"] is True
    assert gates["ev_ok"] is False
    assert gates["confidence_ok"] is False
    assert result["promotion_earned"] is False


def test_every_gate_including_confidence_and_capacity_is_required(tmp_path: Path) -> None:
    state = _state(tmp_path)
    rows = [
        {"pnl_usd": 0.08 if i % 2 else 0.06, "won": True, "count": 2.0}
        for i in range(100)
    ]
    _cache(state, rows)
    result = climb.evaluate(audit_data=_clean_audit(), state_dir=state)
    gates = result["gates_to_next"]
    assert gates["ev_ok"] is True
    assert gates["confidence_ok"] is True
    assert gates["exchange_truth_ok"] is True
    assert gates["capacity_ok"] is True
    assert gates["bankroll_ok"] is True
    assert result["promotion_earned"] is True


def test_incomplete_reconciliation_blocks_even_positive_sample(tmp_path: Path) -> None:
    state = _state(tmp_path)
    _cache(
        state,
        [{"pnl_usd": 0.10, "won": True, "count": 2.0} for _ in range(100)],
        complete=False,
    )
    result = climb.evaluate(audit_data=_clean_audit(), state_dir=state)
    assert result["gates_to_next"]["exchange_truth_ok"] is False
    assert result["promotion_earned"] is False
