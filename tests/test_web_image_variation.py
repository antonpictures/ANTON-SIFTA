from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from System import swarm_web_image_service as media


def test_generated_image_reply_is_contextual_and_varies_without_breaking_idempotence(tmp_path, monkeypatch):
    source = tmp_path / "backend.png"
    Image.new("RGB", (8, 8), "green").save(source)
    monkeypatch.setattr(media.bonsai, "bonsai_backend_status", lambda: {"ok": True})
    monkeypatch.setattr(media.bonsai, "generate_bonsai_image", lambda prompt: {
        "ok": True, "image_path": str(source),
    })
    replies = []
    for index in range(5):
        result = media.handle_media_request({
            "turn_id": f"turn-{index}", "session_id": "same-session",
            "text": f"/create a photo of a bonsai tree in morning light {index}",
        }, state_dir=tmp_path)
        replies.append(result["reply"])
        assert "bonsai" not in result["reply"].split("“", 1)[0].lower()
        assert result["reply"].startswith("I ")
        assert "#SIFTA" in result["reply"]
        assert "This is an AI-generated image, not a photograph of a real event." not in result["reply"]
    assert len(set(replies)) > 1

    repeat = media.handle_media_request({
        "turn_id": "turn-0", "session_id": "same-session",
        "text": "/create a photo of a bonsai tree in morning light 0",
    }, state_dir=tmp_path)
    assert repeat["reply"] == replies[0]
    manifests = list((tmp_path / "web_generated_images").glob("*.json"))
    assert all(json.loads(path.read_text()).get("reply_variant") for path in manifests)
