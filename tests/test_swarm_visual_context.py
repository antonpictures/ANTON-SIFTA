import json
import time


def test_visual_context_surfaces_live_photons_without_fake_glasses(monkeypatch, tmp_path):
    import System.swarm_visual_context as mod

    visual = tmp_path / "visual_stigmergy.jsonl"
    visual.write_text(json.dumps({
        "ts": time.time(),
        "w": 640,
        "h": 360,
        "entropy_bits": 7.1,
        "saliency_peak": 0.8,
        "motion_mean": 0.12,
    }) + "\n")
    monkeypatch.setattr(mod, "_VISUAL_LOG", visual)

    text = mod.summary_for_alice(max_visual_age_s=30.0)

    assert "camera_photons=fresh:true" in text
    assert "640x360" in text
    assert "semantic_limits=no verified glasses" in text
    assert "do not infer from text alone" in text


def test_visual_context_marks_stale_photons(monkeypatch, tmp_path):
    import System.swarm_visual_context as mod

    visual = tmp_path / "visual_stigmergy.jsonl"
    visual.write_text(json.dumps({
        "ts": time.time() - 120,
        "w": 10,
        "h": 10,
        "entropy_bits": 1,
        "saliency_peak": 0,
        "motion_mean": 0,
    }) + "\n")
    monkeypatch.setattr(mod, "_VISUAL_LOG", visual)

    text = mod.summary_for_alice(max_visual_age_s=1.0)

    assert "camera_photons=fresh:false" in text


def test_visual_context_does_not_call_old_live_target_stale(monkeypatch, tmp_path):
    import System.swarm_camera_target as target
    import System.swarm_visual_context as mod

    visual = tmp_path / "visual_stigmergy.jsonl"
    visual.write_text(json.dumps({
        "ts": time.time(),
        "w": 1920,
        "h": 1080,
        "entropy_bits": 7.2,
        "saliency_peak": 0.4,
        "motion_mean": 0.01,
    }) + "\n")
    monkeypatch.setattr(mod, "_VISUAL_LOG", visual)
    monkeypatch.setattr(
        target,
        "read_target",
        lambda: {
            "name": "USB Camera VID:1133 PID:2081",
            "index": 1,
            "writer": "owner_camera_command",
            "ts": time.time() - 240,
        },
    )
    monkeypatch.setattr(target, "resolve_index", lambda rec=None: 1)

    text = mod.summary_for_alice(max_visual_age_s=30.0)

    active_line = next(line for line in text.splitlines() if line.startswith("- active_eye="))
    assert "route_live=true" in active_line
    assert "target_age=" in active_line
    assert "stale=true" not in active_line
