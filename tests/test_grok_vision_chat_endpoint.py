#!/usr/bin/env python3
"""r258: Grok photo eye must use the SAME endpoint as the working text path.

George 2026-06-01: "OAUTH WORKS FOR TEXT THEN WORKS FOR PHOTO." Text (grok_chat.py
--one-shot) authenticates on /v1/chat/completions with the OAuth bearer and works daily;
the photo path had been posting to /v1/responses, which rejects the same valid token.
These tests pin the photo request to /v1/chat/completions with an image_url content block.
"""
from System import xai_grok_oauth_organ as organ


def test_default_endpoint_is_chat_completions():
    # The function default must be the proven-working text endpoint, not /v1/responses.
    import inspect
    sig = inspect.signature(organ.describe_image_via_oauth)
    assert sig.parameters["api_url"].default == organ._CHAT_API_URL
    assert organ._CHAT_API_URL == "https://api.x.ai/v1/chat/completions"


def test_request_shape_matches_working_text_path():
    req = organ._build_grok_vision_chat_request("grok-4", "describe the photo", "data:image/png;base64,AAAA")
    assert req["model"] == "grok-4"
    assert req["stream"] is False
    content = req["messages"][0]["content"]
    kinds = {b.get("type") for b in content}
    assert "text" in kinds
    assert "image_url" in kinds
    img = next(b for b in content if b.get("type") == "image_url")
    assert img["image_url"]["url"].startswith("data:image")  # inlined base64, like grok_chat.py


def test_chat_text_extractor():
    raw = '{"choices":[{"message":{"role":"assistant","content":"a sheriff next to a man"}}]}'
    assert organ._extract_chat_text(raw) == "a sheriff next to a man"
    assert organ._extract_chat_text("not json") == ""


def test_no_credential_is_honest_failure(tmp_path):
    # With no token present in a clean env, the function reports the credential gap
    # (it does not crash and does not claim a fake description).
    img = tmp_path / "x.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 64)
    original = organ.load_credential
    organ.load_credential = lambda **kwargs: None
    try:
        res = organ.describe_image_via_oauth(str(img), "describe", env={})
    finally:
        organ.load_credential = original
    # Either no-credential (clean env) — the honest, non-blind statuses we expect.
    assert res.ok is False
    assert res.status in {"no_xai_oauth_credential", "image_read_failed"}
