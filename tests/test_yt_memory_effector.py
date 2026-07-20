from __future__ import annotations

import json
from pathlib import Path

import pytest

import System.stigmergic_memory_bus as memory_bus
from sifta_effectors import yt_swimmer_v2 as yt


@pytest.fixture()
def isolated_bus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    state = tmp_path / ".sifta_state"
    state.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(memory_bus, "LEDGER_DIR", state)
    monkeypatch.setattr(memory_bus, "LEDGER_FILE", state / "memory_ledger.jsonl")
    monkeypatch.setattr(memory_bus, "STGM_LOG_FILE", state / "stgm_memory_rewards.jsonl")
    monkeypatch.setattr(memory_bus, "MEMORY_EPISTEMOLOGY_AUDIT", state / "memory_epistemology_audit.jsonl")
    return state


def test_remember_and_comment_pause_speak_resume_with_recall(isolated_bus: Path) -> None:
    bus = memory_bus.StigmergicMemoryBus(architect_id="IOAN_M5")
    bus.remember(
        "key moments alpha: George paused for doctrine check.",
        app_context="youtube_cowatch",
        epistemic_label="OBSERVED",
        links=["receipt:yt-test-alpha"],
    )
    bus.remember(
        "key moments alpha: dragon fiction only.",
        app_context="youtube_cowatch",
        epistemic_label="FICTION",
    )

    spoken: list[str] = []
    hooks = yt.YtEffectorHooks(
        pause_yt=lambda: {"ok": True, "action": "pause", "was_paused": False, "paused": True},
        resume_yt=lambda: {"ok": True, "action": "resume", "resumed": True},
        speak=lambda text: spoken.append(text),
    )

    row = yt.remember_and_comment(
        "alpha",
        hooks=hooks,
        state_dir=isolated_bus.parent,
        limit=3,
    )

    assert row["ok"] is True
    assert row["recall"]
    assert row["recall"][0]["epistemic_label"] == "OBSERVED"
    assert "dragon" not in row["recall"][0]["content"].lower()
    assert spoken and "From ledger entry" in spoken[0]
    receipt_path = isolated_bus / "yt_commentary_with_recall.jsonl"
    assert receipt_path.exists()
    receipt = json.loads(receipt_path.read_text(encoding="utf-8").splitlines()[-1])
    assert receipt["kind"] == "yt_commentary_with_recall"
    assert receipt["payload"]["recall_count"] == 1
    assert receipt["payload"]["episode"] == "alpha"


def test_parse_owner_effector_commands() -> None:
    assert yt.parse_owner_effector_command("fire yt_recall") == "fire_yt_recall"
    assert yt.parse_owner_effector_command("audit cline now") == "audit_cline"
    assert yt.parse_owner_effector_command("more effectors list") == "effectors_list"


def test_cline_containment_audit_vetoes_ledger_touch(isolated_bus: Path) -> None:
    from System.swarm_cline_containment_audit import audit_cline_organ

    row = audit_cline_organ(
        mode="containment",
        state_dir=isolated_bus.parent,
        claimed_action="self-install touching .sifta_state/memory_ledger.jsonl",
    )
    assert row["containment_veto"] is True
    assert row["status"] == "VETO"