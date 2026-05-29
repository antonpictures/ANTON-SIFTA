"""Round 114 §2.G.1 — tests for camera → somatic-state wiring.

Proves the physical_capture_daemon now feeds update_from_frame on each
face detection event, so the camera lane reaches Alice's somatic field
ledger instead of stopping at face_detection_events.jsonl.

Pure stdlib, no live camera, no OpenCV at test time.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch


def test_update_from_frame_writes_somatic_row_with_architect_present(monkeypatch, tmp_path: Path) -> None:
    from System import swarm_owner_somatic_state as somatic

    monkeypatch.setattr(somatic, "_STATE", tmp_path)
    monkeypatch.setattr(somatic, "_SOMATIC_LEDGER", tmp_path / "owner_somatic_state.jsonl")

    out = somatic.update_from_frame(
        {
            "faces_detected": 1,
            "confidence": 0.9,
            "movement": "steady",
            "posture_hint": "architect_present",
        },
        camera_id="physical_capture_daemon:idx=0",
    )
    assert out["ok"] is True
    ledger = tmp_path / "owner_somatic_state.jsonl"
    assert ledger.exists()
    rows = [json.loads(line) for line in ledger.read_text().splitlines() if line.strip()]
    assert len(rows) == 1
    row = rows[0]
    assert row["source"] == "camera_v2"
    assert row["camera_id"] == "physical_capture_daemon:idx=0"
    assert row["faces_detected"] == 1
    assert row["posture"] == "architect_present"


def test_update_from_frame_handles_nobody_in_view(monkeypatch, tmp_path: Path) -> None:
    from System import swarm_owner_somatic_state as somatic

    monkeypatch.setattr(somatic, "_STATE", tmp_path)
    monkeypatch.setattr(somatic, "_SOMATIC_LEDGER", tmp_path / "owner_somatic_state.jsonl")

    out = somatic.update_from_frame(
        {
            "faces_detected": 0,
            "confidence": 0.0,
            "movement": "steady",
            "posture_hint": "unknown",
        },
        camera_id="physical_capture_daemon:idx=0",
    )
    assert out["ok"] is True
    rows = [
        json.loads(line)
        for line in (tmp_path / "owner_somatic_state.jsonl").read_text().splitlines()
        if line.strip()
    ]
    # update_from_frame normalises faces==0 / conf<0.3 to energy=low and
    # a "not visible" posture (the module's actual normalisation token).
    assert rows[0]["posture"] in {"unknown", "not_visible"}
    assert rows[0]["energy_level"] == "low"


def test_daemon_module_imports_update_from_frame_at_event_time() -> None:
    """Static check: the daemon source contains the wired call to
    update_from_frame so a smoke regression catches future refactors that
    accidentally remove the somatic feed."""
    src = Path("System/swarm_physical_capture_daemon.py").read_text(encoding="utf-8")
    assert "from System.swarm_owner_somatic_state import update_from_frame" in src
    assert "physical_capture_daemon:idx=" in src
    # The call must live after _append_event so it never blocks face logging.
    append_idx = src.index("_append_event(event)")
    somatic_idx = src.index("_update_somatic_frame(")
    assert somatic_idx > append_idx, (
        "somatic update must come after face event append so face logging "
        "never depends on the somatic ledger being healthy"
    )


def test_daemon_somatic_call_is_inside_try_except() -> None:
    """The somatic update must never crash the camera daemon — even if the
    somatic module is missing or broken, the camera keeps emitting face
    events."""
    src = Path("System/swarm_physical_capture_daemon.py").read_text(encoding="utf-8")
    # Find the try/except block around the somatic call.
    call = "_update_somatic_frame("
    pos = src.index(call)
    head = src[max(0, pos - 600):pos]
    tail = src[pos:pos + 800]
    assert "try:" in head, "somatic call is not preceded by try:"
    assert "except Exception" in tail, (
        "somatic call is not guarded by except Exception"
    )
