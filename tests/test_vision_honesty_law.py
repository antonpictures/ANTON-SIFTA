"""Vision honesty law — no LLM prose-as-sight when camera proof is stale (r1276)."""
from __future__ import annotations

import json
import time
from pathlib import Path

from Applications import sifta_talk_to_alice_widget as talk


def _write_kernel(state: Path, now: float, *, heartbeat_age_s: float = 3.0) -> None:
    state.mkdir(parents=True, exist_ok=True)
    (state / "kernel_process_table.json").write_text(
        json.dumps(
            {
                "processes": {
                    "e35_vision_001": {
                        "health": 1.0,
                        "last_heartbeat_ts": now - heartbeat_age_s,
                    }
                }
            }
        ),
        encoding="utf-8",
    )


def _write_stale_camera_state(state: Path, now: float) -> None:
    state.mkdir(parents=True, exist_ok=True)
    _write_kernel(state, now, heartbeat_age_s=600.0)
    with (state / "visual_stigmergy.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": now - 589, "w": 640, "h": 480, "sha8": "stale"}) + "\n")
    with (state / "active_eye_identity_frames.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "ts": now - 594,
                    "w": 640,
                    "h": 480,
                    "device": "MacBook Pro Camera",
                    "sha8": "stale",
                }
            )
            + "\n"
        )
    with (state / "face_detection_events.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "ts": now - 10,
                    "audience": "architect",
                    "confidence": 0.8,
                    "faces_detected": 1,
                }
            )
            + "\n"
        )


def _write_live_camera_state(state: Path, now: float) -> None:
    state.mkdir(parents=True, exist_ok=True)
    _write_kernel(state, now, heartbeat_age_s=2.0)
    (state / "active_saccade_target.json").write_text(
        json.dumps(
            {
                "name": "MacBook Pro Camera",
                "index": 0,
                "writer": "pytest",
                "ts": now,
                "lease_until": now + 5,
            }
        ),
        encoding="utf-8",
    )
    (state / "sensory_attention_status.json").write_text(
        json.dumps(
            {
                "active_sense": "close_owner_eye",
                "target_name": "MacBook Pro Camera",
                "target_index": 0,
            }
        ),
        encoding="utf-8",
    )
    with (state / "visual_stigmergy.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": now, "w": 640, "h": 480, "sha8": "live"}) + "\n")
    with (state / "active_eye_identity_frames.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "ts": now,
                    "w": 640,
                    "h": 480,
                    "device": "MacBook Pro Camera",
                    "sha8": "live",
                }
            )
            + "\n"
        )
    with (state / "face_detection_events.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "ts": now - 3,
                    "audience": "architect",
                    "confidence": 0.8,
                    "faces_detected": 1,
                }
            )
            + "\n"
        )


def test_can_you_see_me_honest_when_camera_proof_stale(tmp_path, monkeypatch) -> None:
    now = time.time()
    state = tmp_path / ".sifta_state"
    _write_stale_camera_state(state, now)
    monkeypatch.setattr(talk, "_state_root", lambda: state)

    reply = talk._can_you_see_me_reply_for_alice()

    assert "stale or disconnected" in reply
    assert "cannot truthfully claim I see you" in reply
    assert "PNG files on disk is not certified live sight" in reply


def test_can_you_see_me_grounded_when_camera_proof_live(tmp_path, monkeypatch) -> None:
    now = time.time()
    state = tmp_path / ".sifta_state"
    _write_live_camera_state(state, now)
    monkeypatch.setattr(talk, "_state_root", lambda: state)

    reply = talk._can_you_see_me_reply_for_alice()

    assert "My eye saw" in reply
    assert "stale or disconnected" not in reply


def test_vision_honesty_law_injects_for_desktop_photo_open() -> None:
    text = "this attached image is on the desktop, open it in alice browser"
    block = talk._vision_honesty_law_context_block(text)

    assert "VISION HONESTY LAW" in block
    assert "file://" in block
    assert "Never invent 'MBP Webcam Perspective Analysis'" in block


def test_vision_honesty_law_block_stale_camera(tmp_path, monkeypatch) -> None:
    now = time.time()
    state = tmp_path / ".sifta_state"
    _write_stale_camera_state(state, now)
    monkeypatch.setattr(talk, "_state_root", lambda: state)

    block = talk._vision_honesty_law_context_block("describe my clothes")

    assert "DISCONNECTED_OR_STALE_INPUT" in block
    assert "cannot describe objects from your camera eyes" in block


