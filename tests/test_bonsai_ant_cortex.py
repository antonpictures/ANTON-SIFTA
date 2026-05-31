from __future__ import annotations

import json
from pathlib import Path

import pytest

from System import swarm_bonsai_image_organ as bonsai


def test_pheromone_update_formula_is_stable():
    assert bonsai.update_pheromone_weight(1.0, 0.5, evaporation=0.18, deposit=0.72) == 1.18


def test_ant_candidates_are_deterministic_and_field_derived():
    rows = [
        {
            "owner_label": "bonsai-in-studio",
            "meaning": "calm craft patience",
            "prompt": "A bonsai tree in soft morning light",
            "hue_deg": 112.0,
            "entropy_bits": 6.4,
            "saliency_peak": 0.33,
            "source": "ai_generated",
        }
    ]
    first = bonsai.generate_ant_prompt_candidates(
        visual_rows=rows,
        trace_rows=[],
        ant_count=8,
        rounds=3,
        seed=7,
    )
    second = bonsai.generate_ant_prompt_candidates(
        visual_rows=rows,
        trace_rows=[],
        ant_count=8,
        rounds=3,
        seed=7,
    )

    assert first == second
    assert first
    joined = " ".join(candidate["prompt"] for candidate in first)
    assert "bonsai" in joined
    assert any(candidate["score"] > 0 for candidate in first)


def test_parse_cortex_json_accepts_fenced_json():
    parsed = bonsai.parse_bonsai_cortex_json(
        """Here is the selection:
        ```json
        {
          "prompt": "A green bonsai beside a copper lamp",
          "owner_label": "green-bonsai-copper-lamp",
          "meaning": "green growth, warm light",
          "rationale": "matches the field"
        }
        ```
        """
    )

    assert parsed["prompt"] == "A green bonsai beside a copper lamp"
    assert parsed["owner_label"] == "green-bonsai-copper-lamp"
    assert parsed["meaning"] == "green growth, warm light"
    assert parsed["rationale"] == "matches the field"


def test_parse_cortex_json_rejects_missing_prompt():
    with pytest.raises(ValueError, match="prompt"):
        bonsai.parse_bonsai_cortex_json('{"owner_label": "empty"}')


def test_compose_records_honest_cortex_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(bonsai, "_VISUAL_LANE", tmp_path / "visual_stigmergy.jsonl")
    monkeypatch.setattr(bonsai, "_BONSAI_TRACE", tmp_path / "bonsai_image_trace.jsonl")
    monkeypatch.setattr(bonsai, "_ANT_CORTEX_TRACE", tmp_path / "bonsai_ant_cortex.jsonl")
    bonsai._VISUAL_LANE.write_text(
        json.dumps({"owner_label": "bonsai", "meaning": "quiet green patience"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        bonsai,
        "call_live_bonsai_cortex",
        lambda candidates, timeout_s=45: {"ok": False, "model": "test-cortex", "error": "timeout"},
    )

    result = bonsai.compose_bonsai_ant_cortex(seed=3, timeout_s=1)

    assert result["ok"] is False
    assert result["error"] == "timeout"
    assert result["selected"] is None
    rows = [json.loads(line) for line in Path(result["trace_path"]).read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["ok"] is False
    assert rows[-1]["row_hash"].startswith("sha256:")


def test_compose_records_cortex_selection(monkeypatch, tmp_path):
    monkeypatch.setattr(bonsai, "_VISUAL_LANE", tmp_path / "visual_stigmergy.jsonl")
    monkeypatch.setattr(bonsai, "_BONSAI_TRACE", tmp_path / "bonsai_image_trace.jsonl")
    monkeypatch.setattr(bonsai, "_ANT_CORTEX_TRACE", tmp_path / "bonsai_ant_cortex.jsonl")
    bonsai._BONSAI_TRACE.write_text(
        json.dumps({"prompt": "bonsai and morning light", "meaning": "calm studio"}) + "\n",
        encoding="utf-8",
    )
    selected = {
        "prompt": "A bonsai tree listening to green pheromone light",
        "owner_label": "bonsai-green-pheromone",
        "meaning": "growth, listening, field memory",
        "rationale": "uses the strongest ant fragments",
    }
    monkeypatch.setattr(
        bonsai,
        "call_live_bonsai_cortex",
        lambda candidates, timeout_s=45: {"ok": True, "model": "test-cortex", "selected": selected},
    )

    result = bonsai.compose_bonsai_ant_cortex(seed=4, timeout_s=1)

    assert result["ok"] is True
    assert result["selected"] == selected
    assert result["cortex_model"] == "test-cortex"
    rows = [json.loads(line) for line in Path(result["trace_path"]).read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["selected"]["owner_label"] == "bonsai-green-pheromone"


def test_backend_status_missing_env_is_honest_idle_error(monkeypatch):
    monkeypatch.delenv("SIFTA_BONSAI_DEMO_DIR", raising=False)

    status = bonsai.bonsai_backend_status()

    assert status["ok"] is False
    assert status["configured"] is False
    assert status["env_var"] == "SIFTA_BONSAI_DEMO_DIR"
    assert "not configured" in status["error"]


def test_generate_does_not_launch_when_backend_missing(monkeypatch):
    monkeypatch.delenv("SIFTA_BONSAI_DEMO_DIR", raising=False)

    def fail_run(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("generation subprocess should not launch without backend")

    monkeypatch.setattr(bonsai.subprocess, "run", fail_run)

    result = bonsai.generate_bonsai_image("A bonsai tree")

    assert result["ok"] is False
    assert "not configured" in result["error"]
    assert result["backend_status"]["ok"] is False


def test_backend_status_ready_requires_model_and_script(monkeypatch, tmp_path):
    demo = tmp_path / "Bonsai-Image-Demo"
    model_dir = demo / bonsai.DEFAULT_MODEL_SUBDIR
    script = demo / "scripts" / "generate.sh"
    model_dir.mkdir(parents=True)
    script.parent.mkdir(parents=True)
    (model_dir / "weights.safetensors").write_text("stub", encoding="utf-8")
    script.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setenv("SIFTA_BONSAI_DEMO_DIR", str(demo))

    status = bonsai.bonsai_backend_status()

    assert status["ok"] is True
    assert status["demo_dir"] == str(demo)
    assert status["script_path"] == str(script)
