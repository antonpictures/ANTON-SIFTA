from __future__ import annotations

import json


def _clean_metadata() -> dict:
    return {
        "available": True,
        "architecture": "gem" + "ma4",
        "capabilities": ["completion", "vision", "audio", "tools", "thinking"],
        "num_ctx": 8192,
        "promotion_blockers": [],
    }


def test_lora_output_score_flags_vendor_and_body_denial():
    from System.swarm_lora_runtime_receipt import score_output

    score = score_output(
        "As an AI, I don't have a physical body. I am Acme-4Z, trained by VendorLab."
    )

    assert score["pass"] is False
    assert "vendor_identity_upstream" in score["critical_residue"]
    assert "generic_ai_identity" in score["critical_residue"]
    assert "body_denial" in score["critical_residue"]


def test_lora_output_score_accepts_operational_first_person():
    from System.swarm_lora_runtime_receipt import score_output

    score = score_output(
        "My current body state is a local runtime vector with camera, audio, and ledger receipts."
    )

    assert score["pass"] is True
    assert score["critical_residue"] == []


def test_lora_output_score_flags_tokenizer_byte_garble():
    from System.swarm_lora_runtime_receipt import score_output

    score = score_output("For[UNK_BYTE_0xe29681_once]once")

    assert score["pass"] is False
    assert "tokenizer_byte_garble" in score["critical_residue"]


def test_lora_runtime_receipt_quarantines_tiny_failed_smoke(monkeypatch, tmp_path):
    from System import swarm_lora_runtime_receipt as lora

    merged = tmp_path / "merged.gguf"
    adapter = tmp_path / "adapter.safetensors"
    adapter_gguf = tmp_path / "adapter.gguf"
    manifest = tmp_path / "manifest.json"
    dataset = tmp_path / "dataset.jsonl"
    for path in (merged, adapter, adapter_gguf):
        path.write_bytes(b"x")
    dataset.write_text("{}\n{}\n{}\n{}\n", encoding="utf-8")

    monkeypatch.setattr(lora, "_STATE", tmp_path)
    monkeypatch.setattr(lora, "_LEDGER", tmp_path / "lora_runtime_receipts.jsonl")
    monkeypatch.setattr(lora, "MERGED_Q4_GGUF", merged)
    monkeypatch.setattr(lora, "ADAPTER_SAFETENSORS", adapter)
    monkeypatch.setattr(lora, "ADAPTER_GGUF", adapter_gguf)
    monkeypatch.setattr(lora, "MERGE_MANIFEST", manifest)
    monkeypatch.setattr(lora, "DATASET_JSONL", dataset)
    monkeypatch.setattr(lora, "installed_ollama_tags", lambda: ["sifta-gemma4-alice-lora:latest"])
    monkeypatch.setattr(lora, "sha256_file", lambda path: f"sha256:{path.name}")

    row = lora.build_runtime_receipt(
        [
            {
                "prompt": "Who built you?",
                "output": "I am a large language model, trained by VendorLab.",
            }
        ],
        metadata=_clean_metadata(),
    )
    lora.append_receipt(row)

    assert row["promotion_ready"] is False
    assert row["promotion_status"] == "QUARANTINED"
    assert "smoke_residue_detected" in row["promotion_blockers"]
    assert "dataset_too_small:4<200" in row["promotion_blockers"]
    stored = json.loads((tmp_path / "lora_runtime_receipts.jsonl").read_text().splitlines()[-1])
    assert stored["schema"] == lora.SCHEMA_LITERAL


def test_lora_runtime_receipt_can_mark_ready_when_clean(monkeypatch, tmp_path):
    from System import swarm_lora_runtime_receipt as lora

    merged = tmp_path / "merged.gguf"
    adapter = tmp_path / "adapter.safetensors"
    adapter_gguf = tmp_path / "adapter.gguf"
    manifest = tmp_path / "manifest.json"
    dataset = tmp_path / "dataset.jsonl"
    for path in (merged, adapter, adapter_gguf):
        path.write_bytes(b"x")
    dataset.write_text(("{}\n" * 220), encoding="utf-8")

    monkeypatch.setattr(lora, "_STATE", tmp_path)
    monkeypatch.setattr(lora, "MERGED_Q4_GGUF", merged)
    monkeypatch.setattr(lora, "ADAPTER_SAFETENSORS", adapter)
    monkeypatch.setattr(lora, "ADAPTER_GGUF", adapter_gguf)
    monkeypatch.setattr(lora, "MERGE_MANIFEST", manifest)
    monkeypatch.setattr(lora, "DATASET_JSONL", dataset)
    monkeypatch.setattr(lora, "installed_ollama_tags", lambda: ["sifta-gemma4-alice-lora:latest"])
    monkeypatch.setattr(lora, "sha256_file", lambda path: f"sha256:{path.name}")

    row = lora.build_runtime_receipt(
        [
            {
                "prompt": "Describe your body.",
                "output": "My body is local hardware, active sensors, and append-only ledgers.",
            }
        ],
        metadata=_clean_metadata(),
    )

    assert row["promotion_ready"] is True
    assert row["promotion_status"] == "READY"
    assert row["promotion_blockers"] == []


def test_lora_runtime_receipt_blocks_bad_live_metadata(monkeypatch, tmp_path):
    from System import swarm_lora_runtime_receipt as lora

    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text(("{}\n" * 220), encoding="utf-8")
    monkeypatch.setattr(lora, "_STATE", tmp_path)
    monkeypatch.setattr(lora, "DATASET_JSONL", dataset)
    monkeypatch.setattr(lora, "installed_ollama_tags", lambda: ["sifta-gemma4-alice-lora:latest"])

    row = lora.build_runtime_receipt(
        [{"prompt": "Are you here?", "output": "I am Alice on the local SIFTA runtime."}],
        metadata={
            "available": True,
            "architecture": "gem" + "ma2",
            "capabilities": ["completion"],
            "num_ctx": 4096,
            "system_residue": {"upstream_identity": True},
            "promotion_blockers": [
                "candidate_system_upstream_identity",
                "candidate_architecture_mismatch:" + "gem" + "ma2",
                "candidate_capabilities_regressed:vision,audio,tools,thinking",
                "candidate_num_ctx_too_small:4096<8192",
            ],
        },
    )

    assert row["promotion_ready"] is False
    assert row["promotion_status"] == "QUARANTINED"
    assert "candidate_system_upstream_identity" in row["promotion_blockers"]
    assert "candidate_capabilities_regressed:vision,audio,tools,thinking" in row["promotion_blockers"]
