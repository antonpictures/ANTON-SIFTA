import json
import time
from pathlib import Path

import pytest

from System import swarm_speculative_draft as spec


def _reset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, enabled: bool = True) -> Path:
    path = tmp_path / "alice_draft_buffer.jsonl"
    monkeypatch.setattr(spec, "_ENABLED", enabled)
    monkeypatch.setattr(spec, "_BUFFER_FILE", path)
    monkeypatch.setattr(spec, "_DRAFT_MODEL", "gemma4:e2b")
    monkeypatch.setattr(spec, "_MAIN_MODEL", "alice-m5-cortex-8b-6.3gb:latest")
    monkeypatch.setattr(spec, "_SAME_VOCAB_HINT", "gemma4-family")
    monkeypatch.setattr(spec, "_NATIVE_TOKEN_VERIFIER", False)
    monkeypatch.setattr(spec, "_draft_result", None)
    monkeypatch.setattr(spec, "_pending_text", None)
    monkeypatch.setattr(spec, "_DRAFT_TTL_S", 12.0)
    return path


def _seed_draft(trace_id: str = "draft-1", *, ts: float | None = None) -> None:
    spec._draft_result = {
        "user_text": "Alice, answer from your body.",
        "draft_text": "I answer from my local SIFTA runtime.",
        "model": "gemma4:e2b",
        "elapsed_s": 0.2,
        "ts": time.time() if ts is None else ts,
        "trace_id": trace_id,
        "verification_status": "UNVERIFIED",
        "pair_truth": spec.model_pair_truth(probe=False),
    }


def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_consume_without_verifier_blocks_draft_and_appends_receipt(tmp_path, monkeypatch):
    path = _reset(tmp_path, monkeypatch)
    _seed_draft("no-verifier")

    out = spec.consume_draft("Alice, answer from your body.")

    assert out is None
    rows = _rows(path)
    assert rows[-1]["event"] == "draft_unverified_blocked"
    assert rows[-1]["verification_status"] == "UNVERIFIED_BLOCKED"
    assert rows[-1]["parent_trace_id"] == "no-verifier"
    assert rows[-1]["pair_truth"]["speculative_tier"] == "SAME_FAMILY_VERIFIED_PREFETCH"
    assert rows[-1]["pair_truth"]["commit_law"] == "draft_text_must_not_speak_without_target_verifier"


def test_consume_accepts_only_after_caller_verifier(tmp_path, monkeypatch):
    path = _reset(tmp_path, monkeypatch)
    _seed_draft("accept-me")

    out = spec.consume_draft(
        "Alice, answer from your body.",
        verifier=lambda text, row: text.startswith("I answer") and row["trace_id"] == "accept-me",
    )

    assert out == "I answer from my local SIFTA runtime."
    rows = _rows(path)
    assert rows[-1]["event"] == "draft_verification"
    assert rows[-1]["verification_status"] == "VERIFIED_ACCEPTED"
    assert rows[-1]["parent_trace_id"] == "accept-me"


def test_consume_rejects_when_verifier_rejects(tmp_path, monkeypatch):
    path = _reset(tmp_path, monkeypatch)
    _seed_draft("reject-me")

    out = spec.consume_draft("Alice, answer from your body.", verifier=lambda _text, _row: False)

    assert out is None
    rows = _rows(path)
    assert rows[-1]["verification_status"] == "VERIFIED_REJECTED"


def test_expired_draft_never_speaks(tmp_path, monkeypatch):
    path = _reset(tmp_path, monkeypatch)
    monkeypatch.setattr(spec, "_DRAFT_TTL_S", 0.01)
    _seed_draft("expired", ts=time.time() - 10.0)

    out = spec.consume_draft("Alice, answer from your body.", verifier=lambda _text, _row: True)

    assert out is None
    rows = _rows(path)
    assert rows[-1]["event"] == "draft_expired"
    assert rows[-1]["verification_status"] == "EXPIRED"


