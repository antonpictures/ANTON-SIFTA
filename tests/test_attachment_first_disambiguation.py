"""r876 verifier tests for r874 P1-C attachment-first disambiguation."""

import sys
import types

from System.swarm_attachment_first_disambiguation import (
    build_attachment_first_context,
    should_block_xbox_fable_guess,
)


def test_attachment_first_context_blocks_xbox_fable_guess(monkeypatch, tmp_path):
    img = tmp_path / "fable-ui.png"
    img.write_bytes(b"fake-png")

    fake_vision = types.SimpleNamespace(
        describe_attachment_for_talk=lambda *args, **kwargs: "OCR: Claude Fable 5 model picker"
    )
    monkeypatch.setitem(sys.modules, "System.swarm_attachment_vision_lane", fake_vision)

    ctx = build_attachment_first_context(
        "search Fable 5 from Anthropic",
        image_path=str(img),
        state_dir=tmp_path,
    )
    assert ctx is not None
    assert "ATTACHMENT-FIRST DISAMBIGUATION" in ctx
    assert "do NOT answer with Xbox game Fable" in ctx

    assert should_block_xbox_fable_guess(
        "search Fable 5 from Anthropic",
        "Fable is an Xbox open-world game by Playground Games.",
        image_path=str(img),
        state_dir=tmp_path,
    )
