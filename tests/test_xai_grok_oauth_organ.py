from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from System import xai_grok_oauth_organ as organ


def _registration(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({
            "ts": time.time(),
            "kind": "LLM_REGISTRATION",
            "model": "codex",
            "lane": "xai_oauth_test",
        }) + "\n",
        encoding="utf-8",
    )


def test_refuses_without_recent_registration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ledger = tmp_path / "xai_calls.jsonl"
    monkeypatch.setenv("XAI_API_KEY", "xai-test-secret")

    with pytest.raises(PermissionError):
        organ.call_xai_responses(
            "hello",
            trace_path=tmp_path / "missing_trace.jsonl",
            ledger_path=ledger,
            dry_run=True,
        )

    row = json.loads(ledger.read_text(encoding="utf-8").splitlines()[-1])
    assert row["ok"] is False
    assert row["reason"] == "missing_recent_sifta_registration"
    assert row["credential_redacted"] == "xai-t...cret"


def test_dry_run_with_registration_writes_redacted_receipt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    trace = tmp_path / "ide_stigmergic_trace.jsonl"
    ledger = tmp_path / "xai_calls.jsonl"
    _registration(trace)
    monkeypatch.setenv("XAI_OAUTH_ACCESS_TOKEN", "oauth-token-123456")

    row = organ.call_xai_responses(
        "hello",
        trace_path=trace,
        ledger_path=ledger,
        dry_run=True,
    )
    saved = json.loads(ledger.read_text(encoding="utf-8").splitlines()[-1])

    assert row["ok"] is True
    assert saved["reason"] == "dry_run_auth_resolved"
    assert saved["credential_kind"] == "oauth_access_token"
    assert saved["credential_redacted"] == "oauth...3456"


def test_missing_credential_is_receipted_not_faked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    trace = tmp_path / "ide_stigmergic_trace.jsonl"
    ledger = tmp_path / "xai_calls.jsonl"
    _registration(trace)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("XAI_OAUTH_ACCESS_TOKEN", raising=False)

    row = organ.call_xai_responses(
        "hello",
        trace_path=trace,
        ledger_path=ledger,
        token_file=tmp_path / "missing_token.json",
        dry_run=True,
    )

    assert row["ok"] is False
    assert row["reason"] == "missing_xai_credential"


def test_token_file_is_local_and_chmod_600(tmp_path: Path) -> None:
    token_file = tmp_path / "secrets" / "xai.json"
    organ.write_token_file({"access_token": "oauth-token-abcdef"}, token_file=token_file)
    cred = organ.load_credential(token_file=token_file, env={})

    assert cred is not None
    assert cred.kind == "oauth_access_token"
    assert oct(token_file.stat().st_mode & 0o777) == "0o600"


def test_hermes_auth_provider_token_is_accepted(tmp_path: Path) -> None:
    auth_file = tmp_path / "auth.json"
    auth_file.write_text(
        json.dumps(
            {
                "providers": {
                    "xai-oauth": {
                        "tokens": {
                            "access_token": "oauth-hermes-provider-abcdef",
                            "refresh_token": "refresh-xyz",
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    cred = organ.load_credential(
        token_file=tmp_path / "missing_token.json",
        hermes_auth_file=auth_file,
        env={},
    )
    assert cred is not None
    assert cred.kind == "oauth_access_token"
    assert cred.value == "oauth-hermes-provider-abcdef"
    assert "providers.tokens.access_token" in cred.source


def test_hermes_auth_credential_pool_token_is_accepted(tmp_path: Path) -> None:
    auth_file = tmp_path / "auth.json"
    auth_file.write_text(
        json.dumps(
            {
                "credential_pool": {
                    "xai-oauth": [
                        {"access_token": "oauth-hermes-pool-123456", "label": "default"}
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    cred = organ.load_credential(
        token_file=tmp_path / "missing_token.json",
        hermes_auth_file=auth_file,
        env={},
    )
    assert cred is not None
    assert cred.kind == "oauth_access_token"
    assert cred.value == "oauth-hermes-pool-123456"
    assert "credential_pool" in cred.source
