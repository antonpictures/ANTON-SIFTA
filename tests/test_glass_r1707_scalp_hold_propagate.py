#!/usr/bin/env python3
"""r1707 — glass propagates mode / force_flat / fee-true from settled ledger."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from Applications.sifta_prediction_market import (  # noqa: E402
    glass_kind_label,
    human_portfolio_snapshot,
    propagate_settled_scalp_fields,
)


def test_propagate_settled_scalp_fields() -> None:
    settled = {
        "mode": "scalp_execute",
        "force_flat": True,
        "pnl_usd_fee_true": 0.1523,
        "fees_total": 0.0277,
    }
    out = propagate_settled_scalp_fields(settled)
    assert out["mode"] == "scalp_execute"
    assert out["force_flat"] is True
    assert out["pnl_usd_fee_true"] == 0.1523
    assert out["fees_total"] == 0.0277
    assert out["kind_badge"] == "SCALP"


def test_propagate_hold_defaults() -> None:
    out = propagate_settled_scalp_fields({"result": "settled"})
    assert out["kind_badge"] == "HOLD"
    assert out["pnl_usd_fee_true"] is None or out["mode"]


def test_glass_kind_label_flags() -> None:
    assert "SCALP" in glass_kind_label({"mode": "scalp_execute"})
    assert "HOLD" in glass_kind_label({"mode": "hold_settle"})
    assert "TRAIN" in glass_kind_label({"mode": "stgm_training_only"})
    assert "7:30" in glass_kind_label({"mode": "scalp_execute", "force_flat": True})
    assert "DUAL" in glass_kind_label({"mode": "hold_settle", "dual": True})


def test_snapshot_propagates_scalp_from_settled(tmp_path: Path) -> None:
    """Settled scalp_execute appears in recent_results with fee-true $."""
    state = tmp_path / ".sifta_state"
    state.mkdir()
    settled = {
        "ts": 1_700_000_000.0,
        "ticker": "KXBTC15M-TEST-00",
        "asset": "BTC",
        "side": "yes",
        "label": "UP",
        "price": 0.55,
        "mode": "scalp_execute",
        "force_flat": False,
        "pnl_usd_fee_true": 0.12,
        "fees_total": 0.03,
        "pnl": 0.12,
        "win": True,
        "event": "scalp_exit",
        "result": "scalp_execute",
    }
    with (state / "alice_15m_settled.jsonl").open("w") as f:
        f.write(json.dumps(settled) + "\n")
    # minimal required files
    for name, content in {
        "alice_15m_open_book.json": {"open": []},
        "alice_15m_paper_proof.json": {"n_wins": 0, "n_losses": 0, "history": []},
        "alice_15m_body_stgm_budget.json": {
            "realized_pnl_stgm": 0.0,
            "n_wins": 0,
            "n_losses": 0,
            "open_tickets": {},
        },
        "alice_15m_body_stgm_ledger.jsonl": "",
        "stgm_economy_cache.json": {},
    }.items():
        p = state / name
        if name.endswith(".jsonl"):
            p.write_text(content if isinstance(content, str) else "", encoding="utf-8")
        else:
            p.write_text(json.dumps(content), encoding="utf-8")

    snap = human_portfolio_snapshot(state)
    rows = snap.get("recent_results") or []
    assert rows, "expected scalp_execute row in recent_results"
    hit = next((r for r in rows if r.get("ticker") == "KXBTC15M-TEST-00"), None)
    assert hit is not None
    assert hit.get("mode") == "scalp_execute"
    assert hit.get("kind_badge") == "SCALP"
    assert abs(float(hit.get("pnl_usd_fee_true") or 0) - 0.12) < 1e-9
    assert "SCALP" in glass_kind_label(hit)


if __name__ == "__main__":
    test_propagate_settled_scalp_fields()
    test_propagate_hold_defaults()
    test_glass_kind_label_flags()
    with tempfile.TemporaryDirectory() as td:
        test_snapshot_propagates_scalp_from_settled(Path(td))
    print("ok r1707")
