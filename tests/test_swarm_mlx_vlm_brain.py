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
