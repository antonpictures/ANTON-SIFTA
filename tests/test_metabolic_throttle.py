from __future__ import annotations

import json
from pathlib import Path

import pytest

import System.metabolic_throttle as metabolic_throttle
from System.metabolic_throttle import MetabolicThrottle


@pytest.fixture
def isolated_throttle_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
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


def _append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")


def test_m5sifta_reads_unified_alice_m5_wallet(isolated_throttle_state: Path) -> None:
    (isolated_throttle_state / "ALICE_M5.json").write_text(
        json.dumps({"id": "ALICE_M5", "stgm_balance": 97.188}),
        encoding="utf-8",
    )

    throttle = MetabolicThrottle(agent_id="M5SIFTA", ledger_writes=False)

    assert throttle.current_balance() == pytest.approx(97.188)
    assert throttle.clearance().ok is True
    assert throttle.clearance().reason == "healthy"


def test_missing_wallet_fails_open_instead_of_latching_starvation(
    isolated_throttle_state: Path,
) -> None:
    throttle = MetabolicThrottle(
        agent_id="UNKNOWN_NODE",
        starvation_delay_s=60.0,
        ledger_writes=False,
    )

    first = throttle.clearance()
    second = throttle.clearance()

    assert first.ok is True
    assert second.ok is True
    assert second.sleep_needed == pytest.approx(0.0)
    assert second.reason == "wallet_unresolved_fail_open"


def test_canonical_wallet_balance_fallback_without_body_file(
    isolated_throttle_state: Path,
) -> None:
    _append_jsonl(
        metabolic_throttle.REPAIR_LOG,
        {"tx_type": "STGM_MINT", "agent_id": "ALICE_M5", "amount": 12.5},
    )

    throttle = MetabolicThrottle(agent_id="M5SIFTA", ledger_writes=False)

    assert throttle.current_balance() == pytest.approx(12.5)
    assert throttle.clearance().ok is True
    assert throttle.clearance().reason == "healthy"
