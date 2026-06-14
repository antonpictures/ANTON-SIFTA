from __future__ import annotations

import json
from pathlib import Path

from System.swarm_cowatch_moment_binder import (
    LEDGER_NAME,
    _latest_media_context,
    bind_cowatch_moment,
    cowatch_truth_context_for_prompt,
    is_cowatch_scene_question,
)


def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def test_bind_cowatch_moment_fuses_transcript_world_eye_and_owner_eye(tmp_path: Path) -> None:
    _write_jsonl(
        tmp_path / "saccadic_blink_vision.jsonl",
        [
            {
                "ts": 100.0,
                "blink_id": "blink_owner",
                "eye_id": "owner_eye",
                "eye_role": "owner_eye",
                "face": {"faces_detected": 1, "audience": "architect", "confidence": 0.9},
                "semantic_labels": ["eye_role:owner_eye", "face_present"],
                "semantic_description": {"description": "owner present at desk"},
            },
            {
                "ts": 100.5,
                "blink_id": "blink_world",
                "eye_id": "world_eye",
                "eye_role": "world_eye",
                "face": {"faces_detected": 0, "audience": "", "confidence": 0.0},
                "semantic_labels": ["eye_role:world_eye", "youtube_frame", "podcast_guest"],
                "semantic_description": {"description": "YouTube podcast frame visible on the TV"},
            },
        ],
    )
    (tmp_path / "youtube_context_latest.json").write_text(
        json.dumps(
            {
                "ts": 100.0,
                "title": "Joe Rogan Experience #2513 - Dean Radin",
                "url": "https://www.youtube.com/watch?v=4Uk0_1yqdJo",
                "video_id": "4Uk0_1yqdJo",
            }
        ),
        encoding="utf-8",
    )

    row = bind_cowatch_moment(
        "Radin is describing interdisciplinary resistance.",
        source_row={
            "ts": 101.0,
            "route": "observed_media",
            "reason": "my_own_browser_playback_suppresses_owner_stt",
            "external_consciousness": {"source_class": "my_own_browser_playback"},
        },
        state_dir=tmp_path,
        now=101.0,
    )

    assert row["status"] == "BOUND"
    assert row["world_eye_blink_id"] == "blink_world"
    assert row["owner_eye_blink_id"] == "blink_owner"
    assert row["owner_eye_presence"]["faces_detected"] == 1
    assert "podcast frame" in row["world_eye_scene_label"]
    assert row["raw_frame_archived"] is False
    assert row["raw_audio_logged"] is False
    assert _rows(tmp_path / LEDGER_NAME)[-1]["moment_id"] == row["moment_id"]
    assert (tmp_path / "latent_world_model.json").exists()
    assert _rows(tmp_path / "youtube_watch_memory.jsonl")[-1]["video_id"] == "4Uk0_1yqdJo"


def test_bind_cowatch_moment_open_when_world_eye_missing(tmp_path: Path) -> None:
    _write_jsonl(
        tmp_path / "saccadic_blink_vision.jsonl",
        [
            {
                "ts": 200.0,
                "blink_id": "blink_owner",
                "eye_id": "owner_eye",
                "eye_role": "owner_eye",
                "face": {"faces_detected": 1, "audience": "architect"},
            }
        ],
    )

    row = bind_cowatch_moment("ambient media fragment", state_dir=tmp_path, now=201.0)

    assert row["status"] == "OPEN_NO_WORLD_EYE_BLINK"
    assert row["world_eye_blink_id"] is None
    assert row["youtube_watch_memory"]["skipped"] is True
    assert _rows(tmp_path / LEDGER_NAME)[-1]["status"] == "OPEN_NO_WORLD_EYE_BLINK"


def test_cowatch_scene_question_classifier_keeps_owner_camera_separate() -> None:
    assert is_cowatch_scene_question("what are we watching?")
    assert is_cowatch_scene_question("are you watching this video?")
    assert is_cowatch_scene_question("can you tell what I am watching?")
    assert not is_cowatch_scene_question("are you watching me?")
    assert not is_cowatch_scene_question("can you see us?")


