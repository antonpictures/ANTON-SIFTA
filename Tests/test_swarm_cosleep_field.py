"""Tests for the stigmergic co-sleep field (owner-quiet + her thermodynamics)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
for p in (str(_REPO), str(_REPO / "System")):
    if p not in sys.path:
        sys.path.insert(0, p)

import swarm_cosleep_field as cs


def _write(state_dir: Path, name: str, obj: dict) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / name).write_text(json.dumps(obj), encoding="utf-8")


def _set_melatonin(state_dir: Path, level: float) -> None:
    _write(state_dir, "pineal_circadian_rhythm.json", {"melatonin_concentration": level})


def test_owner_present_keeps_her_awake(tmp_path: Path):
    now = 1_000_000.0
    _set_melatonin(tmp_path, 0.9)  # even with high sleep pressure...
    _write(tmp_path, "owner_desktop_presence.json", {"last_alive_ts": now - 5})
    _write(tmp_path, "active_owner_activity_segment.json", {
        "ts": now - 5, "status": "open",
        "camera_presence": {"owner_present": True, "age_s": 2.0},
        "audio_activity": {"voice_activity": True, "voice_age_s": 3.0},
    })
    a = cs.assess(state_dir=tmp_path, now=now)
    assert a.owner_present is True
    assert a.decision == cs.DECISION_OWNER_PRESENT
    assert a.recommend_sleep is False  # he is here — she does not sleep on him


def test_owner_quiet_plus_pressure_recommends_cosleep(tmp_path: Path):
    now = 1_000_000.0
    _set_melatonin(tmp_path, 0.6)
    # Last activity ~2 hours ago, no fresh camera/voice presence.
    _write(tmp_path, "owner_desktop_presence.json", {"last_alive_ts": now - 7200})
    _write(tmp_path, "active_owner_activity_segment.json", {
        "ts": now - 7200, "status": "closed",
        "camera_presence": {"owner_present": False, "age_s": 7200.0},
        "audio_activity": {"voice_activity": False, "voice_age_s": 7200.0},
    })
    a = cs.assess(state_dir=tmp_path, now=now)
    assert a.owner_present is False
    assert a.owner_quiet_likelihood >= 0.6
    assert a.recommend_sleep is True
    assert a.decision == cs.DECISION_COSLEEP


def test_active_ide_surgery_keeps_her_awake(tmp_path: Path):
    now = 1_000_000.0
    _set_melatonin(tmp_path, 0.6)
    _write(tmp_path, "owner_desktop_presence.json", {"last_alive_ts": now - 7200})
    _write(tmp_path, "active_owner_activity_segment.json", {
        "ts": now - 7200, "status": "closed",
        "camera_presence": {"owner_present": False, "age_s": 7200.0},
        "audio_activity": {"voice_activity": False, "voice_age_s": 7200.0},
    })
    trace = {
        "ts": now - 60,
        "doctor": "Codex desktop",
        "action": "LLM_REGISTRATION",
        "mode": "patch",
        "intent": "active surgery",
    }
    (tmp_path / "ide_stigmergic_trace.jsonl").write_text(json.dumps(trace) + "\n", encoding="utf-8")

    a = cs.assess(state_dir=tmp_path, now=now)
    assert a.owner_quiet_likelihood >= 0.6
    assert a.active_ide_surgery is True
    assert a.recommend_sleep is False
    assert a.decision == cs.DECISION_ACTIVE_SURGERY


def test_owner_recently_active_does_not_cosleep(tmp_path: Path):
    now = 1_000_000.0
    _set_melatonin(tmp_path, 0.9)
    # Quiet for only 5 minutes — below the idle floor.
    _write(tmp_path, "owner_desktop_presence.json", {"last_alive_ts": now - 300})
    _write(tmp_path, "active_owner_activity_segment.json", {
        "ts": now - 300, "status": "open",
        "camera_presence": {"owner_present": False, "age_s": 300.0},
        "audio_activity": {"voice_activity": False, "voice_age_s": 300.0},
    })
    a = cs.assess(state_dir=tmp_path, now=now)
    assert a.recommend_sleep is False


def test_receipt_is_written_and_hashed(tmp_path: Path):
    now = 1_000_000.0
    _set_melatonin(tmp_path, 0.6)
    _write(tmp_path, "owner_desktop_presence.json", {"last_alive_ts": now - 7200})
    _write(tmp_path, "active_owner_activity_segment.json", {"ts": now - 7200, "status": "closed"})
    a = cs.assess(state_dir=tmp_path, now=now, write=True)
    assert a.sha256
    ledger = tmp_path / cs.LEDGER_NAME
    assert ledger.exists()
    row = json.loads(ledger.read_text(encoding="utf-8").strip())
    assert row["truth_label"] == cs.TRUTH_LABEL
    assert row["payload"]["decision"] == a.decision
