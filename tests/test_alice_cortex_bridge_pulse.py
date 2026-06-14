from System.alice_cortex_bridge_pulse import assess_cortex_bridge_pulse


def test_timeout_with_recovery_is_ok_recovering():
 pulse = assess_cortex_bridge_pulse(
 [
 {"event": "codex cortex timed out after 150s"},
 {
 "event": "turn preserved in body-stabilization queue",
 "receipt_id": "7951e4bf-79dc-4615-88de-8d38545a3b08",
 },
 ]
 )

 assert pulse.ok is True
 assert pulse.status == "ok_recovering"
 assert "cortex_timeout" not in pulse.blockers
 assert pulse.recoveries == ("7951e4bf-79dc-4615-88de-8d38545a3b08",)
 assert "caught the cortex fault" in pulse.owner_line()


def test_unrecognized_execute_is_not_body_down():
 pulse = assess_cortex_bridge_pulse(
 [{"event": "EXECUTE was triggered but the command context wasn't recognized"}]
 )

 assert pulse.ok is True
 assert pulse.status == "ok_needs_clarified_execute"
 assert pulse.blockers == ("execute_unrecognized",)


def test_timeout_without_recovery_remains_blocked():
 pulse = assess_cortex_bridge_pulse([{"message": "no first token; cortex stalled"}])

 assert pulse.ok is False
 assert pulse.status == "blocked"
 assert pulse.blockers == ("cortex_timeout",)
