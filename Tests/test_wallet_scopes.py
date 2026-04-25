"""Lock the semantic separation between Alice's wallet and the serial-wide
treasury rollup.

Regression target: the HUD used to label the serial treasury as
"Your Wallet (M5)", which contradicted Alice's own composite-identity
view that only sees ``ALICE_M5``. After this change, the Warren accountant
exposes two named functions and the HUD consumes both.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import pytest


@pytest.fixture()
def stub_state_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Build a synthetic .sifta_state with three agents on one serial."""
    serial = "FAKE_SERIAL_TEST"
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    fixtures: Dict[str, Dict[str, object]] = {
        "alice_m5": {"id": "ALICE_M5", "homeworld_serial": serial},
        "m1queen": {"id": "M1QUEEN", "homeworld_serial": serial},
        "repair_drone": {"id": "REPAIR-DRONE", "homeworld_serial": serial},
        "off_serial": {"id": "GHOST_M9", "homeworld_serial": "OTHER_SERIAL"},
    }
    for name, body in fixtures.items():
        (state_dir / f"{name}.json").write_text(json.dumps(body), encoding="utf-8")

    import System.warren_buffett as wb
    monkeypatch.setattr(wb, "STATE_DIR", state_dir, raising=True)

    fake_balances = {
        "ALICE_M5": 154.238,
        "M1QUEEN": 100.000,
        "REPAIR-DRONE": 29.500,
        "GHOST_M9": 999.999,
    }

    def _fake_ledger_balance(agent_id: str) -> float:
        return float(fake_balances.get(str(agent_id).upper(), 0.0))

    import sys
    fake_module = type(sys)("Kernel.inference_economy")
    fake_module.ledger_balance = _fake_ledger_balance  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "Kernel.inference_economy", fake_module)

    return state_dir


def test_alice_wallet_is_only_alice(stub_state_dir: Path) -> None:
    from System.warren_buffett import alice_wallet_balance

    serial = "FAKE_SERIAL_TEST"
    assert alice_wallet_balance(serial) == pytest.approx(154.238)


def test_serial_treasury_includes_siblings(stub_state_dir: Path) -> None:
    from System.warren_buffett import serial_treasury_balance

    serial = "FAKE_SERIAL_TEST"
    expected = 154.238 + 100.000 + 29.500
    assert serial_treasury_balance(serial) == pytest.approx(expected)


def test_treasury_excludes_other_serials(stub_state_dir: Path) -> None:
    from System.warren_buffett import serial_treasury_balance

    assert serial_treasury_balance("OTHER_SERIAL") == pytest.approx(999.999)


def test_alice_wallet_strictly_less_than_treasury(stub_state_dir: Path) -> None:
    """The whole point of the HUD fix: these two numbers must be
    distinguishable when sibling agents share the silicon."""
    from System.warren_buffett import alice_wallet_balance, serial_treasury_balance

    serial = "FAKE_SERIAL_TEST"
    assert alice_wallet_balance(serial) < serial_treasury_balance(serial)


def test_legacy_alias_matches_treasury(stub_state_dir: Path) -> None:
    from System.warren_buffett import _architect_local_stgm, serial_treasury_balance

    serial = "FAKE_SERIAL_TEST"
    assert _architect_local_stgm(serial) == pytest.approx(serial_treasury_balance(serial))


def test_empty_serial_returns_zero(stub_state_dir: Path) -> None:
    from System.warren_buffett import alice_wallet_balance, serial_treasury_balance

    assert alice_wallet_balance("") == 0.0
    assert serial_treasury_balance("") == 0.0
