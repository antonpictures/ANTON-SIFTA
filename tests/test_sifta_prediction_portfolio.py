import json
import time
from pathlib import Path
from urllib.error import URLError

import pytest

from Applications.sifta_prediction_market import (
    format_r1648_deal_strip,
    human_portfolio_snapshot,
)
from System import kalshi_portfolio_read


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")


def test_human_portfolio_separates_real_stgm_from_paper_shares(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    _write(
        state / "alice_15m_open_book.json",
        {
            "open": [
                {
                    "ticker": "BTC-1",
                    "asset": "BTC",
                    "label": "DOWN",
                    "price": 0.68,
                    "stake": 1.0,
                    "stgm_stake": 0.0005,
                    "decision_evidence": {
                        "why": "crowd 68% DOWN · spot trend down · shadow learning"
                    },
                }
            ]
        },
    )
    _write(
        state / "alice_15m_body_stgm_budget.json",
        {
            "realized_pnl_stgm": 0.001,
            "n_wins": 5,
            "n_losses": 3,
            "n_settled": 8,
            "open_staked_stgm": 0.0005,
            "max_open_stgm": 0.01,
            "open_tickets": {"BTC-1": {"stake": 0.0005}},
        },
    )
    _write(
        state / "alice_15m_paper_proof.json",
        {"n_wins": 10, "n_losses": 7, "n_settled": 17, "pnl": -2.0},
    )
    _write(
        state / "stgm_economy_cache.json",
        {"spendable_total_stgm": 1145.1, "alice_m5_spendable_stgm": 97.4},
    )
    _append(
        state / "alice_15m_settled.jsonl",
        {
            "ticker": "KXETH15M-26JUL121415-15",
            "decision_evidence": {
                "why": "crowd 80% UP · own trail 61% · proxy chart mixed"
            },
        },
    )
    _append(
        state / "alice_15m_body_stgm_ledger.jsonl",
        {
            "truth_label": "ALICE_15M_BODY_STGM_V2",
            "kind": "loss",
            "ticker": "KXBTC15M-26JUL121415-15",
            "asset": "BTC",
            "label": "UP",
            "price": 0.7,
            "stake": 0.0005,
            "pnl_stgm": -0.0005,
            "ts": 1.0,
        },
    )
    _append(
        state / "alice_15m_body_stgm_ledger.jsonl",
        {
            "truth_label": "ALICE_15M_BODY_STGM_V2",
            "kind": "win",
            "ticker": "KXETH15M-26JUL121415-15",
            "asset": "ETH",
            "label": "DOWN",
            "price": 0.8,
            "stake": 0.0005,
            "pnl_stgm": 0.0005,
            "ts": 2.0,
        },
    )
    _append(
        state / "alice_15m_body_stgm_ledger.jsonl",
        {
            "truth_label": "ALICE_15M_BODY_STGM_V2",
            "kind": "win",
            "ticker": "KXSOL15M-26JUL121415-15",
            "asset": "SOL",
            "label": "DOWN",
            "price": 0.75,
            "stake": 0.0005,
            "pnl_stgm": 0.0005,
            "ts": 3.0,
        },
    )
    snap = human_portfolio_snapshot(state)
    assert snap["body_total_stgm"] == pytest.approx(1145.1)
    assert snap["body_pnl_stgm"] == pytest.approx(0.001)
    assert snap["open_risk_stgm"] == pytest.approx(0.0005)
    assert snap["open"][0]["price_cents"] == pytest.approx(68.0)
    assert snap["open"][0]["paper_shares"] == pytest.approx(1.471, abs=0.001)
    assert "spot trend down" in snap["open"][0]["decision_reason"]
    assert snap["recent_results"][0]["result"] == "WIN"
    assert snap["recent_results"][0]["body_pnl_stgm"] == pytest.approx(0.0005)
    eth_result = next(row for row in snap["recent_results"] if row["asset"] == "ETH")
    assert "proxy chart mixed" in eth_result["decision_reason"]
    # last completed window: wins + losses both available for the panel
    assert snap["last_run_id"] == "26JUL121415-15"
    assert snap["last_run_summary"]["wins"] == 2
    assert snap["last_run_summary"]["losses"] == 1
    assert {r["asset"] for r in snap["last_run_wins"]} == {"ETH", "SOL"}
    assert {r["asset"] for r in snap["last_run_losses"]} == {"BTC"}
    assert len(snap["last_run_wins"]) + len(snap["last_run_losses"]) == 3


def test_human_portfolio_surfaces_stale_reservation_warning(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    _write(state / "alice_15m_open_book.json", {"open": []})
    _write(
        state / "alice_15m_body_stgm_budget.json",
        {"open_tickets": {"GHOST": {"stake": 0.0005}}},
    )
    snap = human_portfolio_snapshot(state)
    assert snap["stale_reservations"] == ["GHOST"]


def test_usd_exchange_tracked_and_stgm_books_stay_separate(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    now = time.time()
    _write(
        state / "alice_15m_open_book.json",
        {
            "open": [
                {
                    "ticker": "STGM-BTC",
                    "asset": "BTC",
                    "label": "UP",
                    "price": 0.82,
                    "stake": 1.0,
                    "stgm_stake": 0.001,
                }
            ]
        },
    )
    _write(
        state / "kalshi_portfolio_cache.json",
        {
            "positions_ok": True,
            "positions_ts": now,
            "positions_last_attempt_ts": now,
            "positions_source": "KALSHI_PROD_GET_/portfolio/positions",
            "positions_stale_after_seconds": 90.0,
            "exchange_positions": [
                {"ticker": "KXBTC15M-A", "position": 1.0},
                {"ticker": "KXETH15M-B", "position": -1.0},
            ],
        },
    )
    _write(
        state / "kalshi_usd_night.json",
        {
            "open": [{"ticker": "KXSOL15M-C", "side": "yes"}],
            "realized_pnl_usd": -0.57,
            "truth_label": "KALSHI_USD_HAND_V1",
        },
    )

    snap = human_portfolio_snapshot(state)
    assert len(snap["open"]) == 1
    assert snap["open"][0]["lane"] == "STGM_PAPER"
    assert snap["open_provenance"] == "STGM_PAPER_NOT_USD"
    assert snap["usd_exchange"]["known"] is True
    assert snap["usd_exchange"]["count"] == 2
    assert snap["usd_exchange"]["positions"][0]["ticker"] == "KXBTC15M-A"
    assert snap["usd_exchange"]["provenance"] == "CONFIRMED_EXCHANGE_READ"
    assert snap["usd_tracked"]["count"] == 1
    assert snap["usd_tracked"]["open"][0]["ticker"] == "KXSOL15M-C"
    assert snap["usd_tracked"]["provenance"] == "LOCAL_TRACKED_ORDER_BOOK_NOT_EXCHANGE"

    text, tooltip = format_r1648_deal_strip(
        snap, hand_status="US $ HAND LIVE · open 1/3"
    )
    for token in ("3 max/2 dir", "USD 70–88 dual FIRE+THIN", "STGM ON", "$1 evidence lock"):
        assert token in text
    assert "EXCHANGE 2/3 FRESH" in text
    assert "TRACKED 1 local" in text
    assert "alice_15m_open_book.json" in tooltip
    assert "LOCAL_TRACKED_ORDER_BOOK_NOT_EXCHANGE" in tooltip


def test_exchange_reconciliation_uses_exact_no_premium_and_fee() -> None:
    result = kalshi_portfolio_read.reconcile_exchange_history(
        [
            {
                "fill_id": "fill-1",
                "order_id": "alice-order-1",
                "ticker": "KXXRP15M-TEST",
                "side": "no",
                "count_fp": "1.00",
                "yes_price_dollars": "0.1300",
                "no_price_dollars": "0.8700",
                "fee_cost": "0.0080",
            }
        ],
        [
            {
                "ticker": "KXXRP15M-TEST",
                "market_result": "no",
                "settled_time": "2026-07-13T13:15:00Z",
            }
        ],
        campaign_order_ids={"alice-order-1"},
    )
    assert result["complete"] is True
    assert result["n_settled_fills"] == 1
    assert result["rows"][0]["selected_side_price"] == pytest.approx(0.87)
    assert result["rows"][0]["pnl_usd"] == pytest.approx(0.122)
    assert result["total_fees_usd"] == pytest.approx(0.008)


class _ReadResponse:
    status = 200

    def __init__(self, payload: dict) -> None:
        self._payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self) -> bytes:
        return self._payload


def _mock_portfolio_auth(monkeypatch: pytest.MonkeyPatch, state: Path) -> None:
    monkeypatch.setattr(kalshi_portfolio_read, "STATE", state)
    monkeypatch.setattr(
        kalshi_portfolio_read,
        "credentials_status",
        lambda: {"ready": True, "note": "ready"},
    )
    monkeypatch.setattr(kalshi_portfolio_read, "load_private_key_pem", lambda: "pem")
    monkeypatch.setattr(kalshi_portfolio_read, "load_api_key_id", lambda: "kid")
    monkeypatch.setattr(kalshi_portfolio_read, "sign_request", lambda *_a, **_kw: "sig")


def test_fetch_positions_uses_exact_prod_get_and_normalizes_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = tmp_path / ".sifta_state"
    _mock_portfolio_auth(monkeypatch, state)
    seen: dict[str, str] = {}

    def _urlopen(request, *, timeout):
        seen["url"] = request.full_url
        seen["method"] = request.get_method()
        assert timeout == 3.0
        return _ReadResponse(
            {
                "market_positions": [
                    {
                        "ticker": "KXBTC15M-OPEN",
                        "position_fp": "1.00",
                        "market_exposure_dollars": "0.8200",
                    },
                    {"ticker": "KXETH15M-FLAT", "position_fp": "0.00"},
                ]
            }
        )

    monkeypatch.setattr(kalshi_portfolio_read, "urlopen", _urlopen)
    result = kalshi_portfolio_read.fetch_positions(timeout=3.0)
    assert result["ok"] is True
    assert seen == {
        "url": "https://external-api.kalshi.com/trade-api/v2/portfolio/positions",
        "method": "GET",
    }
    assert result["positions_count"] == 1
    cache = kalshi_portfolio_read.load_cache()
    assert cache["exchange_positions"][0]["ticker"] == "KXBTC15M-OPEN"
    assert cache["positions_source"] == "KALSHI_PROD_GET_/portfolio/positions"
    status = kalshi_portfolio_read.cache_status(cache)
    assert status["positions"]["known"] is True
    assert status["positions"]["fresh"] is True
    assert status["positions"]["count"] == 1


def test_failed_position_read_preserves_last_good_and_never_fabricates_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = tmp_path / ".sifta_state"
    _mock_portfolio_auth(monkeypatch, state)
    now = time.time()
    _write(
        state / kalshi_portfolio_read.CACHE,
        {
            "positions_ok": True,
            "positions_ts": now,
            "positions_source": "KALSHI_PROD_GET_/portfolio/positions",
            "exchange_positions": [{"ticker": "LAST-GOOD", "position": 1.0}],
        },
    )

    def _fail(*_args, **_kwargs):
        raise URLError("offline")

    monkeypatch.setattr(kalshi_portfolio_read, "urlopen", _fail)
    result = kalshi_portfolio_read.fetch_positions(timeout=1.0)
    assert result["ok"] is False
    assert result["cache_preserved"] is True
    assert result["cached_positions_count"] == 1
    cache = kalshi_portfolio_read.load_cache()
    assert cache["exchange_positions"] == [{"ticker": "LAST-GOOD", "position": 1.0}]
    assert cache["positions_ok"] is False
    assert cache["positions_error"].startswith("network:")
    status = kalshi_portfolio_read.cache_status(cache)
    assert status["positions"]["known"] is True
    assert status["positions"]["count"] == 1
    assert status["positions"]["error"].startswith("network:")

    # With no prior confirmed snapshot, the same failure is unknown, not flat.
    (state / kalshi_portfolio_read.CACHE).unlink()
    missing = kalshi_portfolio_read.fetch_positions(timeout=1.0)
    assert missing["cached_positions_count"] is None
    unknown = kalshi_portfolio_read.cache_status()
    assert unknown["positions"]["known"] is False
    assert unknown["positions"]["count"] is None
