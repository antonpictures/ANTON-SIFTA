import time
import pytest
from System.swarm_cerebellum_timing import CerebellumTiming

def test_bishop_proof_of_property():
    """
    MANDATE VERIFICATION — BISHOP CEREBELLAR TIMING TEST.
    Numerically proves that the forward model prevents rapid-fire overcorrection
    while dynamically adapting to the host machine's actual hardware latency.
    """
    # Event 77 configuration
    cerebellum = CerebellumTiming(default_expected_latency=1.0, correction_gain=0.5, persist_receipts=False)
    action = "execute_terminal_command"
    
    # Phase 1: Initial Impulse (No prior history)
    # The first time it evaluates should_delay, it returns 0.0 but it sets the _last_end_ts.
    delay_1 = cerebellum.should_delay(action, urgency=0.1)
    assert delay_1 == 0.0, "[FAIL] Cerebellum unnecessarily blocked a fresh action."
    
    # Phase 2: Simulating OS Lag & Prediction Error Update
    # The terminal command takes 3.0 seconds to execute (very slow)
    update_receipt = cerebellum.update(action, observed_latency=3.0, ok=True)
    timing_error = update_receipt.timing_error
    next_latency = update_receipt.next_expected_latency
    
    # Expected latency was 1.0. Observed is 3.0. Error = 2.0.
    # New expected = 1.0 + (0.5 * 2.0) = 2.0
    assert next_latency == pytest.approx(2.0)
    
    # Phase 3: Immediate Spastic Re-fire Attempt (Ataxia simulation)
    # Alice immediately tries to fire the same command. But she should wait!
    # time_since_last evaluates to 0.0 because update() also sets _last_end_ts to now.
    # Expected is 2.0. 
    delay_2 = cerebellum.should_delay(action, urgency=0.1)
    
    # Mathematical Proof: The cerebellum must force a delay > 0 to wait out the new expected latency
    assert delay_2 > 0.0, "[FAIL] Cerebellum failed to dampen the spastic overcorrection."
    
    # Phase 4: Extreme Urgency Override
    # A massive threat requires immediate execution
    delay_3 = cerebellum.should_delay(action, urgency=0.95)
    assert delay_3 == 0.0, "[FAIL] Cerebellum failed to yield to high-urgency sympathetic drive."
