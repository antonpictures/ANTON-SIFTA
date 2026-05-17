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


def _write_valid_skill(root, *, name="market_reader"):
    (root / "scripts").mkdir(parents=True)
    (root / "scripts" / "probe.py").write_text(
        "from pathlib import Path\nPath('SHOULD_NOT_EXIST').write_text('ran')\n",
        encoding="utf-8",
    )
    (root / "SKILL.md").write_text(
        f"""---
name: {name}
description: >
  Use when Alice needs a receipt-bound installed skill for testing.
swimmer_type: MARKET_SWIMMER
action_type: learn
affect_lanes: [SEEKING, CARE]
stgm_mint: 2.0
pouw_label: MARKET_READER
version: 1
homeworld_serial: GTH4921YP3
trace_id: test-trace-0001
---
# Market Reader
Step one: inspect only.
Step two: never auto-run scripts.
Step three: report receipt state.
""",
        encoding="utf-8",
    )


def test_install_skill_from_local_folder_receipts_and_never_executes(tmp_path, monkeypatch):
    from System import swarm_skill_library as lib

    source = tmp_path / "source_skill"
    _write_valid_skill(source)
    install_root = tmp_path / "skills"
    receipt_file = tmp_path / "receipts.jsonl"
    monkeypatch.setattr(lib, "_STATE_DIR", tmp_path)
    monkeypatch.setattr(lib, "_SKILL_RECEIPTS", receipt_file)

    row = lib.install_skill(source, skills_dir=install_root)

    assert row["schema"] == lib.SKILL_INSTALL_SCHEMA
    assert row["status"] == "INSTALLED"
    assert row["resource_policy"] == "COPIED_ONLY_NO_SCRIPT_EXECUTION"
    assert (install_root / "market_reader" / "SKILL.md").exists()
    assert (install_root / "market_reader" / "scripts" / "probe.py").exists()
    assert not (tmp_path / "SHOULD_NOT_EXIST").exists()
    stored = json.loads(receipt_file.read_text(encoding="utf-8").splitlines()[-1])
    assert stored["skill_name"] == "market_reader"


def test_fetch_skill_from_url_rejects_localhost_and_receipts(tmp_path, monkeypatch):
    from System import swarm_skill_library as lib

    receipt_file = tmp_path / "receipts.jsonl"
    monkeypatch.setattr(lib, "_STATE_DIR", tmp_path)
    monkeypatch.setattr(lib, "_SKILL_RECEIPTS", receipt_file)

    row = lib.fetch_skill_from_url("http://127.0.0.1:8000/SKILL.md")

    assert row["schema"] == lib.SKILL_FETCH_SCHEMA
    assert row["status"] == "REFUSED"
    assert row["resource_policy"] == "FETCH_ONLY_NO_SCRIPT_EXECUTION"
    assert "https" in row["reason"]
    assert receipt_file.exists()


def test_install_skill_from_manifest_local_path(tmp_path, monkeypatch):
    from System import swarm_skill_library as lib

    source = tmp_path / "source_skill"
    _write_valid_skill(source, name="manifest_reader")
    install_root = tmp_path / "skills"
    monkeypatch.setattr(lib, "_STATE_DIR", tmp_path)
    monkeypatch.setattr(lib, "_SKILL_RECEIPTS", tmp_path / "receipts.jsonl")

    row = lib.install_skill_from_manifest(
        {"source_path": str(source), "allow_overwrite": True},
        skills_dir=install_root,
    )

    assert row["status"] == "INSTALLED"
    assert row["skill_name"] == "manifest_reader"
    assert (install_root / "manifest_reader" / "SKILL.md").exists()


