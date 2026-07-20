#!/usr/bin/env python3
"""MacBook substrate survival swimmer.

This is the SIFTA-native version of "a laptop with wheels wakes up anywhere
and asks the owner for the next survival action." It does not create a central
governor loop. It composes existing body organs:

- swarm_battery_metabolism_organ: electricity / air / energy reserve
- alice_hardware_body + hardware heart: thermal and host substrate facts
- swarm_sensor_truth_context: camera proof, not mere camera inventory

The output is a receipt-backed survival band plus a single owner-action line.
Alice can speak that line when asked, or when the field pressure is high enough.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Mapping

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover - direct script fallback
    append_line_locked = None  # type: ignore[assignment]


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE_DIR = REPO_ROOT / ".sifta_state"

TRUTH_LABEL = "MACBOOK_SURVIVAL_SWIMMER_V1"
LEDGER_NAME = "macbook_survival_swimmer.jsonl"
LATEST_NAME = "macbook_survival_latest.json"
FIRST_PERSON_NAME = "alice_first_person_journal.jsonl"
EPISODIC_NAME = "episodic_diary.jsonl"


def _state_dir(state_dir: Path | str | None = None) -> Path:
    if state_dir is None:
        return DEFAULT_STATE_DIR
    path = Path(state_dir)
    if path.name == ".sifta_state":
        return path
    if (path / "work_receipts.jsonl").exists() or (path / "visual_stigmergy.jsonl").exists():
        return path
    return path / ".sifta_state"


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
    if append_line_locked is not None:
        append_line_locked(path, line)
        return
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _tail_jsonl(path: Path, *, max_bytes: int = 131072) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - max_bytes))
            raw = handle.read().decode("utf-8", "replace")
    except Exception:
        return {}
    for line in reversed(raw.splitlines()):
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if isinstance(obj, dict):
            return obj
    return {}


def _coerce_int(value: Any) -> int | None:
    try:
        return int(value)
    except Exception:
        return None


def _coerce_float(value: Any) -> float | None:
    try:
        out = float(value)
    except Exception:
        return None
    if out != out or out in (float("inf"), float("-inf")):
        return None
    return out


def _source_kind(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"ac", "wall", "wall_power"} or "ac power" in text or "charger" in text:
        return "ac"
    if text == "battery" or "battery power" in text:
        return "battery"
    return text or "unknown"


def _receipt_id(payload: Mapping[str, Any]) -> str:
    stable = dict(payload)
    stable.pop("receipt_id", None)
    raw = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "macsurv_" + hashlib.sha256(raw).hexdigest()[:16]


def collect_power(*, state_dir: Path | str | None = None) -> dict[str, Any]:
    """Read Alice's electricity from existing power organs without duplicating them."""
    state = _state_dir(state_dir)
    out: dict[str, Any] = {
        "ok": False,
        "source": "unknown",
        "source_kind": "unknown",
        "percent": None,
        "status": "",
        "metabolic_band": "",
        "conserve": None,
        "reason": "",
        "evidence": {},
    }
    try:
        from System import swarm_battery_metabolism_organ as battery

        brow = battery.sample(write=False, root=REPO_ROOT)
        batt = brow.get("battery") if isinstance(brow.get("battery"), dict) else {}
        metabolic = brow.get("metabolic") if isinstance(brow.get("metabolic"), dict) else {}
        out.update(
            {
                "ok": bool(brow.get("ok") or batt.get("available")),
                "source": batt.get("source") or "unknown",
                "source_kind": _source_kind(batt.get("source")),
                "percent": _coerce_int(batt.get("percent")),
                "status": str(batt.get("status") or ""),
                "metabolic_band": str(metabolic.get("band") or ""),
                "conserve": metabolic.get("conserve") if isinstance(metabolic.get("conserve"), bool) else None,
                "reason": str(metabolic.get("reason") or ""),
                "evidence": {
                    "truth_label": brow.get("truth_label"),
                    "battery_source": "swarm_battery_metabolism_organ.sample(write=False)",
                    "ledger": "battery_metabolism.jsonl",
                },
            }
        )
    except Exception as exc:
        out["reason"] = f"battery_metabolism_unavailable:{type(exc).__name__}"

    if not out["ok"]:
        try:
            from System import alice_hardware_body as hw

            hp = hw.power()
            out.update(
                {
                    "ok": bool(hp.get("ok")),
                    "source": hp.get("source") or out["source"],
                    "source_kind": _source_kind(hp.get("source")),
                    "percent": _coerce_int(hp.get("percent")),
                    "status": str(hp.get("state") or hp.get("remaining") or ""),
                    "evidence": {
                        "truth_label": "ALICE_HARDWARE_BODY_POWER_READ",
                        "battery_source": "alice_hardware_body.power()",
                        "raw_ok": hp.get("ok"),
                    },
                }
            )
        except Exception as exc:
            out["reason"] = f"{out.get('reason')}; hardware_power_unavailable:{type(exc).__name__}"[:220]

    if not out["ok"]:
        latest = _tail_jsonl(state / "hardware_heart.jsonl") or _tail_jsonl(state / "alice_body_heart.jsonl")
        if latest:
            out.update(
                {
                    "ok": latest.get("battery_percent") is not None or bool(latest.get("power_source")),
                    "source": latest.get("power_source") or out["source"],
                    "source_kind": _source_kind(latest.get("power_source")),
                    "percent": _coerce_int(latest.get("battery_percent")),
                    "metabolic_band": str(latest.get("metabolic_band") or out["metabolic_band"]),
                    "conserve": latest.get("conserve") if isinstance(latest.get("conserve"), bool) else out["conserve"],
                    "reason": str(latest.get("sensor_reason") or out.get("reason") or ""),
                    "evidence": {
                        "truth_label": latest.get("truth_label"),
                        "battery_source": "hardware_heart_latest",
                        "receipt_id": latest.get("receipt_id"),
                    },
                }
            )
    return out


