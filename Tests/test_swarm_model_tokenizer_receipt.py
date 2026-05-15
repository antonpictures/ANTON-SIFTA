import json
from pathlib import Path

from System import swarm_model_tokenizer_receipt as tok


def test_hash_items_is_stable_and_order_sensitive():
    a, na = tok._hash_items(["<pad>", "<eos>", "hello"])
    b, nb = tok._hash_items(["<pad>", "<eos>", "hello"])
    c, nc = tok._hash_items(["<pad>", "hello", "<eos>"])

    assert na == nb == nc == 3
    assert a == b
    assert a != c


def test_compare_model_tokenizers_writes_observed_shared_receipt(monkeypatch, tmp_path: Path):
    def fake_summary(model: str, *, blob_path=None):
        return {
            "model": model,
            "blob_path": f"/models/{model}",
            "blob_sha256": "a" * 64 if "draft" in model else "b" * 64,
            "blob_size_bytes": 123,
            "architecture": "gemma4",
            "context_length": 131072,
            "embedding_length": 1536 if "draft" in model else 2560,
            "tokenizer_hash": "shared-tokenizer",
            "tokenizer_fields": {},
            "vocab_size": 262144,
            "merge_count": 514906,
            "token_type_count": 262144,
            "score_count": 262144,
        }

    monkeypatch.setattr(tok, "read_model_tokenizer_summary", fake_summary)
    ledger = tmp_path / "model_tokenizer_receipts.jsonl"

    row = tok.compare_model_tokenizers(
        "sifta-gemma4-draft:latest",
        "alice-m5-cortex-8b-6.3gb:latest",
        ledger_path=ledger,
        write_ledger=True,
        trace_id="trace-test",
    )

    assert row["same_tokenizer_hash"] is True
    assert row["same_vocabulary_status"] == "OBSERVED_SHARED_TOKENIZER"
    assert row["tokenizer_hash"] == "shared-tokenizer"
    stored = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert stored[0]["trace_id"] == "trace-test"
    assert stored[0]["draft"]["vocab_size"] == 262144


def test_compare_model_tokenizers_detects_mismatch(monkeypatch):
    def fake_summary(model: str, *, blob_path=None):
        return {
            "model": model,
            "blob_path": f"/models/{model}",
            "blob_sha256": "a" * 64,
            "blob_size_bytes": 123,
            "architecture": "gemma4",
            "context_length": 131072,
            "embedding_length": 1536,
            "tokenizer_hash": "draft-hash" if "draft" in model else "target-hash",
            "tokenizer_fields": {},
            "vocab_size": 262144,
            "merge_count": 514906,
            "token_type_count": 262144,
            "score_count": 262144,
        }

    monkeypatch.setattr(tok, "read_model_tokenizer_summary", fake_summary)

    row = tok.compare_model_tokenizers("draft", "target")

    assert row["same_tokenizer_hash"] is False
    assert row["same_vocabulary_status"] == "OBSERVED_TOKENIZER_MISMATCH"
    assert row["tokenizer_hash"] is None


def test_proof_of_property_is_true():
    assert tok.proof_of_property()["ok"] is True