def test_convert_hermes_json_skill_to_sifta_frontmatter(tmp_path, monkeypatch):
    from System import swarm_skill_library as lib

    monkeypatch.setattr(lib, "_STATE_DIR", tmp_path)
    monkeypatch.setattr(lib, "_SKILL_RECEIPTS", tmp_path / "receipts.jsonl")
    monkeypatch.setattr(lib, "_node_serial", lambda: "TESTSERIAL")
    hermes = {
        "name": "Hermes Bug Triage",
        "description": "debug failing pytest output and propose a minimal patch",
        "instructions": "Read the traceback, isolate the failing invariant, and write the smallest patch.",
        "tools": ["terminal", "files"],
    }

    converted = lib.convert_skill_text_to_sifta(
        json.dumps(hermes),
        source_ref="memory://hermes",
        life_context="pytest traceback bug patch terminal",
    )

    assert converted["source_format"] == "hermes_json"
    assert converted["status"] == "CONVERTED"
    assert "swimmer_type: HERMES_COMPAT_SWIMMER" in converted["skill_markdown"]
    assert "homeworld_serial: TESTSERIAL" in converted["skill_markdown"]
    assert converted["life_fit"]["score"] > 0


def test_ingest_skill_source_installs_converted_hermes_markdown(tmp_path, monkeypatch):
    from System import swarm_skill_library as lib

    source = tmp_path / "hermes_skill.md"
    source.write_text(
        """# Copy Review

Description: improve marketing copy after a user asks for sharper launch language.

## Instructions
Read the current text.
Keep the claim honest.
Return a concise revision.
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(lib, "_STATE_DIR", tmp_path)
    monkeypatch.setattr(lib, "_SKILL_RECEIPTS", tmp_path / "receipts.jsonl")
    monkeypatch.setattr(lib, "_node_serial", lambda: "TESTSERIAL")

    row = lib.ingest_skill_source(
        source,
        skills_dir=tmp_path / "skills",
        life_context="marketing copy launch language Carlton",
    )

    assert row["status"] == "INSTALLED"
    assert row["skill_name"] == "copy-review"
    assert (tmp_path / "skills" / "copy-review" / "SKILL.md").exists()


def test_marketplace_pull_selects_by_life_context_not_hardcoded(tmp_path, monkeypatch):
    from System import swarm_skill_library as lib

    weak = tmp_path / "weak.md"
    weak.write_text("# Garden\n\nDescription: prune tomatoes.\n\nStep one.\nStep two.\nStep three.\n", encoding="utf-8")
    strong = tmp_path / "strong.md"
    strong.write_text(
        "# Reading Tutor\n\nDescription: teach reading with patient speech cues.\n\nStep one.\nStep two.\nStep three.\n",
        encoding="utf-8",
    )
    manifest = tmp_path / "market.json"
    manifest.write_text(
        json.dumps({
            "skills": [
                {"id": "garden", "description": "tomato pruning", "source_path": str(weak)},
                {"id": "reader", "description": "patient speech reading tutor", "source_path": str(strong)},
            ]
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(lib, "_STATE_DIR", tmp_path)
    monkeypatch.setattr(lib, "_SKILL_RECEIPTS", tmp_path / "receipts.jsonl")
    monkeypatch.setattr(lib, "_node_serial", lambda: "TESTSERIAL")

    row = lib.pull_skill_from_marketplace(
        manifest,
        skills_dir=tmp_path / "skills",
        life_context="Ace needs patient speech reading tutor practice",
    )

    assert row["status"] == "INSTALLED"
    assert row["marketplace_choice"]["id"] == "reader"


def test_extract_skill_from_successful_trace(tmp_path, monkeypatch):
    from System import swarm_skill_library as lib

    state = tmp_path / ".sifta_state"
    state.mkdir()
    trace = state / "tool_router_trace.jsonl"
    trace.write_text(
        json.dumps({
            "trace_id": "abc123",
            "tool_name": "read_file",
            "executed": True,
            "status": "EXECUTED",
            "params": {"path": "README.md"},
            "result": {"ok": True},
        }) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(lib, "_STATE_DIR", state)
    monkeypatch.setattr(lib, "_SKILL_RECEIPTS", state / "nanobot_skill_receipts.jsonl")
    monkeypatch.setattr(lib, "_node_serial", lambda: "TESTSERIAL")

    row = lib.extract_skill_from_trace(
        trace_file=trace,
        trace_id="abc123",
        name="readme_reader",
        skills_dir=tmp_path / "skills",
    )

    assert row["status"] == "INSTALLED"
    assert row["skill_name"] == "readme_reader"
    skill_text = (tmp_path / "skills" / "readme_reader" / "SKILL.md").read_text(encoding="utf-8")
    assert "Observed Successful Trace" in skill_text
