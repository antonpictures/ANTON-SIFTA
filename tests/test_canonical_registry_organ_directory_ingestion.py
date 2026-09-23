"""r1727-11 — the canonical registry must ingest the living organ directory.

Regression for the 2026-09-23 audit finding: build_registry() never read
System/swarm_organ_directory.py, so organs registered there with live probes
and ledgers (web_global_chat, W4, included) were absent from
canonical_organ_registry_snapshot.json and invisible to the eval matrix —
8 of 8 as measured. These tests pin the wiring closed.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from System import swarm_canonical_organ_registry as registry_module
from System.swarm_canonical_organ_registry import (
    _organ_directory_organs,
    build_registry,
)


@dataclass
class _FakeOrganRecord:
    name: str
    truth_label: str = "TRUTH"
    truth_boundary: str = "boundary"
    ledger_path: str = ""
    claim_template: str = ""
    verifier_kind: str | None = None
    probe_module: str | None = None
    probe_callable: str | None = None
    registered_at: float = 0.0
    notes: str = ""


def test_organ_directory_source_builds_rows(monkeypatch) -> None:
    import System.swarm_organ_directory as organ_directory

    def fake_list_organs(*, state_dir: Any = None):
        return [
            _FakeOrganRecord(
                name="web_global_chat",
                ledger_path=".sifta_state/web_global_chat_metabolism.jsonl",
                probe_callable="probe_web_global_chat_health",
            ),
            _FakeOrganRecord(name="wall_clock"),
        ]

    monkeypatch.setattr(organ_directory, "list_organs", fake_list_organs)
    rows = _organ_directory_organs(state=Path("."))

    assert [row["display_name"] for row in rows] == ["web_global_chat", "wall_clock"]
    assert all(row["source_registry"] == "swarm_organ_directory" for row in rows)
    assert all(row["organ_id"].startswith("organ_dir_") for row in rows)
    chat = next(row for row in rows if row["display_name"] == "web_global_chat")
    assert chat["organ_directory_probe"] == "probe_web_global_chat_health"
    assert chat["ledgers"] == ("web_global_chat_metabolism.jsonl",)
    assert chat["write_action"] is True
    assert chat["aliases"] == ("web_global_chat",)
    bare = next(row for row in rows if row["display_name"] == "wall_clock")
    assert bare["ledgers"] == ()
    assert bare["write_action"] is False


def test_build_registry_ingests_organ_directory(monkeypatch) -> None:
    import System.swarm_organ_directory as organ_directory

    def fake_list_organs(*, state_dir: Any = None):
        return [
            _FakeOrganRecord(
                name="web_global_chat",
                ledger_path=".sifta_state/web_global_chat_metabolism.jsonl",
                probe_callable="probe_web_global_chat_health",
            ),
        ]

    monkeypatch.setattr(organ_directory, "list_organs", fake_list_organs)
    snap = build_registry(
        root=registry_module._REPO,
        state_dir=registry_module._STATE,
        include_dynamic=True,
    )
    ids = {row["organ_id"] for row in snap["organs"]}
    assert "organ_dir_" + registry_module._stable_id("web_global_chat") in ids
    assert snap["merged_sources"]["organ_directory"] == 1
    chat = next(
        row for row in snap["organs"] if row.get("source_registry") == "swarm_organ_directory"
    )
    assert chat["present"] is True
    assert chat["pipeline_category"] == "organ_directory"
    # The living organ must now be findable by its plain name through aliases.
    assert any(
        row.get("display_name") == "web_global_chat"
        or "web_global_chat" in tuple(row.get("aliases") or ())
        for row in snap["organs"]
    )