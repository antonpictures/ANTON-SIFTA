"""r1632 — Kalshi DEMO client iron boundary + caps + kill switch."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from System import kalshi_demo_client as kdc


def test_prod_url_raises() -> None:
    with pytest.raises(kdc.ProdHostForbidden):
        kdc.assert_demo_url("https://external-api.kalshi.com/trade-api/v2/portfolio/balance")
    with pytest.raises(kdc.ProdHostForbidden):
        kdc.assert_demo_url("https://api.elections.kalshi.com/trade-api/v2/markets")


def test_demo_url_ok() -> None:
    assert kdc.assert_demo_url(kdc.DEMO_BASE).startswith("https://")


def test_kill_switch_blocks_write(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    state.mkdir()
    kdc.set_kill_switch(True, reason="test", state_dir=state)
    c = kdc.KalshiDemoClient(state_dir=state)
    with pytest.raises(kdc.KillSwitchActive):
        c.place_limit_order(ticker="T", side="yes", price=0.75)


def test_price_band_cap(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    state.mkdir()
    kdc.set_kill_switch(False, state_dir=state)
    c = kdc.KalshiDemoClient(state_dir=state)
    with pytest.raises(kdc.CapRejected):
        c.place_limit_order(ticker="T", side="yes", price=0.55)
    with pytest.raises(kdc.CapRejected):
        c.place_limit_order(ticker="T", side="yes", price=0.95)


def test_shadow_order_in_band(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    state.mkdir()
    kdc.set_kill_switch(False, state_dir=state)
    c = kdc.KalshiDemoClient(state_dir=state)
    r = c.place_limit_order(ticker="KXTEST15M", side="yes", price=0.74)
    assert r["ok"] and r.get("shadow") is True
    assert r["client_order_id"].startswith("sifta-")
    c.cancel_order(r["client_order_id"])


def test_max_open_cap(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    state.mkdir()
    kdc.set_kill_switch(False, state_dir=state)
    c = kdc.KalshiDemoClient(state_dir=state)
    for i in range(kdc.MAX_OPEN):
        c.place_limit_order(ticker=f"T{i}", side="yes", price=0.75)
    with pytest.raises(kdc.CapRejected):
        c.place_limit_order(ticker="TOVER", side="yes", price=0.75)


def test_rsa_sign_roundtrip() -> None:
    out = kdc.run_self_test()
    assert out["tests"]["rsa_sign_verify"] == "PASS"
    assert out["tests"]["prod_forbidden"] == "PASS"
    assert out["all_pass"] is True


def test_self_test_cli_shape() -> None:
    out = kdc.run_self_test()
    assert "status" in out
    assert out["status"]["env"] == "demo"
    assert "external-api.demo.kalshi.co" in out["status"]["base"]
