"""Tests for swarm_mammal_organ — MAMMAL as a SIFTA tool organ.

Architect 2026-05-13 23:55: "I WANT THE LLM AS ONE OF OUR ORGANS/TOOLS"

The wrapper is testable WITHOUT downloading the 458M model. Tests
exercise:
  - weights_present() returns False when model not on disk
  - pull_instructions() returns the exact commands the architect runs
  - find_mammal_weights() probes the canonical paths
  - query() returns a clean error (no silent fakes) when weights missing
  - failed-query receipts still get written (evidence even on failure)
  - status() snapshot matches truth_label / model_id
  - The query result carries truth_class=HYPOTHESIS per truth boundary

The "model actually loads and embeds" path requires real weights — we
verify it only via the load_error code path and a monkeypatched fake.
"""
import hashlib
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import System.swarm_mammal_organ as organ_mod
from System.swarm_mammal_organ import (
    DEFAULT_MODEL_ID,
    LEDGER_NAME,
    MammalOrgan,
    MammalQueryResult,
    TRUTH_LABEL_ORGAN,
    TRUTH_LABEL_QUERY,
    find_mammal_weights,
    pull_instructions,
)


# ── Discovery / probe ─────────────────────────────────────────────

def test_default_model_id_matches_paper():
    """The IBM Research paper figure shows biomed.omics.bl.sm.ma-ted-458m."""
    assert DEFAULT_MODEL_ID == "ibm-research/biomed.omics.bl.sm.ma-ted-458m"


def test_find_mammal_weights_returns_present_false_when_missing(tmp_path, monkeypatch):
    """Empty paths → present=False, location=None."""
    monkeypatch.setenv("HF_HOME", str(tmp_path / "hf"))
    out = find_mammal_weights(model_id="ibm/dummy-fake-model")
    assert out["present"] is False
    assert out["location"] is None
    assert out["evidence_files"] == []
    # Probes the right canonical paths
    assert any("models--ibm--dummy-fake-model" in p
               for p in out["candidate_paths_probed"])


def test_find_mammal_weights_detects_present_safetensors(tmp_path, monkeypatch):
    """Drop a .safetensors file in the expected HF cache, expect present=True."""
    fake_hf = tmp_path / "hf"
    cache_dir = fake_hf / "hub" / "models--ibm--fake-model"
    cache_dir.mkdir(parents=True)
    (cache_dir / "model.safetensors").write_bytes(b"\x00" * 16)
    monkeypatch.setenv("HF_HOME", str(fake_hf))
    out = find_mammal_weights(model_id="ibm/fake-model")
    assert out["present"] is True
    assert out["location"] == str(cache_dir)
    assert len(out["evidence_files"]) >= 1


def test_find_mammal_weights_detects_sifta_state_copy(tmp_path, monkeypatch):
    """Codex weight-manager copies under .sifta_state must satisfy the organ."""
    monkeypatch.setattr(organ_mod, "_STATE", tmp_path / ".sifta_state")
    local_dir = tmp_path / ".sifta_state" / "mammal_weights" / "fake-model"
    local_dir.mkdir(parents=True)
    (local_dir / "model.safetensors").write_bytes(b"\x00" * 16)
    out = find_mammal_weights(model_id="ibm/fake-model")
    assert out["present"] is True
    assert out["location"] == str(local_dir)
    assert str(local_dir) in out["candidate_paths_probed"][0]


def test_pull_instructions_includes_hf_command():
    """The architect must see the exact pull command."""
    instr = pull_instructions(DEFAULT_MODEL_ID)
    assert "huggingface-cli download" in instr
    assert DEFAULT_MODEL_ID in instr
    assert "pip3 install" in instr or "pip install" in instr
    # Must include the gated-model 403 fallback
    assert "huggingface-cli login" in instr or "403" in instr


# ── Organ status ──────────────────────────────────────────────────

def test_organ_status_when_weights_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("HF_HOME", str(tmp_path / "hf"))
    organ = MammalOrgan(model_id="ibm/missing-model", state_root=tmp_path)
    s = organ.status()
    assert s["truth_label"] == TRUTH_LABEL_ORGAN
    assert s["model_id"] == "ibm/missing-model"
    assert s["weights_present"] is False
    assert s["loaded"] is False
    assert s["pull_instructions"] is not None
    assert "huggingface-cli download" in s["pull_instructions"]


def test_organ_weights_present_false_when_no_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("HF_HOME", str(tmp_path / "hf"))
    organ = MammalOrgan(model_id="ibm/missing-model", state_root=tmp_path)
    assert organ.weights_present() is False


# ── Query — failure paths (no silent fakes) ──────────────────────

