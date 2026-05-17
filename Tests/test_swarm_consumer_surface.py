from __future__ import annotations

import json
from pathlib import Path

from System import swarm_consumer_surface as surface


def _mini_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "Applications").mkdir(parents=True)
    (repo / "System").mkdir()
    (repo / "Documents").mkdir()
    (repo / "scripts").mkdir()
    (repo / "skills").mkdir()
    (repo / "exports").mkdir()
    (repo / "Applications" / "sifta_consumer_home.py").write_text("# app\n", encoding="utf-8")
    (repo / "Applications" / "sifta_organism_doctor.py").write_text("# doctor\n", encoding="utf-8")
    (repo / "Applications" / "sifta_skill_browser.py").write_text("# skills\n", encoding="utf-8")
    (repo / "Applications" / "sifta_genesis_widget.py").write_text("# genesis\n", encoding="utf-8")
    (repo / "scripts" / "distro_scrubber.py").write_text("# scrubber\n", encoding="utf-8")
    (repo / "Documents" / "PUBLIC_PUSH_CHECKLIST.md").write_text("check\n", encoding="utf-8")
    (repo / "Documents" / "SIFTA_DISTRO_DOCTRINE_v2.md").write_text("doctrine\n", encoding="utf-8")
    (repo / "exports" / "SIFTA_90S_OOBE_DEMO.mp4").write_text("demo\n", encoding="utf-8")
    manifest = {
        "SIFTA Home": {
            "category": "Alice",
            "entry_point": "Applications/sifta_consumer_home.py",
            "widget_class": "SiftaHomeWidget",
            "description": "home",
        },
        "Owner Genesis": {
            "category": "System Settings",
            "entry_point": "Applications/sifta_genesis_widget.py",
            "widget_class": "GenesisWidget",
            "description": "owner",
        },
        "Organism Doctor": {
            "category": "Utilities",
            "entry_point": "Applications/sifta_organism_doctor.py",
            "widget_class": "OrganismDoctorWidget",
            "description": "health",
        },
        "SIFTA Skill Browser": {
            "category": "Developer",
            "entry_point": "Applications/sifta_skill_browser.py",
            "widget_class": "SkillBrowserApp",
            "description": "skills",
        },
    }
    (repo / "Applications" / "apps_manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )
    return repo


def test_consumer_snapshot_collects_apps_tools_oobe_and_distro(tmp_path: Path) -> None:
    repo = _mini_repo(tmp_path)

    snap = surface.build_snapshot(repo)

    assert snap["truth_label"] == surface.TRUTH_LABEL
    assert any(app["name"] == "Organism Doctor" for app in snap["apps"])
    assert any(tool["name"] == "consumer_surface_status" for tool in snap["tools"])
    assert snap["oobe_ready"]["total"] == 6
    assert snap["distro"]["demo_assets"] == ["exports/SIFTA_90S_OOBE_DEMO.mp4"]


def test_render_page_uses_dropdown_pages_without_missing_surface_claim(tmp_path: Path) -> None:
    repo = _mini_repo(tmp_path)

    text = surface.render_page(surface.PAGE_TOOLS, repo_root=repo)

    assert "SIFTA Home - Talk Tools" in text
    assert "consumer_surface_status" in text
    assert "[TOOL_CALL: consumer_surface_status" in text


def test_discovery_page_exposes_field_scan_and_oobe_blockers(tmp_path: Path) -> None:
    repo = _mini_repo(tmp_path)

    text = surface.render_page(surface.PAGE_DISCOVERY, repo_root=repo)

    assert "SIFTA Home - Discovery" in text
    assert "skill_autoproposal_scan" in text
    assert "OOBE/distro status" in text


def test_surface_receipt_hash_chain(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"

    first = surface.write_surface_receipt(action="test", page="overview", state_dir=state)
    second = surface.write_surface_receipt(action="test", page="tools", state_dir=state)

    rows = [
        json.loads(line)
        for line in (state / "consumer_surface_trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [row["schema"] for row in rows] == [surface.TRACE_SCHEMA, surface.TRACE_SCHEMA]
    assert first["prev_hash"] == "genesis"
    assert second["prev_hash"] == first["hash"]
    assert rows[-1]["hash"] == second["hash"]
