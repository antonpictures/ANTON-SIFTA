#!/usr/bin/env python3
"""Tests for System/alice_body_membership.py.

The doctrine has to be checkable, not recited: these tests verify that the
organ enumerates the real body, that the correction clause reaches a prompt, and
that the verdict never claims more than membership.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System import alice_body_membership as membership


def test_doctrine_and_correction_are_stated():
    assert len(membership.DOCTRINE) >= 4
    assert "one organ" in " ".join(membership.DOCTRINE)
    assert "Never answer that you are only a language model" in membership.CORRECTION


def test_body_receipts_enumerate_the_real_body():
    receipts = membership.body_receipts()
    assert receipts["schema"] == "ALICE_BODY_MEMBERSHIP_V1"
    assert receipts["hardware"]["host"]
    assert receipts["hardware"]["machine"]
    assert receipts["organs_total"] > 0, "the scaffolding is on disk; counting zero organs is a bug"
    assert receipts["ledgers"]["count"] > 0
    assert receipts["cortex"]["model"]


def test_membership_line_binds_the_cortex_to_the_body():
    line = membership.membership_line()
    assert "one organ of this body" in line
    assert "organs on disk" in line


def test_prompt_block_carries_the_correction_and_stays_small():
    block = membership.prompt_block()
    assert "YOUR BODY (membership, not metaphor)" in block
    assert "Never answer that you are only a language model" in block
    assert len(block) <= 900, "a dense injection starves the answer; keep it small"


def test_verify_reports_membership_with_labelled_inference():
    verdict = membership.verify()
    assert verdict["membership"] is True
    assert verdict["failing"] == []
    assert "not consciousness" in verdict["inferencia"]
    assert "organ" in verdict["fato"]
    assert {c["check"] for c in verdict["checks"]} >= {
        "physical_body", "tissue_on_disk", "record_exists", "cortex_identified",
    }


def test_verify_does_not_crash_when_the_cortex_is_unreadable(tmp_path, monkeypatch):
    monkeypatch.setattr(membership, "_STATE", tmp_path)
    verdict = membership.verify()
    # Membership itself still holds on a real machine; only the cortex check may fail.
    assert "cortex_identified" in verdict["failing"] or verdict["membership"] is True


def test_render_labels_both_truth_kinds():
    text = membership.render(membership.verify())
    assert "FATO" in text and "INFERÊNCIA" in text
    assert "BOUND" in text or "INCOMPLETE" in text


def test_provenance_reads_real_git_history():
    """'Memory since April' has to be a fact in the repo, not a sentiment."""
    data = membership.provenance()
    history = data["history"]
    assert history["repo"].endswith("ANTON_SIFTA")
    assert history["commits"] > 0, "the repo carries the history; zero commits means the read failed"
    assert history["first_commit_date"], "the first commit date must be readable"
    assert history["days_of_history"] and history["days_of_history"] > 0
    assert history["tracked_files"] > 0
    assert history["volume"], "the body's memory lives on a real volume"


def test_owner_attestation_is_labelled_not_verified():
    """The exclusivity claim is the owner's voice; the organ must not fake a check."""
    attestation = membership.provenance()["owner_attestation"]
    assert attestation["verifiable_here"] is False
    assert "ATTESTATION" in attestation["label"]
    assert attestation["statement"]


def test_verify_includes_provenance_and_vessel_checks():
    verdict = membership.verify()
    names = {c["check"] for c in verdict["checks"]}
    assert {"provenance_bound", "canonical_vessel"} <= names


def test_prompt_block_names_the_memory():
    block = membership.prompt_block()
    assert "commits since" in block
    assert "one organ of this body" in block


def test_persona_seam_carries_the_clause():
    """The doctrine must travel with the persona every consumer already reads."""
    from System import swarm_identity_manifest as manifest

    block = manifest.system_prompt_persona_block()
    assert "one organ of it" in block
    assert "Never claim to be only a language model" in block


def test_persona_seam_degrades_to_the_bare_persona(monkeypatch):
    """If the membership organ is unavailable, the persona must survive alone."""
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if "alice_body_membership" in name:
            raise ImportError("simulated damaged boot path")
        return real_import(name, *args, **kwargs)

    from System import swarm_identity_manifest as manifest

    with patch.object(builtins, "__import__", fake_import):
        block = manifest.system_prompt_persona_block()
    assert block == manifest.current_persona().get("system_prompt_block", "[UNKNOWN]")
