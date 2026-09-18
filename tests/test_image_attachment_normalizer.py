from pathlib import Path

import pytest

from System.swarm_image_attachment_normalizer import (
    detect_image_format,
    normalize_image_attachment,
)


def _fake_heic() -> bytes:
    return b"\x00\x00\x00\x18ftypheic" + b"\x00" * 32


def test_detects_heic_ftyp_brand():
    assert detect_image_format(_fake_heic()) == "heif"


def test_normalizes_heic_with_pillow_decoder(monkeypatch, tmp_path):
    Image = pytest.importorskip("PIL.Image")
    source = tmp_path / "IMG_4314.HEIC"
    source.write_bytes(_fake_heic())

    output = __import__("io").BytesIO()
    Image.new("RGB", (2, 2), "red").save(output, format="JPEG")

    def fake_pillow(data, max_pixels, timeout, *args):
        if data != _fake_heic():
            assert data.startswith(b"\xff\xd8\xff")
        return output.getvalue()

    monkeypatch.setattr(
        "System.swarm_image_attachment_normalizer._convert_with_pillow_subprocess",
        fake_pillow,
    )
    result = normalize_image_attachment(source)
    assert result.converted is True
    assert result.format == "jpeg"
    assert result.mime == "image/jpeg"
    assert result.data.startswith(b"\xff\xd8\xff")
    assert len(result.source_sha256) == 64
    assert len(result.data_sha256) == 64
    assert source.read_bytes() == _fake_heic()


def test_pillow_conversion_applies_exif_orientation(monkeypatch, tmp_path):
    Image = pytest.importorskip("PIL.Image")
    source = tmp_path / "rotated.HEIC"
    source.write_bytes(_fake_heic())
    picture = Image.new("RGB", (8, 4), "red")
    exif = picture.getexif()
    exif[274] = 6
    picture.info["exif"] = exif.tobytes()
    real_open = Image.open
    monkeypatch.setattr(Image, "open", lambda path: picture)

    from System.swarm_image_attachment_normalizer import _convert_with_pillow
    data = _convert_with_pillow(source, 40_000_000)
    monkeypatch.setattr(Image, "open", real_open)
    with Image.open(__import__("io").BytesIO(data)) as decoded:
        assert decoded.size == (4, 8)
        assert decoded.getexif().get(274) is None


def test_decoder_timeout_terminates_child_process(monkeypatch, tmp_path):
    import subprocess
    source = tmp_path / "timeout.HEIC"
    source.write_bytes(_fake_heic())

    monkeypatch.setattr(
        "System.swarm_image_attachment_normalizer._convert_with_pillow_subprocess",
        lambda data, max_pixels, timeout, *args: (_ for _ in ()).throw(TimeoutError("decoder exceeded")),
    )
    monkeypatch.setattr(
        "System.swarm_image_attachment_normalizer._convert_with_sips",
        lambda *args, **kwargs: None,
    )
    with pytest.raises(ValueError, match="decoder unavailable or failed"):
        normalize_image_attachment(source, conversion_timeout=0.05)


def test_heic_reports_missing_decoder(monkeypatch, tmp_path):
    source = tmp_path / "photo.heif"
    source.write_bytes(_fake_heic())
    monkeypatch.setattr(
        "System.swarm_image_attachment_normalizer._convert_with_pillow",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "System.swarm_image_attachment_normalizer._convert_with_sips",
        lambda *args, **kwargs: None,
    )
    with pytest.raises(ValueError, match="decoder unavailable"):
        normalize_image_attachment(source)


def test_rejects_fake_heic_and_oversized_source(tmp_path):
    source = tmp_path / "fake.HEIC"
    source.write_bytes(b"not an image")
    with pytest.raises(ValueError, match="unsupported image bytes"):
        normalize_image_attachment(source)
