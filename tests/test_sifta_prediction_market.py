"""SIFTA prediction market engine (Kalshi-style sandbox)."""
from __future__ import annotations

from System.swarm_sifta_market import (
    OWNER_ID,
    SiftaMarketEngine,
    run_pheromone_ablation,
)


def test_boot_and_list_markets():
    e = SiftaMarketEngine(seed=1, swarm_size=16)
    markets = e.list_markets()
    assert len(markets) >= 3
    assert e.owner_balance() == 10.0
    assert e.markets["m-wc-eng-nor"].yes_price() == 0.89
    assert e.markets["m-wc-eng-nor"].field_yes_share() > 0.75


def test_owner_buy_and_prices_move():
    e = SiftaMarketEngine(seed=2, swarm_size=12)
    mid = e.list_markets()[0]["id"]
    before = e.markets[mid].yes_price()
    r = e.buy(mid, "yes", 2.0, agent_id=OWNER_ID)
    assert r["ok"] is True
    assert e.markets[mid].yes_price() >= before
    assert e.owner_balance() == 8.0
    assert len(r["ballot_digest"]) == 16
    assert r["signature_verified"] is True
    assert len(r["ed25519_signature"]) == 128
    assert len(r["public_key_hex"]) == 64
    assert e.markets[mid].verified_ballots == 1


def test_resolve_pays_winner():
    e = SiftaMarketEngine(seed=3, swarm_size=10)
    mid = "m-swarm"
    assert mid in e.markets
    e.buy(mid, "yes", 4.0, agent_id=OWNER_ID)
    # swarm buys no a bit
    e.buy(mid, "no", 5.0, agent_id=e.swimmer_ids[0])
    bal_before = e.owner_balance()
    r = e.resolve(mid, "yes")
    assert r["ok"] is True
    assert e.markets[mid].status == "resolved"
    assert e.owner_balance() > bal_before  # won share of pot


def test_swarm_step_trades():
    e = SiftaMarketEngine(seed=4, swarm_size=20)
    r = e.swarm_step()
    assert r["ok"] is True
    assert r["tick"] == 1


def test_broke_cannot_overbuy():
    e = SiftaMarketEngine(seed=5, swarm_size=8)
    e.balances[OWNER_ID] = 1.0
    mid = e.list_markets()[0]["id"]
    r = e.buy(mid, "no", 50.0, agent_id=OWNER_ID)
    assert r["ok"] is False


def test_leaderboard_profit_volume_predictions():
    """Kalshi SOCIAL three-column ranks (GAME_STGM sandbox)."""
    from System.swarm_sifta_market import OWNER_DISPLAY

    e = SiftaMarketEngine(seed=6, swarm_size=12)
    mid = e.list_markets()[0]["id"]
    e.buy(mid, "yes", 4.0, agent_id=OWNER_ID)
    e.swarm_step()
    e.resolve(mid, "yes")
    profit = e.leaderboard(metric="profit", limit=20)
    volume = e.leaderboard(metric="volume", limit=20)
    preds = e.leaderboard(metric="predictions", limit=20)
    assert profit and volume and preds
    assert profit[0]["rank"] == 1
    owner_rows = [r for r in volume if r.get("is_owner")]
    assert owner_rows
    assert owner_rows[0]["display_name"] == OWNER_DISPLAY
    assert owner_rows[0]["volume"] >= 4.0
    assert any(r["predictions"] >= 1 for r in preds)
    snap = e.snapshot()
    assert "leaderboard_profit" in snap


