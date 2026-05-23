"""test_stigmero_body_connection_proof.py

Falsifier: if ANY check in build_body_connection_proof() returns ok=False,
           the hand (Stigmerobotics) is not properly attached to Alice's body.

This test runs as part of the active proof runner in sifta_stigmerobotics_widget.py.
It is the machine-readable receipt that "Stigmerobotics is Alice's attached hand."

Covenant §6 (effector/claim vs. receipt), §7.2 (deterministic fast paths),
§7.12 (probe-before-claim), §8.6 (absorption).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

from System.stigmerobotics_body_connection import (
    ATTACHMENT_ROLE,
    ORGANS,
    BodyConnectionProof,
    build_body_connection_proof,
)


@pytest.fixture(scope="module")
def proof() -> BodyConnectionProof:
    return build_body_connection_proof()


# ── Structural invariants ─────────────────────────────────────────────────────

def test_attachment_role(proof: BodyConnectionProof) -> None:
    """The proof must declare itself as Alice's attached hand, not a second OS."""
    assert proof.attachment_role == ATTACHMENT_ROLE


def test_organ_count(proof: BodyConnectionProof) -> None:
    """All 13 registered organs must be present in the proof."""
    assert proof.organ_count == len(ORGANS)
    assert proof.organ_count >= 13


def test_overall_pass(proof: BodyConnectionProof) -> None:
    """The proof verdict must be PASS. Any failing check is a body disconnect."""
    failing = proof.failing_checks
    assert proof.ok, (
        f"Body connection proof FAILED. Disconnected checks:\n"
        + "\n".join(f"  - {c.name}: {c.detail}" for c in failing)
    )


# ── macOS-like singleton distro law ──────────────────────────────────────────

def test_macos_manifest_singleton(proof: BodyConnectionProof) -> None:
    """Exactly one active Stigmerobotics entry in apps_manifest.json (no fork/second OS)."""
    check = next(c for c in proof.checks if c.name == "macos_manifest_singleton")
    assert check.ok, f"Manifest singleton broken: {check.detail}"


def test_developer_menu_placement(proof: BodyConnectionProof) -> None:
    """Stigmerobotics is in the Developer menu, not a top-level OS."""
    check = next(c for c in proof.checks if c.name == "developer_menu_app")
    assert check.ok, f"Developer menu placement broken: {check.detail}"


def test_no_web_escape_surface(proof: BodyConnectionProof) -> None:
    """No QWebEngineView/browser open — it must remain inside the Python process."""
    check = next(c for c in proof.checks if c.name == "no_web_escape_surface")
    assert check.ok, f"Web escape surface found: {check.detail}"


# ── Organ connectivity ────────────────────────────────────────────────────────

def test_organ_files_present(proof: BodyConnectionProof) -> None:
    """All organ module files and test files exist on disk."""
    check = next(c for c in proof.checks if c.name == "organ_files_present")
    assert check.ok, f"Missing organ files: {check.detail}"


def test_widget_runs_organ_tests(proof: BodyConnectionProof) -> None:
    """All organ tests are included in the Stigmerobotics active proof runner."""
    check = next(c for c in proof.checks if c.name == "widget_runs_organ_tests")
    assert check.ok, f"Organ tests not in active runner: {check.detail}"


def test_e46b_directionality(proof: BodyConnectionProof) -> None:
    """E46b segmental organ exposes wave_direction and propagation_speed."""
    check = next(c for c in proof.checks if c.name == "e46b_directionality_connected")
    assert check.ok, f"E46b directionality not wired: {check.detail}"


def test_e48_truth_labeled(proof: BodyConnectionProof) -> None:
    """E48 physical protocol keeps HYPOTHESIS label and safety gate intact."""
    check = next(c for c in proof.checks if c.name == "e48_boundary_truth_labeled")
    assert check.ok, f"E48 boundary truth label missing: {check.detail}"


# ── Alice Talk fast-path integration ─────────────────────────────────────────

def test_life_recall_fast_path_before_model(proof: BodyConnectionProof) -> None:
    """Day-segment recall runs before LLM generation in _start_brain."""
    check = next(c for c in proof.checks if c.name == "alice_recall_fast_path_before_model")
    assert check.ok, f"Life recall fast path missing or after model: {check.detail}"


def test_work_recall_fast_path_before_model(proof: BodyConnectionProof) -> None:
    """E35 deterministic work recall runs before LLM generation in _start_brain."""
    check = next(c for c in proof.checks if c.name == "alice_work_recall_fast_path_before_model")
    assert check.ok, f"Work recall fast path missing or after model: {check.detail}"


# ── STGM economy integrity ────────────────────────────────────────────────────

