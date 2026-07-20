"""R1625-02 claim chorus — receipts as paddle votes."""
from __future__ import annotations

from System.swarm_claim_chorus_gate import gate_browser_mouth_claim


def test_solo_see_claim_without_receipt_is_blocked(tmp_path):
    out = gate_browser_mouth_claim(
        "I can see the Mercedes page on my browser and I searched it successfully.",
        state_dir=tmp_path,
    )
    # no live page state under tmp → red chorus
    assert out["changed"] is True
    assert "refuse" in out["text"].lower() or "receipt" in out["text"].lower()


def test_no_claim_passes():
    out = gate_browser_mouth_claim("Hello George, how are you?")
    assert out["changed"] is False
