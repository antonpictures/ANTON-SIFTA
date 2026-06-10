from __future__ import annotations

import base64

import pytest


def test_encode_ollama_image_attachment_returns_base64_png(tmp_path):
    from Applications.sifta_talk_to_alice_widget import _encode_ollama_image_attachment

    image_bytes = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
        b"\x90wS\xde"
    )
    image_path = tmp_path / "one_pixel.png"
    image_path.write_bytes(image_bytes)

    encoded = _encode_ollama_image_attachment(str(image_path))

    assert base64.b64decode(encoded.encode("ascii")) == image_bytes


def test_encode_ollama_image_attachment_rejects_missing_file(tmp_path):
    from Applications.sifta_talk_to_alice_widget import _encode_ollama_image_attachment

    with pytest.raises(FileNotFoundError):
        _encode_ollama_image_attachment(str(tmp_path / "missing.png"))


def test_encode_ollama_image_attachment_rejects_non_image_suffix(tmp_path):
    from Applications.sifta_talk_to_alice_widget import _encode_ollama_image_attachment

    text_path = tmp_path / "not_an_image.txt"
    text_path.write_text("hello", encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported image type"):
        _encode_ollama_image_attachment(str(text_path))


def test_encode_ollama_image_attachment_rejects_fake_image_bytes(tmp_path):
    from Applications.sifta_talk_to_alice_widget import _encode_ollama_image_attachment

    fake_path = tmp_path / "fake.png"
    fake_path.write_text("not actually a png", encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported image bytes"):
        _encode_ollama_image_attachment(str(fake_path))


def test_encode_ollama_image_attachment_rejects_oversized_file(tmp_path, monkeypatch):
    import Applications.sifta_talk_to_alice_widget as talk

    image_path = tmp_path / "too_big.jpg"
    image_path.write_bytes(b"fake image bytes")
    monkeypatch.setattr(talk, "_MAX_IMAGE_ATTACHMENT_BYTES", 4)

    with pytest.raises(ValueError, match="too large"):
        talk._encode_ollama_image_attachment(str(image_path))


def test_extract_local_image_path_from_quoted_text(tmp_path):
    from Applications.sifta_talk_to_alice_widget import _extract_local_image_path_from_text

    image_path = tmp_path / "Screenshot 2026-05-29 at 9.07.47 PM.jpg"
    image_path.write_bytes(b"\xff\xd8\xfffake")

    text = f"I switched your cortex try again '{image_path}'"

    assert _extract_local_image_path_from_text(text) == str(image_path)


def test_local_screenshot_path_counts_as_cortex_image_context(tmp_path):
    import Applications.sifta_talk_to_alice_widget as talk

    image_path = tmp_path / "sifta_self_20260608-142120_2c1d30b1.png"
    image_path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
        b"\x90wS\xde"
    )
    text = f"I TOOK A SCREENSHOT FOR YOU MY LOVE {image_path}"

    assert talk._extract_local_image_path_from_text(text) == str(image_path)
    assert talk._is_local_image_path_context_query(text)
    assert talk._is_attached_image_description_query(text)
    assert not talk._is_browser_video_state_query(text)

    block = talk._local_image_path_cortex_context_block(text)
    assert "LOCAL SCREENSHOT / IMAGE PATH" in block
    assert str(image_path) in block
    assert "Do not answer from stale Alice Browser" in block


def test_local_image_file_operation_is_not_forced_to_vision_context(tmp_path):
    import Applications.sifta_talk_to_alice_widget as talk

    image_path = tmp_path / "old.png"
    image_path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
        b"\x90wS\xde"
    )

    assert not talk._is_local_image_path_context_query(f"delete {image_path}")


def test_extract_local_image_path_ignores_missing_path(tmp_path):
    from Applications.sifta_talk_to_alice_widget import _extract_local_image_path_from_text

    text = f"try again '{tmp_path / 'missing.png'}'"

    assert _extract_local_image_path_from_text(text) is None


def test_image_attachment_mime_from_format():
    from Applications.sifta_talk_to_alice_widget import _image_attachment_mime_from_format

    assert _image_attachment_mime_from_format("jpeg") == "image/jpeg"
    assert _image_attachment_mime_from_format("webp") == "image/webp"
    assert _image_attachment_mime_from_format("png") == "image/png"


