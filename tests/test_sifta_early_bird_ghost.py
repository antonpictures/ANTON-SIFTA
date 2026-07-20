"""Early-Bird Ghost r1643 — cheap/early counterfactual, paper only."""
from __future__ import annotations

import json
import time
from unittest import mock

from System import swarm_sifta_early_bird_ghost as eb


def _age_book(state, seconds: float) -> None:
    p = state / ".sifta_state" / eb.BIRD_BOOK
    book = json.loads(p.read_text())
    for r in book["open"]:
        r["ts"] = time.time() - seconds
    p.write_text(json.dumps(book))


def test_record_dedupes_and_tags_cheap(tmp_path) -> None:
    ok1 = eb.record_early_bird(
        asset="ZEC",
        ticker="CHEAP1",
        side="yes",
        entry_price=0.55,
        strategy="follow_crowd",
        state_dir=tmp_path,
    )
    ok2 = eb.record_early_bird(
        asset="ZEC",
        ticker="CHEAP1",
        side="yes",
        entry_price=0.55,
        state_dir=tmp_path,
    )
    assert ok1 is True and ok2 is False
    book = json.loads((tmp_path / ".sifta_state" / eb.BIRD_BOOK).read_text())
    row = book["open"][0]
    assert row["cheap"] is True
    assert row["lane"] == "cheap_early"
    assert row["price"] == 0.55


def test_settle_splits_cheap_vs_in_band(tmp_path) -> None:
    # cheap win at 50¢ → +1.0u gross (1/0.5 - 1)
    eb.record_early_bird(
        asset="SOL", ticker="C50", side="yes", entry_price=0.50, state_dir=tmp_path
    )
    # in-band loss at 75¢ → -1.0u
    eb.record_early_bird(
        asset="BTC", ticker="B75", side="no", entry_price=0.75, state_dir=tmp_path
    )
    _age_book(tmp_path, eb.WINDOW_S + eb.SETTLE_GRACE_S + 5)

    def fake_get_json(path, timeout=8.0):
        # C50 yes wins; B75 no loses if result is yes
        return {"market": {"result": "yes"}}

    with mock.patch("System.swarm_kalshi_public_feed._get_json", fake_get_json):
        out = eb.settle_early_bird(state_dir=tmp_path)

    assert out["n_settled"] == 2
    s = eb.early_bird_status(state_dir=tmp_path)
    # cheap win +1.0, in-band loss -1.0 => total 0
    assert abs(s["pnl"] - 0.0) < 1e-6
    assert s["n_cheap"] == 1
    assert abs(s["cheap_pnl"] - 1.0) < 1e-6
    assert s["n_in_band"] == 1
    assert abs(s["in_band_pnl"] - (-1.0)) < 1e-6


def test_status_line_warming(tmp_path) -> None:
    line = eb.status_line(tmp_path)
    assert "EARLY BIRD" in line
    assert "no graded" in line or "warming" in line.lower() or "no graded" in line
