"""r20260714-updown-regime-align — block fading strong UP/DOWN drift (STGM only)."""

from __future__ import annotations

import pytest

from System import alice_15m_scalp_strategies as strat


# 2026-07-14 16:47 window: all 6 tickets DOWN while Kalshi UP 69–99%
WINDOW_1647 = [
    ("BTC", 0.99),
    ("BNB", 0.87),
    ("SOL", 0.91),
    ("XRP", 0.80),
    ("DOGE", 0.92),
    ("ETH", 0.80),
]


def test_regime_gate_thresh_is_config_not_magic() -> None:
    assert strat.REGIME_GATE_IMPLIED_THRESH == pytest.approx(0.70)
    assert strat.REGIME_GATE_ENABLED is True


def test_regime_gate_blocks_down_when_up_strong() -> None:
    # ticket alone at 87% UP, field silent → market defines regime
    assert (
        strat.regime_gate(side="no", yes_mid=0.87, field=None)
        == "regime_block_down_vs_up_drift"
    )
    assert strat.regime_gate(side="yes", yes_mid=0.87, field=None) is None


def test_regime_gate_blocks_up_when_down_strong() -> None:
    assert (
        strat.regime_gate(side="yes", yes_mid=0.20, field=None)
        == "regime_block_up_vs_down_drift"
    )
    assert strat.regime_gate(side="no", yes_mid=0.20, field=None) is None


def test_regime_gate_requires_field_agreement_when_present() -> None:
    # strong UP mid but field says DOWN → do not treat as UP-only block
    # (breadth negative = field_down)
    assert (
        strat.regime_gate(
            side="no",
            yes_mid=0.80,
            field={"majors_breadth": -0.8, "anchor_side": "no"},
        )
        is None
    )
    # field agrees UP
    assert (
        strat.regime_gate(
            side="no",
            yes_mid=0.80,
            field={"majors_breadth": 0.8, "anchor_side": "yes"},
        )
        == "regime_block_down_vs_up_drift"
    )


def test_1647_six_down_window_all_blocked() -> None:
    """Reproduce 16:47 six-DOWN death: zero DOWN entries pass the gate."""
    # co-dir field agreed UP (strong breadth)
    field = {"majors_breadth": 1.0, "anchor_side": "yes"}
    blocked = 0
    for asset, up_imp in WINDOW_1647:
        assert up_imp >= 0.69
        why = strat.regime_gate(side="no", yes_mid=up_imp, field=field)
        assert why == "regime_block_down_vs_up_drift", f"{asset} UP={up_imp} should block DOWN"
        blocked += 1
        # UP side may still pass gate (alignment)
        assert strat.regime_gate(side="yes", yes_mid=up_imp, field=field) is None
    assert blocked == 6


def test_1647_strategy_enter_emits_no_trade_on_down_fade() -> None:
    """Arm _enter path: DOWN intent becomes no_trade under UP regime."""
    for asset, up_imp in WINDOW_1647:
        book = {
            "asset": asset,
            "yes_mid": up_imp,
            "yes_bids": [[f"{up_imp - 0.01:.2f}", "5"]],
            "yes_asks": [[f"{min(0.99, up_imp + 0.01):.2f}", "5"]],
            "no_bids": [[f"{max(0.01, 1 - up_imp - 0.01):.2f}", "5"]],
            "seconds_left": 400,
            "volume_24h": 8000,
            "recv_ts_ms": 1,
        }
        st = strat.ArmState(strategy_id="taker_momentum_tp")
        field = {"majors_breadth": 1.0, "mom_yes": 0.05, "anchor_side": "yes"}
        # force-ish path: call _enter directly as fade would
        intent = strat._enter("no", book, st, reason="fade_test", field=field)
        assert intent.action == "no_trade"
        assert intent.reason == "regime_block_down_vs_up_drift"


def test_regime_preferred_side_aligns_with_up_drift() -> None:
    assert strat.regime_preferred_side(0.90, field={"majors_breadth": 1.0}) == "yes"
    assert strat.regime_preferred_side(0.10, field={"majors_breadth": -1.0}) == "no"


def test_disabled_gate_allows_fade() -> None:
    assert (
        strat.regime_gate(
            side="no", yes_mid=0.95, field=None, enabled=False
        )
        is None
    )