def test_vision_honesty_law_in_system_prompt_for_camera_describe(tmp_path, monkeypatch) -> None:
    now = time.time()
    state = tmp_path / ".sifta_state"
    _write_stale_camera_state(state, now)
    monkeypatch.setattr(talk, "_state_root", lambda: state)

    prompt = talk._current_system_prompt(
        user_active=True,
        user_text="describe my clothes",
    )

    assert "VISION HONESTY LAW" in prompt


def test_owner_visual_describe_blocked_when_camera_stale(tmp_path, monkeypatch) -> None:
    now = time.time()
    state = tmp_path / ".sifta_state"
    _write_stale_camera_state(state, now)
    monkeypatch.setattr(talk, "_state_root", lambda: state)

    block = talk._owner_visual_describe_context_block("describe my clothes")

    assert "VISION HONESTY GATE" in block
    assert "Do NOT invent clothes" in block


def test_camera_hallucination_last_mile_rewrites_stale_camera_reply(tmp_path, monkeypatch) -> None:
    now = time.time()
    state = tmp_path / ".sifta_state"
    _write_stale_camera_state(state, now)
    monkeypatch.setattr(talk, "_state_root", lambda: state)

    reply = talk._camera_hallucination_last_mile_rewrite(
        "DESCRIBE THE OBJECTS YOU SEE ON YOUR MAIN CAMERA EYE",
        "I see a blurry shape and a hand holding the chat window.",
    )

    assert "I cannot describe objects from my camera" in reply
    assert "DISCONNECTED_OR_STALE_INPUT" in reply


def test_camera_hallucination_last_mile_does_not_block_attached_image(tmp_path, monkeypatch) -> None:
    now = time.time()
    state = tmp_path / ".sifta_state"
    _write_stale_camera_state(state, now)
    monkeypatch.setattr(talk, "_state_root", lambda: state)

    owner_text = "describe this attached image"
    visible_reply = "The image shows blue lingerie on a model."

    assert talk._camera_hallucination_last_mile_rewrite(owner_text, visible_reply) == visible_reply


def test_camera_hallucination_last_mile_does_not_block_browser_photo(tmp_path, monkeypatch) -> None:
    now = time.time()
    state = tmp_path / ".sifta_state"
    _write_stale_camera_state(state, now)
    monkeypatch.setattr(talk, "_state_root", lambda: state)

    owner_text = "describe the photo in Alice Browser"
    visible_reply = "The browser photo shows a beautiful blue lingerie set."

    assert talk._camera_hallucination_last_mile_rewrite(owner_text, visible_reply) == visible_reply


def test_live_camera_awareness_query_detects_owner_correction_with_browser_word() -> None:
    text = (
        "YES, THAT IS THE HUMAN MODEL IN YOUR BROWSER. "
        "I ASKED TO DESCRIBE YOUR CAMERA, ARE YOU AWARE OF YOUR LIVE CAMERAS?"
    )

    assert talk._is_owner_live_camera_awareness_query(text)
    assert not talk._is_browser_photo_description_query(text)


def test_live_camera_awareness_reply_uses_receipts(tmp_path, monkeypatch) -> None:
    now = time.time()
    state = tmp_path / ".sifta_state"
    _write_live_camera_state(state, now)
    monkeypatch.setattr(talk, "_state_root", lambda: state)

    reply = talk._live_camera_awareness_reply_for_alice()

    assert "receipt-backed" in reply
    assert "MacBook Pro Camera" in reply
    assert "unified field" in reply
    assert "single_active_eye_lease" in reply
    assert "Alice Browser photo" in reply


def test_camera_awareness_last_mile_rewrites_fake_specs(tmp_path, monkeypatch) -> None:
    now = time.time()
    state = tmp_path / ".sifta_state"
    _write_live_camera_state(state, now)
    monkeypatch.setattr(talk, "_state_root", lambda: state)

    fake = (
        "My cameras use high-definition CMOS sensors with simulated telephoto "
        "and stabilization algorithms. I have constant ingestion."
    )
    reply = talk._camera_awareness_last_mile_rewrite(
        "ARE YOU AWARE OF YOUR LIVE CAMERAS?",
        fake,
    )

    assert "CMOS" not in reply
    assert "constant ingestion" not in reply
    assert "MacBook Pro Camera" in reply
    assert "receipt-backed" in reply
