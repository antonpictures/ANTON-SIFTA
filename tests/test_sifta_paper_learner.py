"""Regression proof for Alice's paper-only 15-minute learning loop."""
from __future__ import annotations

import json
import random

from System.swarm_sifta_market import SiftaMarketEngine
from System.swarm_sifta_paper_learner import (
    choose,
    learn,
    learn_status,
    load_model,
    save_model,
    rebuild_from_unique_settlements,
)
from System.swarm_sifta_paper_loop import save_open_book, settle_paper_from_api


def _settled_model(*, follow: float, fade: float) -> dict:
    return {
        "truth_label": "SIFTA_PAPER_LEARNER_V1",
        "token": "PAPER_UNIT",
        "assets": {
            "BTC": {
                "follow_crowd": {
                    "strength": follow,
                    "wins": 10,
                    "losses": 2,
                    "pnl": 4.0,
                },
                "fade_crowd": {
                    "strength": fade,
                    "wins": 2,
                    "losses": 10,
                    "pnl": -4.0,
                },
            }
        },
        "recent": [1] * 20,
        "n_updates": 60,
        "n_explore": 8,
        "stability": "stable",
    }


def test_choose_uses_the_stronger_asset_trail() -> None:
    follow = choose(
        "BTC",
        0.70,
        model=_settled_model(follow=5.0, fade=0.05),
        rng=random.Random(10),
    )
    assert follow["action"] == "bet"
    assert follow["strategy"] == "follow_crowd"
    assert follow["side"] == "yes"

    fade_model = _settled_model(follow=0.05, fade=5.0)
    fade_model["assets"]["BTC"]["fade_crowd"]["pnl"] = 4.0
    fade = choose(
        "BTC",
        0.70,
        model=fade_model,
        rng=random.Random(10),
    )
    assert fade["strategy"] == "fade_crowd"
    assert fade["side"] == "no"


def test_win_and_loss_update_and_persist_the_trail(tmp_path) -> None:
    won = learn("ETH", "fade_crowd", True, 1.25, ticker="ETH-WIN", state_dir=tmp_path)
    after_win = load_model(tmp_path)
    strength_after_win = after_win["assets"]["ETH"]["fade_crowd"]["strength"]
    assert won["win"] is True
    assert strength_after_win > 1.0

    lost = learn("ETH", "fade_crowd", False, -1.0, ticker="ETH-LOSS", state_dir=tmp_path)
    after_loss = load_model(tmp_path)
    assert lost["win"] is False
    assert after_loss["assets"]["ETH"]["fade_crowd"]["strength"] < strength_after_win
    assert after_loss["assets"]["ETH"]["fade_crowd"]["wins"] == 1
    assert after_loss["assets"]["ETH"]["fade_crowd"]["losses"] == 1
    assert (tmp_path / ".sifta_state" / "alice_15m_learner.jsonl").exists()


def test_weak_losing_asset_can_learn_to_sit_out(tmp_path) -> None:
    model = _settled_model(follow=0.10, fade=0.12)
    model["assets"]["BTC"]["follow_crowd"]["pnl"] = -3.0
    model["assets"]["BTC"]["fade_crowd"]["pnl"] = -3.0
    save_model(model, state_dir=tmp_path)

    decision = choose("BTC", 0.62, state_dir=tmp_path, rng=random.Random(1))
    assert decision["action"] == "sit_out"
    assert decision["asset_pnl"] == -6.0


