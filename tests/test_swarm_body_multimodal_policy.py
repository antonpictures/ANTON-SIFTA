import json
from pathlib import Path

from System.swarm_body_multimodal_policy import (
    classify_body_multimodal_need,
    cowatch_novelty_line,
    image_turn_vlm_redirect,
    is_text_only_cortex,
    prompt_block_for_alice,
)


def test_source_separation_turn_flags_8b_as_composer_not_proof(tmp_path: Path):
    row = classify_body_multimodal_need(
        "Vitaliy is whistling through the iPhone speaker near my ear; compare it with my real room voice.",
        current_model="alice-m5-cortex-8b-6.3gb:latest",
        write=True,
        state_dir=tmp_path,
    )

    assert row["needs_joint_audio_vision"] is True
    assert row["source_separation"] is True
    assert row["current_8b_limit"] is True
    assert row["route"] == "sensor_receipts_first_then_cortex_compose"
    assert "audio_source_classifications.jsonl" in row["required_receipts"]

    lines = (tmp_path / "body_multimodal_task_policy.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["truth_label"] == "BODY_MULTIMODAL_TASK_POLICY_V1"


def test_background_birds_requires_receipt_not_species_guess(tmp_path: Path):
    block = prompt_block_for_alice(
        owner_text="record a piece of the background noise with birds and mark it as background receipt",
        current_model="alice-m5-cortex-8b-6.3gb:latest",
        state_dir=tmp_path,
    )

    assert "BODY MULTIMODAL POLICY" in block
    assert "species labels" in block
    assert "audio_ingress" in block
    assert "confident guess" in block


def test_ordinary_text_turn_does_not_inject_policy(tmp_path: Path):
    block = prompt_block_for_alice(
        owner_text="good morning Alice",
        current_model="alice-m5-cortex-8b-6.3gb:latest",
        state_dir=tmp_path,
    )

    assert block == ""
    assert not (tmp_path / "body_multimodal_task_policy.jsonl").exists()


def test_cowatch_model_video_logs_policy_receipt(tmp_path: Path, monkeypatch):
    from System import swarm_body_multimodal_policy as policy

    monkeypatch.setattr(policy, "STATE", tmp_path)
    line = cowatch_novelty_line(
        "MisoTTS - Most Emotive Voice Model in the World - Really?",
        current_model="alice-m5-cortex-8b-6.3gb:latest",
    )

    assert "body multimodal policy" in line
    assert "sensor receipts first" in line
    assert "Gemma 4 12B" in line
    assert (tmp_path / "body_multimodal_task_policy.jsonl").exists()


def test_image_on_igor_text_only_redirects_to_vlm():
    assert is_text_only_cortex("igorls/gemma-4-12B-it-qat-q4_0-unquantized-heretic:latest")

    row = image_turn_vlm_redirect(
        "igorls/gemma-4-12B-it-qat-q4_0-unquantized-heretic:latest",
        True,
        available_vlms=["mlx-vlm:osmQwopus-3.6-27B-OptiQ-3.7bpw-mlx"],
    )

    assert row["redirect"] is True
    assert row["to"] == "mlx-vlm:osmQwopus-3.6-27B-OptiQ-3.7bpw-mlx"
    assert "text-only cortex" in row["reason"]


def test_image_redirect_is_conservative_for_unknown_or_missing_vlm():
    unknown = image_turn_vlm_redirect(
        "some-new-vision-model",
        True,
        available_vlms=["mlx-vlm:osmQwopus-3.6-27B-OptiQ-3.7bpw-mlx"],
    )
    missing = image_turn_vlm_redirect(
        "igorls/gemma-4-12B-it-qat-q4_0-unquantized-heretic:latest",
        True,
        available_vlms=[],
    )

    assert unknown["redirect"] is False
    assert missing["redirect"] is False
    assert "NO VLM available" in missing["reason"]


def test_default_vlm_discovery_includes_installed_local_ollama_eye(monkeypatch):
    from System import swarm_body_multimodal_policy as policy
    monkeypatch.setattr(
        "System.swarm_ollama_vision_arm.pick_local_vision_model",
        lambda: "hf.co/huihui-ai/Huihui-MiniCPM-V-4_5-abliterated:Q4_K_M",
    )
    vlms = policy._default_vlms()
    assert "hf.co/huihui-ai/Huihui-MiniCPM-V-4_5-abliterated:Q4_K_M" in vlms
    row = policy.image_turn_vlm_redirect(
        "ater vin2011/Aries:latest", True, available_vlms=vlms,
    )
    assert row["redirect"] is False  # unknown model remains conservative
    assert row["capability"] == "unknown"
    assert "unknown" in row["reason"]

    row = policy.image_turn_vlm_redirect(
        "ornith-1.5:9b", True, available_vlms=vlms,
    )
    assert row["redirect"] is True
    assert "MiniCPM" in row["to"]


def test_redirect_respects_first_owner_selected_eye_without_osm_override():
    row = image_turn_vlm_redirect(
        "ornith-1.5:9b",
        True,
        available_vlms=["hf.co/huihui-ai/Huihui-MiniCPM-V-4_5-abliterated:Q4_K_M", "mlx-vlm:osmQwopus"],
    )
    assert row["redirect"] is True
    assert row["to"].startswith("hf.co/huihui-ai/Huihui-MiniCPM")


def test_live_text_only_capability_routes_unknown_named_cortex(monkeypatch):
    from System import swarm_body_multimodal_policy as policy
    from System import swarm_cortex_capabilities as capabilities
    monkeypatch.setattr(
        capabilities, "_ollama_capabilities", lambda model: frozenset({"completion"}),
    )
    row = policy.image_turn_vlm_redirect(
        "atervin2011/Aries:latest", True, available_vlms=["minicpm-v:latest"],
    )
    assert row["redirect"] is True
    assert row["to"] == "minicpm-v:latest"


def test_live_capability_metadata_overrides_model_name(monkeypatch):
    from System import swarm_body_multimodal_policy as policy
    from System import swarm_cortex_capabilities as capabilities

    monkeypatch.setattr(
        capabilities, "_ollama_capabilities", lambda model: frozenset({"completion", "vision"}),
    )
    row = policy.image_turn_vlm_redirect(
        "gemma:2b", True, available_vlms=["minicpm-v:latest"],
    )
    assert row["redirect"] is False
    assert row["capability"] == "known_vision"
