from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace


def test_self_query_trigger_matcher_is_narrow():
    from System.swarm_self_query_skill import looks_like_self_query

    assert looks_like_self_query("Alice, what do you need?")
    assert looks_like_self_query("please self-check")
    assert looks_like_self_query("are you ok")
    assert not looks_like_self_query("please open the browser")


def test_self_query_report_uses_owner_label_and_receipts(tmp_path, monkeypatch):
    from System import swarm_organ_directory
    from System.swarm_self_query_skill import build_self_query_report

    state = tmp_path / ".sifta_state"
    state.mkdir()
    (state / "stgm_memory_rewards.jsonl").write_text(
        json.dumps({"ts": time.time(), "amount": 2.5}) + "\n",
        encoding="utf-8",
    )
    (state / "camera_unified_field_proof.jsonl").write_text(
        json.dumps({"frame_age_s": 0.5, "camera_healthy": True, "status": "CAMERA_HEALTHY"}) + "\n",
        encoding="utf-8",
    )
    (state / "memory.jsonl").write_text(json.dumps({"ok": True}) + "\n", encoding="utf-8")

    monkeypatch.setattr(
        swarm_organ_directory,
        "list_organs",
        lambda: [
            SimpleNamespace(
                name="memory",
                truth_label="MEMORY_TEST",
                ledger_path=".sifta_state/memory.jsonl",
                probe_module="",
                probe_callable="",
            )
        ],
    )

    report = build_self_query_report(root=tmp_path, owner_label="Ace")
    assert report.stgm_wallet_balance == 2.5
    assert report.stgm_recent_mints == 1
    assert report.organ_count == 1
    assert report.healthy_count == 1
    assert report.camera_healthy is True
    assert "If Ace observes a problem" in report.prompt_block
    assert "If George observes a problem" not in report.prompt_block
    assert report.sha256


def test_self_query_receipt_writes_jsonl(tmp_path, monkeypatch):
    from System import swarm_organ_directory
    from System.swarm_self_query_skill import LEDGER_NAME, build_self_query_report, write_self_query_receipt

    state = tmp_path / ".sifta_state"
    state.mkdir()
    monkeypatch.setattr(swarm_organ_directory, "list_organs", lambda: [])

    report = build_self_query_report(root=tmp_path, owner_label="George")
    row = write_self_query_receipt(report, root=tmp_path)
    assert row["kind"] == "SELF_QUERY_REPORT"
    assert row["sha256"] == report.sha256
    lines = (state / LEDGER_NAME).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["trace_id"] == report.trace_id
