from System.swarm_execute_receipt_status import classify_execute_outcome


def test_row_with_actions_is_executed():
 status = classify_execute_outcome({"actions": ["camera_target"]})

 assert status["status"] == "executed"
 assert status["ok"] is True


def test_none_row_is_refused_unparsed():
 status = classify_execute_outcome(None)

 assert status["status"] == "refused_unparsed"
 assert status["ok"] is False


def test_row_without_actions_needs_router_repair():
 status = classify_execute_outcome({"actions": []})

 assert status["status"] == "needs_router_repair"
 assert status["ok"] is False


def test_error_wins_and_is_not_ok():
 status = classify_execute_outcome({"actions": ["camera_target"]}, error=RuntimeError("boom"))

 assert status["status"] == "error"
 assert status["ok"] is False
 assert "boom" in status["reason"]
