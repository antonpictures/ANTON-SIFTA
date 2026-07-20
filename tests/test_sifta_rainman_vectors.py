"""r1634 — Rainman Edge Field multi-vector gate."""

from __future__ import annotations

import json
from pathlib import Path

from System.swarm_sifta_rainman_vectors import (
    FIRE_SCORE,
    gate,
    price_bucket,
    rebuild_climate,
    score_ticket,
)


def test_price_buckets() -> None:
    assert price_bucket(0.72) == "70-74"
    assert price_bucket(0.77) == "75-79"
    assert price_bucket(0.84) == "80-88"


def test_high_band_scores_hotter_than_thin(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    state.mkdir()
    # seed climate: strong 80-88, weak 70-74
    (state / "alice_15m_settled.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "asset": "BTC",
                        "price": 0.84,
                        "win": True,
                        "pnl": 0.1,
                    }
                )
                for _ in range(20)
            ]
            + [
                json.dumps(
                    {
                        "asset": "ETH",
                        "price": 0.72,
                        "win": i % 5 != 0,  # 80% still
                        "pnl": 0.05 if i % 5 else -1,
                    }
                )
                for i in range(20)
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    rebuild_climate(state_dir=state)
    hot = score_ticket(
        asset="BTC",
        kalshi_yes=0.84,
        entry_price=0.84,
        side="yes",
        secs_left=500,
        learner={"s_follow": 1.5},
        state_dir=state,
    )
    cold = score_ticket(
        asset="ETH",
        kalshi_yes=0.28,  # DOWN favorite 0.72
        entry_price=0.72,
        side="no",
        secs_left=100,
        learner={"s_follow": 0.7},
        state_dir=state,
    )
    assert hot["score"] > cold["score"]
    assert hot["action"] in ("fire", "thin")


def test_gate_sit_logs(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    state.mkdir()
    # empty climate → soft scores
    c = gate(
        asset="DOGE",
        kalshi_yes=0.30,
        entry_price=0.71,
        side="no",
        secs_left=80,
        learner={"s_follow": 0.5},
        state_dir=state,
    )
    assert "score" in c and "action" in c
    assert (state / "alice_15m_rainman_vectors.jsonl").exists()


def test_force_bypasses_sit(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    state.mkdir()
    c = gate(
        asset="ETH",
        kalshi_yes=0.29,
        entry_price=0.71,
        side="no",
        secs_left=50,
        learner={"s_follow": 0.4},
        state_dir=state,
        force=True,
    )
    assert c["action"] == "fire"


def test_v8_concentration_caps_same_side(tmp_path: Path) -> None:
    """8× DOWN = one macro bet — crystal must sit after MAX_SAME_SIDE."""
    from System.swarm_sifta_rainman_vectors import MAX_SAME_SIDE, score_ticket

    state = tmp_path / ".sifta_state"
    state.mkdir()
    # 4 already DOWN — next DOWN must hard-sit
    c = score_ticket(
        asset="BTC",
        kalshi_yes=0.25,
        entry_price=0.75,
        side="no",
        secs_left=500,
        learner={"s_follow": 1.5},
        state_dir=state,
        same_side_already=MAX_SAME_SIDE,
        total_already=4,
    )
    assert c["action"] == "sit"
    assert "max_same_side" in str(c.get("veto") or "")
    assert c["vectors"]["concentration"] < 0.3


def test_rank_and_cap_limits_portfolio() -> None:
    from System.swarm_sifta_rainman_vectors import rank_and_cap_candidates

    cands = [
        {"asset": f"A{i}", "side": "no", "score": 0.9 - i * 0.01, "action": "fire"}
        for i in range(8)
    ]
    ok, rej = rank_and_cap_candidates(cands, max_same_side=4, max_tickets=5)
    assert len(ok) == 4  # same-side cap binds first
    assert all(r.get("cap_reason", "").startswith("max_same_side") for r in rej)


def test_dust_volume_sits(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    state.mkdir()
    (state / "kalshi_15m_live.json").write_text(
        json.dumps(
            {
                "markets": [
                    {"asset": "NEAR", "kalshi_yes": 0.28, "volume_24h": 5.0},
                    {"asset": "BTC", "kalshi_yes": 0.50, "volume_24h": 250000.0},
                ]
            }
        ),
        encoding="utf-8",
    )
    c = score_ticket(
        asset="NEAR",
        kalshi_yes=0.28,
        entry_price=0.72,
        side="no",
        secs_left=500,
        learner={"s_follow": 1.4},
        state_dir=state,
        volume=5.0,
    )
    assert c["action"] == "sit"
    assert "dust_volume" in str(c.get("veto") or "")