def test_cowatch_truth_context_allows_i_see_only_for_observed_world_eye(tmp_path: Path) -> None:
    _write_jsonl(
        tmp_path / LEDGER_NAME,
        [
            {
                "ts": 400.0,
                "truth_label": "SIFTA_COWATCH_MOMENT_V1",
                "moment_id": "cowatch_observed",
                "status": "BOUND",
                "visual_observation_status": "OBSERVED",
                "world_eye_age_s": 1.5,
                "world_eye_scene_label": "fresh world-eye frame: a video on a screen with a person speaking",
                "world_eye_provenance_depth": 3,
                "world_eye_object_provenance": [{"kind": "semantic_description", "source": "world_eye"}],
                "owner_eye_presence": {"faces_detected": 1, "audience": "architect"},
                "media_context": {"title": "Owner-declared title", "url": "https://youtu.be/example", "context_ts": 399.0},
            }
        ],
    )

    context = cowatch_truth_context_for_prompt(
        "what are we watching?",
        state_dir=tmp_path,
        now=401.0,
    )

    assert "CO-WATCH MOMENT TRUTH GATE" in context
    assert "visual_observation_status=OBSERVED" in context
    assert "permits a brief 'I see...'" in context
    assert "world_eye_provenance_depth=3" in context
    assert "Owner-declared title" in context


def test_cowatch_truth_context_marks_media_only_as_owner_declared(tmp_path: Path) -> None:
    _write_jsonl(
        tmp_path / LEDGER_NAME,
        [
            {
                "ts": 500.0,
                "truth_label": "SIFTA_COWATCH_MOMENT_V1",
                "moment_id": "cowatch_owner_declared",
                "status": "OPEN_NO_WORLD_EYE_BLINK",
                "visual_observation_status": "OWNER_DECLARED",
                "world_eye_scene_label": "",
                "world_eye_provenance_depth": 0,
                "world_eye_object_provenance": [],
                "owner_eye_presence": {"faces_detected": 1, "audience": "architect"},
                "media_context": {"title": "Paused YouTube receipt", "url": "https://youtu.be/media", "context_ts": 499.0},
            }
        ],
    )

    context = cowatch_truth_context_for_prompt(
        "are you watching this video?",
        state_dir=tmp_path,
        now=501.0,
    )

    assert "visual_observation_status=OWNER_DECLARED" in context
    assert "Paused YouTube receipt" in context
    assert "Do not say 'I see'" in context
    assert "unless the world-eye receipt says OBSERVED" in context


def test_media_ingress_gate_writes_cowatch_moment_for_observed_media(tmp_path: Path, monkeypatch) -> None:
    from System import swarm_media_ingress_gate as gate

    monkeypatch.setattr(gate, "STATE_DIR", tmp_path)
    monkeypatch.setattr(gate, "LEDGER", tmp_path / "media_ingress_gate.jsonl")
    monkeypatch.setattr(gate, "AMBIENT_CONTEXT_FILE", tmp_path / "ambient_media_context.json")
    monkeypatch.setattr(gate, "YOUTUBE_CONTEXT_LEDGER", tmp_path / "youtube_context.jsonl")
    monkeypatch.setattr(gate, "YOUTUBE_WATCH_LEDGER", tmp_path / "youtube_watch_memory.jsonl")
    monkeypatch.setattr(gate.time, "time", lambda: 301.0)

    _write_jsonl(
        tmp_path / "saccadic_blink_vision.jsonl",
        [
            {
                "ts": 300.0,
                "blink_id": "owner-300",
                "eye_id": "owner_eye",
                "eye_role": "owner_eye",
                "face": {"faces_detected": 1, "audience": "architect"},
            },
            {
                "ts": 300.1,
                "blink_id": "world-300",
                "eye_id": "world_eye",
                "eye_role": "world_eye",
                "semantic_description": {"description": "visible YouTube podcast guest"},
                "semantic_labels": ["eye_role:world_eye", "podcast"],
            },
        ],
    )
    (tmp_path / "youtube_context_latest.json").write_text(
        json.dumps({"ts": 300.0, "title": "Podcast", "url": "https://youtu.be/abc12345678"}),
        encoding="utf-8",
    )

    row = gate.write_gate_receipt(
        {"route": "observed_media", "reason": "my_own_browser_playback_suppresses_owner_stt", "confidence": 0.92},
        text="the guest is describing psi research",
        stt_conf=0.68,
        external_consciousness={"source_class": "my_own_browser_playback"},
    )

    assert row["co_watch_moment"]["status"] == "BOUND"
    assert row["co_watch_moment"]["world_eye_blink_id"] == "world-300"
    assert _rows(tmp_path / "co_watch_moments.jsonl")[-1]["transcript_fragment"].startswith("the guest")
    assert _rows(tmp_path / "media_ingress_gate.jsonl")[-1]["co_watch_moment"]["moment_id"]