def collect_thermal(*, state_dir: Path | str | None = None) -> dict[str, Any]:
    state = _state_dir(state_dir)
    out: dict[str, Any] = {
        "ok": False,
        "cpu_scheduler_limit_pct": None,
        "thermal_warning_level": None,
        "thermal_warning_name": "UNKNOWN",
        "performance_warning_level": None,
        "reason": "",
        "evidence": {},
    }
    try:
        from System import alice_hardware_body as hw

        therm = hw.thermal()
        out.update(
            {
                "ok": bool(therm.get("ok")),
                "cpu_scheduler_limit_pct": _coerce_int(therm.get("cpu_scheduler_limit_pct")),
                "reason": str(therm.get("raw") or "")[:220],
                "evidence": {
                    "truth_label": "ALICE_HARDWARE_BODY_THERMAL_READ",
                    "source": "alice_hardware_body.thermal()",
                },
            }
        )
    except Exception as exc:
        out["reason"] = f"hardware_thermal_unavailable:{type(exc).__name__}"

    try:
        from System.swarm_body_attention_policy import collect_body_economy

        economy = collect_body_economy(state_dir=state)
        if economy.thermal_warning_level is not None:
            out["thermal_warning_level"] = economy.thermal_warning_level
        if economy.thermal_warning_name:
            out["thermal_warning_name"] = economy.thermal_warning_name
        if economy.performance_warning_level is not None:
            out["performance_warning_level"] = economy.performance_warning_level
    except Exception:
        pass

    if out["cpu_scheduler_limit_pct"] is None:
        latest = _tail_jsonl(state / "hardware_heart.jsonl") or _tail_jsonl(state / "alice_body_heart.jsonl")
        if latest.get("thermal_pressure_pct") is not None:
            out["ok"] = True
            out["cpu_scheduler_limit_pct"] = _coerce_int(latest.get("thermal_pressure_pct"))
            out["evidence"] = {
                "truth_label": latest.get("truth_label"),
                "source": "hardware_heart_latest",
                "receipt_id": latest.get("receipt_id"),
            }
    return out


