"""r1018 — live self-improvement dry run receipts (incident, KEEP, REVERT, cosign)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture()
def state_dir(tmp_path: Path) -> Path:
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True)
    return sd


def test_r1018_incident_closed_receipt(state_dir: Path) -> None:
    from System.swarm_self_improvement_loop import close_r1016_two_tab_incident

    result = close_r1016_two_tab_incident(state_dir=state_dir)
    gate = result["gate"]
    row = result["ledger_row"]
    assert gate["ok"] is False
    assert gate["reason"] == "recovery_context_no_effector"
    assert gate.get("incident_prevented") == "91e01405-uncommanded-browser-click"
    assert row["action"] == "incident_closed"
    assert row["incident_chain"] == "245fcb4e-timeout-recovery-replay→91e01405-uncommanded-browser-click"
    assert row["verdict"] == "REFUSED"

    ledger = state_dir / "effector_gate.jsonl"
    assert ledger.exists()
    rows = [json.loads(ln) for ln in ledger.read_text(encoding="utf-8").splitlines() if ln.strip()]
    closed = [r for r in rows if r.get("action") == "incident_closed"]
    assert closed


def test_r1018_apoptosis_keep_cycle(state_dir: Path) -> None:
    from System.swarm_self_improvement_loop import run_apoptosis_keep_cycle

    result = run_apoptosis_keep_cycle(state_dir=state_dir)
    assert result["status"] == "KEPT"
    assert result["measured_tests"] >= 12


def test_r1018_bad_proposal_reverts_byte_identical(
    state_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from System import swarm_self_improvement_loop as loop

    repo = Path(__file__).resolve().parents[1]
    monkeypatch.setattr(loop, "_repo_root", lambda: repo)
    result = loop.run_bad_proposal_revert_cycle(state_dir=state_dir)
    assert result["status"] == "REVERTED"
    assert result["byte_identical"] is True


def test_r1018_cosign_stall_no_apply(state_dir: Path) -> None:
    from System.swarm_self_improvement_loop import run_cosign_stall_cycle

    result = run_cosign_stall_cycle(state_dir=state_dir)
    assert result["stalled"] is True
    assert result["applied"] is False
    assert "gate_file_requires_owner_cosign" in result["vote"]["floors_failed"]


def test_r1018_full_dry_run_bundle(state_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from System import swarm_self_improvement_loop as loop

    repo = Path(__file__).resolve().parents[1]
    monkeypatch.setattr(loop, "_repo_root", lambda: repo)
    bundle = loop.run_r1018_dry_run(state_dir=state_dir)
    assert bundle["incident_closed"]["ledger_row"]["verdict"] == "REFUSED"
    assert bundle["first_keep"]["status"] == "KEPT"
    assert bundle["first_revert"]["byte_identical"] is True
    assert bundle["cosign_stall"]["stalled"] is True

    dry_path = state_dir / "self_improvement_dry_run_receipts.jsonl"
    assert dry_path.exists()
    kinds = {json.loads(ln)["kind"] for ln in dry_path.read_text(encoding="utf-8").splitlines() if ln.strip()}
    assert "incident_closed" in kinds
    assert "first_keep" in kinds
    assert "first_revert" in kinds
    assert "cosign_stall" in kinds


def test_improve_and_quorum_slash_render(state_dir: Path) -> None:
    from System.swarm_alice_slash_commands import handle_slash_command
    from System.swarm_self_improvement_loop import run_apoptosis_keep_cycle

    run_apoptosis_keep_cycle(state_dir=state_dir)
    improve = handle_slash_command("/improve", state_dir=state_dir)
    assert "SELF-IMPROVEMENT" in improve["reply"]
    assert "KEPT" in improve["reply"]

    proposals = (state_dir / "self_improvement_proposals.jsonl").read_text(encoding="utf-8")
    pid = json.loads(proposals.strip().splitlines()[-1])["proposal_id"][:8]
    quorum = handle_slash_command(f"/quorum {pid}", state_dir=state_dir)
    assert "quorum" in quorum["reply"]