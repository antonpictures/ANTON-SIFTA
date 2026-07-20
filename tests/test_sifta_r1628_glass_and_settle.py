"""r1628 — glass UI writer election + smart settle skip/backoff."""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from System import swarm_sifta_paper_loop as paper_loop
from System.swarm_sifta_paper_loop import (
    _ticket_close_ts_guess,
    _usd_mirror_volume,
    load_open_book,
    register_open_bets,
    settle_paper_from_api,
)
from System.swarm_sifta_paper_monitor import (
    _tail_jsonl,
    should_yield_to_app,
)
from System.swarm_sifta_market import SiftaMarketEngine


def _state(tmp_path: Path) -> Path:
    """Match _state_dir nesting used by the paper loop."""
    d = tmp_path / ".sifta_state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def test_register_open_bets_records_entry_clock(tmp_path: Path) -> None:
    state = _state(tmp_path)
    ts = time.time()
    n = register_open_bets(
        [
            {
                "ok": True,
                "ticker": "KXTEST15M-1",
                "asset": "BTC",
                "side": "yes",
                "label": "UP",
                "kalshi_yes": 0.75,
                "stake": 1.0,
                "stgm_stake": 0.0005,
                "ts": ts,
                "secs": 400,  # ~6m40s left — inside minute-7 window
            }
        ],
        state_dir=state,
    )
    assert n == 1
    book = json.loads((state / "alice_15m_open_book.json").read_text())
    row = book["open"][0]
    assert row["secs_left_at_entry"] == 400
    assert "entry_clock" in row and row["entry_clock"]
    # Unambiguous remaining: NmNNs (not H:MM which looked like a 2nd wall clock)
    assert "6m40s left" in row["entry_clock"]


def _bet(ticker: str, side: str, *, stake: float = 1.0) -> dict:
    return {
        "ok": True,
        "ticker": ticker,
        "asset": "BTC",
        "side": side,
        "label": "UP" if side == "yes" else "DOWN",
        "kalshi_yes": 0.75 if side == "yes" else 0.25,
        "stake": stake,
        "ts": time.time(),
        "secs": 600,
    }


