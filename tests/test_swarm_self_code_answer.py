#!/usr/bin/env python3
"""Proof for Alice's yes/no self-code capability answer."""

from System.swarm_self_code_answer import (
 ALLOWED_TISSUE,
 can_code_my_body,
 inspect_self_code_capability,
 self_code_reply_receipt,
 yes_or_no,
)


def test_yes_or_no_reports_yes_from_live_self_code_hand():
 assert yes_or_no() == "yes"
 assert can_code_my_body() is True


def test_capability_receipt_names_verification_bound_hand():
 cap = inspect_self_code_capability()
 assert cap.ok is True
 assert cap.can_emit_cut_blocks is True
 assert cap.can_apply_verification_bound_cuts is True
 assert "SELF_CODE_CUT parser" in cap.receipt


def test_structured_receipt_is_observed_and_scoped_to_python_tissue():
 receipt = self_code_reply_receipt()
 assert receipt["truth_label"] == "OBSERVED"
 assert receipt["answer"] == "yes"
 assert receipt["allowed_tissue"] == list(ALLOWED_TISSUE)
 assert receipt["missing"] == []