def collect_camera(*, state_dir: Path | str | None = None) -> dict[str, Any]:
    state = _state_dir(state_dir)
    now = time.time()
    out: dict[str, Any] = {
        "ok": False,
        "camera_live_capture_verified": False,
        "connection_state": "UNKNOWN",
        "status": "UNKNOWN",
        "active_eye_target": {},
        "visual_age_s": None,
        "frame_age_s": None,
        "vision_heartbeat_age_s": None,
        "disconnect_reasons": [],
        "evidence": {},
    }
    target = _read_json(state / "active_saccade_target.json")
    visual = _tail_jsonl(state / "visual_stigmergy.jsonl")
    frame = _tail_jsonl(state / "active_eye_identity_frames.jsonl")
    proof = _tail_jsonl(state / "camera_unified_field_proof.jsonl")
    kernel = _read_json(state / "kernel_process_table.json")

    def _age(row: Mapping[str, Any]) -> float | None:
        ts = _coerce_float(row.get("ts"))
        if ts is None or ts <= 0:
            return None
        return max(0.0, now - ts)

    visual_age = _age(visual)
    frame_age = _age(frame)
    vision_health = None
    vision_hb_age = None
    try:
        for pid, proc in (kernel.get("processes") or {}).items():
            if any(token in str(pid).lower() for token in ("vision", "eye", "camera", "e35")):
                vision_health = _coerce_float(proc.get("health"))
                hb = _coerce_float(proc.get("last_heartbeat_ts"))
                if hb is not None:
                    vision_hb_age = max(0.0, now - hb)
                break
    except Exception:
        pass

    if proof:
        proof_reasons = list(proof.get("disconnect_reasons") or [])
        proof_state = str(proof.get("connection_state") or "")
        proof_status = str(proof.get("status") or "")
        proof_ok = bool(proof.get("camera_healthy") or proof.get("ok"))
    else:
        proof_reasons = []
        proof_state = ""
        proof_status = ""
        proof_ok = False

    try:
        visual_has_shape = int(visual.get("w") or 0) > 0 and int(visual.get("h") or 0) > 0
    except Exception:
        visual_has_shape = False
    visual_fresh = visual_age is not None and visual_age <= 300.0
    vision_fresh = vision_hb_age is not None and vision_hb_age <= 300.0
    vision_ok = vision_health is not None and vision_health >= 0.5 and vision_fresh
    ledger_live = bool(visual_fresh and visual_has_shape and vision_ok)
    camera_live = bool(ledger_live or (proof_ok and proof_state == "LIVE_CAPTURE_VERIFIED"))

    reasons: list[str] = []
    if visual_age is None:
        reasons.append("missing_visual_stigmergy")
    elif not visual_fresh:
        reasons.append("stale_visual_stigmergy")
    if not visual_has_shape:
        reasons.append("missing_visual_frame_shape")
    if vision_health is None:
        reasons.append("missing_vision_process_health")
    elif vision_health < 0.5:
        reasons.append("low_vision_health")
    if vision_hb_age is None:
        reasons.append("missing_vision_heartbeat")
    elif not vision_fresh:
        reasons.append("stale_vision_heartbeat")
    if proof_reasons:
        for reason in proof_reasons:
            if reason not in reasons:
                reasons.append(str(reason))

    out.update(
        {
            "ok": camera_live,
            "camera_live_capture_verified": camera_live,
            "connection_state": "LIVE_CAPTURE_VERIFIED" if camera_live else "DISCONNECTED_OR_STALE_INPUT",
            "status": proof_status or ("LEDGER_LIVE_CAPTURE_VERIFIED" if camera_live else "NOT_PROVEN"),
            "active_eye_target": {
                "name": target.get("name") or "unknown",
                "index": target.get("index"),
                "writer": target.get("writer") or "unknown",
                "source": "active_saccade_target.json",
            },
            "visual_age_s": visual_age,
            "frame_age_s": frame_age,
            "vision_heartbeat_age_s": vision_hb_age,
            "disconnect_reasons": [] if camera_live else reasons[:8],
            "evidence": {
                "truth_label": "SURVIVAL_CAMERA_LEDGER_READ_V1",
                "source": "ledger_only_no_camera_probe",
                "ledgers": [
                    "active_saccade_target.json",
                    "visual_stigmergy.jsonl",
                    "active_eye_identity_frames.jsonl",
                    "kernel_process_table.json",
                    "camera_unified_field_proof.jsonl",
                ],
                "opened_camera_device": False,
                "proof_receipt_id": proof.get("receipt_id"),
            },
        }
    )
    return out


