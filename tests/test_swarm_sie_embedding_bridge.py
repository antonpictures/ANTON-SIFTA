"""r1622-01 — SIE probe is honest when offline."""
from __future__ import annotations

from System.swarm_sie_embedding_bridge import encode_texts, probe_sie, sie_status_block


def test_probe_offline_is_not_ok(tmp_path):
    row = probe_sie(
        base_url="http://127.0.0.1:59999",
        timeout_s=0.3,
        state_dir=tmp_path,
        write_receipt=True,
    )
    assert row["ok"] is False
    assert row.get("error")


def test_encode_refuses_without_connection():
    out = encode_texts(["hello"])
    assert out["ok"] is False
    assert out["reason"] == "sie_not_connected"


def test_status_block_does_not_claim_running():
    block = sie_status_block()
    assert "SIE" in block
    # either NOT RUNNING or REACHABLE — never silent pretend
    assert "NOT RUNNING" in block or "REACHABLE" in block
