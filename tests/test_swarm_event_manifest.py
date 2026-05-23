import json
from pathlib import Path

from System.swarm_event_manifest import build_event_manifest, write_event_manifest

_REPO = Path(__file__).resolve().parents[1]


def test_build_event_manifest_contains_swarm_stability():
    m = build_event_manifest(repo_root=_REPO)
    names = {row["file"] for row in m["modules"]}
    assert "swarm_stability_audit.py" in names
    stab = next(r for r in m["modules"] if r["file"] == "swarm_stability_audit.py")
    assert 134 in stab["event_ids"]


def test_write_event_manifest(tmp_path):
    out = tmp_path / "event_manifest.json"
    p = write_event_manifest(out_path=out, repo_root=_REPO)
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["kind"] == "EVENT_MANIFEST"
    assert data["modules"]
