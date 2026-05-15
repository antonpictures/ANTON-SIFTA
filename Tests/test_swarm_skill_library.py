from __future__ import annotations

import json


def test_skill_markdown_frontmatter_parses_description_and_affects():
    from System import swarm_skill_library as lib

    meta, body = lib._parse_skill_markdown(
        """---
name: camera_switch
description: >
  Use when George asks Alice to switch cameras.
swimmer_type: SENSOR_GATE
action_type: execute
affect_lanes: [SEEKING, CARE]
stgm_mint: 3.5
---
# Body
Step one.
"""
    )

    assert meta["name"] == "camera_switch"
    assert meta["description"] == "Use when George asks Alice to switch cameras."
    assert meta["affect_lanes"] == ["SEEKING", "CARE"]
    assert meta["stgm_mint"] == 3.5
    assert body.startswith("# Body")


def test_discover_skill_files_is_file_backed_progressive_index(tmp_path):
    from System import swarm_skill_library as lib

    (tmp_path / "alpha.md").write_text(
        """---
name: alpha
description: >
  Use when alpha work is needed.
swimmer_type: TEST_SWIMMER
action_type: repair
affect_lanes: [SEEKING]
stgm_mint: 1.0
pouw_label: ALPHA
version: 1
---
# Alpha
Do the steps.
""",
        encoding="utf-8",
    )

    rows = lib.discover_skill_files(tmp_path)

    assert rows[0]["name"] == "alpha"
    assert rows[0]["procedure_exists"] is True
    assert rows[0]["procedure_lines"] == 2
    assert rows[0]["procedure_sha256"]


def test_discover_community_skill_folder_counts_resources(tmp_path):
    from System import swarm_skill_library as lib

    root = tmp_path / "camera_switch"
    (root / "scripts").mkdir(parents=True)
    (root / "references").mkdir()
    (root / "assets").mkdir()
    (root / "scripts" / "probe.py").write_text("print('no auto run')\n", encoding="utf-8")
    (root / "references" / "receipt.md").write_text("receipt rules\n", encoding="utf-8")
    (root / "assets" / "icon.txt").write_text("eye\n", encoding="utf-8")
    (root / "SKILL.md").write_text(
        """---
name: camera_switch
description: >
  Use when George asks Alice to switch cameras.
swimmer_type: SENSOR_GATE
action_type: execute
affect_lanes: [SEEKING, CARE]
stgm_mint: 8.0
pouw_label: CAMERA_SWITCH
version: 1
---
# Camera Switch
Verify the receipt.
""",
        encoding="utf-8",
    )

    rows = lib.discover_skill_files(tmp_path)

    assert rows[0]["name"] == "camera_switch"
    assert rows[0]["procedure_file"] == "camera_switch/SKILL.md"
    assert rows[0]["community_style"] is True
    assert rows[0]["resource_counts"] == {
        "scripts": 1,
        "references": 1,
        "assets": 1,
    }
    assert rows[0]["resource_policy"] == "ON_DEMAND_REVIEW_REQUIRED"
    assert lib.load_procedure("camera_switch", skills_dir=tmp_path).startswith("# Camera")


def test_match_skills_returns_index_only_without_body():
    from System import swarm_skill_library as lib

    matches = lib.match_skills("Alice has vendor identity gag residue to repair", limit=3)

    assert matches
    assert matches[0]["name"] == "gag_self_report"
    assert "output guarantee" not in json.dumps(matches).lower()


def test_append_skill_selection_receipt_never_executes_resources(tmp_path, monkeypatch):
    from System import swarm_skill_library as lib

    monkeypatch.setattr(lib, "_STATE_DIR", tmp_path)
    monkeypatch.setattr(lib, "_SKILL_RECEIPTS", tmp_path / "nanobot_skill_receipts.jsonl")

    matches = [{"name": "gag_self_report", "score": 4.0}]
    row = lib.append_skill_selection_receipt("repair this gag", matches)

    assert row["schema"] == lib.SKILL_SELECTION_SCHEMA
    assert row["resource_policy"] == "INDEX_ONLY_NO_SCRIPT_EXECUTION"
    stored = json.loads((tmp_path / "nanobot_skill_receipts.jsonl").read_text().splitlines()[-1])
    assert stored["selected"][0]["name"] == "gag_self_report"


def test_validate_skill_contracts_reports_tournament_grade_repo_skills():
    from System import swarm_skill_library as lib

    report = lib.validate_skill_contracts()

    assert report["schema"] == lib.SKILL_CONTRACT_SCHEMA
    assert report["passed"] is True
    assert report["skills_checked"] >= 8
    assert report["resource_policy"] == "TIER3_COUNT_ONLY_NO_SCRIPT_EXECUTION"
    names = {row["name"] for row in report["skills"]}
    assert {"camera_switch", "ide_boot_covenant", "memory_store"} <= names
