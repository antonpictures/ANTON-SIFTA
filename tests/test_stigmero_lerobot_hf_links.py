"""HF LeRobot robot-urdfs leg link ingest."""

from __future__ import annotations

from pathlib import Path

from System.stigmerobotics_lerobot_hf_links import (
    build_hf_leg_links_report,
    default_urdf_path,
    hf_bucket_id,
    load_fixture_manifest,
    manifest_matches_report,
    parse_urdf_links,
)

FIXTURE = Path(__file__).parent / "fixtures" / "stigmero_lerobot_hf_g1_leg_links.json"
URDF = default_urdf_path()


def test_hf_bucket_id_is_lerobot_robot_urdfs() -> None:
    assert hf_bucket_id() == "lerobot/robot-urdfs"


def test_g1_urdf_parses_leg_links() -> None:
    if not URDF.exists():
        return
    report = build_hf_leg_links_report(urdf_path=URDF)
    assert report.ok
    assert report.leg_link_count >= 6
    assert report.proof_of_property["truth_label"] == "OPERATIONAL"
    assert report.proof_of_property["physical_motion_label"] == "HYPOTHESIS"
    names = [r.name for r in report.leg_links]
    assert "left_knee_link" in names
    assert "right_ankle_pitch_link" in names


def test_fixture_manifest_matches_cached_urdf() -> None:
    if not URDF.exists() or not FIXTURE.exists():
        return
    report = build_hf_leg_links_report(urdf_path=URDF)
    manifest = load_fixture_manifest(FIXTURE)
    assert manifest["bucket_id"] == "lerobot/robot-urdfs"
    assert manifest_matches_report(report, manifest)


def test_parse_urdf_links_extracts_mass() -> None:
    if not URDF.exists():
        return
    links = parse_urdf_links(URDF.read_text(encoding="utf-8"))
    pelvis = next(l for l in links if l.name == "pelvis")
    assert pelvis.mass_kg is not None
    assert pelvis.mass_kg > 0.0