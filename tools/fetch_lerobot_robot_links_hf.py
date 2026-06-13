#!/usr/bin/env python3
"""Download LeRobot HF robot leg links from bucket ``lerobot/robot-urdfs``.

Usage:
  python3 tools/fetch_lerobot_robot_links_hf.py
  python3 tools/fetch_lerobot_robot_links_hf.py --robot g1 --manifest-only
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.stigmerobotics_lerobot_hf_links import (  # noqa: E402
    DEFAULT_LEG_MESH_PATHS,
    build_hf_leg_links_report,
    default_urdf_path,
)

_DEST = _REPO / "assets" / "robotics" / "lerobot_hf" / "robot-urdfs"
_MANIFEST = _REPO / "tests" / "fixtures" / "stigmero_lerobot_hf_g1_leg_links.json"

_ROBOT_FILES = {
    "g1": {
        "urdf": "g1/g1_body29_hand14.urdf",
        "meshes": list(DEFAULT_LEG_MESH_PATHS),
    }
}


def _download_files(paths: list[str]) -> None:
    from huggingface_hub import HfApi

    api = HfApi()
    _DEST.mkdir(parents=True, exist_ok=True)
    files = [(remote, _DEST / remote) for remote in paths]
    api.download_bucket_files("lerobot/robot-urdfs", files)


def _write_manifest(report) -> None:
    payload = {
        "bucket_id": report.bucket_id,
        "robot_id": report.robot_id,
        "urdf_remote": "g1/g1_body29_hand14.urdf",
        "mesh_paths": list(report.mesh_paths),
        "leg_link_names": [r.name for r in report.leg_links],
        "leg_link_count": report.leg_link_count,
        "hf_urls": report.hf_urls,
        "truth_label": report.proof_of_property.get("truth_label", "OPERATIONAL"),
    }
    _MANIFEST.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--robot", default="g1", choices=sorted(_ROBOT_FILES))
    parser.add_argument("--manifest-only", action="store_true", help="Rebuild fixture manifest from cached URDF")
    args = parser.parse_args()

    spec = _ROBOT_FILES[args.robot]
    paths = [spec["urdf"], *spec["meshes"]]

    if not args.manifest_only or not default_urdf_path().exists():
        print(f"Downloading lerobot/robot-urdfs ({len(paths)} files) …")
        _download_files(paths)
        print(f"Saved under {_DEST}")

    report = build_hf_leg_links_report(urdf_path=default_urdf_path(), robot_id=args.robot)
    if not report.ok:
        raise SystemExit(f"Leg link report not ok: count={report.leg_link_count}")
    _write_manifest(report)
    print(f"Manifest: {_MANIFEST} ({report.leg_link_count} leg links)")
    print(json.dumps(report.proof_of_property, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())