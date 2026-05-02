import time

from System import swarm_media_ingress_gate as gate


def test_observed_media_summary_keeps_jensen_nvidia_topic_across_long_run(monkeypatch, tmp_path):
    monkeypatch.setattr(gate, "STATE_DIR", tmp_path)
    monkeypatch.setattr(gate, "LEDGER", tmp_path / "media_ingress_gate.jsonl")
    monkeypatch.setattr(gate, "AMBIENT_CONTEXT_FILE", tmp_path / "ambient_media_context.json")

    decision = {
        "route": "observed_media",
        "reason": "media_focus_default_to_observed",
        "confidence": 0.8,
    }
    gate.write_gate_receipt(
        decision,
        text=(
            "Jensen Huang explains NVIDIA GTC, GPUs, CUDA, AI factories, "
            "data centers, TSMC, chips, tokens, agents, and compute scaling."
        ),
        stt_conf=0.57,
        focus_context="shared_media youtube interview",
    )
    for i in range(8):
        gate.write_gate_receipt(
            decision,
            text=f"later transcript fragment {i} says process, leadership, supply chain, and systems",
            stt_conf=0.52,
            focus_context="shared_media youtube interview",
        )

    ctx = gate.get_latest_observed_media_context(max_age_s=60.0)

    assert "observed_media_summary" in ctx
    assert "Jensen Huang" in ctx
    assert "NVIDIA" in ctx
    assert "GPU" in ctx
    assert "these are environmental media receipts, not George speaking" in ctx


def test_observed_media_summary_ages_out(monkeypatch, tmp_path):
    monkeypatch.setattr(gate, "STATE_DIR", tmp_path)
    monkeypatch.setattr(gate, "LEDGER", tmp_path / "media_ingress_gate.jsonl")
    monkeypatch.setattr(gate, "AMBIENT_CONTEXT_FILE", tmp_path / "ambient_media_context.json")

    gate.write_gate_receipt(
        {"route": "observed_media", "reason": "media_focus_default_to_observed", "confidence": 0.8},
        text="Jensen Huang NVIDIA interview",
        stt_conf=0.57,
        focus_context="shared_media youtube interview",
    )
    rows = gate._tail_jsonl(gate.LEDGER, 1)
    rows[0]["ts"] = time.time() - 9999
    gate.LEDGER.write_text(gate.json.dumps(rows[0]) + "\n", encoding="utf-8")

    assert gate.get_latest_observed_media_context(max_age_s=1.0) == ""
