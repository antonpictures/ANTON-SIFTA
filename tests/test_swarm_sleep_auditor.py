"""Sleep auditor — snapshots, metrics, integrity hash, ledger."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from System.swarm_sleep_auditor import SleepAuditor, _duplicate_engram_rows


def test_duplicate_engram_rows_counts_repeat_hashes(tmp_path: Path) -> None:
    eng = tmp_path / "engram_store.jsonl"
    rows = [
        {"content_hash": "aa", "facts": ["predator_bond_moment"]},
        {"content_hash": "bb", "facts": []},
        {"content_hash": "aa", "facts": []},
    ]
    eng.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    assert _duplicate_engram_rows(eng) == 1


def test_audit_writes_ledger_and_hash(tmp_path: Path) -> None:
    st = tmp_path / ".state"
    st.mkdir(parents=True, exist_ok=True)
    (st / "alice_conversation.jsonl").write_text(
        '{"role":"user","text":"commit fix for the swarm","ts":1.0}\n', encoding="utf-8"
    )
    (st / "engram_store.jsonl").write_text("", encoding="utf-8")
    (st / "hippocampal_replay_history.jsonl").write_text(
        '{"ts":9999999999,"kind":"replay"}\n', encoding="utf-8"
    )
    (st / "td_receipts.jsonl").write_text('{"ts":9999999999}\n', encoding="utf-8")

    aud = SleepAuditor(state_dir=st)
    pre = aud.take_snapshot(now=1.0)
    post = aud.take_snapshot(now=2.0)
    r = aud.audit(pre, post, window_s=1.0, now=3.0, persist=True)
    assert r.post_sleep_integrity_hash and len(r.post_sleep_integrity_hash) == 64
    assert r.audit_id
    text = (st / "sleep_audit.jsonl").read_text(encoding="utf-8")
    row = json.loads(text.strip().splitlines()[-1])
    assert row["kind"] == "sleep_audit"
    assert row["post_sleep_integrity_hash"] == r.post_sleep_integrity_hash


def test_audit_single_snapshot_no_crash(tmp_path: Path) -> None:
    st = tmp_path / "s"
    st.mkdir(parents=True, exist_ok=True)
    (st / "alice_conversation.jsonl").write_text("x\n", encoding="utf-8")
    (st / "engram_store.jsonl").write_text("y\n", encoding="utf-8")
    aud = SleepAuditor(state_dir=st)
    r = aud.audit(None, None, window_s=3600.0, now=1e9, persist=False)
    assert r.receipt_compression_ratio >= 0.0
    assert isinstance(r.notes, dict)
