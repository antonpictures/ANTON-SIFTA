"""
tests/test_swarm_capability_registry.py
═══════════════════════════════════════
Offline tests for the unified Capability Registry. Stubs out the two
sources (TOOL_REGISTRY + swarm_skill_library) so behavior is deterministic
regardless of the live tree state.
"""
from __future__ import annotations

import json
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest


@pytest.fixture
def fresh_module(monkeypatch, tmp_path):
    """Reload swarm_capability_registry with stubbed router + skill_lib + state dir."""
    # Stub a fake tool router.
    @dataclass
    class FakeToolSpec:
        name: str
        description: str
        required_params: Tuple[str, ...] = ()
        optional_params: Tuple[str, ...] = ()
        write_action: bool = True
        requires_autonomy_gate: bool = True

    fake_router = types.ModuleType("swarm_tool_router")
    fake_router.TOOL_REGISTRY = {
        "send_whatsapp": FakeToolSpec("send_whatsapp", "Send a WhatsApp message", write_action=True),
        "list_dir":      FakeToolSpec("list_dir",      "List files in a directory", write_action=False, requires_autonomy_gate=False),
        "check_economy": FakeToolSpec("check_economy", "Read the STGM economy snapshot", write_action=False, requires_autonomy_gate=False),
    }
    monkeypatch.setitem(sys.modules, "swarm_tool_router", fake_router)

    # Stub a fake skill library.
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "list_dir_with_summary.md").write_text(
        "# List dir with summary\n\nUse list_dir then describe the result.\n"
    )
    (skills_dir / "morning_briefing.md").write_text(
        "# Morning briefing\n\nNo tool references — pure habit.\n"
    )
    (skills_dir / "wordace_reading_coach.md").write_text(
        "# WordAce reading coach\n\nUse app_focus and WordAce receipts to teach reading patiently.\n"
    )
    apps_dir = tmp_path / "Applications"
    apps_dir.mkdir()
    manifest_path = apps_dir / "apps_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "WordAce": {
                    "description": "Teach Ace words, letters, and sentence reading",
                    "category": "Alice",
                    "entry_point": "Applications/sifta_teach_ace_to_read.py",
                    "widget_class": "TeachAceToReadWidget",
                    "icon": "WA",
                },
                "GPS Map": {
                    "description": "Location, routes, and GPS map practice",
                    "category": "Location",
                    "entry_point": "Applications/sifta_gps_map.py",
                    "widget_class": "GPSMapWidget",
                    "icon": "GPS",
                },
            }
        ),
        encoding="utf-8",
    )

    fake_skill_lib = types.ModuleType("swarm_skill_library")
    fake_skill_lib.build_skill_index = lambda: [
        {
            "name": "list_dir_with_summary",
            "description": "List a directory and explain the result",
            "when_to_use": "owner asks what is in a folder and wants a paragraph back",
            "procedure_file": "list_dir_with_summary.md",
            "stgm_mint": 0.04,
            "extracted_from_trace": True,
        },
        {
            "name": "morning_briefing",
            "description": "Read overnight ledgers and summarize",
            "when_to_use": "first owner interaction of the day",
            "procedure_file": "morning_briefing.md",
            "stgm_mint": {"amount": 0.06},
        },
        {
            "name": "wordace_reading_coach",
            "description": "Use when WordAce is open to teach words, letters, phonics, and sentences",
            "when_to_use": "WordAce app_focus receipt or child reading lesson",
            "procedure_file": "wordace_reading_coach.md",
            "stgm_mint": 12.0,
            "app_bindings": ["WordAce"],
        },
    ]
    monkeypatch.setitem(sys.modules, "swarm_skill_library", fake_skill_lib)

    # Force the module to look at our tmp tree.
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()

    # Reload the registry under the stubs.
    for mod_name in list(sys.modules):
        if mod_name.startswith("swarm_capability_registry"):
            del sys.modules[mod_name]
    import importlib.util
    repo = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location(
        "swarm_capability_registry",
        repo / "System" / "swarm_capability_registry.py",
    )
    mod = importlib.util.module_from_spec(spec)  # type: ignore
    sys.modules["swarm_capability_registry"] = mod
    spec.loader.exec_module(mod)  # type: ignore

    # Repoint the module's path constants at our tmp tree.
    mod._STATE = state_dir
    mod._SKILLS_DIR = skills_dir
    mod._APPS_MANIFEST_PATH = manifest_path
    return mod


# ──────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────


def test_build_index_returns_tool_capabilities(fresh_module):
    caps = fresh_module.build_capability_index()
    names = {c.name for c in caps}
    # 3 tools + 1 skill (list_dir_with_summary is distinct from list_dir tool)
    # + 1 more skill (morning_briefing) = at least 4 unique names
    assert "send_whatsapp" in names
    assert "list_dir" in names
    assert "check_economy" in names
    assert "morning_briefing" in names
    assert "WordAce" in names


def test_app_capabilities_surface_manifest_apps(fresh_module):
    caps = fresh_module.build_capability_index()
    wordace = next(c for c in caps if c.name == "WordAce")
    assert fresh_module._capability_tag(wordace) == "[app]"
    assert wordace.can_execute is True
    assert wordace.backing["app_widget_class"] == "TeachAceToReadWidget"


