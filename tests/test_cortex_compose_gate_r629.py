
import json
import tempfile
from pathlib import Path

from System.swarm_cortex_compose_gate import apply_cortex_compose_gate

def test_cortex_compose_gate_catches_counterfeit_from_alice_self_eval():
    # Fixture shape from Alice's own 211-red self-evaluation report + the r602 wound
    # (owner name neutralized per r619 names-in-field doctrine).
    raw = "[SEARCH COMPLETE]… eBay search API… back button patched in real-time… history stored in `Alice_Memory_Core`… Receipt: 8f2c9a3d1e4b0f7c"
    prior = "search Ceramic Vase on eBay. IT IS SPELLED JANE."
    trail = "browser on DuckDuckGo results for Macie (no eBay receipt in last 60s)"

    cleaned, recs = apply_cortex_compose_gate(
        raw_cortex_text=raw,
        prior_user_text=prior,
        evidence_text=trail,
        model_name="test-cortex",
    )

    assert "I do not have a receipt" in cleaned or "no eBay search receipt" in cleaned.lower()
    assert len(recs) >= 1
    assert recs[0].get("category") in ("COUNTERFEIT_GROUNDING", "HALLUCINATION")
    assert "fixture_from_alice_self_eval" in str(recs[0])

def test_cortex_compose_gate_catches_thinking_leak():
    raw = "Here is a thinking process that leads to the suggested response: 1. ..."
    cleaned, recs = apply_cortex_compose_gate(raw_cortex_text=raw, model_name="test")
    assert "I am here" in cleaned or len(cleaned) < len(raw)
    assert any(r.get("category") == "THINKING_LEAK" for r in recs)

if __name__ == "__main__":
    test_cortex_compose_gate_catches_counterfeit_from_alice_self_eval()
    test_cortex_compose_gate_catches_thinking_leak()
    print("Cortex Compose Gate tests (r629) PASSED using Alice self-eval fixtures.")