def test_query_returns_clean_error_when_weights_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("HF_HOME", str(tmp_path / "hf"))
    organ = MammalOrgan(model_id="ibm/missing-model", state_root=tmp_path)
    result = organ.query("MKTAYIAKQRQISFVKSHFSRQLEERLG")
    assert isinstance(result, MammalQueryResult)
    assert result.ok is False
    assert result.error is not None
    assert "not found" in result.error.lower() or \
           "transformers" in result.error.lower() or \
           "MAMMAL" in result.error
    assert result.pull_instructions is not None
    # No silent fake output
    assert result.output is None
    # But the receipt schema still works
    assert result.truth_label == TRUTH_LABEL_QUERY
    assert result.truth_class == "HYPOTHESIS"
    assert len(result.sha256) == 64
    assert len(result.receipt_id) == 16


def test_failed_query_writes_receipt(tmp_path, monkeypatch):
    """Even failures leave evidence on disk."""
    monkeypatch.setenv("HF_HOME", str(tmp_path / "hf"))
    organ = MammalOrgan(model_id="ibm/missing-model", state_root=tmp_path)
    result = organ.query("query that will fail because no weights")
    ledger = tmp_path / LEDGER_NAME
    assert ledger.exists()
    last = ledger.read_text().strip().splitlines()[-1]
    parsed = json.loads(last)
    assert parsed["truth_label"] == TRUTH_LABEL_QUERY
    assert parsed["truth_class"] == "HYPOTHESIS"
    assert parsed["ok"] is False
    assert parsed["receipt_id"] == result.receipt_id
    assert parsed["sha256"] == result.sha256


def test_query_increments_failure_counter(tmp_path, monkeypatch):
    monkeypatch.setenv("HF_HOME", str(tmp_path / "hf"))
    organ = MammalOrgan(model_id="ibm/missing-model", state_root=tmp_path)
    organ.query("test 1")
    organ.query("test 2")
    assert organ.queries_failed == 2
    assert organ.queries_served == 0


# ── Query — success path with fake model ───────────────────────

def test_query_succeeds_with_monkeypatched_model(tmp_path, monkeypatch):
    """Exercise the success branch by injecting a fake model + tokenizer
    so the test runs without downloading 1 GB of weights."""
    organ = MammalOrgan(state_root=tmp_path)
    # Bypass the weight-check path by marking the organ as loaded
    organ._loaded = True
    organ._tokenizer = MagicMock()
    fake_tokens = MagicMock()
    fake_tokens.to = MagicMock(return_value=fake_tokens)
    organ._tokenizer.return_value = fake_tokens
    # Fake model that returns an object with last_hidden_state
    fake_output = MagicMock()
    fake_hidden = MagicMock()

    class _FakeMean:
        def __init__(self, vals):
            self._vals = vals

        def detach(self):
            return self

        def cpu(self):
            return self

        def numpy(self):
            import numpy as np
            return np.array([self._vals])
    fake_hidden.mean = MagicMock(return_value=_FakeMean([0.1, 0.2, 0.3, 0.4]))
    fake_output.last_hidden_state = fake_hidden
    organ._model = MagicMock(return_value=fake_output)
    result = organ.query("PROTEIN MKTAYIA")
    assert result.ok is True
    assert result.output is not None
    assert "kind" in result.output
    assert result.output["kind"] == "EMBEDDING"
    assert organ.queries_served == 1


# ── Truth-class boundary ──────────────────────────────────────────

def test_query_result_carries_hypothesis_truth_class(tmp_path, monkeypatch):
    """All biomedical outputs are HYPOTHESIS until wet-lab validation."""
    monkeypatch.setenv("HF_HOME", str(tmp_path / "hf"))
    organ = MammalOrgan(model_id="ibm/missing", state_root=tmp_path)
    result = organ.query("test")
    assert result.truth_class == "HYPOTHESIS"


def test_truth_boundary_forbids_collider_claims():
    """§20.F discipline: receipt boundary cannot claim Standard Model results."""
    from System.swarm_mammal_organ import TRUTH_BOUNDARY
    assert "ATLAS" in TRUTH_BOUNDARY or "CERN" in TRUTH_BOUNDARY or "§20.F" in TRUTH_BOUNDARY
    assert "HYPOTHESIS" in TRUTH_BOUNDARY


# ── Receipt sha256 stability ─────────────────────────────────────

def test_two_failed_queries_with_different_prompts_have_different_sha256(tmp_path, monkeypatch):
    monkeypatch.setenv("HF_HOME", str(tmp_path / "hf"))
    organ = MammalOrgan(model_id="ibm/missing", state_root=tmp_path)
    r1 = organ.query("alpha")
    r2 = organ.query("beta")
    assert r1.sha256 != r2.sha256
    assert r1.receipt_id != r2.receipt_id
