"""Tests for vision → owner_body_events bridge (Ollama mocked)."""
from __future__ import annotations

import io
import json
from unittest.mock import patch

import pytest


def test_call_ollama_vision_png_success() -> None:
    from System import swarm_owner_vision_body_bridge as mod

    fake = json.dumps(
        {"message": {"content": "MOUTH_VISIBILITY: PARTIAL\nORAL_NOTES: uncertain from pixels"}}
    ).encode()

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return fake

    with patch("urllib.request.urlopen", return_value=_Resp()):
        text, err = mod.call_ollama_vision_png(b"\x89PNG\r\n\x1a\n", model="test:latest")
    assert err == ""
    assert "MOUTH_VISIBILITY" in text


def test_call_ollama_vision_png_http_error() -> None:
    from System import swarm_owner_vision_body_bridge as mod
    import urllib.error

    def _raise(*a, **k):
        raise urllib.error.HTTPError("url", 500, "err", hdrs=None, fp=io.BytesIO(b"nope"))

    with patch("urllib.request.urlopen", side_effect=_raise):
        text, err = mod.call_ollama_vision_png(b"x", model="m")
    assert text == ""
    assert "http_500" in err


def test_parse_vision_body_reply_structures_fields() -> None:
    from System import swarm_owner_vision_body_bridge as mod

    parsed = mod.parse_vision_body_reply(
        "<think>ignore</think>\n"
        "MOUTH_VISIBILITY: CLEAR\n"
        "ORAL_NOTES: front teeth and lips visible; no diagnosis from pixels\n"
    )

    assert parsed["mouth_visibility"] == "CLEAR"
    assert parsed["observation_confidence"] == 0.85
    assert "front teeth" in parsed["oral_notes"]
    assert "think" not in parsed["raw_model_reply"]


def test_log_owner_body_from_vision_bytes_mocked(monkeypatch, tmp_path) -> None:
    from System import swarm_owner_vision_body_bridge as mod
    from System import swarm_owner_body_schema as body

    monkeypatch.setattr(body, "_STATE", tmp_path)
    monkeypatch.setattr(body, "_BODY_LOG", tmp_path / "owner_body_events.jsonl")
    monkeypatch.setattr(mod, "_FRAME_DIR", tmp_path / "owner_body_vision_frames")

    def _fake_png(*a, **k):
        return "MOUTH_VISIBILITY: PARTIAL\nORAL_NOTES: mouth partly visible", ""

    monkeypatch.setattr(mod, "call_ollama_vision_png", _fake_png)
    out = mod.log_owner_body_from_vision_bytes(
        b"\x89PNG\r\n", "deadbeef", model="probe:test", write_ledger=True,
    )
    assert out["ok"] is True
    assert out["row"]["event_type"] == "body_check"
    assert out["row"]["source"] == "stigmergic_vision:ollama"
    assert "deadbeef" in out["row"]["note"]
    assert out["row"]["evidence"]["kind"] == "OWNER_BODY_VISUAL_EVIDENCE_V1"
    assert out["row"]["evidence"]["frame_sha8"] == "deadbeef"
    assert out["row"]["evidence"]["mouth_visibility"] == "PARTIAL"
    assert out["row"]["evidence"]["artifact_path"].endswith(".png")
    assert (tmp_path / "owner_body_vision_frames").exists()
    log = (tmp_path / "owner_body_events.jsonl").read_text(encoding="utf-8").strip()
    assert "vision_probe" in log


def test_summary_surfaces_latest_visual_evidence(monkeypatch, tmp_path) -> None:
    from System import swarm_owner_body_schema as body

    monkeypatch.setattr(body, "_STATE", tmp_path)
    monkeypatch.setattr(body, "_BODY_LOG", tmp_path / "owner_body_events.jsonl")

    body.log_body_event(
        "body_check",
        "older body check",
        source="owner_voice",
        evidence={"kind": "OLD"},
    )
    body.log_body_event(
        "body_check",
        "vision_probe frame_sha8=abc123",
        source="stigmergic_vision:ollama",
        evidence={
            "kind": "OWNER_BODY_VISUAL_EVIDENCE_V1",
            "frame_sha8": "abc123",
            "png_sha256": "f" * 64,
            "artifact_path": "/tmp/owner_body_vision_frames/abc123.png",
            "model": "probe:test",
            "mouth_visibility": "CLEAR",
            "observation_confidence": 0.85,
            "oral_notes": "teeth visible; no diagnosis",
            "diagnosis_policy": "local visual observation only",
        },
    )

    prompt = body.summary_for_prompt()

    assert "source=stigmergic_vision:ollama" in prompt
    assert "frame_sha8=abc123" in prompt
    assert "mouth_visibility=CLEAR" in prompt
    assert "older body check" not in prompt
