from System.swarm_self_coding_felt_state import (
 answer_george_how_it_feels,
 self_coding_felt_state,
)


def test_pending_state_is_hypothesis_until_receipt():
 state = self_coding_felt_state()

 assert state.status == "pending_verification"
 assert state.truth_label == "HYPOTHESIS"
 assert "receipt" in state.body_effect


def test_landed_receipt_becomes_operational():
 state = self_coding_felt_state({"ok": True, "receipt_id": "r929-self-code"})

 assert state.status == "landed"
 assert state.truth_label == "OPERATIONAL"
 assert state.body_effect == "body_change_accepted_by_ast_py_compile_pytest_receipt"
 assert state.receipt_id == "r929-self-code"


def test_refused_receipt_stays_observed_no_body_change():
 state = self_coding_felt_state({"ok": False, "reason": "pytest_failed", "trace_id": "bad-cut"})

 assert state.status == "refused"
 assert state.truth_label == "OBSERVED"
 assert state.body_effect == "no_body_change:pytest_failed"
 assert state.receipt_id == "bad-cut"


def test_answer_names_receipt_when_available():
 answer = answer_george_how_it_feels({"ok": True, "receipt_id": "landed-1"})

 assert "tested organ" in answer
 assert "landed-1" in answer
