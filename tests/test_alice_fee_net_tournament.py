"""r1667 fee-net tournament — cohorts, fees, policy hash, weird assets."""

from __future__ import annotations

import json
from pathlib import Path

from System.alice_fee_net_tournament import (
    COHORT_LEGACY,
    COHORT_M5_BEST1,
    COHORT_M7_BEST1,
    COHORT_M7_BEST2,
    asset_trade_class,
    bootstrap_report,
    compute_policy_hash,
    fee_net_unit_pnl,
    normalize_cohort,
    pair_decision,
    policy_allows_trade,
    policy_payload,
    record_shadow_window,
    settle_shadow_ticket,
    should_skip_live_asset,
    write_policy_hash,
)


def test_legacy_unknown_cohort() -> None:
    assert normalize_cohort(None) == COHORT_LEGACY
    assert normalize_cohort("") == COHORT_LEGACY
    assert normalize_cohort("minute11_learner", rule="minute11") == COHORT_LEGACY
    assert normalize_cohort("minute7_best1") == COHORT_M7_BEST1
    assert normalize_cohort("minute7_best2_same_dir") == COHORT_M7_BEST2
    assert normalize_cohort("minute5_best1") == COHORT_M5_BEST1


def test_shadow_only_and_weird() -> None:
    assert asset_trade_class("HYPE") == "weird"
    assert asset_trade_class("ZEC") == "weird"
    assert asset_trade_class("DOGE") == "shadow_only"
    assert asset_trade_class("NEAR") == "weird"
    assert asset_trade_class("BTC") == "live_ok"
    assert should_skip_live_asset("NEAR") == (True, "weird_asset")


def test_fee_net_expensive_win_small() -> None:
    """At 88¢ a win is tiny; one loss wipes many wins (fee-net)."""
    w = fee_net_unit_pnl(win=True, entry_price=0.88)
    l = fee_net_unit_pnl(win=False, entry_price=0.88)
    assert w["net"] < 0.15  # ~0.12 after fee
    assert l["net"] < -0.88
    # 5 wins cannot cover 1 loss at 88¢
    assert 5 * w["net"] + l["net"] < 0


def test_pair_prefers_single_live(tmp_path: Path) -> None:
    cands = [
        {"asset": "BTC", "side": "no", "co_dir_score": 0.9, "fav": 0.84, "secs": 400},
        {"asset": "ETH", "side": "no", "co_dir_score": 0.7, "fav": 0.80, "secs": 400},
        {"asset": "ZEC", "side": "no", "co_dir_score": 0.99, "fav": 0.85, "secs": 400},
    ]
    d = pair_decision(cands)
    assert d["action"] == "bet"
    assert len(d["live"]) == 1
    assert d["live"][0]["asset"] == "BTC"
    assert "ZEC" not in [x["asset"] for x in d["live"]]
    # pair shadow may include ETH but not ZEC
    assert all(x["asset"] != "ZEC" for x in d["shadow_pair"])


def test_weird_asset_is_shadow_visible_but_not_live() -> None:
    cands = [
        {"asset": "NEAR", "side": "no", "co_dir_score": 0.95, "fav": 0.83},
        {"asset": "BTC", "side": "no", "co_dir_score": 0.80, "fav": 0.78},
    ]
    d = pair_decision(cands)
    assert [x["asset"] for x in d["live"]] == ["BTC"]
    assert "NEAR" in [x["asset"] for x in d["shadow_pair"]]