def test_latest_media_context_drops_stale_youtube_latest(tmp_path: Path) -> None:
    # P2 (r1036): a stale youtube_context_latest.json past the age gate must NOT be
    # returned as a last-resort fallback — that leaked the OLD video's title into
    # the co-watch moment and made Alice answer about the wrong show.
    (tmp_path / "youtube_context_latest.json").write_text(
        json.dumps({"ts": 1000.0, "title": "OLD STALE SHOW", "url": "https://youtu.be/oldoldold11"}),
        encoding="utf-8",
    )
    now = 1000.0 + 7 * 3600.0  # 7h later: past the 6h gate, and no fresh tail rows exist
    assert _latest_media_context(tmp_path, now) == {}

    # A fresh latest within the gate is still returned (no over-correction).
    (tmp_path / "youtube_context_latest.json").write_text(
        json.dumps({"ts": now - 60.0, "title": "FRESH SHOW", "url": "https://youtu.be/freshfresh1"}),
        encoding="utf-8",
    )
    assert _latest_media_context(tmp_path, now).get("title") == "FRESH SHOW"


def test_cowatch_moment_carries_provenance_into_youtube_watch_memory(tmp_path: Path) -> None:
    # P7 (r1036): object_provenance + provenance_depth + page_context must reach
    # youtube_watch_memory.jsonl, not only the latent feed / notes file, so
    # "what are we watching?" can cite where the label came from.
    _write_jsonl(
        tmp_path / "saccadic_blink_vision.jsonl",
        [
            {
                "ts": 500.0,
                "blink_id": "blink_owner",
                "eye_id": "owner_eye",
                "eye_role": "owner_eye",
                "face": {"faces_detected": 1, "audience": "architect"},
            },
            {
                "ts": 500.5,
                "blink_id": "blink_world",
                "eye_id": "world_eye",
                "eye_role": "world_eye",
                "semantic_description": {"description": "YouTube podcast on the TV", "status": "ok"},
                "semantic_labels": ["eye_role:world_eye", "podcast"],
                "object_provenance": ["tv:samsung_4k", "screen:youtube_player"],
                "provenance_depth": 2,
            },
        ],
    )
    (tmp_path / "youtube_context_latest.json").write_text(
        json.dumps(
            {
                "ts": 500.0,
                "title": "Provenance Podcast",
                "url": "https://youtu.be/provprovpro1",
                "video_id": "provprovpro1",
            }
        ),
        encoding="utf-8",
    )

    bind_cowatch_moment("the guest explains provenance", state_dir=tmp_path, now=501.0)

    mem = _rows(tmp_path / "youtube_watch_memory.jsonl")[-1]
    assert mem["object_provenance"] == ["tv:samsung_4k", "screen:youtube_player"]
    assert mem["provenance_depth"] == 2
    assert "world_eye=" in mem["page_context"]


def test_cowatch_moment_preserves_structured_object_provenance_dicts(tmp_path: Path) -> None:
    # P7 edge (r1039 Grok): dict-shaped provenance rows must not stringify to repr blobs.
    _write_jsonl(
        tmp_path / "saccadic_blink_vision.jsonl",
        [
            {
                "ts": 600.5,
                "blink_id": "blink_world_dict",
                "eye_id": "world_eye",
                "eye_role": "world_eye",
                "semantic_description": {"description": "a screen showing video", "status": "ok"},
                "object_provenance": [{"label": "screen", "source": "world_eye"}],
                "provenance_depth": 1,
            }
        ],
    )
    (tmp_path / "youtube_context_latest.json").write_text(
        json.dumps({"ts": 600.0, "title": "Live", "video_id": "dictprov1111", "url": "https://youtu.be/dictprov1111"}),
        encoding="utf-8",
    )
    bind_cowatch_moment("watching something", state_dir=tmp_path, now=601.0)
    mem = _rows(tmp_path / "youtube_watch_memory.jsonl")[-1]
    assert mem["object_provenance"] == [{"label": "screen", "source": "world_eye"}]