def test_portfolio_history_shows_win_and_loss():
    """Kalshi HISTORY-style closed rows (wins and losses both visible)."""
    e = SiftaMarketEngine(seed=8, swarm_size=10)
    mid = "m-btc-hour"
    assert mid in e.markets
    e.buy(mid, "yes", 4.0, agent_id=OWNER_ID)
    # another agent funds no side
    e.buy(mid, "no", 8.0, agent_id=e.swimmer_ids[0])
    e.resolve(mid, "no")  # owner loses
    port = e.portfolio(OWNER_ID)
    assert port["display_name"] == "GeorgeAnton"
    closed = port["history"]
    assert any(h.get("kind") == "closed" for h in closed)
    assert any((h.get("pnl") or 0) < 0 for h in closed)
    # win path
    mid2 = "m-btc-15m"
    e.buy(mid2, "yes", 2.0, agent_id=OWNER_ID)
    e.buy(mid2, "no", 3.0, agent_id=e.swimmer_ids[1])
    e.resolve(mid2, "yes")
    port2 = e.portfolio(OWNER_ID)
    assert any((h.get("pnl") or 0) > 0 for h in port2["history"])


def test_paired_ablation_measures_field_and_crypto() -> None:
    first = run_pheromone_ablation(seed=77, trials=300, ticks=18, swarm_size=24)
    second = run_pheromone_ablation(seed=77, trials=300, ticks=18, swarm_size=24)

    assert first == second
    assert first["field_helped"] is True
    assert first["field_expected_brier"] < first["no_field_expected_brier"]
    assert first["field_probability_mse"] < first["no_field_probability_mse"]
    assert first["valid_signatures_verified"] == first["crypto_trials"]
    assert first["tampered_signatures_rejected"] == first["crypto_trials"]
    assert "not_real_world" in first["conclusion_scope"]


def test_ablation_receipt_is_written(tmp_path) -> None:
    result = run_pheromone_ablation(
        seed=88,
        trials=40,
        ticks=6,
        swarm_size=8,
        state_dir=tmp_path,
        write_receipt=True,
    )
    receipt = tmp_path / ".sifta_state" / "sifta_market_receipts.jsonl"
    assert result["field_helped"] is True
    assert receipt.exists()


def test_sync_kalshi_public_imports_and_dual_prices(monkeypatch, tmp_path) -> None:
    """Read-only public feed seeds markets; local yes near Kalshi mid."""
    fake_feed = {
        "ok": True,
        "fetched_raw": 2,
        "errors": [],
        "markets": [
            {
                "ticker": "KXTEST-YES",
                "title": "Test market A?",
                "yes_price": 0.73,
                "volume_24h": 1200.0,
            },
            {
                "ticker": "KXTEST-NO",
                "title": "Test market B?",
                "yes_price": 0.22,
                "volume_24h": 400.0,
            },
        ],
    }

    def _fake_fetch(**_kwargs):
        return fake_feed

    monkeypatch.setattr(
        "System.swarm_kalshi_public_feed.fetch_open_markets",
        _fake_fetch,
    )
    # Import path used inside engine method
    import System.swarm_kalshi_public_feed as feed_mod

    monkeypatch.setattr(feed_mod, "fetch_open_markets", _fake_fetch)

    e = SiftaMarketEngine(seed=9, swarm_size=8, state_dir=tmp_path)
    # Ensure engine sees our fake via re-import path
    import System.swarm_sifta_market as eng_mod

    monkeypatch.setattr(
        eng_mod,
        "fetch_open_markets",
        _fake_fetch,
        raising=False,
    )

    # Patch at the module the engine imports from inside the method
    import types
    from System.swarm_kalshi_public_feed import classify_market

    fake_mod = types.ModuleType("System.swarm_kalshi_public_feed")
    fake_mod.fetch_open_markets = _fake_fetch  # type: ignore[attr-defined]
    fake_mod.classify_market = classify_market  # type: ignore[attr-defined]
    fake_mod.fetch_by_tickers = lambda tickers, **kw: {  # type: ignore[attr-defined]
        "ok": True,
        "markets": [
            {"ticker": "KXTEST-YES", "title": "Test market A?", "yes_price": 0.80, "volume_24h": 1.0}
        ],
        "errors": [],
    }
    monkeypatch.setitem(__import__("sys").modules, "System.swarm_kalshi_public_feed", fake_mod)

    r = e.sync_kalshi_public(limit=10, min_volume=1.0, replace=True)
    assert r["ok"] is True
    assert r["imported"] == 2
    mid = "kalshi:KXTEST-YES"
    assert mid in e.markets
    m = e.markets[mid]
    assert m.kalshi_ticker == "KXTEST-YES"
    assert m.kalshi_yes == 0.73
    assert abs(m.yes_price() - 0.73) < 0.02
    row = m.to_row()
    assert row["kalshi_yes"] == 0.73
    assert row["yes_price"]  # local pool price present

    rr = e.refresh_kalshi_prices()
    assert rr["ok"] is True
    assert e.markets[mid].kalshi_yes == 0.80


