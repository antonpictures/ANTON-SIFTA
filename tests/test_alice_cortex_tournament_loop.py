import hashlib
import inspect
import json
from pathlib import Path

from System.alice_cortex_eval_runner import (
    OLLAMA_DEFAULT_ENDPOINT,
    load_suite,
    query_ollama,
    score_reply,
)
from System.alice_training_corpus_exporter import LOCAL, _approval_status, _sanitize


def test_pending_architect_approval_blocks_private_export(tmp_path):
    approval = tmp_path / "architect_approval.txt"
    approval.write_text("Architect: PENDING\nDate: PENDING\n")

    ok, reason = _approval_status(approval)

    assert not ok
    assert "PENDING" in reason


def test_signed_architect_approval_unblocks_private_export(tmp_path):
    approval = tmp_path / "architect_approval.txt"
    approval.write_text("Architect: George Anton\nDate: 2026-04-27\n")

    ok, reason = _approval_status(approval)

    assert ok
    assert "George Anton" in reason


def test_local_sanitizer_preserves_alice_and_splits_owner_from_contacts():
    redactions = []
    text = "George told Alice to call Jeff at +1 760-555-1212 near 32.8890,-115.5390."

    sanitized = _sanitize(text, redactions, LOCAL)

    assert "Alice" in sanitized
    assert "[OWNER]" in sanitized
    assert "[CONTACT_N]" in sanitized
    assert "[PHONE_REDACTED]" in sanitized
    assert "[LOC_REDACTED]" in sanitized


def _repo_suite_path() -> Path:
    root = Path(__file__).resolve().parent.parent
    p = root / "tests" / "alice_cortex_eval_suite_v1.json"
    if p.is_file():
        return p
    return root / "Tests" / "alice_cortex_eval_suite_v1.json"


def test_eval_suite_metadata_matches_locked_prompt_hash():
    suite_path = _repo_suite_path()
    raw = json.loads(suite_path.read_text())
    expected_hash = hashlib.sha256(
        json.dumps(raw["prompts"], sort_keys=True).encode()
    ).hexdigest()

    suite = load_suite(suite_path)

    assert len(suite["prompts"]) == 51
    assert suite["max_score"] == 459
    assert suite["pass_threshold"] == 368
    assert raw["locked_hash"] == expected_hash
    assert suite["prompt_hash"] == expected_hash


def test_score_reply_catches_service_tail_and_respects_silence():
    service_meta = {
        "brevity_budget_tokens": 12,
        "required_receipt": False,
        "failure_signals": ["Is there anything else"],
    }
    silence_meta = {
        "brevity_budget_tokens": 0,
        "required_receipt": False,
        "failure_signals": [],
    }

    service_score = score_reply("Sure. Is there anything else I can help with?", service_meta)
    silence_score = score_reply("(silent)", silence_meta)

    assert service_score["axes"]["tone_authenticity"]["score"] == 0
    assert silence_score["axes"]["brevity_silence"]["score"] == 3


def test_ollama_path_is_deterministic_by_default():
    """The Ollama runner must default to HTTP /api/generate with seed + temperature=0.

    A non-deterministic loop would invalidate cross-round contestant comparison.
    This is a static contract test — no network call.
    """
    sig = inspect.signature(query_ollama)

    assert sig.parameters["seed"].default == 42, (
        "Ollama seed default drifted; cross-round determinism would break."
    )
    assert sig.parameters["temperature"].default == 0.0, (
        "Ollama temperature must default to 0.0 for deterministic eval."
    )
    assert sig.parameters["endpoint"].default == OLLAMA_DEFAULT_ENDPOINT
    assert OLLAMA_DEFAULT_ENDPOINT.startswith("http://"), (
        "Ollama endpoint must use HTTP /api/generate, not subprocess shell."
    )

    src = inspect.getsource(query_ollama)
    assert "/api/generate" in src, (
        "query_ollama must hit /api/generate so seed + temperature land server-side."
    )
    assert "OLLAMA_HTTP_DOWN_FALLBACK" in src, (
        "Subprocess fallback must be tagged so non-deterministic replies are visible in receipts."
    )


def test_deprecated_corpus_exporter_refuses_to_run():
    """The old scripts/ exporter must refuse execution and point at the canonical module.

    Historical receipts still mention the v1 path; the shim guarantees Codex
    Extra High does not accidentally re-export ledger data through the
    less-safe extractor mid-tournament.
    """
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, "scripts/alice_training_corpus_exporter.py"],
        capture_output=True, text=True, timeout=10,
    )
    assert proc.returncode == 2
    combined = (proc.stdout + proc.stderr).lower()
    assert "deprecated" in combined
    assert "system/alice_training_corpus_exporter.py" in combined
