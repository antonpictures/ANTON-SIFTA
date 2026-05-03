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
