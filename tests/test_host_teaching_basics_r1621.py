"""r1621-02 — host teaching present for identity basics (teach not gag)."""
from __future__ import annotations

from System.swarm_alice_body_receipt_answer import body_receipt_teaching_block
from System.swarm_subliminal_cortex_fingerprint import teaching_host_block


def test_host_teaching_names_sifta_and_local_weights(tmp_path):
    block = teaching_host_block(state_dir=tmp_path)
    assert "HOST TEACHING" in block
    assert "SIFTA" in block
    assert "weights" in block.lower() or "cortex" in block.lower()
    assert "gag" in block.lower()


def test_describe_yourself_gets_body_receipt_block(tmp_path):
    b = body_receipt_teaching_block("what are you", state_dir=tmp_path)
    assert "BODY FROM RECEIPTS" in b
    assert "local" in b.lower() or "cortex" in b.lower() or "mind" in b.lower()