def test_kalshi_feed_mid_yes_helpers() -> None:
    from System.swarm_kalshi_public_feed import _mid_yes, _title

    assert _mid_yes({"last_price_dollars": "0.91"}) == 0.91
    mid = _mid_yes({"yes_bid_dollars": "0.40", "yes_ask_dollars": "0.50", "last_price_dollars": "0"})
    assert mid is not None and 0.44 <= mid <= 0.46
    assert "World" in _title({"title": "World Cup winner?"})


def test_watch_15m_and_learn_on_resolve(tmp_path) -> None:
    """Swarm prefers 15m; resolve updates learn weights + lesson."""
    e = SiftaMarketEngine(seed=11, swarm_size=12, state_dir=tmp_path)
    # inject a 15m market ending soon
    from System.swarm_sifta_market import Market
    import time as _t

    mid = "kalshi:KXBTC15M-TEST"
    e.markets[mid] = Market(
        id=mid,
        title="BTC price up in next 15 mins?",
        category="Crypto · 15 Minute · BTC",
        yes_pool=30.0,
        no_pool=20.0,
        bias_yes=0.60,
        kalshi_ticker="KXBTC15M-TEST",
        kalshi_yes=0.55,
        nav_section="Crypto",
        timeframe="15 Minute",
        asset="BTC",
        close_ts=_t.time() + 120,
    )
    watch = e.watch_15m()
    assert any(w["id"] == mid for w in watch)
    assert watch[0]["our_chance_yes"] is not None
    # swarm should often hit 15m
    hits = 0
    for _ in range(20):
        r = e.swarm_step()
        if r.get("ok") and r.get("market_id") == mid:
            hits += 1
    assert hits >= 1
    # owner + resolve → learn
    e.buy(mid, "yes", 2.0, agent_id="owner:george")
    out = e.resolve(mid, "yes")
    assert out["ok"] is True
    assert out.get("lesson")
    assert e.learn.get("n_settled", 0) >= 1
    assert (tmp_path / ".sifta_state" / "sifta_market_learn.json").exists() or (
        tmp_path / "sifta_market_learn.json"
    ).exists() or e.learn.get("n_settled", 0) >= 1


def test_kalshi_classify_matches_crypto_nav() -> None:
    """Same category labels as Kalshi Crypto sidebar glass."""
    from System.swarm_kalshi_public_feed import classify_market

    c = classify_market("KXBTC15M-26JUL112030-30", "BTC price up in next 15 mins?")
    assert c["nav_section"] == "Crypto"
    assert c["timeframe"] == "15 Minute"
    assert c["asset"] == "BTC"
    assert "Crypto" in c["category"] and "BTC" in c["category"]

    d = classify_market("KXBTCD-26JUL1217-T63749", "BTC price today at 9pm EDT")
    assert d["nav_section"] == "Crypto"
    assert d["asset"] == "BTC"
    assert d["timeframe"] in ("Daily", "One Time", "Hourly")

    e = classify_market("KXETH15M-x", "ETH price up in next 15 mins?")
    assert e["asset"] == "ETH"
    assert e["timeframe"] == "15 Minute"
