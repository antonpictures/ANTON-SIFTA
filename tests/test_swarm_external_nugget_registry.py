from __future__ import annotations

from pathlib import Path

from System import swarm_external_nugget_registry as reg


def test_registry_validates_coded_artifacts() -> None:
    report = reg.validate_registry()
    assert report["ok"], report["issues"]
    assert report["coded_or_mirrored"] >= 4


def test_promptfoo_is_coded_but_cloud_tools_are_not_claimed() -> None:
    rows = {row["name"]: row for row in reg.all_nuggets()}
    assert rows["Promptfoo"]["status"] == "coded_in_repo"
    assert "tests/rlhs_evals/promptfooconfig.yaml" in rows["Promptfoo"]["local_artifacts"]

    assert rows["PostHog"]["status"] != "coded_in_repo"
    assert rows["Maigret"]["status"] != "coded_in_repo"
    assert rows["GitHub Copilot SDK"]["status"] != "coded_in_repo"


def test_agent_skills_are_mirrored_by_local_artifacts() -> None:
    coded = {row["name"]: row for row in reg.coded_or_mirrored()}
    skill_row = coded["Agent Skills / mattpocock skills pattern"]
    artifacts = set(skill_row["local_artifacts"])
    assert "System/swarm_skill_library.py" in artifacts
    assert "System/swarm_skill_validator.py" in artifacts
    assert "Applications/sifta_skill_browser.py" in artifacts


def test_document_points_to_registry_source() -> None:
    repo = Path(reg.__file__).resolve().parent.parent
    doc = repo / "Documents" / "SIFTA_EXTERNAL_NUGGETS_REGISTRY.md"
    text = doc.read_text(encoding="utf-8")
    assert "System/swarm_external_nugget_registry.py" in text
    assert "No, the full link-list was not coded as third-party integrations" in text


def test_second_batch_stays_probe_or_research_only() -> None:
    rows = {row["name"]: row for row in reg.all_nuggets()}

    assert rows["Temporal durable workflow stack"]["status"] == "probe_first"
    assert rows["Langfuse"]["status"] == "probe_first"
    assert rows["OSV-Scanner"]["status"] == "research_only"
    assert rows["DeepGEMM"]["status"] == "research_only"
    assert rows["claude-mem / Onyx / OpenMetadata / context-graph / Hippo"]["status"] == "probe_first"
    assert rows["Deep-Live-Cam / face-swap tooling"]["status"] == "skip_until_scoped"
    assert rows["Wispr Flow / Hex voice tools"]["status"] == "probe_first"
    assert rows["ref=manuagi SaaS links"]["status"] == "skip_until_scoped"

    assert rows["Langfuse"]["local_artifacts"] == ()
    assert rows["Deep-Live-Cam / face-swap tooling"]["local_artifacts"] == ()
    assert rows["Wispr Flow / Hex voice tools"]["local_artifacts"] == ()


def test_external_registry_document_names_unknown_vector_gate() -> None:
    repo = Path(reg.__file__).resolve().parent.parent
    doc = repo / "Documents" / "SIFTA_EXTERNAL_NUGGETS_REGISTRY.md"
    text = doc.read_text(encoding="utf-8")

    assert "Unknown Vector Questions" in text
    assert "What data leaves the node" in text
    assert "Deep-Live-Cam / face-swap tooling" in text
    assert "Wispr Flow / Hex voice tools" in text
