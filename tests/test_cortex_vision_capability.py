#!/usr/bin/env python3
"""r310: after George set the default Cline cortex to the image-capable openai/gpt-5.4-mini,
Alice's vision router must recognize her DEFAULT cortex as able to see — so it stops routing
vision away from the default path (which would defeat the r308/r309 airdropped-photo curriculum).
"""
from System import swarm_cortex_capabilities as caps


def test_image_capable_cline_default_is_recognized():
    assert caps.is_vision_capable_model("openai/gpt-5.4-mini") is True
    assert caps.is_vision_capable_model("cline:cline-cli-default") is True


def test_existing_vision_models_still_recognized_no_regression():
    assert caps.is_vision_capable_model("gemini-3.1-pro") is True
    assert caps.is_vision_capable_model("qwen:accounts/fireworks/models/kimi-k2p6") is True
    assert caps.is_vision_capable_model("llama3.2-vision:latest") is True


def test_text_only_model_is_not_vision():
    assert caps.is_vision_capable_model("deepseek-v4-flash") is False
    assert caps.is_vision_capable_model("") is False


def test_native_image_payload_path_stays_conservative():
    # CLI teachers (cline / gpt-5.4-mini) send an image PATH, not raw bytes → not "native"
    assert caps.is_vision_capable_model("openai/gpt-5.4-mini", require_native_image_payload=True) is False
    assert caps.is_vision_capable_model("cline:cline-cli-default", require_native_image_payload=True) is False
    # local Ollama vision tags CAN send native bytes
    assert caps.is_vision_capable_model("llama3.2-vision:latest", require_native_image_payload=True) is True


def test_codex_5_5_cortex_is_recognized_as_vision():
    # r324: George selected `codex:gpt-5.5` in inference settings. The codex_agent arm is
    # native_multimodal (gpt-5.5), so this cortex must be TRIED for an attached image, not
    # pre-empted to local ollama. This is the bug George hit: image fell to local gemma4.
    assert caps.is_vision_capable_model("codex:gpt-5.5") is True
    assert caps.is_vision_capable_model("gpt-5.5") is True
    # codex CLI receives an image PATH, not raw bytes → conservative on the native-bytes path
    # (same as cline / gpt-5.4-mini); local-image delivery is judged by the arm transport.
    assert caps.is_vision_capable_model("codex:gpt-5.5", require_native_image_payload=True) is False
    # the codex_agent arm itself carries the local-image transport (native_cli_image)
    assert caps._arm_can_receive_local_image("codex_agent") is True