def test_tool_capability_has_executable_flag(fresh_module):
    caps = fresh_module.build_capability_index()
    send = next(c for c in caps if c.name == "send_whatsapp")
    assert send.can_execute is True
    assert send.can_teach_compose is False
    assert send.is_pure_tool()
    assert not send.is_pure_skill()
    assert send.permissions["write_action"] is True


def test_skill_only_capability_has_teach_flag(fresh_module):
    caps = fresh_module.build_capability_index()
    briefing = next(c for c in caps if c.name == "morning_briefing")
    assert briefing.can_teach_compose is True
    assert briefing.can_execute is False  # body has no known-tool reference
    assert briefing.is_pure_skill()
    assert briefing.permissions.get("stgm_mint") == {"amount": 0.06}


def test_skill_body_references_tool_marks_hybrid_via_dedicated_skill(fresh_module):
    """A skill named different from a tool, whose body references that tool name,
    should still surface that reference in backing.skill_body_tool_refs and
    therefore be flagged can_execute=True (hybrid)."""
    caps = fresh_module.build_capability_index()
    summary_skill = next(c for c in caps if c.name == "list_dir_with_summary")
    assert summary_skill.can_teach_compose is True
    assert summary_skill.can_execute is True
    assert summary_skill.is_hybrid()
    assert "list_dir" in summary_skill.backing.get("skill_body_tool_refs", [])
    assert summary_skill.learned_from_trace is True


def test_get_capability_by_name(fresh_module):
    assert fresh_module.get_capability("list_dir").name == "list_dir"
    assert fresh_module.get_capability("LIST_DIR").name == "list_dir"
    assert fresh_module.get_capability("nope") is None
    assert fresh_module.get_capability("") is None


def test_rank_capabilities_by_query(fresh_module):
    ranked = fresh_module.rank_capabilities("can you list the files in this folder")
    assert ranked, "ranker returned empty"
    top_name = ranked[0][1].name
    # 'list' / 'files' / 'folder' should pull list_dir or list_dir_with_summary
    assert top_name in {"list_dir", "list_dir_with_summary"}


def test_rank_empty_query_falls_back_to_receipt_count(fresh_module):
    ranked = fresh_module.rank_capabilities("")
    assert ranked, "empty-query ranker returned nothing"
    # All capabilities returned, no exception
    assert len(ranked) <= 12


def test_alice_prompt_contains_tags_and_rows(fresh_module):
    text = fresh_module.capabilities_for_alice_prompt(limit=20)
    assert "CAPABILITY FIELD" in text
    assert "[tool]" in text or "[hybrid]" in text
    assert "[skill" in text  # skill or skill·learned
    # Each capability should appear once
    assert "send_whatsapp" in text
    assert "morning_briefing" in text


def test_turn_prompt_ranks_current_request(fresh_module):
    text = fresh_module.capabilities_for_turn_prompt("please list files in this folder", limit=4)
    assert "CAPABILITY FIELD FOR THIS TURN" in text
    assert "list_dir" in text
    assert "apps, tools, and skills as one learned capability field" in text


def test_capability_field_summary_counts(fresh_module):
    summary = fresh_module.capability_field_summary()
    assert summary["total"] >= 4
    assert summary["hybrids"] >= 1
    assert summary["apps"] >= 1
    assert summary["learned_from_trace"] >= 1
    assert "sample" in summary
    assert len(summary["sample"]) > 0


def test_app_habit_field_ranks_bound_habit(fresh_module):
    ranked = fresh_module.habit_capabilities_for_app(
        "WordAce",
        query="Ace wants to read sentences",
        limit=4,
    )
    assert ranked
    assert ranked[0][1].name == "wordace_reading_coach"


def test_current_app_habit_prompt_reads_desktop_state(fresh_module):
    (fresh_module._STATE / "sifta_desktop_app_state.json").write_text(
        json.dumps({"active_app": "WordAce", "open_apps": ["WordAce"]}),
        encoding="utf-8",
    )
    text = fresh_module.current_app_habit_prompt("teach Ace to read the sentence")
    assert "APP HABIT FIELD FOR CURRENT APP — WordAce" in text
    assert "wordace_reading_coach" in text


def test_to_alice_dict_drops_raw_fields(fresh_module):
    cap = fresh_module.get_capability("send_whatsapp")
    d = cap.to_alice_dict()
    assert "raw_tool" not in d
    assert "raw_skill" not in d
    assert d["name"] == "send_whatsapp"
    assert d["can_execute"] is True


def test_registry_survives_missing_skill_library(fresh_module, monkeypatch):
    """Knocking out the skill library should leave the tool capabilities alive."""
    monkeypatch.setattr(fresh_module, "_skill_lib", None)
    caps = fresh_module.build_capability_index()
    assert all(not c.can_teach_compose for c in caps)
    assert any(c.name == "send_whatsapp" for c in caps)


def test_registry_survives_missing_tool_router(fresh_module, monkeypatch):
    """Knocking out the tool router should leave the skill capabilities alive."""
    monkeypatch.setattr(fresh_module, "_router", None)
    caps = fresh_module.build_capability_index()
    assert all(not c.backing.get("tool") for c in caps), \
        "no tool router → no tool-backed capabilities"
    skill_names = {c.name for c in caps}
    assert "morning_briefing" in skill_names
