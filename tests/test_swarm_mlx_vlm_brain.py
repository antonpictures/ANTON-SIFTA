from pathlib import Path


def test_prepare_image_keeps_path_strings_for_mlx_vlm_cli_parity():
    from System import swarm_mlx_vlm_brain as vlm

    path = "/tmp/alice-browser-frame.png"
    assert vlm._prepare_image(path) == path
    assert vlm._prepare_image([path]) == [path]


def test_apply_generation_chat_template_counts_image_media(monkeypatch):
    from System import swarm_mlx_vlm_brain as vlm
    import mlx_vlm.prompt_utils as prompt_utils

    class Model:
        config = {"model_type": "gemma4"}

    class Processor:
        pass

    calls = {}

    def fake_apply_chat_template(processor, config, prompt, **kwargs):
        calls.update(kwargs)
        assert processor is vlm._PROCESSOR
        assert config == Model.config
        return f"TEMPLATE::{prompt}"

    monkeypatch.setattr(vlm, "_MODEL", Model())
    monkeypatch.setattr(vlm, "_PROCESSOR", Processor())
    monkeypatch.setattr(prompt_utils, "apply_chat_template", fake_apply_chat_template)

    out = vlm._apply_generation_chat_template(
        "Describe this image.",
        image=[str(Path("/tmp/a.png")), str(Path("/tmp/b.png"))],
    )

    assert out == "TEMPLATE::Describe this image."
    assert calls["num_images"] == 2
    assert calls["num_audios"] == 0
    assert calls["enable_thinking"] is False


def test_hf_cached_gemma4_12b_mlx_resolves_to_repo_tag(monkeypatch, tmp_path):
    from System import swarm_mlx_vlm_brain as vlm

    repo_root = tmp_path / "hub" / "models--SuperagenticAI--gemma-4-12b-it-8bit-mlx"
    snap = repo_root / "snapshots" / "abc123"
    snap.mkdir(parents=True)
    (repo_root / "refs").mkdir()
    (repo_root / "refs" / "main").write_text("abc123", encoding="utf-8")
    (snap / "config.json").write_text('{"model_type":"gemma4_unified"}', encoding="utf-8")

    monkeypatch.setenv("HF_HOME", str(tmp_path))
    monkeypatch.setattr(vlm, "MLX_VLM_AVAILABLE", True)

    assert vlm._hf_cached_model_dir("SuperagenticAI/gemma-4-12b-it-8bit-mlx") == str(snap)
    assert vlm._get_model_dir("mlx-vlm:SuperagenticAI/gemma-4-12b-it-8bit-mlx") == str(snap)
    assert vlm._model_tag_for_dir(snap) == "mlx-vlm:SuperagenticAI/gemma-4-12b-it-8bit-mlx"
    assert "mlx-vlm:SuperagenticAI/gemma-4-12b-it-8bit-mlx" in vlm.describe_models()
