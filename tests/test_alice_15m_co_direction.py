"""Co-direction best-of-pair picker + weird/shadow-only assets."""

from __future__ import annotations

import json
from pathlib import Path

from System.alice_15m_co_direction import (
    board_field,
    is_weird_15m_asset,
    should_skip_contrarian,
)


def test_hype_zec_near_weird() -> None:
    assert is_weird_15m_asset("HYPE") is True
    assert is_weird_15m_asset("zec") is True
    assert is_weird_15m_asset("NEAR") is True
    assert is_weird_15m_asset("BTC") is False
    assert is_weird_15m_asset("") is False


def test_contrarian_skipped_when_field_clear(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    state.mkdir()
    # HYPE/ZEC/NEAR are weird: excluded live but available to shadow research.
    markets = []
    for a, yes in [
        ("BTC", 0.75),
        ("ETH", 0.80),
        ("SOL", 0.72),
        ("XRP", 0.70),
        ("BNB", 0.68),
        ("DOGE", 0.71),
        ("HYPE", 0.65),  # weird
        ("NEAR", 0.35),  # weird
        ("ZEC", 0.40),  # weird
    ]:
        markets.append(
            {
                "asset": a,
                "kalshi_ticker": f"KX{a}15M-T",
                "kalshi_yes": yes,
                "kalshi_volume_24h": 5000 if a != "NEAR" else 100,
            }
        )
    (state / "kalshi_15m_live.json").write_text(
        json.dumps({"markets": markets}), encoding="utf-8"
    )
    f = board_field(state_dir=state)
    ranked_assets = {r["asset"] for r in (f.get("ranked") or [])}
    assert "HYPE" not in ranked_assets
    assert "ZEC" not in ranked_assets
    assert "NEAR" not in ranked_assets
    assert f["field_clear"] is True
    assert f["label"] == "UP"
    # r1664: best pair (2), not 3
    assert len(f.get("best2") or f.get("best3") or []) <= 2
    assert len(f["best3"]) <= 2
    assert all(a not in f["avoid"] for a in f["best3"])
    # Weird assets always skip live selection (even if not on field).
    skip_z, why_z = should_skip_contrarian("ZEC", "no", field=f)
    assert skip_z is True
    assert why_z == "weird_asset"
    skip_h, why_h = should_skip_contrarian("HYPE", "yes", field=f)
    assert skip_h is True
    assert why_h == "weird_asset"
    skip_n, why_n = should_skip_contrarian("NEAR", "no", field=f)
    assert skip_n is True
    assert why_n == "weird_asset"
    skip2, _ = should_skip_contrarian("BTC", "yes", field=f)
    assert skip2 is False