def test_policy_hash_interlock(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    state.mkdir()
    row = write_policy_hash(state_dir=state)
    assert row["policy_hash"] == compute_policy_hash(policy_payload())
    ok, why = policy_allows_trade(state_dir=state)
    assert ok is True, why
    # corrupt disk hash
    bad = json.loads((state / "alice_policy_hash.json").read_text())
    bad["policy_hash"] = "deadbeefdeadbeef"
    (state / "alice_policy_hash.json").write_text(json.dumps(bad))
    ok2, why2 = policy_allows_trade(state_dir=state)
    assert ok2 is False
    assert "mismatch" in why2


def test_weird_asset_remains_shadow_visible(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    state.mkdir()
    write_policy_hash(state_dir=state)
    cands = [
        {"asset": "BTC", "side": "yes", "co_dir_score": 0.8, "fav": 0.75, "secs": 350},
        {"asset": "HYPE", "side": "yes", "co_dir_score": 0.9, "fav": 0.80, "secs": 350},
    ]
    out = record_shadow_window(
        window_id="TESTWIN",
        field="UP",
        candidates=cands,
        point_in_time_ts=1_000_000.0,
        state_dir=state,
    )
    assert [x["asset"] for x in out["decision"]["live"]] == ["BTC"]
    shadow_assets = {
        t["asset"]
        for row in out["shadow_rows"]
        for t in row.get("tickets") or []
    }
    assert "HYPE" in shadow_assets


def test_owner_intervention_flag(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    state.mkdir()
    r = settle_shadow_ticket(
        window_id="W1",
        cohort=COHORT_M7_BEST1,
        asset="XRP",
        win=False,
        entry_price=0.70,
        state_dir=state,
        owner_intervention=True,
    )
    assert r["owner_intervention"] is True
    assert r["exit_kind"] == "owner_intervention"


def test_bootstrap_report_runs(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    state.mkdir()
    write_policy_hash(state_dir=state)
    # seed a few paper settles as legacy
    lines = []
    for i, win in enumerate([True, True, False]):
        lines.append(
            json.dumps(
                {
                    "asset": "BTC",
                    "label": "DOWN",
                    "price": 0.84,
                    "win": win,
                    "ticker": f"KXBTC15M-26JUL13{1000+i}-00",
                    "strategy_variant": "minute7_best1",
                }
            )
        )
    (state / "alice_15m_settled.jsonl").write_text("\n".join(lines) + "\n")
    rep = bootstrap_report(state_dir=state)
    assert "cohorts" in rep
    assert rep["cohorts"][COHORT_M7_BEST1]["n"] == 3
    assert rep["promote_gates"]["promote"] is False  # far below 200 tickets


def test_usd_evaluate_refuses_shadow_epoch(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    state.mkdir()
    from System.alice_fee_net_tournament import save_config, default_config, write_policy_hash

    write_policy_hash(state_dir=state)
    cfg = default_config()
    cfg["epoch_active"] = True
    cfg["usd_shadow_only"] = True
    save_config(cfg, state_dir=state)
    from System.kalshi_usd_hand import evaluate_ticket

    r = evaluate_ticket(
        entry_price=0.80,
        side="yes",
        rainman_action="fire",
        asset="BTC",
        state_dir=state,
    )
    assert r["ok"] is False
    assert r["reason"] == "r1667_usd_shadow_only"


def test_minute11_alignment_3_of_4_down() -> None:
    from System.alice_fee_net_tournament import measure_major_alignment

    rows = [
        {"asset": "BTC", "yes": 0.30, "secs": 660},
        {"asset": "ETH", "yes": 0.35, "secs": 660},
        {"asset": "SOL", "yes": 0.40, "secs": 660},
        {"asset": "XRP", "yes": 0.55, "secs": 660},  # UP minority
    ]
    a = measure_major_alignment(rows)
    assert a["consensus"] == "DOWN"
    assert a["n_down"] == 3
    assert a["n_up"] == 1
    assert a["trend_down_hypothesis"] is True
    assert a["of4"] == "3_of_4"


def test_minute11_record_once_no_hindsight(tmp_path: Path) -> None:
    from System.alice_fee_net_tournament import (
        maybe_record_minute11_trend,
        minute11_shadow_summary,
        M11_SHADOW_LOG,
    )

    state = tmp_path / ".sifta_state"
    state.mkdir()
    # Board at ~11 min left, all down
    markets = []
    for a, y in [("BTC", 0.32), ("ETH", 0.35), ("SOL", 0.38), ("XRP", 0.40)]:
        markets.append(
            {
                "asset": a,
                "kalshi_yes": y,
                "seconds_to_close": 660,
                "kalshi_ticker": f"KX{a}15M-26JUL131500-00",
            }
        )
    (state / "kalshi_15m_live.json").write_text(
        json.dumps({"markets": markets}), encoding="utf-8"
    )
    r1 = maybe_record_minute11_trend(state_dir=state, now=1_000_000.0)
    assert r1.get("recorded") is True
    assert r1.get("alignment", {}).get("trend_down_hypothesis") is True
    r2 = maybe_record_minute11_trend(state_dir=state, now=1_000_010.0)
    assert r2.get("recorded") is False
    assert r2.get("reason") == "already_recorded"
    # outside band
    for m in markets:
        m["seconds_to_close"] = 400
    (state / "kalshi_15m_live.json").write_text(
        json.dumps({"markets": markets}), encoding="utf-8"
    )
    r3 = maybe_record_minute11_trend(state_dir=state, now=1_000_020.0)
    assert r3.get("recorded") is False
    # log has exactly one context row
    lines = (state / M11_SHADOW_LOG).read_text().strip().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["hindsight"] is False
    assert row["live_effect"] == "none"
    assert row["usd_effect"] == "none"
    sm = minute11_shadow_summary(state_dir=state)
    assert sm["n_snapshots"] == 1
    assert sm["n_trend_down_3plus"] == 1
