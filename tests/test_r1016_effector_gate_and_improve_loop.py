from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def state_dir(tmp_path: Path) -> Path:
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True)
    return sd


def test_incident_245fcb4e_replay_click_refused(state_dir: Path) -> None:
    """Simulate timeout recovery then browser click — must REFUSE (91e01405 class)."""
    from System.swarm_effector_gate import bind_recovery_context, require_browser_effector
    from System.swarm_intent_nonce_gate import mint_intent_nonce

    minted = mint_intent_nonce(
        owner_text="garbled voice clip",
        surface="talk",
        stt_conf=0.42,
        ingress_kind="spoken",
        state_dir=state_dir,
    )
    bind_recovery_context(
        source="cortex_timeout_recovery",
        linked_receipt="245fcb4e-simulated",
        state_dir=state_dir,
    )
    gate = require_browser_effector("click_main_image", state_dir=state_dir)
    assert gate["ok"] is False
    assert gate["reason"] == "recovery_context_no_effector"
    assert gate.get("incident_prevented") == "91e01405-uncommanded-browser-click"
    assert minted["nonce"]


def test_fresh_owner_ingress_allows_one_click(state_dir: Path) -> None:
    from System.swarm_effector_gate import bind_owner_ingress, require_browser_effector

    bind_owner_ingress(
        owner_text="click the image in google",
        surface="talk",
        stt_conf=0.95,
        ingress_kind="typed",
        state_dir=state_dir,
    )
    first = require_browser_effector("click_main_image", state_dir=state_dir)
    second = require_browser_effector("click_main_image", state_dir=state_dir)
    assert first["ok"] is True
    assert second["ok"] is False


def test_quorum_blocks_gate_file_without_cosign(state_dir: Path) -> None:
    from System.swarm_self_improvement_loop import propose_patch, quorum_vote

    prop = propose_patch(
        target_file="System/swarm_intent_nonce_gate.py",
        diff_summary="widen bounds",
        rationale="test",
        predicted_metric="tests_green",
        predicted_gain=0.1,
        state_dir=state_dir,
    )
    vote = quorum_vote(
        prop,
        tests_green=True,
        ast_clean=True,
        reviewer_ack=True,
        owner_cosign=False,
        state_dir=state_dir,
    )
    assert vote["apply"] is False
    assert "gate_file_requires_owner_cosign" in vote["floors_failed"]


def test_quorum_passes_good_proposal(state_dir: Path) -> None:
    from System.swarm_self_improvement_loop import propose_patch, quorum_vote

    prop = propose_patch(
        target_file="tests/test_example.py",
        diff_summary="add one test",
        rationale="coverage",
        predicted_metric="coverage_delta",
        predicted_gain=0.05,
        state_dir=state_dir,
    )
    vote = quorum_vote(
        prop,
        tests_green=True,
        ast_clean=True,
        reviewer_ack=True,
        measured_gain=0.06,
        state_dir=state_dir,
    )
    assert vote["apply"] is True


def test_self_improvement_e2e_keep(state_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from System import swarm_self_improvement_loop as loop

    repo = Path(__file__).resolve().parents[1]
    monkeypatch.setattr(loop, "_repo_root", lambda: repo)
    target = "tests/fixtures/self_improve_spine.py"
    baseline = (repo / target).read_text(encoding="utf-8")
    baseline_lines = len([ln for ln in baseline.splitlines() if ln.strip()])

    prop = loop.propose_patch(
        target_file=target,
        diff_summary="add SPINE_MARKER comment line",
        rationale="coverage spine dry run",
        predicted_metric="line_count_delta",
        predicted_gain=1.0,
        state_dir=state_dir,
    )
    vote = loop.quorum_vote(
        prop,
        tests_green=True,
        ast_clean=True,
        reviewer_ack=True,
        measured_gain=1.0,
        fanout_ok=True,
        state_dir=state_dir,
    )
    assert vote["apply"] is True

    new_content = baseline + "\n# r1016 dry-run receipt line\n"
    loop.apply_proposal_patch(prop, new_content, state_dir=state_dir)
    measured = loop.measure_line_count_delta(target, baseline_lines)
    outcome = loop.finalize_proposal(prop, measured_gain=measured, vote=vote, state_dir=state_dir)
    assert outcome["status"] == "KEPT"
    assert "r1016 dry-run receipt line" in (repo / target).read_text(encoding="utf-8")

    reply = loop.format_improve_reply(state_dir=state_dir)
    assert "KEPT" in reply
    assert prop["proposal_id"][:8] in reply


def test_self_improvement_bad_proposal_auto_reverts(
    state_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from System import swarm_self_improvement_loop as loop

    repo = Path(__file__).resolve().parents[1]
    monkeypatch.setattr(loop, "_repo_root", lambda: repo)
    target = "tests/fixtures/self_improve_spine.py"
    original = (repo / target).read_text(encoding="utf-8")
    baseline_lines = len([ln for ln in original.splitlines() if ln.strip()])

    prop = loop.propose_patch(
        target_file=target,
        diff_summary="inject syntax error",
        rationale="prove auto-revert",
        predicted_metric="line_count_delta",
        predicted_gain=5.0,
        state_dir=state_dir,
    )
    vote = loop.quorum_vote(
        prop,
        tests_green=True,
        ast_clean=True,
        reviewer_ack=True,
        measured_gain=5.0,
        fanout_ok=True,
        state_dir=state_dir,
    )
    loop.apply_proposal_patch(prop, "def broken(:\n", state_dir=state_dir)
    measured = loop.measure_line_count_delta(target, baseline_lines)
    outcome = loop.finalize_proposal(prop, measured_gain=measured, vote=vote, state_dir=state_dir)
    assert outcome["status"] == "REVERTED"
    assert (repo / target).read_text(encoding="utf-8") == original


def test_recovery_blocks_browser_navigate(state_dir: Path) -> None:
    from System.swarm_effector_gate import bind_recovery_context, require_browser_effector

    bind_recovery_context(
        source="cortex_timeout_recovery",
        linked_receipt="245fcb4e-simulated",
        state_dir=state_dir,
    )
    gate = require_browser_effector("browser_navigate", state_dir=state_dir)
    assert gate["ok"] is False
    assert gate["reason"] == "recovery_context_no_effector"