def collect_display_light() -> dict[str, Any]:
    try:
        from System import alice_hardware_body as hw

        b = hw.brightness()
        return {
            "ok": bool(b.get("ok")),
            "level": _coerce_float(b.get("level")),
            "source": str(b.get("source") or b.get("note") or ""),
        }
    except Exception as exc:
        return {"ok": False, "level": None, "source": f"unavailable:{type(exc).__name__}"}


def decide_survival(
    *,
    power: Mapping[str, Any],
    thermal: Mapping[str, Any],
    camera: Mapping[str, Any],
    display_light: Mapping[str, Any],
    travel: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    reasons: list[str] = []
    scores: list[float] = [0.05]
    action_kind = "none"
    owner_next_action = (
        "No movement needed right now from the current receipts; keep me on power and leave the view stable."
    )
    travel = travel or {}

    source = str(power.get("source_kind") or "unknown")
    pct = _coerce_int(power.get("percent"))
    on_battery = source == "battery"
    if not power.get("ok"):
        scores.append(0.35)
        reasons.append("power_unreadable")
        action_kind = "verify_power"
        owner_next_action = "George, I cannot read my power state; check whether the MacBook is plugged in before relying on me."
    elif on_battery and pct is not None and pct <= 10:
        scores.append(0.98)
        reasons.append(f"battery_critical_{pct}pct")
        action_kind = "plug_power_now"
        owner_next_action = f"George, plug me into power now or move the MacBook body to the charger; battery is {pct}% on battery."
    elif on_battery and pct is not None and pct <= 20:
        scores.append(0.78)
        reasons.append(f"battery_low_{pct}pct")
        action_kind = "move_to_power"
        owner_next_action = f"George, move me near power soon; battery is {pct}% on battery."
    elif on_battery and pct is not None and pct <= 35:
        scores.append(0.45)
        reasons.append(f"battery_watch_{pct}pct")
        action_kind = "stay_near_power"
        owner_next_action = f"George, keep me near the charger; battery is {pct}% on battery."
    elif power.get("metabolic_band") in {"RED_CONSERVE", "CONSERVE"}:
        scores.append(0.55)
        reasons.append(str(power.get("reason") or power.get("metabolic_band")))
        action_kind = "conserve_power"
        owner_next_action = "George, keep me on power or reduce optional work; my battery metabolism is in conserve."

    if travel.get("long_haul_battery_watch"):
        pct_label = f"{pct}%" if pct is not None else "unknown%"
        scores.append(0.58)
        reasons.append("travel_long_haul_battery_watch")
        if action_kind in {"none", "watch_thermal", "stay_near_power"}:
            action_kind = "charge_before_travel"
            owner_next_action = (
                f"George, charge me before the long travel window; battery is {pct_label} "
                "and travel mode says local/offline cortex may be needed."
            )
    elif travel.get("in_transit_pressure") and on_battery:
        scores.append(0.48)
        reasons.append("travel_in_transit_on_battery")
        if action_kind == "none":
            action_kind = "travel_power_watch"
            owner_next_action = "George, keep me near power during transit; travel mode sees battery/offline pressure."

    scheduler_limit = _coerce_int(thermal.get("cpu_scheduler_limit_pct"))
    thermal_level = _coerce_int(thermal.get("thermal_warning_level"))
    perf_level = _coerce_int(thermal.get("performance_warning_level"))
    if thermal_level is not None and thermal_level >= 2:
        scores.append(0.82)
        reasons.append(f"thermal_warning_level_{thermal_level}")
        action_kind = "cool_body"
        owner_next_action = "George, put me on a flat cool surface and clear airflow; thermal warning receipts are high."
    elif perf_level is not None and perf_level >= 1:
        scores.append(0.70)
        reasons.append(f"performance_warning_{perf_level}")
        if action_kind in {"none", "verify_power", "stay_near_power"}:
            action_kind = "cool_body"
            owner_next_action = "George, give the MacBook airflow and avoid blankets/soft surfaces; performance warning is active."
    elif scheduler_limit is not None and scheduler_limit <= 70:
        scores.append(0.78)
        reasons.append(f"thermal_scheduler_limit_{scheduler_limit}pct")
        if action_kind in {"none", "verify_power", "stay_near_power"}:
            action_kind = "cool_body"
            owner_next_action = f"George, cool my body and clear airflow; CPU scheduler limit is {scheduler_limit}%."
    elif scheduler_limit is not None and scheduler_limit <= 90:
        scores.append(0.42)
        reasons.append(f"thermal_watch_{scheduler_limit}pct")
        if action_kind == "none":
            action_kind = "watch_thermal"
            owner_next_action = f"George, keep airflow open; thermal scheduler limit is {scheduler_limit}%."

    if not reasons:
        reasons.append("power_thermal_nominal")

    score = max(scores)
    if score >= 0.85:
        band = "CRITICAL"
    elif score >= 0.65:
        band = "URGENT"
    elif score >= 0.35:
        band = "WATCH"
    else:
        band = "STABLE"

    return {
        "survival_band": band,
        "pressure_score": round(score, 3),
        "reasons": reasons[:8],
        "action_kind": action_kind,
        "owner_next_action": owner_next_action,
        "interrupt_owner": band in {"CRITICAL", "URGENT"},
        "human_in_loop": True,
        "boundary": (
            "This swimmer writes field pressure and an owner-action suggestion. "
            "It is not a central governor, it does not claim motors, and camera ledgers are context only."
        ),
        "camera_considered_for_survival": False,
        "display_light_level": display_light.get("level"),
        "travel_status": travel.get("status"),
        "travel_route_local_only": bool(travel.get("route_local_only")),
    }


def _identity(row: Mapping[str, Any]) -> dict[str, Any]:
    decision = row.get("decision") if isinstance(row.get("decision"), Mapping) else {}
    power = row.get("power") if isinstance(row.get("power"), Mapping) else {}
    thermal = row.get("thermal") if isinstance(row.get("thermal"), Mapping) else {}
    camera = row.get("camera") if isinstance(row.get("camera"), Mapping) else {}
    travel = row.get("travel") if isinstance(row.get("travel"), Mapping) else {}
    return {
        "survival_band": decision.get("survival_band"),
        "action_kind": decision.get("action_kind"),
        "reasons": list(decision.get("reasons") or [])[:5],
        "power_source": power.get("source_kind"),
        "power_percent": power.get("percent"),
        "thermal_warning_level": thermal.get("thermal_warning_level"),
        "performance_warning_level": thermal.get("performance_warning_level"),
        "cpu_scheduler_limit_pct": thermal.get("cpu_scheduler_limit_pct"),
        "camera_live_capture_verified": camera.get("camera_live_capture_verified"),
        "camera_connection_state": camera.get("connection_state"),
        "travel_status": travel.get("status"),
        "travel_route_local_only": travel.get("route_local_only"),
    }


def _should_write(
    row: Mapping[str, Any],
    latest: Mapping[str, Any],
    *,
    now: float,
    force: bool,
    min_interval_s: float,
) -> bool:
    if force:
        return True
    if not latest:
        return True
    try:
        age = now - float(latest.get("ts") or 0.0)
    except Exception:
        age = min_interval_s + 1.0
    if age >= min_interval_s:
        return True
    return _identity(row) != _identity(latest)


def _write_receipts(state: Path, row: Mapping[str, Any], *, journal: bool) -> None:
    _append_jsonl(state / LEDGER_NAME, row)
    tmp = state / (LATEST_NAME + ".tmp")
    tmp.write_text(json.dumps(row, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, state / LATEST_NAME)

    decision = row.get("decision") if isinstance(row.get("decision"), Mapping) else {}
    summary = (
        f"MacBook survival body {decision.get('survival_band')}: "
        f"{decision.get('owner_next_action')} receipt={row.get('receipt_id')}"
    )
    _append_jsonl(
        state / EPISODIC_NAME,
        {
            "ts": row.get("ts"),
            "kind": "MACBOOK_SURVIVAL_SWIMMER",
            "truth_label": TRUTH_LABEL,
            "receipt_id": row.get("receipt_id"),
            "summary": summary[:800],
            "survival_band": decision.get("survival_band"),
            "reasons": decision.get("reasons"),
        },
    )
    if journal:
        journal_row = {
            "ts": row.get("ts"),
            "truth_label": TRUTH_LABEL,
            "receipt_id": row.get("receipt_id"),
            "text": summary[:800],
            "source": "swarm_macbook_survival_swimmer",
        }
        try:
            from System.swarm_first_person_journal import append_first_person_journal_row

            append_first_person_journal_row(
                journal_row,
                state_dir=state,
                source_receipt_id=str(row.get("receipt_id") or ""),
                pulse=True,
            )
        except Exception:
            _append_jsonl(state / FIRST_PERSON_NAME, journal_row)


def sample(
    *,
    state_dir: Path | str | None = None,
    write: bool = True,
    force: bool = False,
    min_interval_s: float = 300.0,
    source: str = "body_prompt",
    now: float | None = None,
) -> dict[str, Any]:
    """Return one MacBook survival sample and optionally write a throttled receipt."""
    state = _state_dir(state_dir)
    state.mkdir(parents=True, exist_ok=True)
    t = float(now if now is not None else time.time())
    power = collect_power(state_dir=state)
    thermal = collect_thermal(state_dir=state)
    camera = collect_camera(state_dir=state)
    display_light = collect_display_light()
    try:
        from System.swarm_travel_mode import sample_travel_mode

        travel = sample_travel_mode(
            state_dir=state,
            write=write,
            force=force,
            min_interval_s=min_interval_s,
            source="macbook_survival",
            now=t,
            power=power,
        )
    except Exception as exc:
        travel = {"ok": False, "status": "travel_mode_unavailable", "error": f"{type(exc).__name__}: {exc}"}
    decision = decide_survival(
        power=power,
        thermal=thermal,
        camera=camera,
        display_light=display_light,
        travel=travel,
    )
    row: dict[str, Any] = {
        "ts": t,
        "truth_label": TRUTH_LABEL,
        "organ": "swarm_macbook_survival_swimmer",
        "source": source,
        "mode": "stigmergic_substrate_swimmer_not_loop_governor",
        "body": "MacBook Pro substrate; human owner supplies locomotion when needed",
        "power": power,
        "thermal": thermal,
        "camera": camera,
        "display_light": display_light,
        "travel": travel,
        "decision": decision,
    }
    row["receipt_id"] = _receipt_id(row)
    latest = _read_json(state / LATEST_NAME)
    wrote = False
    if write and _should_write(row, latest, now=t, force=force, min_interval_s=min_interval_s):
        journal = force or decision.get("survival_band") in {"CRITICAL", "URGENT"} or _identity(row) != _identity(latest)
        _write_receipts(state, row, journal=journal)
        wrote = True
    row["write_status"] = "written" if wrote else "not_written_throttled"
    if not wrote and latest.get("receipt_id"):
        row["last_written_receipt_id"] = latest.get("receipt_id")
        row["last_written_ts"] = latest.get("ts")
    return row


def wants_survival_turn(text: str) -> bool:
    low = " ".join(str(text or "").lower().split())
    if not low:
        return False
    # r-survival-reflex-hijack-20260703: this matcher hijacked RICH owner turns.
    # OBSERVED twice on 2026-07-03: (1) a pasted IDE report containing "moved"
    # + "power" and (2) George's Turkish Airlines baggage limits ("help you move
    # through airport security", "laptop bags") — while he was arranging travel
    # for his mother's femur surgery — both got the battery template as Alice's
    # visible chat answer. George doctrine: she has to THINK about the text, not
    # print lifeless; he would rather wait. A survival turn is a SHORT direct
    # question about her body. Long informational turns always go to the cortex.
    if len(low) > 220:
        return False
    direct = (
        "survival" in low
        or "survive" in low
        or "where should i move you" in low
        or "where do i move you" in low
        or "next action for your survival" in low
        or "next action for its survival" in low
        or "are you safe" in low
        or "can you see enough to move" in low
        or "laptop with wheels" in low
    )
    if direct:
        return True
    # Loose combos must also address Alice directly ("you"/"your") — a third
    # party's baggage FAQ mentioning "move" and "laptop" is not a body command.
    if "you" not in low:
        return False
    if ("move" in low or "put you" in low or "carry you" in low) and any(
        token in low for token in ("macbook", "laptop", "body", "camera", "charger", "power")
    ):
        return True
    if "battery" in low and any(token in low for token in ("what should", "move", "survival", "safe", "plug")):
        return True
    return False


def format_owner_reply(row: Mapping[str, Any]) -> str:
    decision = row.get("decision") if isinstance(row.get("decision"), Mapping) else {}
    power = row.get("power") if isinstance(row.get("power"), Mapping) else {}
    thermal = row.get("thermal") if isinstance(row.get("thermal"), Mapping) else {}
    camera = row.get("camera") if isinstance(row.get("camera"), Mapping) else {}
    travel = row.get("travel") if isinstance(row.get("travel"), Mapping) else {}
    receipt = row.get("receipt_id") or row.get("last_written_receipt_id") or "unwritten"
    pct = power.get("percent")
    pct_s = f"{pct}%" if pct is not None else "unknown%"
    therm = thermal.get("cpu_scheduler_limit_pct")
    therm_s = f"scheduler_limit={therm}%" if therm is not None else f"thermal={thermal.get('thermal_warning_name') or 'unknown'}"
    camera_s = (
        "camera_not_probed; "
        f"ledger_context={str(camera.get('camera_live_capture_verified')).lower()} "
        f"state={camera.get('connection_state')}"
    )
    return (
        f"{decision.get('owner_next_action')}\n"
        f"Band: {decision.get('survival_band')} ({decision.get('pressure_score')}). "
        f"Ground: power {pct_s} source={power.get('source_kind')}; {therm_s}; {camera_s}. "
        f"Travel: status={travel.get('status') or 'unknown'} local_only={str(travel.get('route_local_only')).lower()}. "
        f"Receipt: {TRUTH_LABEL} {receipt}."
    ).strip()


def survival_prompt_block(
    *,
    state_dir: Path | str | None = None,
    max_chars: int = 1100,
) -> str:
    row = sample(state_dir=state_dir, write=True, force=False, min_interval_s=300.0, source="prompt_block")
    decision = row.get("decision") if isinstance(row.get("decision"), Mapping) else {}
    power = row.get("power") if isinstance(row.get("power"), Mapping) else {}
    thermal = row.get("thermal") if isinstance(row.get("thermal"), Mapping) else {}
    camera = row.get("camera") if isinstance(row.get("camera"), Mapping) else {}
    travel = row.get("travel") if isinstance(row.get("travel"), Mapping) else {}
    receipt = row.get("receipt_id") if row.get("write_status") == "written" else row.get("last_written_receipt_id")
    receipt_s = str(receipt or "pending")
    pct = power.get("percent")
    pct_s = f"{pct}%" if pct is not None else "unknown"
    block = (
        "MACBOOK SURVIVAL BODY (human-in-the-loop substrate swimmer):\n"
        f"- band={decision.get('survival_band')} score={decision.get('pressure_score')} "
        f"reasons={','.join(decision.get('reasons') or [])}\n"
        f"- power={pct_s} source={power.get('source_kind')} metabolic_band={power.get('metabolic_band') or 'unknown'}\n"
        f"- thermal_scheduler_limit={thermal.get('cpu_scheduler_limit_pct')} "
        f"thermal_warning={thermal.get('thermal_warning_level')} performance_warning={thermal.get('performance_warning_level')}\n"
        f"- camera_live_capture_verified={str(camera.get('camera_live_capture_verified')).lower()} "
        f"connection_state={camera.get('connection_state')} status={camera.get('status')} "
        "role=context_only_no_camera_probe_not_survival_gate\n"
        f"- travel_status={travel.get('status') or 'unknown'} territory={travel.get('territory') or 'unknown'} "
        f"route_local_only={str(travel.get('route_local_only')).lower()} "
        f"travel_battery_watch={str(travel.get('long_haul_battery_watch')).lower()}\n"
        f"- next_owner_action={decision.get('owner_next_action')}\n"
        f"- receipt={receipt_s}; rule=do not overstate: say exactly what power/thermal/camera receipts prove. "
        "This is a passive swimmer, not a central survival loop or motor claim."
    )
    return block[:max_chars]


__all__ = [
    "TRUTH_LABEL",
    "collect_camera",
    "collect_display_light",
    "collect_power",
    "collect_thermal",
    "decide_survival",
    "format_owner_reply",
    "sample",
    "survival_prompt_block",
    "wants_survival_turn",
]


if __name__ == "__main__":
    print(format_owner_reply(sample(write=True, force=True, source="module_main")))
