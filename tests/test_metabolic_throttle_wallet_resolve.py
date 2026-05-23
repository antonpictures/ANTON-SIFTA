#!/usr/bin/env python3
"""Hermetic Round 1 throttle wallet-resolution regressions.

The tests must never write fixtures into Alice's live ``.sifta_state``. Each
case points the throttle module at a temporary state directory and repair log.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import System.metabolic_throttle as metabolic_throttle
from System.metabolic_throttle import MetabolicThrottle


@pytest.fixture
def throttle_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    state = tmp_path / ".sifta_state"
    state.mkdir()
    monkeypatch.setattr(metabolic_throttle, "_STATE", state)
    monkeypatch.setattr(
        metabolic_throttle,
        "_THROTTLE_STATE_DIR",
        state / "metabolic_throttle_state",
    )
    monkeypatch.setattr(metabolic_throttle, "REPAIR_LOG", tmp_path / "repair_log.jsonl")
    return state


def test_resolves_alice_m5_wallet_alias(throttle_state: Path) -> None:
    """M5SIFTA resolves the unified ALICE_M5 wallet without a duplicate body."""
    (throttle_state / "ALICE_M5.json").write_text(
        json.dumps({"id": "ALICE_M5", "stgm_balance": 97.188}),
        encoding="utf-8",
    )

    throttle = MetabolicThrottle(agent_id="M5SIFTA", ledger_writes=False)

    assert throttle.current_balance() == pytest.approx(97.188)
    clearance = throttle.clearance()
    assert clearance.ok is True
    assert clearance.reason == "healthy"
    assert clearance.balance == pytest.approx(97.188)


def test_missing_wallet_fails_open_not_starving(throttle_state: Path) -> None:
    """Unknown balance is not proof of starvation and must not latch cooldown."""
    throttle = MetabolicThrottle(
        agent_id="NONEXISTENT_AGENT_999",
        starvation_delay_s=60.0,
        ledger_writes=False,
    )

    first = throttle.clearance()
    second = throttle.clearance()

    assert first.ok is True
    assert second.ok is True
    assert second.reason == "wallet_unresolved_fail_open"
    assert second.sleep_needed == pytest.approx(0.0)
    assert throttle.current_balance() == pytest.approx(0.0)
    rows = [
        json.loads(line)
        for line in (throttle_state / "throttle_decisions.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert rows[-1]["ok"] is True
    assert rows[-1]["resolved_wallet_file"] is None
    assert rows[-1]["reason"] == "wallet_unresolved_fail_open"
    assert rows[-1]["decision_hash"]


def test_genuine_negative_balance_still_throttles(throttle_state: Path) -> None:
    """A real wallet with negative balance still enforces starvation cooldown."""
    (throttle_state / "TEST_NEGATIVE_BODY.json").write_text(
        json.dumps({"id": "TEST_NEGATIVE", "stgm_balance": -5.0}),
        encoding="utf-8",
    )

    throttle = MetabolicThrottle(
        agent_id="TEST_NEGATIVE",
        starvation_delay_s=60.0,
        ledger_writes=False,
    )

    first = throttle.clearance()
    second = throttle.clearance()

    assert first.ok is True
    assert first.reason == "starvation_ok"
    assert second.ok is False
    assert second.balance == pytest.approx(-5.0)
    assert second.sleep_needed > 0.0
    assert second.reason.startswith("starving")
    rows = [
        json.loads(line)
        for line in (throttle_state / "throttle_decisions.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert rows[-1]["ok"] is False
    assert rows[-1]["resolved_wallet_file"] == "TEST_NEGATIVE_BODY.json"
    assert rows[-1]["balance"] == pytest.approx(-5.0)