def test_register_open_bets_enforces_caps_and_reports_without_trimming(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    first = [_bet("YES-1", "yes"), _bet("YES-2", "yes")]
    assert register_open_bets(first, state_dir=state) == 2

    same_dir = _bet("YES-3", "yes")
    report: list[dict] = []
    assert register_open_bets([same_dir], state_dir=state, skip_report=report) == 0
    assert same_dir["persistence"]["reason"] == "max_same_dir"
    assert report[0]["reason"] == "max_same_dir"

    assert register_open_bets([_bet("NO-1", "no")], state_dir=state) == 1
    fourth = _bet("NO-2", "no")
    assert register_open_bets([fourth], state_dir=state) == 0
    assert fourth["persistence"]["reason"] == "max_open"

    book = load_open_book(state)
    assert [row["ticker"] for row in book["open"]] == ["YES-1", "YES-2", "NO-1"]
    assert book["last_registration"]["skipped"][0]["reason"] == "max_open"


def test_concurrent_registration_cannot_insert_two_thirds(tmp_path: Path) -> None:
    state = _state(tmp_path)
    assert register_open_bets(
        [_bet("BASE-YES", "yes"), _bet("BASE-NO", "no")], state_dir=state
    ) == 2
    candidates = [_bet("RACE-YES", "yes"), _bet("RACE-NO", "no")]

    with ThreadPoolExecutor(max_workers=2) as pool:
        added = list(
            pool.map(lambda bet: register_open_bets([bet], state_dir=state), candidates)
        )

    book = load_open_book(state)
    assert sum(added) == 1
    assert len(book["open"]) == 3
    assert {row["ticker"] for row in book["open"]}.issuperset(
        {"BASE-YES", "BASE-NO"}
    )
    rejected = [bet for bet in candidates if not bet["persistence"]["ok"]]
    assert len(rejected) == 1
    assert rejected[0]["persistence"]["reason"] == "max_open"


def test_usd_mirror_volume_uses_exchange_field_only() -> None:
    market = SimpleNamespace(
        volume={"alice": 999_999.0},
        kalshi_volume=888_888.0,
        kalshi_volume_24h=777.0,
    )
    assert _usd_mirror_volume(market) == 777.0
    assert _usd_mirror_volume(SimpleNamespace(volume={"alice": 999_999.0})) is None
    assert _usd_mirror_volume(SimpleNamespace(kalshi_volume_24h="unknown")) is None


def test_ticket_close_ts_uses_secs_left() -> None:
    entry = 1_000_000.0
    close = _ticket_close_ts_guess({"ts": entry, "secs_left_at_entry": 600})
    assert close == entry + 600


def test_settle_skips_open_window_without_api(tmp_path: Path) -> None:
    """Tickets still inside the 15m window must not call Kalshi."""
    state = _state(tmp_path)
    now = time.time()
    register_open_bets(
        [
            {
                "ok": True,
                "ticker": "KXTEST15M-OPEN",
                "asset": "ETH",
                "side": "no",
                "label": "DOWN",
                "kalshi_yes": 0.3,
                "stake": 1.0,
                "ts": now,
                "secs": 500,  # ~8:20 left → not due
            }
        ],
        state_dir=state,
    )
    eng = SiftaMarketEngine(seed=1, swarm_size=2, state_dir=state)

    def _boom(*_a, **_k):
        raise AssertionError("API should not be called for early tickets")

    with patch("System.swarm_kalshi_public_feed._get_json", side_effect=_boom):
        out = settle_paper_from_api(eng)
    assert out["n_settled"] == 0
    assert out["skipped_early"] >= 1
    assert out["n_polled"] == 0


def test_settle_hypothetical_usd_uses_thin_ticket_stake(tmp_path: Path) -> None:
    state = _state(tmp_path)
    thin = _bet("KXTEST15M-THIN", "yes", stake=0.5)
    thin["ts"] = time.time() - 1000
    thin["secs"] = 0
    assert register_open_bets([thin], state_dir=state) == 1
    eng = SiftaMarketEngine(seed=2, swarm_size=2, state_dir=state)

    with patch(
        "System.swarm_kalshi_public_feed._get_json",
        return_value={"market": {"result": "no", "status": "settled"}},
    ):
        out = settle_paper_from_api(eng)

    assert out["n_settled"] == 1
    row = out["settled"][0]
    assert row["stake"] == 0.5
    assert row["if_real_usd"] == -0.5


def test_paper_cycle_calls_periodic_audit_once_fail_soft(tmp_path: Path) -> None:
    state = _state(tmp_path)
    engine = SimpleNamespace(state_dir=state)
    proof = {
        "pnl": 0.0,
        "n_settled": 0,
        "n_wins": 0,
        "n_losses": 0,
        "proven": False,
    }
    with (
        patch.object(paper_loop, "load_open_book", return_value={"open": []}),
        patch.object(
            paper_loop,
            "settle_paper_from_api",
            return_value={"n_settled": 0, "n_open": 0},
        ),
        patch.object(paper_loop, "paper_bet_15m", return_value={"n_bets": 0, "bets": [], "skipped": []}),
        patch.object(paper_loop, "load_proof", return_value=proof),
        patch.object(paper_loop, "write_alice_report"),
        patch("System.alice_15m_body_stgm.reconcile_reservations"),
        patch("System.kalshi_usd_hand.status_line", return_value="US $ HAND OFF"),
        patch(
            "System.ledger_deal.maybe_write_periodic_audit",
            create=True,
            return_value={"wrote": True, "segment": "morning"},
        ) as audit,
    ):
        out = paper_loop.paper_loop_tick(engine)

    audit.assert_called_once_with(state_dir=state)
    assert out["periodic_audit"] == {"wrote": True, "segment": "morning"}


def test_tail_jsonl_seek_not_full_file(tmp_path: Path) -> None:
    p = tmp_path / "big.jsonl"
    # write many lines
    with p.open("w", encoding="utf-8") as f:
        for i in range(500):
            f.write(json.dumps({"i": i, "payload": "x" * 50}) + "\n")
    rows = _tail_jsonl(p, max_lines=5)
    assert len(rows) == 5
    assert rows[-1]["i"] == 499


def test_should_not_yield_after_glass_open(tmp_path: Path) -> None:
    state = _state(tmp_path)
    receipts = state / "sifta_market_app_receipts.jsonl"
    with receipts.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "ts": time.time(),
                    "event": "open",
                    "mode": "glass_only_r1628",
                    "writer": "headless_monitor",
                }
            )
            + "\n"
        )
        f.write(
            json.dumps({"ts": time.time(), "event": "paper_loop_off", "reason": "r1628"})
            + "\n"
        )
    assert should_yield_to_app(state_dir=state) is False
