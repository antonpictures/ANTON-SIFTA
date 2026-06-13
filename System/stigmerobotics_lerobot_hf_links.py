#!/usr/bin/env python3
"""
System/stigmerobotics_lerobot_hf_links.py
=========================================

Hugging Face LeRobot robot-link ingest for legs / kinematics reference.

Pulls leg link URDF + mesh paths from the public HF bucket
``lerobot/robot-urdfs`` (G1 humanoid leg chain today). LeRobot Humanoid
hardware STLs remain on GitHub; this lane is HF kinematic link truth only.
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

_REPO = Path(__file__).resolve().parent.parent
_HF_BUCKET = "lerobot/robot-urdfs"
_HF_BUCKET_URL = "https://huggingface.co/buckets/lerobot/robot-urdfs"
_HF_LEROBOT_ORG = "https://huggingface.co/lerobot"
_HF_HUMANOID_BLOG = "https://huggingface.co/blog/VirgileBatto/lerobot-humanoid"
_DEFAULT_ROBOT = "g1"
_DEFAULT_URDF = _REPO / "assets" / "robotics" / "lerobot_hf" / "robot-urdfs" / "g1" / "g1_body29_hand14.urdf"
_FIXTURE_MANIFEST = _REPO / "tests" / "fixtures" / "stigmero_lerobot_hf_g1_leg_links.json"

LEG_LINK_RE = re.compile(r"(hip|knee|ankle|pelvis)", re.IGNORECASE)

DEFAULT_LEG_MESH_PATHS: tuple[str, ...] = (
    "g1/meshes/pelvis.stl",
    "g1/meshes/left_hip_pitch_link.stl",
    "g1/meshes/left_knee_link.stl",
    "g1/meshes/left_ankle_pitch_link.stl",
    "g1/meshes/right_hip_pitch_link.stl",
    "g1/meshes/right_knee_link.stl",
    "g1/meshes/right_ankle_pitch_link.stl",
)


@dataclass(frozen=True)
class RobotLinkRecord:
    name: str
    mass_kg: float | None
    mesh: str | None

    @property
    def is_leg_link(self) -> bool:
        return bool(LEG_LINK_RE.search(self.name))


@dataclass(frozen=True)
class HfLegLinksReport:
    bucket_id: str
    robot_id: str
    urdf_path: str
    leg_links: tuple[RobotLinkRecord, ...]
    leg_link_count: int
    mesh_paths: tuple[str, ...]
    hf_urls: dict[str, str]
    proof_of_property: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.leg_link_count >= 6 and bool(self.leg_links)


def _float_attr(node: ET.Element | None, attr: str) -> float | None:
    if node is None:
        return None
    raw = node.get(attr)
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def parse_urdf_links(urdf_text: str) -> list[RobotLinkRecord]:
    root = ET.fromstring(urdf_text)
    records: list[RobotLinkRecord] = []
    for link in root.findall("link"):
        name = link.get("name", "")
        inertial = link.find("inertial")
        mass_node = inertial.find("mass") if inertial is not None else None
        mass = _float_attr(mass_node, "value")
        mesh = None
        for mesh_node in link.findall(".//mesh"):
            filename = mesh_node.get("filename")
            if filename:
                mesh = filename
                break
        records.append(RobotLinkRecord(name=name, mass_kg=mass, mesh=mesh))
    return records


def leg_links_from_urdf(path: Path) -> tuple[RobotLinkRecord, ...]:
    if not path.exists():
        raise FileNotFoundError(f"URDF not found at {path}")
    records = parse_urdf_links(path.read_text(encoding="utf-8"))
    return tuple(r for r in records if r.is_leg_link)


def build_hf_leg_links_report(
    *,
    urdf_path: Path | None = None,
    robot_id: str = _DEFAULT_ROBOT,
    mesh_paths: Sequence[str] = DEFAULT_LEG_MESH_PATHS,
) -> HfLegLinksReport:
    path = urdf_path or _DEFAULT_URDF
    legs = leg_links_from_urdf(path)
    proof = {
        "P_n": "HF robot-urdfs leg link chain parses without schema loss",
        "bucket": _HF_BUCKET,
        "robot_id": robot_id,
        "leg_link_count": len(legs),
        "falsifier": "leg_link_count < 6 or missing URDF",
        "truth_label": "OPERATIONAL",
        "physical_motion_label": "HYPOTHESIS",
        "note": (
            "G1 URDF leg links from HF bucket are a kinematic reference for Alice's "
            "future LeRobot legs organ — not a claim that metal legs are attached."
        ),
    }
    return HfLegLinksReport(
        bucket_id=_HF_BUCKET,
        robot_id=robot_id,
        urdf_path=str(path),
        leg_links=legs,
        leg_link_count=len(legs),
        mesh_paths=tuple(mesh_paths),
        hf_urls={
            "bucket": _HF_BUCKET_URL,
            "lerobot_org": _HF_LEROBOT_ORG,
            "humanoid_blog": _HF_HUMANOID_BLOG,
        },
        proof_of_property=proof,
    )


def load_fixture_manifest(path: Path | None = None) -> dict[str, Any]:
    manifest_path = path or _FIXTURE_MANIFEST
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def manifest_matches_report(report: HfLegLinksReport, manifest: Mapping[str, Any]) -> bool:
    names = [r.name for r in report.leg_links]
    return names == list(manifest.get("leg_link_names", []))


def default_urdf_path() -> Path:
    return _DEFAULT_URDF


def hf_bucket_id() -> str:
    return _HF_BUCKET