def test_settlement_credits_the_exact_strategy(monkeypatch, tmp_path) -> None:
    import System.swarm_kalshi_public_feed as feed

    monkeypatch.setattr(
        feed,
        "_get_json",
        lambda *_args, **_kwargs: {"market": {"result": "yes", "status": "finalized"}},
    )
    engine = SiftaMarketEngine(seed=1626, swarm_size=8, state_dir=tmp_path)
    save_open_book(
        {
            "truth_label": "SIFTA_PAPER_LOOP_V2",
            "token": "PAPER_UNIT",
            "open": [
                {
                    "asset": "SOL",
                    "ticker": "KXSOL15M-TEST",
                    "side": "yes",
                    "label": "UP",
                    "kalshi_yes": 0.60,
                    "price": 0.60,
                    "stake": 1.0,
                    "strategy": "fade_crowd",
                    "explored": True,
                    "decision_evidence": {
                        "why": "crowd 60% UP · proxy spot trend up",
                        "spot": {
                            "predicted_side": "UP",
                            "features": {
                                "signal_strength": 0.6,
                                "regime": "trend_up",
                            },
                            "source": "Coinbase proxy",
                        },
                    },
                }
            ],
        },
        state_dir=tmp_path,
    )

    result = settle_paper_from_api(engine)
    model = load_model(tmp_path)
    status = learn_status(tmp_path)

    assert result["n_settled"] == 1
    assert result["settled"][0]["strategy"] == "fade_crowd"
    assert model["assets"]["SOL"]["fade_crowd"]["wins"] == 1
    assert model["n_explore"] == 1
    assert status["n_updates"] == 1
    assert result["settled"][0]["decision_evidence"]["why"].startswith("crowd")
    eval_rows = (
        tmp_path / ".sifta_state" / "alice_crypto_behavior_eval.jsonl"
    ).read_text(encoding="utf-8").splitlines()
    assert len(eval_rows) == 1


def test_empty_market_monitor_still_reports_loop_state(monkeypatch) -> None:
    import Applications.sifta_prediction_market as app_module

    class Label:
        def __init__(self) -> None:
            self.text = ""

        def setText(self, value: str) -> None:  # noqa: N802 - Qt-shaped test double
            self.text = value

    class Monitor:
        def __init__(self) -> None:
            self.items: list[str] = []

        def isHidden(self) -> bool:  # noqa: N802 - Qt-shaped test double
            return False

        def clear(self) -> None:
            self.items.clear()

        def addItem(self, value: str) -> None:  # noqa: N802 - Qt-shaped test double
            self.items.append(value)

    class Engine:
        markets: dict = {}

        @staticmethod
        def watch_15m(*, limit: int) -> list:
            assert limit == 12
            return []

    class Tabs:
        @staticmethod
        def currentIndex() -> int:  # noqa: N802 - Qt-shaped test double
            return 1

    fake = type("FakeWidget", (), {})()
    fake.ab_monitor = Monitor()
    fake.ab_results = Label()
    fake.ab_status = Label()
    fake.engine = Engine()
    fake.tabs = Tabs()
    fake.paper_loop_on = True
    fake._refresh_learn_state = lambda: None
    monkeypatch.setattr(
        app_module,
        "load_proof",
        lambda *_args, **_kwargs: {
            "n_wins": 2,
            "n_losses": 1,
            "pnl": 0.5,
            "n_settled": 3,
            "proven": False,
        },
    )

    app_module.SiftaPredictionMarketWidget._refresh_autobet_monitor(fake)

    assert fake.ab_status.text.startswith("Paper @ minute 11: On")
    assert "2W/1L" in fake.ab_results.text
    assert fake.ab_monitor.items == ["No 15m — Sync"]


def test_learner_rebuild_uses_each_ticker_once(tmp_path) -> None:
    state = tmp_path / ".sifta_state"
    state.mkdir(parents=True)
    rows = [
        {
            "ticker": "BTC-A",
            "asset": "BTC",
            "win": True,
            "pnl": 0.25,
            "strategy": "follow_crowd",
            "ts": 1,
        },
        {
            "ticker": "BTC-A",
            "asset": "BTC",
            "win": True,
            "pnl": 0.25,
            "strategy": "follow_crowd",
            "ts": 2,
        },
        {
            "ticker": "ETH-B",
            "asset": "ETH",
            "win": False,
            "pnl": -1.0,
            "strategy": "follow_crowd",
            "ts": 3,
        },
    ]
    with (state / "alice_15m_settled.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")

    receipt = rebuild_from_unique_settlements(state)
    model = load_model(state)
    assert receipt["raw_rows"] == 3
    assert receipt["unique_rows"] == 2
    assert receipt["duplicates_ignored"] == 1
    assert model["n_updates"] == 2
    assert set(model["seen_tickers"]) == {"BTC-A", "ETH-B"}

    duplicate = learn(
        "BTC",
        "follow_crowd",
        True,
        0.25,
        ticker="BTC-A",
        state_dir=state,
    )
    assert duplicate["event"] == "duplicate_ticker_ignored"
    assert load_model(state)["n_updates"] == 2
