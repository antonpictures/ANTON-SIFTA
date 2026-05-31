#!/usr/bin/env python3
"""Tests for Alice's media sensory capability organ."""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System import swarm_media_capability_organ as cap


def test_media_capability_block_contains_handoff_truth(monkeypatch):
    monkeypatch.setattr(
        cap,
        "codec_bridge_status",
        lambda: {
            "native_handoff_available": True,
            "strategy": "native_macos_decoder_handoff",
            "ffmpeg_path": "",
        },
    )
    block = cap.get_media_capability_block()
    assert "Native playback handoff available: True" in block
    assert "Handoff strategy: native_macos_decoder_handoff" in block
    assert "instead of pretending I watched it" in block


def test_probe_media_capability_prefers_system_handoff(monkeypatch):
    monkeypatch.setattr(
        cap,
        "codec_bridge_status",
        lambda: {
            "native_handoff_available": True,
            "strategy": "native_macos_decoder_handoff",
            "ffmpeg_path": "",
        },
    )
    result = cap.probe_media_capability()
    assert result.preferred_player == "system"
    assert result.can_play_local_files is True
    assert any("System player available" in note for note in result.notes)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