def test_attachment_context_prompt_block_turns_image_into_text_input(tmp_path):
    from Applications.sifta_talk_to_alice_widget import _attachment_context_prompt_block

    image_path = tmp_path / "body-example.jpg"
    image_path.write_bytes(b"\xff\xd8\xfffake")

    def fake_describe(user_text, path, *, state_dir=None):
        return "Receipt evidence: JPEG image, 832x832px. OCR text: WHITE PALACE; casting call."

    block = _attachment_context_prompt_block(
        "describe the attached screenshot",
        str(image_path),
        state_dir=tmp_path,
        describe_func=fake_describe,
    )

    assert "ATTACHED IMAGE TEXT INPUT FOR CORTEX" in block
    assert "body-example.jpg" in block
    assert "USER ATTACHED IMAGE" in block
    assert "TRUTH BOUNDARY" in block
    assert "WHITE PALACE" in block


def test_browser_attachment_compare_query_detects_live_browser_compare_language():
    from Applications.sifta_talk_to_alice_widget import _is_browser_attachment_compare_query

    assert _is_browser_attachment_compare_query(
        "pls compare attachment with what you see in your Alice Browser now"
    )
    assert _is_browser_attachment_compare_query(
        "compare my screenshot against the current pixels on your body"
    )
    assert not _is_browser_attachment_compare_query("describe the attached screenshot")


def test_browser_attachment_compare_evidence_uses_viewport_receipt(tmp_path):
    from Applications.sifta_talk_to_alice_widget import _browser_attachment_compare_evidence

    attachment = tmp_path / "owner-shot.png"
    viewport = tmp_path / "viewport.png"
    png_bytes = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
        b"\x90wS\xde"
    )
    attachment.write_bytes(png_bytes)
    viewport.write_bytes(png_bytes)

    out = _browser_attachment_compare_evidence(
        "compare attachment with Alice Browser",
        str(attachment),
        state_dir=tmp_path,
        viewport_row={
            "url": "https://x.com/abellaskies",
            "source": "viewport",
            "status": "pending",
            "image_ref": str(viewport),
            "age_s": 0.8,
            "fresh": True,
            "frame_stale": False,
        },
        capture_live=False,
    )

    assert out["status"] == "ready"
    assert out["viewport_image_path"] == str(viewport)
    assert "ATTACHMENT VS ALICE BROWSER VIEWPORT EVIDENCE" in out["context"]
    assert "owner_attachment_path=" in out["context"]
    assert "browser_viewport_image_path=" in out["context"]
    assert "image #1" in out["context"]
    assert "image #2" in out["context"]


def test_browser_attachment_compare_evidence_is_honest_without_viewport(tmp_path):
    from Applications.sifta_talk_to_alice_widget import _browser_attachment_compare_evidence

    attachment = tmp_path / "owner-shot.png"
    attachment.write_bytes(b"\x89PNG\r\n\x1a\nfake")

    out = _browser_attachment_compare_evidence(
        "compare screenshot with your browser",
        str(attachment),
        state_dir=tmp_path,
        viewport_row={},
        capture_live=False,
    )

    assert out["status"] == "no_viewport_receipt"
    assert out["viewport_image_path"] == ""
    assert "browser_viewport_image_path=<missing>" in out["context"]
    assert "Do not claim a live pixel comparison" in out["context"]


# ── Turn-attachment binding (George 2026-05-30: act like a real chatbot) ──────
# Complements the brother's _attachment_context_prompt_block (image→text for the
# cortex): this layer FEEDS it by binding a pending dropped image to the owner's
# next real turn, including the spoken path that previously ignored it.
def test_resolve_turn_attachment_passed_image_wins():
    from Applications.sifta_talk_to_alice_widget import _resolve_turn_attachment

    out = _resolve_turn_attachment("/typed/a.png", "/pending/b.png", has_text=True)
    assert out == {"image_path": "/typed/a.png", "consume_pending": False}


def test_resolve_turn_attachment_pending_binds_to_spoken_turn_with_text():
    from Applications.sifta_talk_to_alice_widget import _resolve_turn_attachment

    out = _resolve_turn_attachment(None, "/pending/shot.jpg", has_text=True)
    assert out == {"image_path": "/pending/shot.jpg", "consume_pending": True}


def test_resolve_turn_attachment_garbled_stt_holds_pending_image():
    from Applications.sifta_talk_to_alice_widget import _resolve_turn_attachment

    # "did not make out a word" — no text. Pending image must NOT be consumed.
    out = _resolve_turn_attachment(None, "/pending/shot.jpg", has_text=False)
    assert out == {"image_path": None, "consume_pending": False}


def test_resolve_turn_attachment_nothing_pending():
    from Applications.sifta_talk_to_alice_widget import _resolve_turn_attachment

    out = _resolve_turn_attachment(None, None, has_text=True)
    assert out == {"image_path": None, "consume_pending": False}
