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
