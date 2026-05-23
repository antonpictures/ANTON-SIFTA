#!/usr/bin/env python3
"""Tests for swarm_api_sentry — owner-side API egress sentry (tranche 2 organ 2/12).

Upgraded contract: zero delta on core 4 + the organ's own output ledger
(api_egress_log.jsonl) and keys file.

Focus: credential loading, audit logging, call wrapper (heavily mocked), health.
All network and file writes isolated.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from System import swarm_api_sentry as sentry


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return len(path.read_text(encoding="utf-8", errors="replace").splitlines())


def test_get_credentials_and_fingerprint(tmp_path, monkeypatch):
    """Real behavior 1: credential surface and fingerprinting."""
    original_keys = sentry._KEYS_FILE
    sentry._KEYS_FILE = tmp_path / "api_keys.json"

    try:
        key_data = {"gemini": {"api_key": "sk-test-1234567890abcdef"}}
        sentry._KEYS_FILE.write_text(__import__("json").dumps(key_data))

        creds = sentry.get_credentials("gemini")
        assert creds is not None
        assert "api_key" in creds

        fp = sentry._key_fingerprint(creds["api_key"])
        assert len(fp) == 12
    finally:
        sentry._KEYS_FILE = original_keys


def test_audit_tail_and_record_under_isolation(tmp_path, monkeypatch):
    """Core audit contract under full ledger isolation."""
    original_log = sentry._AUDIT_LOG
    sentry._AUDIT_LOG = tmp_path / "api_egress_log.jsonl"

    try:
        before = _count_lines(sentry._AUDIT_LOG)

        # Use the public call surface which internally calls _record
        with patch("System.swarm_api_sentry.urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"candidates": [{"content": {"parts": [{"text": "audit test"}]}}]}'
            mock_resp.__enter__.return_value = mock_resp
            mock_urlopen.return_value = mock_resp

            text, audit = sentry.call_gemini(prompt="test for audit", caller="isolation_test")

        after = _count_lines(sentry._AUDIT_LOG)
        assert (after - before) == 1

        tail = sentry.audit_tail(limit=5)
        assert len(tail) >= 1
    finally:
        sentry._AUDIT_LOG = original_log


def test_call_gemini_mocked_no_network(tmp_path, monkeypatch):
    """Call surface works without real network (full mock)."""
    original_log = sentry._AUDIT_LOG
    sentry._AUDIT_LOG = tmp_path / "api_egress_log.jsonl"

    try:
        with patch("System.swarm_api_sentry.get_credentials") as mock_creds, \
             patch("System.swarm_api_sentry.urllib.request.urlopen") as mock_urlopen:

            mock_creds.return_value = {"api_key": "fake-key-for-test"}
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.read.return_value = b'{"candidates": [{"content": {"parts": [{"text": "mock response"}]}}]}'
            mock_resp.__enter__.return_value = mock_resp
            mock_urlopen.return_value = mock_resp

            text, audit = sentry.call_gemini(
                prompt="test prompt",
                caller="test",
                sender_agent="TEST_AGENT",
            )

            assert text is not None          # happy path reached
            assert audit is not None
            assert audit["provider"] == "google_gemini"
            assert "mock" in str(text).lower() or audit.get("status") in ("success", "ok")
    finally:
        sentry._AUDIT_LOG = original_log


def test_real_ledgers_untouched_including_organ_own(tmp_path, monkeypatch):
    """Explicit isolation gate (core 4 + organ own audit log + keys)."""
    state = Path(".sifta_state")
    watch = [
        state / "memory_ledger.jsonl",
        state / "stgm_memory_rewards.jsonl",
        state / "work_receipts.jsonl",
        state / "ide_stigmergic_trace.jsonl",
        state / "api_egress_log.jsonl",
        state / "api_keys.json",
    ]
    before = {str(p): _count_lines(p) for p in watch}

    original_log = sentry._AUDIT_LOG
    original_keys = sentry._KEYS_FILE
    sentry._AUDIT_LOG = tmp_path / "api_egress_log.jsonl"
    sentry._KEYS_FILE = tmp_path / "api_keys.json"

    try:
        with patch("System.swarm_api_sentry.urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"candidates": [{"content": {"parts": [{"text": "x"}]}}]}'
            mock_resp.__enter__.return_value = mock_resp
            mock_urlopen.return_value = mock_resp

            _ = sentry.call_gemini(prompt="test", caller="isolation_test")
            _ = sentry.audit_tail(limit=1)
            _ = sentry.health()
    finally:
        sentry._AUDIT_LOG = original_log
        sentry._KEYS_FILE = original_keys

    after = {str(p): _count_lines(p) for p in watch}
    delta = {k: after[k] - before[k] for k in before}

    assert all(v == 0 for v in delta.values()), f"Real ledgers (incl. organ own) contaminated: {delta}"
