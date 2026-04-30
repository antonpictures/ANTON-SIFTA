import importlib.util
import json
import sys
import types
from pathlib import Path

from System import whatsapp_bridge_autopilot as wa
from System.swarm_whatsapp_receptor import build_inbox_row, validate_inbox_row


def _load_alice_server_module():
    repo = Path(__file__).resolve().parent.parent
    path = repo / "scripts" / "whatsapp_alice_server.py"
    spec = importlib.util.spec_from_file_location("whatsapp_alice_server_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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


def test_python_ingest_preserves_node_social_frame(monkeypatch, tmp_path):
    mod = _load_alice_server_module()
    inbox_file = tmp_path / "whatsapp_inbox.jsonl"
    monkeypatch.setattr(mod, "INBOX_FILE", inbox_file)
    monkeypatch.setitem(
        sys.modules,
        "System.swarm_pheromone",
        types.SimpleNamespace(
            PHEROMONE_FIELD=types.SimpleNamespace(deposit=lambda *_args, **_kwargs: None)
        ),
    )

    mod._deposit_inbox(
        "owner already sent this from WhatsApp",
        "110411378614437@lid",
        "George",
        from_me=True,
        chat_type="direct",
    )

    row = json.loads(inbox_file.read_text(encoding="utf-8").splitlines()[0])
    assert row["from_me"] is True
    assert row["chat_type"] == "direct"
    assert row["name"] == "George"


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
