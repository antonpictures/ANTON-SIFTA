from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from System import stigall_cursor_signin as signin


@dataclass
class _FakeIdentity:
    trigger_code: str = "CG55M"
    model_label: str = "GPT-5.5 Medium"
    ide_surface: str = "cursor_ide_m5"


def _patch_identity(monkeypatch, *, serial: str = "GTH4921YP3") -> None:
    monkeypatch.setattr(signin, "owner_silicon", lambda: serial)

    import System.swarm_ide_boot_identity as boot

    monkeypatch.setattr(boot, "resolve_boot_identity", lambda _ide: _FakeIdentity())


def test_cursor_auto_signin_declares_opaque_model_by_default(monkeypatch):
    _patch_identity(monkeypatch)

    row = signin.sign_in(dry_run=True)

    assert row["doctor"] == "CG55M"
    assert row["ide_name"] == "Cursor"
    assert row["model"] == "AUTO_OPAQUE"
    assert row["selected_model"] == "AUTO_OPAQUE"
    assert row["reasoning"] == "auto"
    assert row["payload"] == "CG55M@cursor_ide_m5 / AUTO_OPAQUE / Cursor IDE"
    assert row["meta"]["router_visible"] is False
    assert row["meta"]["model_confidence"] == "opaque_router"
    assert row["meta"]["registry_model_label"] == "GPT-5.5 Medium"
    assert "not cryptographic vendor-router attestation" in row["known_limits"]


def test_cursor_signin_accepts_explicit_model_when_endpoint_visible(monkeypatch):
    _patch_identity(monkeypatch)

    row = signin.sign_in(
        selected_model="Claude Opus 4.7",
        reasoning="high",
        mode="patch",
        lane="Surgeon",
        dry_run=True,
    )

    assert row["model"] == "Claude Opus 4.7"
    assert row["reasoning"] == "high"
    assert row["mode"] == "patch"
    assert row["lane"] == "Surgeon"
    assert row["meta"]["router_visible"] is True
    assert row["meta"]["model_confidence"] == "declared_exact"
    assert row["known_limits"] == ""


def test_cursor_signin_appends_jsonl_when_not_dry(monkeypatch, tmp_path: Path):
    _patch_identity(monkeypatch, serial="TESTSERIAL")
    trace = tmp_path / "ide_stigmergic_trace.jsonl"
    monkeypatch.setattr(signin, "_TRACE", trace)

    row = signin.sign_in(context="test_cursor_auto")

    stored = json.loads(trace.read_text(encoding="utf-8").strip())
    assert stored["trace_id"] == row["trace_id"]
    assert stored["model"] == "AUTO_OPAQUE"
    assert stored["homeworld_serial"] == "TESTSERIAL"
    assert stored["meta"]["grounding_label"] == "CURSOR_AUTO_ROUTER_OPAQUE"
