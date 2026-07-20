import json
from pathlib import Path

import pytest

from System import swarm_crypto_behavior_memory as behavior


def _raw_candles(n: int = 90, *, start: int = 10_000) -> list[list[float]]:
    rows = []
    price = 100.0
    for i in range(n):
        price *= 1.001 if i % 7 else 0.999
        rows.append(
            [
                start + i * 300,
                price * 0.998,
                price * 1.002,
                price * 0.999,
                price,
                1000.0 + i,
            ]
        )
    return rows


def test_public_candles_are_cached_and_described_as_proxy(tmp_path: Path) -> None:
    calls = []

    def fetcher(url: str, timeout: float):
        calls.append((url, timeout))
        return list(reversed(_raw_candles()))

    first = behavior.behavior_snapshot(
        "BTC",
        state_dir=tmp_path,
        now=100_000,
        fetcher=fetcher,
    )
    second = behavior.behavior_snapshot(
        "BTC",
        state_dir=tmp_path,
        now=100_010,
        fetcher=lambda *_args: pytest.fail("fresh cache should avoid network"),
    )

    assert first["available"] is True
    assert first["basis"] == "proxy_spot_not_kalshi_settlement_index"
    assert first["features"]["n_candles"] == 90
    assert "sma_spread_pct" in first["features"]
    assert "ema_spread_pct" not in first["features"]
    assert second["cache"] == "fresh"
    assert len(calls) == 1


def test_shadow_signal_requires_forward_confidence_before_trust(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    state.mkdir(parents=True)
    path = state / behavior.EVAL_LEDGER
    with path.open("w", encoding="utf-8") as handle:
        for i in range(59):
            handle.write(
                json.dumps(
                    {
                        "ticker": f"BTC-{i}",
                        "asset": "BTC",
                        "predicted_side": "UP",
                        "actual_side": "UP",
                    }
                )
                + "\n"
            )
    assert behavior.calibration("BTC", state_dir=state)["trusted"] is False

    with path.open("a", encoding="utf-8") as handle:
        for i in range(59, 70):
            handle.write(
                json.dumps(
                    {
                        "ticker": f"BTC-{i}",
                        "asset": "BTC",
                        "predicted_side": "UP",
                        "actual_side": "UP",
                    }
                )
                + "\n"
            )
    calibrated = behavior.calibration("BTC", state_dir=state)
    assert calibrated["trusted"] is True
    assert calibrated["wilson_lower"] > 0.5


def test_shadow_settlement_is_unique_by_ticker(tmp_path: Path) -> None:
    spot = {
        "predicted_side": "DOWN",
        "features": {"signal_strength": 0.7, "regime": "trend_down"},
        "source": behavior.SOURCE_NAME,
    }
    first = behavior.record_settlement(
        asset="ETH",
        ticker="ETH-ONE",
        actual_side="DOWN",
        spot_snapshot=spot,
        state_dir=tmp_path,
        now=1.0,
    )
    second = behavior.record_settlement(
        asset="ETH",
        ticker="ETH-ONE",
        actual_side="UP",
        spot_snapshot=spot,
        state_dir=tmp_path,
        now=2.0,
    )
    assert first["ok"] is True
    assert second["duplicate"] is True
    rows = (tmp_path / ".sifta_state" / behavior.EVAL_LEDGER).read_text().splitlines()
    assert len(rows) == 1