def test_draft_worker_appends_ready_row_without_rewriting(tmp_path, monkeypatch):
    path = _reset(tmp_path, monkeypatch)
    monkeypatch.setattr(spec, "_pending_text", "Alice, answer from your body.")
    monkeypatch.setattr(spec, "_ollama_generate", lambda **_kwargs: "Draft from E2B.")

    spec._draft_worker("Alice, answer from your body.")

    rows = _rows(path)
    assert len(rows) == 1
    assert rows[0]["event"] == "draft_ready"
    assert rows[0]["verification_status"] == "UNVERIFIED"
    assert rows[0]["pair_truth"]["same_vocabulary_status"] == "EXPECTED_GEMMA4_SHARED_TOKENIZER"
    assert spec._draft_result["draft_text"] == "Draft from E2B."


def test_status_report_states_verifier_law_when_disabled(tmp_path, monkeypatch):
    _reset(tmp_path, monkeypatch, enabled=False)

    report = spec.status_report()

    assert "DISABLED" in report
    assert "requires caller-supplied target verifier" in report
    assert "SAME_FAMILY_VERIFIED_PREFETCH" in report


def test_model_pair_truth_same_family_but_lora_shape_diff(monkeypatch):
    monkeypatch.setattr(spec, "_DRAFT_MODEL", "gemma4:e2b")
    monkeypatch.setattr(spec, "_MAIN_MODEL", "alice-m5-cortex-8b-6.3gb:latest")
    monkeypatch.setattr(spec, "_SAME_VOCAB_HINT", "gemma4-family")
    monkeypatch.setattr(spec, "_NATIVE_TOKEN_VERIFIER", False)
    monkeypatch.setattr(spec, "compare_model_tokenizers", None)

    def fake_show(model: str) -> dict:
        if model == "gemma4:e2b":
            return {"architecture": "gemma4", "embedding_length": "1536"}
        return {"architecture": "gemma4", "embedding_length": "2560"}

    monkeypatch.setattr(spec, "_ollama_show_summary", fake_show)

    truth = spec.model_pair_truth(probe=True)

    assert truth["same_family"] is True
    assert truth["same_architecture"] is True
    assert truth["same_embedding_length"] is False
    assert truth["same_vocabulary_status"] == "EXPECTED_GEMMA4_SHARED_TOKENIZER"
    assert truth["lora_adapter_status"] == "SHARED_DATASET_YES_IDENTICAL_LORA_TENSORS_NO_SHAPE_DIFF"
    assert truth["native_token_verifier"] == "CALLER_VERIFIER_REQUIRED"


def test_model_pair_truth_promotes_observed_tokenizer_receipt(monkeypatch):
    monkeypatch.setattr(spec, "_DRAFT_MODEL", "sifta-gemma4-draft:latest")
    monkeypatch.setattr(spec, "_MAIN_MODEL", "alice-m5-cortex-8b-6.3gb:latest")
    monkeypatch.setattr(spec, "_SAME_VOCAB_HINT", "gemma4-family")
    monkeypatch.setattr(spec, "_NATIVE_TOKEN_VERIFIER", False)
    monkeypatch.setattr(
        spec,
        "_ollama_show_summary",
        lambda model: {"architecture": "gemma4", "embedding_length": "1536"},
    )

    def fake_compare(draft_model: str, target_model: str, *, write_ledger: bool = False):
        return {
            "trace_id": "tok-proof",
            "same_vocabulary_status": "OBSERVED_SHARED_TOKENIZER",
            "same_tokenizer_hash": True,
            "tokenizer_hash": "abc123",
            "native_token_verifier": "NOT_PROVEN_BY_TOKENIZER_HASH",
            "draft": {"vocab_size": 262144, "merge_count": 514906, "blob_sha256": "a" * 64},
            "target": {"vocab_size": 262144, "merge_count": 514906, "blob_sha256": "b" * 64},
        }

    monkeypatch.setattr(spec, "compare_model_tokenizers", fake_compare)

    truth = spec.model_pair_truth(probe=True)

    assert truth["same_vocabulary_status"] == "OBSERVED_SHARED_TOKENIZER"
    assert truth["tokenizer_receipt"]["trace_id"] == "tok-proof"
    assert truth["tokenizer_receipt"]["draft_vocab_size"] == 262144
    assert truth["native_token_verifier"] == "CALLER_VERIFIER_REQUIRED"
