import json

from System.swarm_multimodal_grounding_gate import ingest_multimodal_reality


def test_ingest_writes_input_reality_lane(tmp_path):
    root = tmp_path
    wrapped = ingest_multimodal_reality("https://example.com pasted here", has_image=False, root=root)
    ledger = root / ".sifta_state" / "multimodal_telemetry_receipts.jsonl"
    assert ledger.is_file()
    line = ledger.read_text(encoding="utf-8").strip().splitlines()[-1]
    row = json.loads(line)
    assert row["input_reality_lane"] == "REMOTE_URL_PRESENT"
    assert "ingress_lane=REMOTE_URL_PRESENT" in wrapped
    assert "[END TELEMETRY RECEIPT]" in wrapped
