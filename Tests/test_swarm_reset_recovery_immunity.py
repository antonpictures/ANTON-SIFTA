import json
import time
from pathlib import Path

from System import swarm_reset_recovery_immunity as rri


def _warm(path: Path, ts: float | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"ts": ts if ts is not None else time.time()}) + "\n", encoding="utf-8")


def test_reset_recovery_immunity_empty_state_blocks_autonomy(tmp_path: Path) -> None:
    row = rri.compute_reset_recovery(state_dir=tmp_path)

    assert row["truth_label"] == rri.TRUTH_LABEL
    assert row["phase"] == "WOUND_REPAIR"
    assert row["autonomy_gate"] == "BLOCK"
    assert row["warmth"] == 0.0
    assert "force_observe_then_repair" in row["recommended_actions"]


def test_reset_recovery_ready_when_required_ledgers_are_warm(tmp_path: Path) -> None:
    for path in rri.required_ledger_paths(tmp_path).values():
        _warm(path)

    row = rri.compute_reset_recovery(state_dir=tmp_path)

    assert row["phase"] == "READY"
    assert row["autonomy_gate"] == "ALLOW"
    assert row["recovery_score"] == 1.0


def test_reset_recovery_limited_for_partially_warm_state(tmp_path: Path) -> None:
    paths = list(rri.required_ledger_paths(tmp_path).values())
    for path in paths[:4]:
        _warm(path)

    row = rri.compute_reset_recovery(state_dir=tmp_path)

    assert row["phase"] == "REHYDRATE"
    assert row["autonomy_gate"] == "LIMITED"
    assert 0.5 <= row["warmth"] < 0.85


def test_reset_recovery_write_receipt_and_recovery_action(tmp_path: Path) -> None:
    row = rri.write_reset_recovery(state_dir=tmp_path)
    action = rri.recovery_action(row)

    log = tmp_path / rri.RECOVERY_LOG_NAME
    assert log.exists()
    assert action["type"] == "repair"
    assert action["reason"] == "reset_recovery_immunity_block"
    assert action["autonomy_gate"] == "BLOCK"
    assert action["drive_bias_applied"] is False