def test_stgm_wallet_positive(proof: BodyConnectionProof) -> None:
    """STGM wallet must be non-negative (organism is not bankrupt)."""
    assert proof.wallet_stgm >= 0.0, f"Wallet negative: {proof.wallet_stgm}"


def test_no_double_spend(proof: BodyConnectionProof) -> None:
    """Immune cost is computed once per epoch — no double-spend."""
    assert proof.no_double_spend, "STGM double-spend detected in immune cost epoch"


def test_blocked_actions_charge_zero(proof: BodyConnectionProof) -> None:
    """Blocked immune actions must not be charged to the STGM wallet."""
    check = next((c for c in proof.checks if c.name == "blocked_actions_charge_zero"), None)
    if check is not None:
        assert check.ok, f"Blocked actions are charging: {check.detail}"


# ── Grok-report smoke test ───────────────────────────────────────────────────

def test_grok_report_contains_pass(proof: BodyConnectionProof) -> None:
    """The Grok-ready proof report must contain Verdict: PASS."""
    report = proof.grok_report()
    assert "Verdict: PASS" in report, f"Grok report not PASS:\n{report}"


def test_as_dict_round_trips(proof: BodyConnectionProof) -> None:
    """The proof dict must be JSON-serialisable (for ledger/receipt writing)."""
    import json
    blob = json.dumps(proof.as_dict(), ensure_ascii=False)
    back = json.loads(blob)
    assert back["ok"] == proof.ok
    assert back["organ_count"] == proof.organ_count
    assert back["attachment_role"] == proof.attachment_role


# ── CODE IT ALL — 7 completion checks (2026-05-06 session) ───────────────────

def test_organ_router_wired_in_talk(proof: BodyConnectionProof) -> None:
    """SCAR/identity/body/economy queries route before LLM via organ_router."""
    check = next((c for c in proof.checks if c.name == "organ_router_wired_in_talk"), None)
    assert check is not None, "organ_router_wired_in_talk check missing from proof"
    assert check.ok, f"Organ router not wired in Talk before LLM: {check.detail}"


def test_ide_registry_all_three_resolve(proof: BodyConnectionProof) -> None:
    """CG55M/AG46/C55M all resolve from ide_model_registry on this node."""
    check = next((c for c in proof.checks if c.name == "ide_registry_all_three_resolve"), None)
    assert check is not None, "ide_registry_all_three_resolve check missing from proof"
    assert check.ok, f"IDE registry missing or broken: {check.detail}"


def test_stgm_signed_spend_on_recall(proof: BodyConnectionProof) -> None:
    """STGM_SPEND rows for E35/organ-router use Ed25519 signed rows (no bare SHA256)."""
    check = next((c for c in proof.checks if c.name == "stgm_signed_spend_on_recall"), None)
    assert check is not None, "stgm_signed_spend_on_recall check missing from proof"
    assert check.ok, f"No signed STGM spend rows found: {check.detail}"


def test_boot_sanity_check_first_turn(proof: BodyConnectionProof) -> None:
    """Epistemic boot sanity check runs in _start_brain on first Talk turn."""
    check = next((c for c in proof.checks if c.name == "boot_sanity_check_first_turn"), None)
    assert check is not None, "boot_sanity_check_first_turn check missing from proof"
    assert check.ok, f"Boot sanity check not found in Talk before LLM: {check.detail}"


def test_bootstrap_registry_runnable(proof: BodyConnectionProof) -> None:
    """System/bootstrap_ide_model_registry.py exists with callable bootstrap_registry()."""
    check = next((c for c in proof.checks if c.name == "bootstrap_registry_runnable"), None)
    assert check is not None, "bootstrap_registry_runnable check missing from proof"
    assert check.ok, f"Bootstrap registry module broken: {check.detail}"


def test_grok_proof_report_on_disk(proof: BodyConnectionProof) -> None:
    """body_connection_proof_report.json must exist in .sifta_state/ for Grok."""
    check = next((c for c in proof.checks if c.name == "grok_proof_report_on_disk"), None)
    assert check is not None, "grok_proof_report_on_disk check missing from proof"
    assert check.ok, f"Grok proof report not on disk: {check.detail}"


def test_tournament_changelog_r_present(proof: BodyConnectionProof) -> None:
    """Tournament changelog (r) with BodyConnectionProof entry must be in tournament doc."""
    check = next((c for c in proof.checks if c.name == "tournament_changelog_r_present"), None)
    assert check is not None, "tournament_changelog_r_present check missing from proof"
    assert check.ok, f"Changelog (r) missing: {check.detail}"


def test_total_check_count(proof: BodyConnectionProof) -> None:
    """Proof must have at least 20 checks (13 original + 7 completion checks)."""
    assert len(proof.checks) >= 20, (
        f"Expected >= 20 checks, got {len(proof.checks)}: "
        + ", ".join(c.name for c in proof.checks)
    )
