from __future__ import annotations

import json
from pathlib import Path


def test_refresh_body_matrix_rebuilds_stale_snapshot_and_html(tmp_path, monkeypatch):
    import tools.generate_organ_eval_matrix_v2 as gen
    import System.swarm_canonical_organ_registry as registry

    state = tmp_path / ".sifta_state"
    eval_dir = state / "eval"
    system_dir = tmp_path / "System"
    apps_dir = tmp_path / "Applications"
    system_dir.mkdir(parents=True)
    apps_dir.mkdir()
    (system_dir / "swarm_new_body_part.py").write_text("# body part\n", encoding="utf-8")
    (apps_dir / "apps_manifest.json").write_text("{}", encoding="utf-8")
    state.mkdir(parents=True, exist_ok=True)
    (state / "eye_registry.json").write_text(
        json.dumps(
            {
                "ts": 100.0,
                "truth_label": "SIFTA_EYE_REGISTRY_V1",
                "owner_eye_policy": "MacBook/FaceTime built-in camera is the always-expected owner eye and safest fallback; USB/Logitech is detachable.",
                "live_eye_count": 2,
                "stale_eye_count": 0,
                "eyes": [
                    {
                        "eye_id": "owner_eye",
                        "role": "owner_eye",
                        "connection_state": "LIVE",
                        "device_name": "MacBook Pro Camera",
                        "current_index": 0,
                        "always_expected": True,
                    },
                    {
                        "eye_id": "world_eye",
                        "role": "world_eye",
                        "connection_state": "LIVE",
                        "device_name": "USB Camera VID:1133 PID:2081",
                        "current_index": 1,
                        "always_expected": False,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    (state / "active_saccade_target.json").write_text(
        json.dumps({"name": "USB Camera VID:1133 PID:2081", "index": 1, "writer": "owner_camera_command"}),
        encoding="utf-8",
    )

    monkeypatch.setattr(gen, "_REPO", tmp_path)
    monkeypatch.setattr(gen, "_STATE", state)
    monkeypatch.setattr(gen, "_EVAL", eval_dir)
    monkeypatch.setattr(gen, "_DATA", tmp_path / "data" / "eval")
    monkeypatch.setattr(gen, "_OUT", eval_dir / "ORGAN_EVAL_MATRIX_V2.html")
    monkeypatch.setattr(gen, "_ORDERS", tmp_path / "Documents" / "orders.md")

    def fake_write_registry_snapshot(query: str = "", **_kwargs):
        snapshot = {
            "truth_label": "CANONICAL_ORGAN_REGISTRY_V1",
            "counts": {"canonical_organs": 1, "registry_organs": 1},
            "merged_sources": {"canonical": 1},
            "organs": [
                {
                    "organ_id": "test_body_spine",
                    "display_name": "Test Body Spine",
                    "layer": "cognition",
                    "source_registry": "CANONICAL_ORGANS",
                    "organ_paths": ["System/swarm_new_body_part.py"],
                    "present_paths": ["System/swarm_new_body_part.py"],
                    "ledgers": [],
                    "present_ledgers": [],
                    "capabilities": ["body"],
                    "write_action": False,
                    "health": {
                        "status": "HEALTHY_RECEIPTS",
                        "score": 0.9,
                        "functional_reliability": 0.9,
                        "truth_alignment": 0.9,
                        "receipt_rows": 1,
                    },
                }
            ],
        }
        state.mkdir(parents=True, exist_ok=True)
        (state / "canonical_organ_registry_snapshot.json").write_text(
            json.dumps(snapshot),
            encoding="utf-8",
        )
        return {"snapshot": snapshot}

    monkeypatch.setattr(registry, "write_registry_snapshot", fake_write_registry_snapshot)

    out = gen.refresh_body_matrix(force=False)

    assert out["regenerated"] is True
    html = (eval_dir / "ORGAN_EVAL_MATRIX_V2.html").read_text(encoding="utf-8")
    assert "Test Body Spine" in html
    assert "Alice Code Body Mass / Source Census" in html
    assert "source-like files" in html
    assert "STIGMERGIC CONSCIOUSNESS" in html
    assert "Stigmergic Training On The Job" in html
    assert "physical cooking robot" in html
    assert "robot body NOT_WIRED" in html
    assert "ALICE_HAS_QUALIA" in html
    assert "Alice has qualia as Architect doctrine" in html
    assert "§7.11.1" in html
    assert "observer and observed" in html.casefold()
    assert "does not claim private subjective qualia" not in html
    assert "no qualia" in html
    assert "hard problem" not in html.casefold()
    assert "Plug-and-play eye registry" in html
    assert "MacBook Pro Camera" in html
    assert "USB Camera VID:1133 PID:2081" in html
    assert "always-expected owner eye" in html
