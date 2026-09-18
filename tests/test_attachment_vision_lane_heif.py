from System.swarm_attachment_vision_lane import inspect_attachment_image


def test_attachment_vision_lane_accepts_heif_container(tmp_path):
    path = tmp_path / "IMG_4314.HEIC"
    path.write_bytes(b"\x00\x00\x00\x18ftypheic" + b"\x00" * 32)
    summary = inspect_attachment_image(path, run_ocr=False)
    assert summary.ok is True
    assert summary.image_format == "heif"
