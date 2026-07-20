"""Ghost Twin control-group contract (r1638) — paper only, no real $."""
from __future__ import annotations

import json
import time
from unittest import mock

from System import swarm_sifta_ghost_twin as gt


def _age_book(state, seconds: float) -> None:
    p = state / ".sifta_state" / gt.GHOST_BOOK
    book = json.loads(p.read_text())
    for r in book["open"]:
        r["ts"] = time.time() - seconds
    p.write_text(json.dumps(book))


def test_record_dedupes_by_ticker(tmp_path) -> None:
    ok1 = gt.record_ghost(asset="BTC", ticker="T1", side="no", entry_price=0.81,
                          real_action="sit", real_stake=0.0, state_dir=tmp_path)
    ok2 = gt.record_ghost(asset="BTC", ticker="T1", side="no", entry_price=0.81,
                          real_action="sit", real_stake=0.0, state_dir=tmp_path)
    assert ok1 is True and ok2 is False


def test_settle_grades_sits_and_computes_edge_value(tmp_path) -> None:
    # sat ticket that LOSES -> correct sit, ghost eats -1, real ate 0
    gt.record_ghost(asset="ETH", ticker="SAT1", side="no", entry_price=0.72,
                    real_action="sit", real_stake=0.0, state_dir=tmp_path)
    # fired ticket that WINS at 80c -> ghost +0.25, real +0.25 (same stake)
    gt.record_ghost(asset="SOL", ticker="FIRE1", side="no", entry_price=0.80,
                    real_action="fire", real_stake=1.0, state_dir=tmp_path)
    _age_book(tmp_path, gt.WINDOW_S + gt.SETTLE_GRACE_S + 5)

    def fake_get_json(path, timeout=8.0):
        return {"market": {"result": "yes" if "SAT1" in path else "no"}}

    with mock.patch("System.swarm_kalshi_public_feed._get_json", fake_get_json):
        out = gt.settle_ghost(state_dir=tmp_path)

    assert out["n_settled"] == 2
    s = gt.ghost_status(state_dir=tmp_path)
    # ghost: SAT1 lost (-1.0), FIRE1 won (+0.25) => ghost pnl -0.75
    assert abs(s["ghost_pnl"] - (-0.75)) < 1e-6
    # real: SAT1 0.0, FIRE1 +0.25 => edge value = 0.25 - (-0.75) = +1.0
    assert abs(s["edge_field_value"] - 1.0) < 1e-6
    assert s["sit_n"] == 1 and s["sit_correct"] == 1 and s["sit_accuracy"] == 1.0


def test_unresolved_ticket_stays_open_then_voids(tmp_path) -> None:
    gt.record_ghost(asset="XRP", ticker="PEND1", side="yes", entry_price=0.75,
                    real_action="thin", real_stake=0.5, state_dir=tmp_path)
    _age_book(tmp_path, gt.WINDOW_S + gt.SETTLE_GRACE_S + 5)

    with mock.patch("System.swarm_kalshi_public_feed._get_json",
                    lambda p, timeout=8.0: {"market": {"result": ""}}):
        out = gt.settle_ghost(state_dir=tmp_path)
    assert out["n_settled"] == 0 and out["n_open"] == 1

    _age_book(tmp_path, 3700)  # past void horizon
    with mock.patch("System.swarm_kalshi_public_feed._get_json",
                    lambda p, timeout=8.0: {"market": {"result": ""}}):
        out = gt.settle_ghost(state_dir=tmp_path)
    assert out["n_open"] == 0  # voided, not graded


def test_status_line_renders(tmp_path) -> None:
    assert "no graded candidates" in gt.status_line(tmp_path)
