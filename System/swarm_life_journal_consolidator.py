#!/usr/bin/env python3
"""Receipt-backed life journal consolidator.

This organ turns live stigmergic traces into two separate ledgers:

- Alice journal rows: what I observed or did.
- George activity segments: what the owner appears to be doing, with evidence.

No LLM inference runs here. The classifier is deterministic and conservative.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from System.jsonl_file_lock import append_line_locked


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"

ACTIVE_OWNER_ACTIVITY_NAME = "active_owner_activity_segment.json"
OWNER_ACTIVITY_LOG_NAME = "owner_activity_segments.jsonl"
RECEIPTS_LOG_NAME = "journal_schedule_receipts.jsonl"
AUDIO_INGRESS_LOG_NAME = "audio_ingress_log.jsonl"
ACOUSTIC_FINGERPRINTS_LOG_NAME = "acoustic_fingerprints.jsonl"
SENSOR_LANE_JOURNAL_NAME = "sensor_lane_journal.jsonl"
SENSOR_LANE_DEDUPE_NAME = "sensor_lane_dedupe.json"

ALICE_JOURNAL_DIR_NAME = "alice_journal"
OWNER_SCHEDULE_DIR_NAME = "owner_schedule"
OWNER_ACTIVITY_TRUTH_LABEL = "OWNER_ACTIVITY_SEGMENT_V1"
ALICE_JOURNAL_TRUTH_LABEL = "OBSERVED"
RECEIPT_TRUTH_LABEL = "JOURNAL_SCHEDULE_RECEIPT_V1"

CODING_APPS = {
    "Cursor",
    "Visual Studio Code",
    "Code",
    "Xcode",
    "Terminal",
    "iTerm2",
    "PyCharm",
}

PHONE_APPS = {"FaceTime", "Phone", "WhatsApp", "Messages", "Signal", "Telegram"}
TALK_MARKERS = ("talk to alice", "sifta python gui os", "alice widget")
AUDIO_FRESH_S = 120.0
VOICE_FRESH_S = 300.0

SENSOR_LANE_SOURCES: tuple[dict[str, str], ...] = (
    {
        "lane": "camera_vision",
        "ledger": "visual_stigmergy.jsonl",
        "summary": "camera / vision trace",
    },
    {
        "lane": "face_presence",
        "ledger": "face_detection_events.jsonl",
        "summary": "face / owner presence trace",
    },
    {
        "lane": "active_focus",
        "ledger": "app_focus.jsonl",
        "summary": "active app focus trace",
    },
    {
        "lane": "gps_location",
        "ledger": "iphone_gps_traces.jsonl",
        "summary": "iPhone GPS trace",
    },
    {
        "lane": "ble_radar",
        "ledger": "alice_ble_radar.jsonl",
        "summary": "BLE proximity trace",
    },
    {
        "lane": "attention_gaze",
        "ledger": "sensory_attention_ledger.jsonl",
        "summary": "sensor attention trace",
    },
    {
        "lane": "audio_voice",
        "ledger": AUDIO_INGRESS_LOG_NAME,
        "summary": "audio energy trace",
    },
)


def _normalize_camera_presence(presence: Any) -> dict[str, Any]:
    """Return a small, serializable camera-presence evidence dictionary."""
    if presence is None:
        return {"source": "swarm_face_detection", "fresh": False, "owner_present": False}

    def get(name: str, default: Any = None) -> Any:
        if isinstance(presence, Mapping):
            return presence.get(name, default)
        return getattr(presence, name, default)

    audience = _short(get("audience", "nobody"), 40)
    stale = bool(get("stale", True))
    faces_detected = int(get("faces_detected", 0) or 0)
    max_confidence = float(get("max_confidence", get("confidence", 0.0)) or 0.0)
    age_s_raw = get("age_s", None)
    age_s = None if age_s_raw in (None, "") else round(float(age_s_raw), 3)
    source = _short(get("source", "swarm_face_detection"), 80)
    fresh = (not stale) and audience in {"architect", "unknown_face"} and faces_detected > 0
    return {
        "source": source,
        "audience": audience or "nobody",
        "faces_detected": faces_detected,
        "max_confidence": round(max_confidence, 4),
        "stale": stale,
        "age_s": age_s,
        "fresh": bool(fresh),
        "owner_present": bool(fresh and audience == "architect"),
        "human_present": bool(fresh and audience in {"architect", "unknown_face"}),
    }


def _read_camera_presence_safe() -> dict[str, Any]:
    """Read camera presence from the face ledger without touching the camera."""
    try:
        from System.swarm_face_detection import current_presence_safe

        return _normalize_camera_presence(current_presence_safe())
    except Exception as exc:
        return {
            "source": "swarm_face_detection",
            "fresh": False,
            "owner_present": False,
            "error": _short(type(exc).__name__, 80),
        }


def _read_last_jsonl_row(path: Path, *, window_bytes: int = 32768) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        with path.open("rb") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            handle.seek(max(0, size - int(window_bytes)))
            rows = handle.read().splitlines()
        for raw in reversed(rows):
            if not raw.strip():
                continue
            row = json.loads(raw.decode("utf-8", "replace"))
            return row if isinstance(row, dict) else None
    except Exception:
        return None
    return None


def _row_ts(row: Mapping[str, Any]) -> float:
    for key in ("ts", "timestamp", "ts_captured", "created_at"):
        value = row.get(key)
        try:
            if value not in (None, ""):
                return float(value)
        except Exception:
            continue
    return 0.0


def _sensor_lane_text(lane: str, source_label: str, row: Mapping[str, Any]) -> str:
    """Return one clean sentence from a raw sensor row."""
    app = _short(row.get("app") or row.get("frontmost_app") or row.get("active_app"), 80)
    window = _short(row.get("window") or row.get("frontmost_window") or row.get("title"), 160)
    audience = _short(row.get("audience") or row.get("who") or row.get("presence"), 80)
    status = _short(row.get("status") or row.get("event") or row.get("kind") or row.get("route"), 80)
    device = _short(row.get("device") or row.get("device_name") or row.get("source"), 80)
    parts = [source_label]
    if status:
        parts.append(f"status={status}")
    if app:
        parts.append(f"app={app}")
    if window:
        parts.append(f"window={window}")
    if audience:
        parts.append(f"audience={audience}")
    if device:
        parts.append(f"device={device}")
    if len(parts) == 1:
        keys = [k for k in sorted(row.keys()) if k not in {"raw", "image", "frame"}][:5]
        parts.append("keys=" + ",".join(keys))
    return f"{lane}: " + "; ".join(parts)


def _load_sensor_dedupe(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_sensor_dedupe(path: Path, data: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(data), sort_keys=True), encoding="utf-8")


def _sensor_row_id(lane: str, ledger: str, row: Mapping[str, Any]) -> str:
    identity = {
        "lane": lane,
        "ledger": ledger,
        "ts": _row_ts(row),
        "status": row.get("status") or row.get("event") or row.get("kind"),
        "app": row.get("app") or row.get("frontmost_app"),
        "window": row.get("window") or row.get("frontmost_window") or row.get("title"),
    }
    return _stable_id(identity)


def _normalize_audio_activity(audio: Any) -> dict[str, Any]:
    """Return a small, serializable audio/VAD evidence dictionary."""
    if audio is None:
        return {"source": "life_journal_audio_lane", "fresh": False, "voice_activity": False}

    if isinstance(audio, Mapping) and (
        "voice_activity" in audio or "audio_active" in audio or "energy_state" in audio
    ) and "energy" not in audio and "voice" not in audio:
        return {
            "source": _short(audio.get("source", "life_journal_audio_lane"), 80),
            "fresh": bool(audio.get("fresh", False)),
            "real_audio": bool(audio.get("real_audio", False)),
            "rms_amplitude": round(float(audio.get("rms_amplitude", 0.0) or 0.0), 6),
            "energy_state": _short(audio.get("energy_state", "stale_or_absent"), 40),
            "audio_active": bool(audio.get("audio_active", False)),
            "voice_activity": bool(audio.get("voice_activity", False)),
            "channel_cue": _short(audio.get("channel_cue", ""), 80),
            "nearfield_voice_likelihood": round(float(audio.get("nearfield_voice_likelihood", 0.0) or 0.0), 4),
            "farfield_replay_likelihood": round(float(audio.get("farfield_replay_likelihood", 0.0) or 0.0), 4),
            "age_s": audio.get("age_s"),
            "energy_age_s": audio.get("energy_age_s"),
            "voice_age_s": audio.get("voice_age_s"),
        }

    def get(name: str, default: Any = None) -> Any:
        if isinstance(audio, Mapping):
            return audio.get(name, default)
        return getattr(audio, name, default)

    ts = get("ts", get("ts_captured", None))
    try:
        ts_f = float(ts) if ts not in (None, "") else 0.0
    except Exception:
        ts_f = 0.0
    age_s = max(0.0, time.time() - ts_f) if ts_f else None

    energy = get("energy") if isinstance(get("energy"), Mapping) else {}
    voice = get("voice") if isinstance(get("voice"), Mapping) else {}
    source = _short(get("source", "life_journal_audio_lane"), 80)
    rms = float(energy.get("rms_amplitude") or energy.get("rms") or get("rms_amplitude", 0.0) or 0.0)
    audio_source = _short(energy.get("source") or get("audio_source") or "", 80)
    channel_cue = _short(voice.get("channel_cue") or get("channel_cue") or "", 80)
    nearfield = float(voice.get("nearfield_voice_likelihood") or get("nearfield_voice_likelihood", 0.0) or 0.0)
    farfield = float(voice.get("farfield_replay_likelihood") or get("farfield_replay_likelihood", 0.0) or 0.0)
    voice_age = voice.get("age_s")
    try:
        voice_age_f = None if voice_age in (None, "") else float(voice_age)
    except Exception:
        voice_age_f = None
    energy_age = energy.get("age_s")
    try:
        energy_age_f = None if energy_age in (None, "") else float(energy_age)
    except Exception:
        energy_age_f = None

    energy_fresh = bool(energy.get("fresh", False))
    voice_fresh = bool(voice.get("fresh", False))
    real_audio = audio_source in {"sounddevice", "ffmpeg"} or bool(energy.get("real_audio"))
    voice_activity = bool(voice_fresh and (channel_cue == "nearfield_voice_likely" or nearfield >= 0.6))
    audio_active = bool(energy_fresh and real_audio and rms >= 0.012)
    if rms >= 0.04:
        energy_state = "loud"
    elif audio_active:
        energy_state = "active"
    elif energy_fresh:
        energy_state = "quiet"
    else:
        energy_state = "stale_or_absent"

    return {
        "source": source,
        "fresh": bool(energy_fresh or voice_fresh),
        "real_audio": bool(real_audio),
        "rms_amplitude": round(rms, 6),
        "energy_state": energy_state,
        "audio_active": audio_active,
        "voice_activity": voice_activity,
        "channel_cue": channel_cue,
        "nearfield_voice_likelihood": round(nearfield, 4),
        "farfield_replay_likelihood": round(farfield, 4),
        "age_s": None if age_s is None else round(age_s, 3),
        "energy_age_s": None if energy_age_f is None else round(energy_age_f, 3),
        "voice_age_s": None if voice_age_f is None else round(voice_age_f, 3),
    }


def _read_audio_activity_safe(state: Path, *, now: float | None = None) -> dict[str, Any]:
    """Read audio energy/VAD evidence from ledgers without opening the microphone."""
    ts_now = float(now if now is not None else time.time())
    energy_row = _read_last_jsonl_row(state / AUDIO_INGRESS_LOG_NAME)
    voice_row = _read_last_jsonl_row(state / ACOUSTIC_FINGERPRINTS_LOG_NAME)

    energy: dict[str, Any] = {}
    if energy_row:
        ts = float(energy_row.get("ts_captured") or energy_row.get("ts") or 0.0)
        source = str(energy_row.get("source") or "")
        age_s = max(0.0, ts_now - ts) if ts else None
        energy = {
            "ts": ts,
            "age_s": age_s,
            "fresh": bool(age_s is not None and age_s <= AUDIO_FRESH_S),
            "source": source,
            "device_name": _short(energy_row.get("device_name"), 90),
            "real_audio": source in {"sounddevice", "ffmpeg"},
            "rms_amplitude": float(energy_row.get("rms_amplitude") or 0.0),
            "duration_s": energy_row.get("duration_s"),
            "sample_id": _short(energy_row.get("sample_id"), 80),
        }

    voice: dict[str, Any] = {}
    if voice_row:
        ts = float(voice_row.get("ts") or 0.0)
        age_s = max(0.0, ts_now - ts) if ts else None
        fp = voice_row.get("playback_fingerprint") if isinstance(voice_row.get("playback_fingerprint"), Mapping) else {}
        voice = {
            "ts": ts,
            "age_s": age_s,
            "fresh": bool(age_s is not None and age_s <= VOICE_FRESH_S),
            "channel_cue": _short(voice_row.get("channel_cue") or fp.get("channel_cue"), 80),
            "nearfield_voice_likelihood": float(fp.get("nearfield_voice_likelihood") or 0.0),
            "farfield_replay_likelihood": float(fp.get("farfield_replay_likelihood") or 0.0),
            "fingerprint_row_id": _short(voice_row.get("fingerprint_row_id"), 80),
            "raw_audio_logged": bool(voice_row.get("raw_audio_logged", False)),
        }

    return _normalize_audio_activity({"source": "life_journal_audio_lane", "energy": energy, "voice": voice})


def _state_dir(state_dir: Path | str | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else STATE_DIR


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    append_line_locked(path, json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def _short(value: Any, limit: int = 240) -> str:
    return " ".join(str(value or "").split())[:limit]


def _local_date(ts: float) -> str:
    return datetime.fromtimestamp(float(ts)).date().isoformat()


def _minute_from_ts(ts: float) -> int:
    lt = time.localtime(float(ts))
    return int(lt.tm_hour) * 60 + int(lt.tm_min)


def _fmt_ts(ts: float) -> str:
    return datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M")


def _journal_label(ts: float) -> str:
    return datetime.fromtimestamp(float(ts)).strftime("%m-%d-%y_%H:%M")


def _fmt_minute(minute: int) -> str:
    minute = int(minute) % (24 * 60)
    h24, m = divmod(minute, 60)
    suffix = "AM" if h24 < 12 else "PM"
    return f"{h24 % 12 or 12}:{m:02d} {suffix}"


def _stable_id(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _focus_key(label: str, app: str, window: str, browser: Mapping[str, Any]) -> str:
    video_id = str(browser.get("youtube_video_id") or "")
    base = f"{label}|{app}|{video_id or window}"
    return hashlib.sha256(base.casefold().encode("utf-8", errors="replace")).hexdigest()[:16]


def classify_activity(
    snapshot: Mapping[str, Any],
    *,
    camera_presence: Any | None = None,
    audio_activity: Any | None = None,
) -> dict[str, Any]:
    """Classify one active-window snapshot into a stable owner activity label."""
    app = _short(snapshot.get("app"), 120)
    window = _short(snapshot.get("window"), 220)
    browser = snapshot.get("browser") if isinstance(snapshot.get("browser"), Mapping) else {}
    browser_title = _short(browser.get("title"), 220)
    browser_url = _short(browser.get("url"), 260)
    visible_low = f"{app} {window} {browser_title} {browser_url}".casefold()
    camera = _normalize_camera_presence(camera_presence)
    audio = _normalize_audio_activity(audio_activity)

    label = "unknown"
    confidence = 0.35
    reason = "frontmost window did not match a known deterministic activity pattern"

    if not snapshot.get("ok"):
        label, confidence, reason = "unknown", 0.2, "active-window probe was not ok"
        if camera.get("owner_present"):
            label, confidence, reason = (
                "present_at_desk",
                0.64,
                "active-window probe failed but camera ledger shows fresh owner presence",
            )
        elif audio.get("voice_activity"):
            label, confidence, reason = (
                "voice_activity",
                0.58,
                "active-window probe failed but audio ledger shows fresh nearfield voice activity",
            )
    elif any(marker in visible_low for marker in TALK_MARKERS):
        label, confidence, reason = "talking_to_alice", 0.88, "frontmost SIFTA/Alice window"
    elif bool(browser.get("is_youtube")) or "youtube" in visible_low or re.search(r"\bvideo\b", visible_low):
        label, confidence, reason = "watching_video", 0.86, "frontmost browser/window indicates video context"
    elif app in PHONE_APPS or re.search(r"\b(phone|facetime|call|whatsapp|messages)\b", visible_low):
        label, confidence, reason = "on_phone", 0.82, "frontmost app/window indicates phone or messaging"
    elif app in CODING_APPS or re.search(
        r"\b(cursor|terminal|pytest|python|\.py\b|\.md\b|\.jsonl\b|anton_sifta|ide|code)\b",
        visible_low,
    ):
        label, confidence, reason = "coding", 0.9, "frontmost app/window indicates coding or repo work"
    elif app == "Ollama" or re.search(r"\bollama\b", visible_low):
        label, confidence, reason = "model_management", 0.84, "frontmost app/window indicates local model management"
    elif app in {"Finder", "SIFTA File Navigator"}:
        label, confidence, reason = "file_browsing", 0.72, "frontmost app indicates file navigation"
    elif app in {"Safari", "Google Chrome", "Brave Browser", "Arc"}:
        label, confidence, reason = "researching", 0.7, "frontmost browser context without media marker"

    if camera.get("owner_present") and label != "unknown":
        confidence = min(0.96, float(confidence) + 0.04)
        reason = f"{reason}; fresh camera presence supports owner-at-desk grounding"
    if audio.get("voice_activity") and label != "unknown":
        confidence = min(0.96, float(confidence) + 0.03)
        reason = f"{reason}; fresh VAD evidence supports live voice grounding"

    return {
        "label": label,
        "confidence": confidence,
        "reason": reason,
        "frontmost_app": app,
        "frontmost_window": window,
        "bundle_id": _short(snapshot.get("bundle_id"), 160),
        "browser": dict(browser),
        "camera_presence": camera,
        "audio_activity": audio,
        "source": "swarm_active_window",
        "source_ts": float(snapshot.get("ts") or time.time()),
        "focus_key": _focus_key(label, app, window, browser),
    }


def _active_path(state: Path) -> Path:
    return state / ACTIVE_OWNER_ACTIVITY_NAME


def read_active_owner_activity(*, state_dir: Path | str | None = None) -> dict[str, Any] | None:
    path = _active_path(_state_dir(state_dir))
    if not path.exists():
        return None
    try:
        row = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return row if isinstance(row, dict) else None


def _write_active(state: Path, row: Mapping[str, Any]) -> None:
    state.mkdir(parents=True, exist_ok=True)
    _active_path(state).write_text(json.dumps(dict(row), ensure_ascii=False, sort_keys=True), encoding="utf-8")


def _journal_path(state: Path, ts: float) -> Path:
    return state / ALICE_JOURNAL_DIR_NAME / f"{_local_date(ts)}.jsonl"


def _alice_journal_md_path(state: Path, ts: float) -> Path:
    return state / ALICE_JOURNAL_DIR_NAME / f"{_local_date(ts)}.md"


def _owner_schedule_md_path(state: Path, ts: float) -> Path:
    return state / OWNER_SCHEDULE_DIR_NAME / f"{_local_date(ts)}.md"


def _append_daily_markdown(path: Path, *, date_label: str, block: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(f"# {date_label}\n\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(block.rstrip() + "\n\n")


def _receipt_ref(receipt: Mapping[str, Any]) -> str:
    return f"journal_schedule_receipts:{receipt.get('receipt_hash', '')}"


def _evidence_line(evidence: Mapping[str, Any]) -> str:
    app = _short(evidence.get("frontmost_app"), 80)
    window = _short(evidence.get("frontmost_window"), 160)
    confidence = evidence.get("confidence")
    camera = evidence.get("camera_presence") if isinstance(evidence.get("camera_presence"), Mapping) else {}
    audio = evidence.get("audio_activity") if isinstance(evidence.get("audio_activity"), Mapping) else {}
    bits = []
    if app:
        bits.append(f"app={app}")
    if window:
        bits.append(f"window={window}")
    if confidence not in (None, ""):
        bits.append(f"confidence={confidence}")
    if camera.get("owner_present"):
        bits.append("camera=owner_present")
    elif camera.get("human_present"):
        bits.append("camera=human_present")
    elif camera:
        bits.append("camera=no_fresh_owner_presence")
    if audio.get("voice_activity"):
        bits.append("audio=voice_activity")
    elif audio.get("audio_active"):
        bits.append("audio=energy_active")
    elif audio:
        bits.append(f"audio={audio.get('energy_state', 'no_fresh_voice')}")
    return "; ".join(bits) or "bounded local trace evidence"


def _display_label(label: Any) -> str:
    return str(label or "activity").replace("_", " ")


def _write_receipt(
    *,
    state: Path,
    operation: str,
    ok: bool,
    status: str,
    owner_activity_id: str = "",
    journal_id: str = "",
    evidence: Mapping[str, Any] | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    ts = float(now if now is not None else time.time())
    row = {
        "ts": ts,
        "truth_label": RECEIPT_TRUTH_LABEL,
        "operation": operation,
        "ok": bool(ok),
        "status": status,
        "owner_activity_id": owner_activity_id,
        "journal_id": journal_id,
        "evidence": dict(evidence or {}),
    }
    row["receipt_hash"] = _stable_id(row)
    _append_jsonl(state / RECEIPTS_LOG_NAME, row)
    return row


def _write_alice_journal(
    *,
    state: Path,
    event_type: str,
    entry: str,
    evidence: Mapping[str, Any],
    now: float,
) -> dict[str, Any]:
    row = {
        "ts": now,
        "local_journal_label": _journal_label(now),
        "local_date": _local_date(now),
        "kind": "EPISODIC_NARRATIVE",
        "narrator": "ALICE_M5",
        "entry": entry,
        "event_type": event_type,
        "truth_label": ALICE_JOURNAL_TRUTH_LABEL,
        "source": "swarm_life_journal_consolidator",
        "source_evidence": dict(evidence),
    }
    row["journal_id"] = _stable_id(row)
    _append_jsonl(_journal_path(state, now), row)
    return row


def _write_alice_journal_markdown(
    *,
    state: Path,
    journal: Mapping[str, Any],
    receipt: Mapping[str, Any],
) -> None:
    ts = float(journal.get("ts") or receipt.get("ts") or time.time())
    evidence = journal.get("source_evidence") if isinstance(journal.get("source_evidence"), Mapping) else {}
    entry = _short(journal.get("entry"), 900)
    if " - " in entry:
        # Daily Markdown already has timestamp headings; keep the prose readable.
        entry = entry.split(" - ", 1)[-1].strip()
    block = (
        f"### {str(journal.get('local_journal_label') or _journal_label(ts))}\n"
        f"{entry}\n\n"
        f"Source: {_evidence_line(evidence)}\n"
        f"Receipt: `{_receipt_ref(receipt)}`"
    )
    _append_daily_markdown(_alice_journal_md_path(state, ts), date_label=_local_date(ts), block=block)


def _write_owner_schedule_markdown(
    *,
    state: Path,
    closed: Mapping[str, Any],
    receipt: Mapping[str, Any],
) -> None:
    ts = float(closed.get("end_ts") or closed.get("ts") or receipt.get("ts") or time.time())
    start = str(closed.get("start_time") or "?")
    end = str(closed.get("end_time") or "?")
    label = str(closed.get("label") or "activity")
    app = _short(closed.get("frontmost_app"), 90)
    window = _short(closed.get("frontmost_window"), 180)
    source = str(closed.get("source") or "swarm_life_journal_consolidator")
    confidence = closed.get("confidence")
    duration = closed.get("duration_minutes")
    duration_text = f"\nDuration: {duration} minutes" if duration not in (None, "") else ""
    block = (
        f"### {start} - {end}\n"
        f"George {_display_label(label)}"
        f"{' in ' + app if app else ''}"
        f"{' on ' + window if window else ''}.\n\n"
        f"Source: {source}\n"
        f"Confidence: {confidence}"
        f"{duration_text}\n"
        f"Receipt: `{_receipt_ref(receipt)}`"
    )
    _append_daily_markdown(_owner_schedule_md_path(state, ts), date_label=_local_date(ts), block=block)


def _owner_open_row(classification: Mapping[str, Any], *, now: float) -> dict[str, Any]:
    label = str(classification.get("label") or "unknown")
    app = str(classification.get("frontmost_app") or "")
    window = str(classification.get("frontmost_window") or "")
    row = {
        "ts": now,
        "timestamp": now,
        "truth_label": OWNER_ACTIVITY_TRUTH_LABEL,
        "status": "open",
        "owner_activity_id": _stable_id({"ts": now, "label": label, "focus_key": classification.get("focus_key")}),
        "source": "swarm_life_journal_consolidator",
        "local_date": _local_date(now),
        "start_ts": now,
        "start_minute_of_day": _minute_from_ts(now),
        "start_time": _fmt_minute(_minute_from_ts(now)),
        "label": label,
        "confidence": float(classification.get("confidence") or 0.0),
        "reason": str(classification.get("reason") or ""),
        "frontmost_app": app,
        "frontmost_window": window,
        "bundle_id": str(classification.get("bundle_id") or ""),
        "camera_presence": dict(classification.get("camera_presence") or {}),
        "audio_activity": dict(classification.get("audio_activity") or {}),
        "focus_key": str(classification.get("focus_key") or ""),
        "context_note": f"George appears to be {label} in {app}: {window}".strip(),
        "source_evidence": dict(classification),
    }
    return row


def _closed_owner_row(active: Mapping[str, Any], *, now: float) -> dict[str, Any]:
    start_ts = float(active.get("start_ts") or now)
    start_min = _minute_from_ts(start_ts)
    end_min = _minute_from_ts(now)
    if end_min <= start_min:
        end_min += 24 * 60
    if end_min == start_min:
        end_min += 1
    row = dict(active)
    row.update(
        {
            "ts": now,
            "timestamp": now,
            "status": "closed",
            "end_ts": now,
            "end_minute_of_day": end_min,
            "end_time": _fmt_minute(end_min),
            "duration_s": max(0.0, now - start_ts),
            "duration_minutes": max(1, int(round(max(0.0, now - start_ts) / 60.0))),
        }
    )
    row["segment_id"] = row.get("owner_activity_id") or _stable_id(row)
    return row


def _mirror_architect_day_segment(state: Path, closed: Mapping[str, Any], *, now: float) -> dict[str, Any] | None:
    """Mirror closed owner activity into the existing day-segment ledger."""
    try:
        from System import swarm_architect_day_segments as day

        row = day._build_row(  # existing schema builder; keeps prompt compatibility.
            label=str(closed.get("label") or "activity"),
            start_minute=int(closed.get("start_minute_of_day") or _minute_from_ts(now)),
            end_minute=int(closed.get("end_minute_of_day") or _minute_from_ts(now) + 1),
            context_note=str(closed.get("context_note") or ""),
            source="swarm_life_journal_consolidator",
            state_dir=state,
            now=now,
            location="desk" if closed.get("label") == "coding" else "",
            media_context="video" if closed.get("label") == "watching_video" else "",
            extra={
                "owner_activity_truth_label": OWNER_ACTIVITY_TRUTH_LABEL,
                "owner_activity_id": closed.get("owner_activity_id"),
                "owner_activity_confidence": closed.get("confidence"),
                "frontmost_app": closed.get("frontmost_app"),
                "frontmost_window": closed.get("frontmost_window"),
            },
        )
        return day.write_day_segment(row, state_dir=state)
    except Exception:
        return None


def _open_new_segment(
    *,
    state: Path,
    classification: Mapping[str, Any],
    now: float,
    reason: str,
) -> dict[str, Any]:
    active = _owner_open_row(classification, now=now)
    _write_active(state, active)
    evidence = {
        "label": active["label"],
        "confidence": active["confidence"],
        "frontmost_app": active["frontmost_app"],
        "frontmost_window": active["frontmost_window"],
        "camera_presence": dict(active.get("camera_presence") or {}),
        "audio_activity": dict(active.get("audio_activity") or {}),
        "reason": active["reason"],
    }
    journal = _write_alice_journal(
        state=state,
        event_type="owner_activity_observed",
        entry=(
            f"{_fmt_ts(now)} — I observed George {_display_label(active['label'])} via "
            f"{active['source']}: {active['frontmost_app']} / {active['frontmost_window']}."
        ),
        evidence=evidence,
        now=now,
    )
    receipt = _write_receipt(
        state=state,
        operation="OPEN_OWNER_ACTIVITY_SEGMENT",
        ok=True,
        status=reason,
        owner_activity_id=str(active.get("owner_activity_id") or ""),
        journal_id=str(journal.get("journal_id") or ""),
        evidence=evidence,
        now=now,
    )
    _write_alice_journal_markdown(state=state, journal=journal, receipt=receipt)
    return {"active": active, "journal": journal, "receipt": receipt}


def consolidate_sensor_lanes_once(
    *,
    state_dir: Path | str | None = None,
    now: float | None = None,
    max_age_s: float = 1800.0,
    min_emit_s: float = 300.0,
    sources: Iterable[Mapping[str, str]] | None = None,
) -> dict[str, Any]:
    """Convert raw sensor lane rows into clean journal/schedule text.

    The raw ledgers remain the evidence. This function writes small derived
    rows with receipts so Alice has a readable daily substrate instead of
    needing to parse every sensor-specific schema during Talk.
    """
    ts = float(now if now is not None else time.time())
    state = _state_dir(state_dir)
    dedupe_path = state / SENSOR_LANE_DEDUPE_NAME
    dedupe = _load_sensor_dedupe(dedupe_path)
    emitted: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for src in tuple(sources or SENSOR_LANE_SOURCES):
        lane = str(src.get("lane") or "")
        ledger = str(src.get("ledger") or "")
        source_label = str(src.get("summary") or ledger or lane)
        if not lane or not ledger:
            continue
        ledger_path = state / ledger
        row = _read_last_jsonl_row(ledger_path)
        if not row:
            skipped.append({"lane": lane, "reason": "missing_ledger_or_empty", "ledger": ledger})
            continue
        row_ts = _row_ts(row)
        if row_ts <= 0:
            try:
                row_ts = ledger_path.stat().st_mtime
            except OSError:
                row_ts = 0.0
        age_s = None if row_ts <= 0 else max(0.0, ts - row_ts)
        if age_s is not None and age_s > float(max_age_s):
            skipped.append({"lane": lane, "reason": "stale", "ledger": ledger, "age_s": round(age_s, 3)})
            continue
        row_id = _sensor_row_id(lane, ledger, row)
        prev = dedupe.get(lane) if isinstance(dedupe.get(lane), Mapping) else {}
        if prev.get("row_id") == row_id and ts - float(prev.get("emitted_ts") or 0.0) < float(min_emit_s):
            skipped.append({"lane": lane, "reason": "deduped", "ledger": ledger})
            continue

        evidence = {
            "lane": lane,
            "ledger": ledger,
            "source_row_id": row_id,
            "source_ts": row_ts,
            "age_s": None if age_s is None else round(age_s, 3),
            "source_row": {k: row.get(k) for k in list(row.keys())[:16]},
        }
        text = _sensor_lane_text(lane, source_label, row)
        journal_row = {
            "ts": ts,
            "truth_label": "SENSOR_LANE_JOURNAL_V1",
            "kind": "SENSOR_LANE_SUMMARY",
            "lane": lane,
            "ledger": ledger,
            "source_row_id": row_id,
            "summary": text,
            "evidence": evidence,
        }
        journal_row["journal_id"] = _stable_id(journal_row)
        _append_jsonl(state / SENSOR_LANE_JOURNAL_NAME, journal_row)
        alice_journal = _write_alice_journal(
            state=state,
            event_type="sensor_lane_observed",
            entry=f"{_fmt_ts(ts)} — {text}.",
            evidence=evidence,
            now=ts,
        )
        receipt = _write_receipt(
            state=state,
            operation="SENSOR_LANE_TO_JOURNAL",
            ok=True,
            status="sensor_lane_summary_written",
            journal_id=str(alice_journal.get("journal_id") or ""),
            evidence=evidence,
            now=ts,
        )
        _write_alice_journal_markdown(state=state, journal=alice_journal, receipt=receipt)
        if lane in {"active_focus", "gps_location", "face_presence", "audio_voice"}:
            block = (
                f"### {_fmt_minute(_minute_from_ts(ts))} sensor lane\n"
                f"{text}.\n\n"
                f"Source: {ledger}\n"
                f"Receipt: `{_receipt_ref(receipt)}`"
            )
            _append_daily_markdown(_owner_schedule_md_path(state, ts), date_label=_local_date(ts), block=block)
        dedupe[lane] = {"row_id": row_id, "emitted_ts": ts, "ledger": ledger}
        emitted.append({"lane": lane, "ledger": ledger, "journal_id": journal_row["journal_id"], "receipt": receipt})
    if emitted:
        _write_sensor_dedupe(dedupe_path, dedupe)
    return {"action": "sensor_lanes_consolidated", "emitted": emitted, "skipped": skipped}


def consolidate_once(
    *,
    state_dir: Path | str | None = None,
    now: float | None = None,
    snapshot: Mapping[str, Any] | None = None,
    camera_presence: Any | None = None,
    audio_activity: Any | None = None,
    min_segment_s: float = 60.0,
    heartbeat_journal_s: float = 900.0,
) -> dict[str, Any]:
    """Run one deterministic consolidation tick.

    Returns a small result dictionary. It writes only when a segment opens,
    changes, closes, or needs a low-rate heartbeat journal.
    """
    ts = float(now if now is not None else time.time())
    state = _state_dir(state_dir)
    try:
        consolidate_sensor_lanes_once(state_dir=state, now=ts)
    except Exception:
        pass
    if snapshot is None:
        from System import swarm_active_window

        snapshot = swarm_active_window.write_snapshot()

    if camera_presence is None:
        camera_presence = _read_camera_presence_safe()
    if audio_activity is None:
        audio_activity = _read_audio_activity_safe(state, now=ts)

    classification = classify_activity(snapshot, camera_presence=camera_presence, audio_activity=audio_activity)
    active = read_active_owner_activity(state_dir=state)
    label = str(classification.get("label") or "unknown")
    focus_key = str(classification.get("focus_key") or "")

    if label == "unknown":
        if active:
            closed = _closed_owner_row(active, now=ts)
            _append_jsonl(state / OWNER_ACTIVITY_LOG_NAME, closed)
            _mirror_architect_day_segment(state, closed, now=ts)
            try:
                _active_path(state).unlink()
            except OSError:
                pass
            receipt = _write_receipt(
                state=state,
                operation="CLOSE_OWNER_ACTIVITY_SEGMENT",
                ok=True,
                status="closed_unknown_focus",
                owner_activity_id=str(closed.get("owner_activity_id") or ""),
                evidence={"label": label, "focus_key": focus_key},
                now=ts,
            )
            _write_owner_schedule_markdown(state=state, closed=closed, receipt=receipt)
            return {"action": "closed", "closed": closed, "receipt": receipt, "classification": classification}
        return {"action": "ignored_unknown", "classification": classification}

    if not active:
        out = _open_new_segment(state=state, classification=classification, now=ts, reason="opened")
        return {"action": "opened", "classification": classification, **out}

    active_focus = str(active.get("focus_key") or "")
    age_s = max(0.0, ts - float(active.get("start_ts") or ts))
    if active_focus != focus_key and age_s >= max(1.0, float(min_segment_s)):
        closed = _closed_owner_row(active, now=ts)
        _append_jsonl(state / OWNER_ACTIVITY_LOG_NAME, closed)
        mirrored = _mirror_architect_day_segment(state, closed, now=ts)
        close_receipt = _write_receipt(
            state=state,
            operation="CLOSE_OWNER_ACTIVITY_SEGMENT",
            ok=True,
            status="activity_changed",
            owner_activity_id=str(closed.get("owner_activity_id") or ""),
            evidence={"old_label": active.get("label"), "new_label": label, "mirrored_day_segment": bool(mirrored)},
            now=ts,
        )
        _write_owner_schedule_markdown(state=state, closed=closed, receipt=close_receipt)
        opened = _open_new_segment(state=state, classification=classification, now=ts, reason="activity_changed")
        return {
            "action": "changed",
            "classification": classification,
            "closed": closed,
            "close_receipt": close_receipt,
            **opened,
        }

    last_journal_ts = float(active.get("last_journal_ts") or active.get("start_ts") or ts)
    if ts - last_journal_ts >= float(heartbeat_journal_s):
        active["last_journal_ts"] = ts
        _write_active(state, active)
        evidence = {
            "label": active.get("label"),
            "frontmost_app": active.get("frontmost_app"),
            "frontmost_window": active.get("frontmost_window"),
            "camera_presence": dict(active.get("camera_presence") or {}),
            "audio_activity": dict(active.get("audio_activity") or {}),
            "duration_s": age_s,
        }
        journal = _write_alice_journal(
            state=state,
            event_type="owner_activity_still_observed",
            entry=(
                f"{_fmt_ts(ts)} — I still observe George {_display_label(active.get('label'))} "
                f"from the same focus evidence."
            ),
            evidence=evidence,
            now=ts,
        )
        receipt = _write_receipt(
            state=state,
            operation="HEARTBEAT_OWNER_ACTIVITY_SEGMENT",
            ok=True,
            status="still_observed",
            owner_activity_id=str(active.get("owner_activity_id") or ""),
            journal_id=str(journal.get("journal_id") or ""),
            evidence=evidence,
            now=ts,
        )
        _write_alice_journal_markdown(state=state, journal=journal, receipt=receipt)
        return {"action": "heartbeat", "classification": classification, "active": active, "journal": journal, "receipt": receipt}

    return {"action": "no_change", "classification": classification, "active": active}


def format_current_activity_for_prompt(*, state_dir: Path | str | None = None) -> str:
    active = read_active_owner_activity(state_dir=state_dir)
    if not active:
        return ""
    return (
        "CURRENT OWNER ACTIVITY (receipt-backed active segment): "
        f"George appears to be {active.get('label')} since {active.get('start_time')} "
        f"via {active.get('source')}; app={active.get('frontmost_app')} "
        f"window={active.get('frontmost_window')} confidence={active.get('confidence')}."
    )


def format_recent_sensor_lanes_for_prompt(*, state_dir: Path | str | None = None, limit: int = 5) -> str:
    state = _state_dir(state_dir)
    path = state / SENSOR_LANE_JOURNAL_NAME
    if not path.exists():
        return ""
    rows: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines()[-200:]:
            if not line.strip():
                continue
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
    except Exception:
        return ""
    if not rows:
        return ""
    lines = ["RECENT SENSOR LANE JOURNAL (receipt-backed summaries):"]
    for row in rows[-max(1, int(limit)):]:
        lines.append(f"- {row.get('lane')}: {row.get('summary')} receipt={row.get('journal_id')}")
    return "\n".join(lines)


__all__ = [
    "ACTIVE_OWNER_ACTIVITY_NAME",
    "OWNER_ACTIVITY_LOG_NAME",
    "OWNER_SCHEDULE_DIR_NAME",
    "RECEIPTS_LOG_NAME",
    "AUDIO_INGRESS_LOG_NAME",
    "ACOUSTIC_FINGERPRINTS_LOG_NAME",
    "SENSOR_LANE_JOURNAL_NAME",
    "SENSOR_LANE_SOURCES",
    "classify_activity",
    "consolidate_once",
    "consolidate_sensor_lanes_once",
    "format_current_activity_for_prompt",
    "format_recent_sensor_lanes_for_prompt",
    "read_active_owner_activity",
]


if __name__ == "__main__":
    print(json.dumps(consolidate_once(), indent=2, ensure_ascii=False))
