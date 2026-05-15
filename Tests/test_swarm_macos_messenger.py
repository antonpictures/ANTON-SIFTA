from __future__ import annotations

import json
import subprocess
from pathlib import Path

from System import swarm_macos_messenger as msg
from System import swarm_skill_library as skills


def test_whatsapp_visible_name_dry_run_writes_receipt(monkeypatch, tmp_path: Path) -> None:
    app = tmp_path / "WhatsApp.app"
    app.mkdir()
    monkeypatch.setattr(msg, "_WHATSAPP_APP", app)
    monkeypatch.setattr(msg, "_SEND_LOG", tmp_path / "macos_messenger_sends.jsonl")
    monkeypatch.setattr(msg, "resolve_contact", lambda _target: None)

    row = msg.send_message("Carlton", "we did it", via="whatsapp", dry_run=True)

    assert row["ok"] is True
    assert row["status"] == "DRY_RUN"
    assert row["transport"] == "whatsapp_visible_name_ui"
    assert "inbound registration" not in row["note"].lower()
    written = json.loads((tmp_path / "macos_messenger_sends.jsonl").read_text().splitlines()[0])
    assert written["target"] == "Carlton"


def test_whatsapp_visible_name_uses_local_app_not_contact_cache(monkeypatch, tmp_path: Path) -> None:
    app = tmp_path / "WhatsApp.app"
    app.mkdir()
    monkeypatch.setattr(msg, "_WHATSAPP_APP", app)
    monkeypatch.setattr(msg, "_SEND_LOG", tmp_path / "macos_messenger_sends.jsonl")
    monkeypatch.setattr(msg, "resolve_contact", lambda _target: None)

    def fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(["osascript"], 0, stdout="sent\n", stderr="")

    monkeypatch.setattr(msg.subprocess, "run", fake_run)

    row = msg.send_message("Carlton", "we submitted the application", via="whatsapp")

    assert row["ok"] is True
    assert row["status"] == "SENT"
    assert row["transport"] == "whatsapp_visible_name_ui"
    assert "register" not in row["note"].lower()


def test_whatsapp_macos_cli_skill_is_discoverable() -> None:
    names = {skill["name"] for skill in skills.build_skill_index()}

    assert "whatsapp_macos_cli" in names
