from __future__ import annotations

import base64


def test_gemini_payload_includes_inline_image_data():
    from System.swarm_gemini_brain import _to_gemini_payload

    image_bytes = b"\x89PNG\r\n\x1a\nsmall"
    image_b64 = base64.b64encode(image_bytes).decode("ascii")

    payload = _to_gemini_payload(
        [
            {"role": "system", "content": "system boundary"},
            {
                "role": "user",
                "content": "describe the image",
                "images": [image_b64],
                "image_mime": "image/png",
            },
        ],
        temperature=0.2,
    )

    assert payload["systemInstruction"]["parts"][0]["text"] == "system boundary"
    parts = payload["contents"][0]["parts"]
    assert parts[0]["text"] == "describe the image"
    assert parts[1]["inlineData"] == {"mimeType": "image/png", "data": image_b64}


def test_teacher_cli_prompt_carries_image_path():
    from System.swarm_gemini_brain import _to_teacher_cli_prompt

    prompt = _to_teacher_cli_prompt(
        [
            {
                "role": "user",
                "content": "try again",
                "image_path": "/Users/ioanganton/Desktop/example.png",
            }
        ],
        teacher="Codex",
    )

    assert "[attached image path]" in prompt
    assert "/Users/ioanganton/Desktop/example.png" in prompt
