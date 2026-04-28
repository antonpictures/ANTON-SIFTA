from pathlib import Path

from System import whatsapp_bridge_autopilot as wa
from System.swarm_whatsapp_receptor import build_inbox_row, validate_inbox_row


def test_inbox_row_records_owner_and_chat_frame():
    row = build_inbox_row(
        "manual owner message",
        from_jid="120363408204674197@g.us",
        name="George",
        from_me=True,
        chat_type="group",
        ts=123.0,
        secret="test-secret",
    )

    assert row["from_me"] is True
    assert row["chat_type"] == "group"
    assert validate_inbox_row(row, secret="test-secret") == (True, "ok")


def test_inbox_row_rejects_missing_social_frame():
    row = build_inbox_row(
        "hello",
        from_jid="15551234567@s.whatsapp.net",
        ts=123.0,
        secret="test-secret",
    )
    row.pop("chat_type")
    row["signature"] = "0" * 64

    ok, reason = validate_inbox_row(row, secret="test-secret")

    assert ok is False
    assert reason == "chat_type_mismatch"


def test_whatsapp_effector_blocks_group_send_by_default(monkeypatch, tmp_path):
    monkeypatch.setattr(wa, "_ALLOW_GROUP_SEND", False)
    monkeypatch.setattr(wa, "_resolve_target", lambda _target: "120363408204674197@g.us")
    monkeypatch.setattr(wa, "_LEDGER", Path(tmp_path) / "whatsapp_bridge_trace.jsonl")

    result = wa.send_whatsapp("SIFTA Group", "hello group")

    assert result["ok"] is False
    assert result["status"] == "BLOCKED_GROUP_SEND_DISABLED"
