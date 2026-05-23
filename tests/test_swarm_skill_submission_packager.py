from __future__ import annotations

import json
from pathlib import Path


def test_package_skill_adds_hardware_binding_and_trade_offer(tmp_path: Path):
    from System.swarm_skill_submission_packager import package_skill

    result = package_skill(
        "camera_switch",
        output_root=tmp_path,
        homeworld_serial="TESTSERIAL",
        trace_id="trace-test",
    )

    assert result["ok"] is True
    skill_text = (tmp_path / "camera_switch" / "SKILL.md").read_text(encoding="utf-8")
    assert "homeworld_serial: \"TESTSERIAL\"" in skill_text
    assert "trace_id: \"trace-test\"" in skill_text
    assert "skill_sha256:" in skill_text

    offer = json.loads((tmp_path / "camera_switch" / "skill_trade_offer_v1.json").read_text())
    assert offer["skill_name"] == "camera_switch"
    assert offer["provider_node"] == "TESTSERIAL"
    assert offer["provider_trace"] == "trace-test"
    assert offer["truth_label"] == "SIFTA_SKILL_TRADE_OFFER_V1"


def test_package_all_writes_submission_manifest(tmp_path: Path):
    from System.swarm_skill_submission_packager import package_all

    manifest = package_all(
        output_root=tmp_path,
        homeworld_serial="TESTSERIAL",
        trace_id="trace-test",
    )

    assert manifest["schema"] == "SIFTA_SKILL_SUBMISSION_MANIFEST_V1"
    assert manifest["ok"] is True
    assert len(manifest["packages"]) >= 8
    assert (tmp_path / "submission_manifest.json").exists()
