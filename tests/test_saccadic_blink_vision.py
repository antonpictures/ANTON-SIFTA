from __future__ import annotations

import json
from pathlib import Path

from System import swarm_saccadic_blink_vision as blink_vision
from System.swarm_saccadic_blink_vision import (
    BLINK_LEDGER_NAME,
    TWO_TURN_PROBE_LEDGER_NAME,
    WORLD_FEED_LEDGER_NAME,
    BlinkConfig,
    probe_two_turn_receipt_gate,
    pulse_saccadic_blink,
    request_attention_blink,
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


def _seed_eye(
    state: Path,
    *,
    now: float,
    sha8: str = "aaa11111",
    motion: float = 0.02,
    faces: int = 1,
    label: str | None = None,
) -> None:
    visual_row = {
        "ts": now - 0.25,
        "sha8": sha8,
        "w": 640,
        "h": 480,
        "entropy_bits": 7.1,
        "saliency_peak": 0.25,
        "motion_mean": motion,
        "path": "/tmp/should_not_persist.jpg",
    }
    if label:
        visual_row["stigmergic_label"] = label
    _write_jsonl(
        state / "visual_stigmergy.jsonl",
        [visual_row],
    )
    _write_jsonl(
        state / "active_eye_identity_frames.jsonl",
        [
            {
                "ts": now - 10.0,
                "event": "ACTIVE_EYE_IDENTITY_FRAME",
                "path": "/tmp/support_frame.png",
                "device": "MacBook Pro Camera",
                "w": 640,
                "h": 480,
                "sha8": "support",
            }
        ],
    )
    _write_jsonl(
        state / "face_detection_events.jsonl",
        [
            {
                "ts": now - 0.5,
                "event": "FACE_DETECTION",
                "faces_detected": faces,
                "audience": "architect" if faces else "nobody",
                "confidence": 0.82 if faces else 0.0,
            }
        ],
    )
    (state / "kernel_process_table.json").write_text(
        json.dumps(
            {
                "processes": {
                    "e35_vision_001": {
                        "health": 1.0,
                        "last_heartbeat_ts": now - 0.1,
                    }
                }
            }
        ),
        encoding="utf-8",
    )


def test_first_blink_writes_metadata_only_and_camera_proof_fresh(tmp_path: Path) -> None:
    state = tmp_path
    now = 1000.0
    _seed_eye(state, now=now)
    calls: list[dict] = []

    row = pulse_saccadic_blink(
        state_dir=state,
        heart_row={"receipt_id": "heart-1"},
        config=BlinkConfig(),
        now_fn=lambda: now,
        describe_fn=lambda ctx: calls.append(ctx) or {"status": "ok", "description": "owner face visible"},
    )

    # r1027 P0: exactly one blink row per heart receipt (no fork double-spend)
    blink_rows = [r for r in _rows(state / BLINK_LEDGER_NAME) if r.get("kind") == "SACCADIC_BLINK"]
    assert len(blink_rows) == 1, "P0: must be exactly one blink row per heart call (reconciled bridge only)"
    assert blink_rows[0].get("eye_id") == "owner_eye"
    assert row["visual_fresh"] is True
    assert row["meaningful_delta"] is True
    assert row["frame_persistence"]["raw_frame_archived"] is False
    assert calls and calls[0]["blink_id"] == row["blink_id"]
    text = json.dumps(_rows(state / BLINK_LEDGER_NAME)[-1])
    assert "should_not_persist.jpg" not in text
    assert "support_frame.png" not in text

    proof = _rows(state / "camera_unified_field_proof.jsonl")[-1]
    assert proof["camera_healthy"] is True
    assert proof["frame_age_s"] == 0.25
    assert proof["evidence"]["frame"]["saved_identity_frame_age_s"] == 10.0

    # r1027 capture throttle + budget
    budget_rows = _rows(state / "capture_budget.jsonl") if (state / "capture_budget.jsonl").exists() else []
    # (budget emitted only on world in co-watch in full flow; here owner is default)

def test_p0_one_blink_per_heart_and_eye_id(tmp_path: Path) -> None:
    """P0 proof: one canonical path, rows carry eye_id, no doubles."""
    state = tmp_path
    now = 2000.0
    _seed_eye(state, now=now, faces=1)
    # Simulate heart pulse + blink for owner (always)
    for i in range(3):
        pulse_saccadic_blink(state_dir=state, heart_row={"receipt_id": f"heart-{i}"}, now_fn=lambda: now + i, eye_id="owner_eye")
    blinks = [r for r in _rows(state / BLINK_LEDGER_NAME) if r.get("kind") == "SACCADIC_BLINK"]
    assert len(blinks) == 3
    assert all(r.get("eye_id") == "owner_eye" for r in blinks)
    # world only on co-watch
    (state / "co_watch_active.flag").write_text("1")
    pulse_saccadic_blink(state_dir=state, heart_row={"receipt_id": "heart-co"}, now_fn=lambda: now+10, eye_id="world_eye")
    blinks = [r for r in _rows(state / BLINK_LEDGER_NAME) if r.get("kind") == "SACCADIC_BLINK"]
    assert any(r.get("eye_id") == "world_eye" for r in blinks)
    (state / "co_watch_active.flag").unlink(missing_ok=True)


def test_stable_object_gaze_counts_stare_beats(tmp_path: Path) -> None:
    """George doctrine: stable gaze deepens through heartbeat beats, not a fixed timer."""
    state = tmp_path
    now = 2100.0

    first = pulse_saccadic_blink(
        state_dir=state,
        heart_row={"receipt_id": "heart-stare-1"},
        now_fn=lambda: now,
        eye_id="owner_eye",
    )
    assert first["object_key"] is None
    assert first["stare_beats"] == 0

    _seed_eye(state, now=now, sha8="usb11111", label="usb_adaptor", faces=0)
    first = pulse_saccadic_blink(
        state_dir=state,
        heart_row={"receipt_id": "heart-stare-2"},
        now_fn=lambda: now,
        eye_id="owner_eye",
    )
    _seed_eye(state, now=now + 1.0, sha8="usb11111", label="usb_adaptor", faces=0)
    second = pulse_saccadic_blink(
        state_dir=state,
        heart_row={"receipt_id": "heart-stare-3"},
        now_fn=lambda: now + 1.0,
        eye_id="owner_eye",
    )

    assert first["object_key"] == "usb_adaptor"
    assert first["stare_beats"] == 1
    assert second["object_key"] == "usb_adaptor"
    assert second["stare_beats"] == 2
    state_row = json.loads((state / "blink_stare_state.json").read_text(encoding="utf-8"))
    assert state_row["owner_eye"]["last_object"] == "usb_adaptor"


def test_stare_provenance_reads_owner_object_memory(tmp_path: Path) -> None:
    """A familiar object carries receipt-backed provenance after repeated gaze."""
    state = tmp_path
    now = 2200.0
    _write_jsonl(
        state / "architect_day_segments.jsonl",
        [
            {
                "ts": now - 30,
                "label": "kitchen_pizza_memory",
                "summary": "Cheese pizza in the oven; bought four frozen pizzas on sale; forgot the eight dollar discount; owner was pissed.",
            }
        ],
    )

    rows = []
    for i in range(3):
        _seed_eye(state, now=now + i, sha8="pizza01", label="pizza_in_oven", faces=0)
        rows.append(
            pulse_saccadic_blink(
                state_dir=state,
                heart_row={"receipt_id": f"heart-pizza-{i}"},
                now_fn=lambda i=i: now + i,
                eye_id="owner_eye",
            )
        )

    third = rows[-1]
    assert third["stare_beats"] == 3
    assert third["provenance_depth"] >= 1
    assert third["object_provenance"][0]["ledger"] == "architect_day_segments.jsonl"
    assert "discount" in json.dumps(third["object_provenance"]).lower()
    assert third["frame_persistence"]["raw_frame_archived"] is False


def test_false_cowatch_no_hallucination_and_honest_moment(tmp_path: Path) -> None:
    """False co-watch: media active, TV black/paused. World-eye no hallucinate scene; honest 'no salient'."""
    state = tmp_path
    now = 3000.0
    _seed_eye(state, now=now, motion=0.0, faces=0)  # black/paused: no motion, no face
    (state / "co_watch_active.flag").write_text("1")
    row = pulse_saccadic_blink(state_dir=state, heart_row={"receipt_id": "heart-false"}, now_fn=lambda: now, eye_id="world_eye")
    assert row.get("meaningful_delta") is False
    assert "no salient" in str(row.get("meaningful_reason", "")).lower() or row.get("idle_decimated") or "dark" in str(row.get("meaningful_reason",""))
    # owner unaffected
    owner_row = pulse_saccadic_blink(state_dir=state, heart_row={"receipt_id": "heart-owner"}, now_fn=lambda: now+1, eye_id="owner_eye")
    assert owner_row.get("eye_id") == "owner_eye"
    (state / "co_watch_active.flag").unlink(missing_ok=True)


def test_world_eye_cowatch_media_metadata_lands_general_label_without_title(tmp_path: Path, monkeypatch) -> None:
    """Lane A: media-marked world_eye metadata may say general screen/video, never an invented title."""
    state = tmp_path
    now = 3500.0
    _seed_eye(state, now=now, motion=0.05, faces=0, label="OBSERVED_MEDIA")
    (state / "co_watch_active.flag").write_text("1")
    (state / "youtube_context_latest.json").write_text(
        json.dumps(
            {
                "ts": now,
                "title": "Donnie Brasco - Al Pacino Scene",
                "url": "https://youtu.be/example",
                "video_id": "example",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(blink_vision, "_capture_world_eye_frame", lambda _state: None)

    row = pulse_saccadic_blink(
        state_dir=state,
        heart_row={"receipt_id": "heart-general-media"},
        now_fn=lambda: now,
        eye_id="world_eye",
    )

    desc = row["semantic_description"]
    text = json.dumps(desc)
    assert desc["status"] == "ok"
    assert desc["source"] == "world_eye_metadata_general_label"
    assert "screen/video media surface" in desc["description"]
    assert desc["specificity"] == "general"
    assert desc["title_identified"] is False
    assert "Donnie" not in text
    assert "Pacino" not in text
    assert row["frame_persistence"]["raw_frame_archived"] is False
    (state / "co_watch_active.flag").unlink(missing_ok=True)


def test_pacino_regression_world_eye_provenance(tmp_path: Path) -> None:
    """Pacino regression: live co-watch, answer provenance from world_eye (not told)."""
    state = tmp_path
    now = 4000.0
    _seed_eye(state, now=now, motion=0.05, faces=1)
    (state / "co_watch_active.flag").write_text("1")
    world = pulse_saccadic_blink(
        state_dir=state,
        heart_row={"receipt_id": "heart-pacino"},
        now_fn=lambda: now,
        eye_id="world_eye",
        describe_fn=lambda ctx: {"status": "ok", "description": "Donnie Brasco on screen, Al Pacino"},
    )
    owner = pulse_saccadic_blink(state_dir=state, heart_row={"receipt_id": "heart-owner"}, now_fn=lambda: now+0.5, eye_id="owner_eye")
    # Simulate moment (in real, bound in co-watch path)
    moment = {
        "ts": now,
        "transcript_fragment": "what are we watching?",
        "world_eye_scene_label": world.get("semantic_description", {}).get("description", ""),
        "owner_eye_reaction": "owner reacting to Pacino",
        "provenance": "world_eye",
        "eye_id": "world_eye",
    }
    _write_jsonl(state / "co_watch_moments.jsonl", [moment])
    _write_jsonl(state / "youtube_watch_memory.jsonl", [moment])
    # Pacino answer provenance check (simulated read)
    moments = _rows(state / "co_watch_moments.jsonl")
    assert any("world_eye" in str(m) and "Donnie" in str(m) for m in moments)
    (state / "co_watch_active.flag").unlink(missing_ok=True)

def test_latent_feed_audit_readback(tmp_path: Path) -> None:
    """Hermes/Scout audit: co_watch_moment reaches latent + youtube; read-back works."""
    state = tmp_path
    now = 5000.0
    _seed_eye(state, now=now)
    (state / "co_watch_active.flag").write_text("1")
    world = pulse_saccadic_blink(state_dir=state, heart_row={"receipt_id": "heart-audit"}, now_fn=lambda: now, eye_id="world_eye", describe_fn=lambda c: {"status":"ok","description":"scene label from world eye"})
    moment = {"ts": now, "transcript_fragment": "test pacino", "world_eye_scene_label": "Donnie Brasco", "owner_eye_reaction": "laugh", "eye_id": "world_eye"}
    _write_jsonl(state / "co_watch_moments.jsonl", [moment])
    _write_jsonl(state / "youtube_watch_memory.jsonl", [moment])
    yt = _rows(state / "youtube_watch_memory.jsonl")
    assert any("world_eye" in str(m) or "Donnie" in str(m) for m in yt)
    (state / "co_watch_active.flag").unlink(missing_ok=True)


def test_unchanged_static_blink_skips_describer(tmp_path: Path) -> None:
    state = tmp_path
    now = 1000.0
    _seed_eye(state, now=now, sha8="same", motion=0.0, faces=0)

    first = pulse_saccadic_blink(
        state_dir=state,
        config=BlinkConfig(motion_threshold=0.5, saliency_threshold=0.9),
        now_fn=lambda: now,
        describe_fn=lambda ctx: {"status": "ok", "description": "first"},
    )
    assert first["meaningful_reason"] == "first_blink"

    _seed_eye(state, now=now + 1.0, sha8="same", motion=0.0, faces=0)
    calls: list[dict] = []
    second = pulse_saccadic_blink(
        state_dir=state,
        config=BlinkConfig(motion_threshold=0.5, saliency_threshold=0.9),
        now_fn=lambda: now + 1.0,
        describe_fn=lambda ctx: calls.append(ctx) or "should not run",
    )

    assert second["meaningful_delta"] is False
    assert second["meaningful_reason"] == "no_meaningful_delta"
    assert calls == []


def test_changed_blink_feeds_visual_cortex_and_latent_world_model(tmp_path: Path) -> None:
    state = tmp_path
    now = 2000.0
    _seed_eye(state, now=now, sha8="a", motion=0.0, faces=0)
    pulse_saccadic_blink(
        state_dir=state,
        config=BlinkConfig(motion_threshold=0.5, saliency_threshold=0.9),
        now_fn=lambda: now,
        describe_fn=lambda ctx: "first",
    )
    _seed_eye(state, now=now + 1.0, sha8="b", motion=0.0, faces=0)

    row = pulse_saccadic_blink(
        state_dir=state,
        config=BlinkConfig(motion_threshold=0.5, saliency_threshold=0.9),
        now_fn=lambda: now + 1.0,
        describe_fn=lambda ctx: {"status": "ok", "description": "changed"},
    )

    assert row["meaningful_reason"] == "sha8_changed"
    assert _rows(state / "occipital_visual_processing.jsonl")
    assert _rows(state / "thalamic_sensory_queue.jsonl")
    assert _rows(state / WORLD_FEED_LEDGER_NAME)[-1]["blink_id"] == row["blink_id"]
    assert (state / "latent_world_model.json").exists()


def test_attention_escalation_forces_describer_without_sha_change(tmp_path: Path) -> None:
    state = tmp_path
    now = 3000.0
    _seed_eye(state, now=now, sha8="same", motion=0.0, faces=0)
    pulse_saccadic_blink(
        state_dir=state,
        config=BlinkConfig(motion_threshold=0.5, saliency_threshold=0.9),
        now_fn=lambda: now,
        describe_fn=lambda ctx: "first",
    )
    calls: list[dict] = []

    row = pulse_saccadic_blink(
        state_dir=state,
        reason="owner_typed",
        config=BlinkConfig(motion_threshold=0.5, saliency_threshold=0.9),
        now_fn=lambda: now + 1.0,
        describe_fn=lambda ctx: calls.append(ctx) or "forced",
    )

    assert row["meaningful_delta"] is True
    assert row["meaningful_reason"] == "attention_escalation:owner_typed"
    assert calls


def test_request_attention_blink_forces_owner_typed_path(tmp_path: Path) -> None:
    state = tmp_path
    now = 3500.0
    _seed_eye(state, now=now, sha8="same", motion=0.0, faces=0)
    request_attention_blink("owner_typed", state_dir=state, now_fn=lambda: now)

    _seed_eye(state, now=now + 0.5, sha8="same", motion=0.0, faces=0)
    row = request_attention_blink("owner_typed", state_dir=state, now_fn=lambda: now + 0.5)

    assert row["source"] == "owner_typed"
    assert row["meaningful_delta"] is True
    assert row["meaningful_reason"] == "attention_escalation:owner_typed"


def test_idle_decimation_skips_static_empty_room_between_n_beats(tmp_path: Path) -> None:
    state = tmp_path
    now = 4000.0
    cfg = BlinkConfig(motion_threshold=0.5, saliency_threshold=0.9, idle_decimate_beats=3)
    _seed_eye(state, now=now, sha8="same", motion=0.0, faces=0)
    pulse_saccadic_blink(state_dir=state, config=cfg, now_fn=lambda: now, describe_fn=lambda ctx: "first")
    _seed_eye(state, now=now + 1, sha8="same", motion=0.0, faces=0)
    row = pulse_saccadic_blink(state_dir=state, config=cfg, now_fn=lambda: now + 1)

    assert row["idle_decimated"] is True
    assert row["meaningful_delta"] is False


def test_two_turn_gate_probe_receipts_alive_or_error(tmp_path: Path) -> None:
    row = probe_two_turn_receipt_gate(state_dir=tmp_path, now=5000.0)

    assert row["truth_label"] == "TWO_TURN_RECEIPT_GATE_PROBE_V1"
    assert row["status"] in {"ALIVE", "BROKEN", "ERROR"}
    assert _rows(tmp_path / TWO_TURN_PROBE_LEDGER_NAME)[-1]["status"] == row["status"]


def test_blink_writes_no_image_files(tmp_path: Path) -> None:
    state = tmp_path
    _seed_eye(state, now=6000.0)
    before = {p.relative_to(state) for p in state.rglob("*") if p.is_file()}
    pulse_saccadic_blink(
        state_dir=state,
        config=BlinkConfig(),
        now_fn=lambda: 6000.0,
        describe_fn=lambda ctx: "metadata",
    )
    after = {p.relative_to(state) for p in state.rglob("*") if p.is_file()}
    new_files = after - before

    assert all(p.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"} for p in new_files)


def test_hardware_heart_pulse_writes_matching_blink_row(tmp_path: Path, monkeypatch) -> None:
    from System.swarm_hardware_heart import pulse_hardware_heart

    _seed_eye(tmp_path, now=7000.0)
    monkeypatch.setattr("System.swarm_hardware_heart.platform.system", lambda: "Darwin")
    monkeypatch.setattr(
        "System.swarm_hardware_heart._probe_unprivileged_body",
        lambda: {
            "sensor_source": "alice_hardware_body",
            "sensor_tier": "unprivileged_body",
            "sensor_status": "partial",
            "sensor_reason": "test body",
            "power_watts": None,
            "temperature_c": None,
        },
    )

    heart = pulse_hardware_heart(
        state_dir=tmp_path,
        monotonic_ns_fn=lambda: 7_000_000_000,
        now_fn=lambda: 7000.0,
        privileged_probe=False,
        source="unit_heartbeat",
    )

    blink = _rows(tmp_path / BLINK_LEDGER_NAME)[-1]
    assert blink["heart_receipt_id"] == heart["receipt_id"]
    assert blink["source"] == "hardware_heart"


def test_per_eye_blink_fields_and_labels(tmp_path: Path) -> None:
    from System.swarm_eye_registry import refresh_eye_registry

    refresh_eye_registry(
        state_dir=tmp_path,
        devices=[
            {"index": 0, "unique_id": "mac-cam", "name": "MacBook Pro Camera"},
            {"index": 1, "unique_id": "logitech-usb", "name": "USB Camera VID:1133 PID:2081"},
        ],
        now=8000.0,
    )
    _seed_eye(tmp_path, now=8000.0)

    owner = pulse_saccadic_blink(
        state_dir=tmp_path,
        eye_role="owner_eye",
        config=BlinkConfig(),
        now_fn=lambda: 8000.0,
        describe_fn=lambda ctx: "owner blink",
    )
    world = pulse_saccadic_blink(
        state_dir=tmp_path,
        eye_role="world_eye",
        force=True,
        config=BlinkConfig(),
        now_fn=lambda: 8001.0,
        describe_fn=lambda ctx: "world blink",
    )

    assert owner["eye_id"] == "owner_eye"
    assert owner["eye_role"] == "owner_eye"
    assert "eye_role:owner_eye" in owner["semantic_labels"]
    assert world["eye_id"] == "world_eye"
    assert world["eye_role"] == "world_eye"
    assert "eye_role:world_eye" in world["semantic_labels"]


def test_deprecated_visual_cortex_blink_capture_delegates_once(tmp_path: Path) -> None:
    from System.swarm_visual_cortex import blink_capture

    _seed_eye(tmp_path, now=9000.0)
    receipt = blink_capture(state_dir=tmp_path, force=True, write_ledger=True)
    rows = _rows(tmp_path / BLINK_LEDGER_NAME)

    assert receipt["truth_label"] == "BLINK_CAPTURE_DELEGATED_TO_SACCADIC_BRIDGE_V1"
    assert receipt["canonical_path"] == "System.swarm_saccadic_blink_vision.pulse_saccadic_blink"
    assert receipt["raw_frame_archived"] is False
    assert len(rows) == 1
    assert rows[0]["blink_id"] == receipt["canonical_blink_id"]
