from __future__ import annotations

import json
import sys
import types
from pathlib import Path

from System import whatsapp_bridge_autopilot as wa


def test_unknown_target_queues_sifta_outbox_without_macos_fallback(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, str]] = []

    fake_macos = types.SimpleNamespace(
        send_message=lambda target, text, via="whatsapp": calls.append((target, text))
    )
    monkeypatch.setitem(sys.modules, "System.swarm_macos_messenger", fake_macos)
    monkeypatch.setattr(wa, "_LEDGER", tmp_path / "whatsapp_bridge_trace.jsonl")
    monkeypatch.setattr(wa, "_OUTBOX", tmp_path / "sifta_whatsapp_outbox.jsonl")
    monkeypatch.setattr(wa, "_resolve_target", lambda _target: "")

    result = wa.send_whatsapp("Carlton", "have a wonderful day", transport="auto")

    assert result["ok"] is False
    assert result["status"] == "QUEUED_NEEDS_SIFTA_WHATSAPP_SYNC"
    assert "No macOS WhatsApp fallback was used" in result["result"]
    assert calls == []

    outbox_row = json.loads((tmp_path / "sifta_whatsapp_outbox.jsonl").read_text().splitlines()[0])
    assert outbox_row["target"] == "Carlton"
    assert outbox_row["transport"] == "sifta_bridge"


def test_owner_explicit_macos_transport_writes_unified_whatsapp_ledger(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, str, str, bool]] = []

    def fake_send_message(target: str, text: str, via: str = "whatsapp", *, dry_run: bool = False):
        calls.append((target, text, via, dry_run))
        return {
            "ok": True,
            "status": "SENT",
            "target": target,
            "message": text,
            "transport": "whatsapp_visible_name_ui",
            "note": "fake local WhatsApp.app dispatch",
        }

    fake_macos = types.SimpleNamespace(send_message=fake_send_message)
    monkeypatch.setitem(sys.modules, "System.swarm_macos_messenger", fake_macos)
    monkeypatch.setattr(wa, "_LEDGER", tmp_path / "whatsapp_bridge_trace.jsonl")

    result = wa.send_whatsapp(
        "Kole Beeson",
        "Welcome to BeeSon.",
        transport="macos_app",
        source="whatsapp_organ_ui",
    )

    assert result["ok"] is True
    assert result["status"] == "SENT_MACOS_APP"
    assert calls == [("Kole Beeson", "Welcome to BeeSon.", "whatsapp", False)]

    row = json.loads((tmp_path / "whatsapp_bridge_trace.jsonl").read_text().splitlines()[0])
    assert row["transport"] == "macos_app"
    assert row["status"] == "SENT_MACOS_APP"
    assert row["native_receipt"]["status"] == "SENT"
    assert "local WhatsApp.app UI dispatch" in row["truth_note"]


def test_talk_widget_spinal_reflex_uses_sifta_bridge_not_native_messenger() -> None:
    src = Path("Applications/sifta_talk_to_alice_widget.py").read_text(encoding="utf-8")

    assert "from System.swarm_macos_messenger import send_message as _native_send" not in src
    assert "spinal_reflex_sifta_whatsapp" in src
    assert "QUEUED_NEEDS_SIFTA_WHATSAPP_SYNC" in src


def test_whatsapp_organ_widget_uses_bridge_ledger_and_sender() -> None:
    src = Path("Applications/sifta_whatsapp_organ.py").read_text(encoding="utf-8")

    assert "whatsapp_bridge_trace.jsonl" in src
    assert "from System.whatsapp_bridge_autopilot import send_whatsapp" in src
    assert "from System.swarm_macos_messenger import send_message" not in src
    assert "WhatsApp.app names/groups" in src
    assert "transport=transport" in src
