from __future__ import annotations

import json
from pathlib import Path


def _read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def test_should_trigger_reflex_for_grok_auth_and_connectivity_failures():
    from System.swarm_grok_connection_reflex import should_trigger_reflex

    assert should_trigger_reflex("grok:grok-4.3", "No xAI credential found and local `grok` CLI is missing")
    assert should_trigger_reflex("grok:grok-4.3", "xAI HTTP 403 Forbidden")
    assert not should_trigger_reflex("alice-m5-cortex-8b-6.3gb:latest", "No xAI credential found")
    assert not should_trigger_reflex("grok:grok-4.3", "unrelated local model timeout")


def test_register_and_claim_owner_notice(tmp_path: Path):
    from System.swarm_grok_connection_reflex import (
        claim_pending_owner_notice,
        format_owner_notice,
        register_reflex_event,
    )

    notice = register_reflex_event(
        state_dir=tmp_path,
        from_model="grok:grok-4.3",
        fallback_model="alice-m5-cortex-8b-6.3gb:latest",
        failure_message="No xAI credential found and local `grok` CLI is missing",
        switch_ok=True,
    )

    assert notice["kind"] == "pending_owner_notice"
    assert notice["notice_id"].startswith("grok_fallback_")
    assert (tmp_path / "work_receipts.jsonl").exists()
    assert (tmp_path / "episodic_diary.jsonl").exists()

    first = claim_pending_owner_notice(state_dir=tmp_path)
    assert first is not None
    assert first["notice_id"] == notice["notice_id"]
    second = claim_pending_owner_notice(state_dir=tmp_path)
    assert second is None

    message = format_owner_notice(first)
    assert "switched to local cortex" in message.lower()
    assert "grok connection break" in message.lower()

    reflex_rows = _read_jsonl(tmp_path / "grok_connection_reflex.jsonl")
    assert any(row.get("kind") == "pending_owner_notice" for row in reflex_rows)
    assert any(row.get("kind") == "owner_notice_delivered" for row in reflex_rows)
