from __future__ import annotations

import json
from pathlib import Path

from System import ide_doctor_mailbox as mailbox
from System import ide_stigmergic_bridge as bridge


def test_doctor_mailbox_sends_and_threads_grok_request(tmp_path, monkeypatch):
    trace = tmp_path / "ide_stigmergic_trace.jsonl"
    monkeypatch.setattr(bridge, "TRACE_PATH", trace)
    monkeypatch.setattr(mailbox.bridge, "TRACE_PATH", trace)

    request = mailbox.send_message(
        from_doctor="codex",
        to_doctor="grok",
        subject="review Hermes tools",
        body="Please review the guarded Talk tool surface and reply with receipt boundaries.",
        homeworld_serial="GTH4921YP3",
    )
    reply = mailbox.send_message(
        from_doctor="grokcli",
        to_doctor="codex",
        subject="review Hermes tools reply",
        body="Reviewed. Boundary is bus-visible, not a live xAI API call.",
        parent_trace_id=request["trace_id"],
        requires_reply=False,
        homeworld_serial="GTH4921YP3",
    )

    rows = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["kind"] == mailbox.KIND_MESSAGE
    assert rows[0]["meta"]["to_doctor"] == "grokcli"
    assert rows[1]["kind"] == mailbox.KIND_REPLY
    assert rows[1]["meta"]["parent_trace_id"] == request["trace_id"]
    assert mailbox.inbox("grok") == [request]
    assert mailbox.inbox("codex") == [reply]
    assert [row["trace_id"] for row in mailbox.thread(request["trace_id"])] == [
        request["trace_id"],
        reply["trace_id"],
    ]
    assert mailbox.open_requests("grok") == []


def test_doctor_mailbox_reports_open_request(tmp_path, monkeypatch):
    trace = tmp_path / "ide_stigmergic_trace.jsonl"
    monkeypatch.setattr(bridge, "TRACE_PATH", trace)
    monkeypatch.setattr(mailbox.bridge, "TRACE_PATH", trace)

    request = mailbox.send_message(
        from_doctor="codex",
        to_doctor="grok",
        subject="need review",
        body="Reply when you have inspected the file.",
        homeworld_serial="GTH4921YP3",
    )

    assert mailbox.open_requests("grok") == [request]
    summary = mailbox.summary_for_alice()
    assert "DOCTOR MAILBOX" in summary
    assert "grokcli:1" in summary
    assert "codex -> grokcli" in summary


def test_doctor_mailbox_ack_closes_request(tmp_path, monkeypatch):
    trace = tmp_path / "ide_stigmergic_trace.jsonl"
    monkeypatch.setattr(bridge, "TRACE_PATH", trace)
    monkeypatch.setattr(mailbox.bridge, "TRACE_PATH", trace)

    request = mailbox.send_message(
        from_doctor="codex",
        to_doctor="grok",
        subject="ack me",
        body="Ack this direct mailbox lane.",
        homeworld_serial="GTH4921YP3",
    )
    ack = mailbox.ack(
        from_doctor="grok",
        parent_trace_id=request["trace_id"],
        note="seen",
        homeworld_serial="GTH4921YP3",
    )

    assert ack["kind"] == mailbox.KIND_ACK
    assert mailbox.open_requests("grok") == []


def test_source_followup_does_not_close_target_request(tmp_path, monkeypatch):
    trace = tmp_path / "ide_stigmergic_trace.jsonl"
    monkeypatch.setattr(bridge, "TRACE_PATH", trace)
    monkeypatch.setattr(mailbox.bridge, "TRACE_PATH", trace)

    request = mailbox.send_message(
        from_doctor="codex",
        to_doctor="grok",
        subject="still need grok",
        body="Grok should be the one to close this.",
        homeworld_serial="GTH4921YP3",
    )
    mailbox.send_message(
        from_doctor="codex",
        to_doctor="grok",
        subject="followup",
        body="Codex follow-up should not close the request.",
        parent_trace_id=request["trace_id"],
        requires_reply=False,
        homeworld_serial="GTH4921YP3",
    )

    assert mailbox.open_requests("grok") == [request]
