#!/usr/bin/env python3
"""Heartbeat-synchronized sparse visual blink.

r1026: George/Fable doctrine says Alice should not archive a surveillance
stream. The existing eye already writes photon math into
``visual_stigmergy.jsonl``. This bridge rides the hardware heartbeat, reads that
existing eye field, keeps only compact meaning/delta rows, and discards any
frame reference before persistence.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

try:
    from System.jsonl_file_lock import append_line_locked, read_text_locked
except Exception:  # pragma: no cover
    append_line_locked = None  # type: ignore[assignment]
    read_text_locked = None  # type: ignore[assignment]


_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

TRUTH_LABEL = "SIFTA_SACCADIC_BLINK_VISION_V1"
BLINK_LEDGER_NAME = "saccadic_blink_vision.jsonl"
SNAPSHOT_NAME = "saccadic_blink_vision.json"
WORLD_FEED_LEDGER_NAME = "latent_world_model_visual_feed.jsonl"
TWO_TURN_PROBE_LEDGER_NAME = "two_turn_receipt_gate_probe.jsonl"

ESCALATION_REASONS = {
    "owner_spoke",
    "owner_typed",
    "effector_preflight",
    "manual",
    "slash",
    "test_force",
}

FRAME_PATH_KEYS = {
    "path",
    "frame_path",
    "image_path",
    "file_path",
    "raw_frame",
    "raw_pixels",
    "bytes",
    "png",
    "jpg",
}


DescribeFn = Callable[[dict[str, Any]], Mapping[str, Any] | str | None]


@dataclass(frozen=True)
class BlinkConfig:
    visual_fresh_s: float = 2.0
    proof_stale_s: float = 2.0
    motion_threshold: float = 0.01
    saliency_threshold: float = 0.22
    idle_decimate_beats: int = 1
    enable_local_vlm: bool = False

    @classmethod
    def from_env(cls) -> "BlinkConfig":
        def _float(name: str, default: float) -> float:
            try:
                return float(os.environ.get(name, default))
            except Exception:
                return default

        def _int(name: str, default: int) -> int:
            try:
                return max(1, int(os.environ.get(name, default)))
            except Exception:
                return default

        enabled = os.environ.get("SIFTA_BLINK_ENABLE_LOCAL_VLM", "").strip().lower()
        return cls(
            visual_fresh_s=_float("SIFTA_BLINK_VISUAL_FRESH_S", 2.0),
            proof_stale_s=_float("SIFTA_BLINK_PROOF_STALE_S", 2.0),
            motion_threshold=_float("SIFTA_BLINK_MOTION_THRESHOLD", 0.01),
            saliency_threshold=_float("SIFTA_BLINK_SALIENCY_THRESHOLD", 0.22),
            idle_decimate_beats=_int("SIFTA_BLINK_IDLE_DECIMATE_N", 1),
            enable_local_vlm=enabled in {"1", "true", "yes", "on"},
        )


def _state_dir(state_dir: Path | str | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else _STATE


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(dict(row), ensure_ascii=False, sort_keys=True, default=str) + "\n"
    if append_line_locked is not None:
        append_line_locked(path, line, encoding="utf-8")
    else:  # pragma: no cover
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)


def _read_jsonl_tail(path: Path, limit: int = 20, max_bytes: int = 256_000) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        if read_text_locked is not None and path.stat().st_size <= max_bytes:
            text = read_text_locked(path, encoding="utf-8", errors="replace")
        else:
            with path.open("rb") as handle:
                handle.seek(0, os.SEEK_END)
                size = handle.tell()
                handle.seek(max(0, size - max_bytes))
                text = handle.read().decode("utf-8", errors="replace")
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    for line in text.splitlines()[-max(1, limit):]:
        line = line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except Exception:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _latest(path: Path) -> dict[str, Any]:
    rows = _read_jsonl_tail(path, 1)
    return rows[-1] if rows else {}


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _age(now: float, row: Mapping[str, Any]) -> float | None:
    try:
        ts = float(row.get("ts") or row.get("timestamp") or row.get("t") or 0.0)
    except Exception:
        return None
    if ts <= 0:
        return None
    return max(0.0, now - ts)


def _sanitize_visual(row: Mapping[str, Any], *, now: float) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in (
        "ts",
        "sha8",
        "w",
        "h",
        "entropy_bits",
        "saliency_peak",
        "motion_mean",
        "hue_deg",
        "grid_size",
        "total_cells",
        "source_thumb_px",
        "active_app_focus",
        "source",
        "stigmergic_label",
    ):
        if key in row:
            out[key] = row.get(key)
    out["age_s"] = _age(now, row)
    return out


def _sanitize_face(row: Mapping[str, Any], *, now: float) -> dict[str, Any]:
    return {
        "age_s": _age(now, row),
        "faces_detected": int(row.get("faces_detected") or 0),
        "audience": str(row.get("audience") or ""),
        "confidence": row.get("confidence"),
        "error": row.get("error"),
    }


def _semantic_labels(
    visual: Mapping[str, Any],
    face: Mapping[str, Any],
    *,
    meaningful_reason: str,
    eye_id: str = "",
    eye_role: str = "",
) -> list[str]:
    labels = ["heartbeat_blink", f"reason:{meaningful_reason}"]
    if eye_id:
        labels.append(f"eye:{eye_id}")
    if eye_role:
        labels.append(f"eye_role:{eye_role}")
    if visual.get("sha8"):
        labels.append("visual_delta:" + str(visual.get("sha8")))
    if visual.get("w") and visual.get("h"):
        labels.append(f"frame_shape:{visual.get('w')}x{visual.get('h')}")
    motion = _coerce_float(visual.get("motion_mean"))
    if motion:
        labels.append(f"motion:{motion:.3f}")
    sal = _coerce_float(visual.get("saliency_peak"))
    if sal:
        labels.append(f"saliency:{sal:.3f}")
    faces = int(face.get("faces_detected") or 0)
    if faces > 0:
        labels.append("face_present")
        audience = str(face.get("audience") or "unknown")
        labels.append(f"audience:{audience}")
    else:
        labels.append("no_face")
    return labels[:12]


def _redacted_row_hash(row: Mapping[str, Any]) -> str:
    safe = {k: v for k, v in row.items() if k not in FRAME_PATH_KEYS}
    body = json.dumps(safe, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


def _collect_object_provenance(
    state: Path,
    object_key: str | None,
    *,
    max_rows_per_ledger: int = 20,
    max_hits: int = 4,
) -> list[dict[str, Any]]:
    """Collect compact receipt snippets for a stable gaze target.

    George's r1027+ stare doctrine says a familiar object should deepen from
    current facts into provenance only when attention keeps returning to it.
    This helper searches existing owner/body ledgers and returns tiny snippets;
    it does not invent object history and it stores no pixels.
    """
    if not object_key:
        return []

    key = str(object_key).lower()
    query_terms = {key}
    if key.startswith("sha8:"):
        # A visual hash is stable but semantically opaque. Keep it as evidence,
        # then add owner-coined anchors from this doctrine so a pizza/USB memory
        # row can be found without pretending the hash names the object.
        query_terms.update({"pizza", "discount", "sale", "usb", "adaptor", "adapter"})
    else:
        query_terms.update(part for part in key.replace(":", " ").replace("_", " ").split() if part)

    ledgers = (
        "architect_day_segments.jsonl",
        "day_segments.jsonl",
        "work_receipts.jsonl",
        "affective_valence.jsonl",
        "owner_body_events.jsonl",
        "alice_first_person_journal.jsonl",
    )
    hits: list[dict[str, Any]] = []
    for ledger_name in ledgers:
        p = state / ledger_name
        if not p.exists():
            continue
        for ln in _read_jsonl_tail(p, max_rows_per_ledger):
            txt = json.dumps(ln, ensure_ascii=False, sort_keys=True, default=str).lower()
            if not any(term and term in txt for term in query_terms):
                continue
            hits.append(
                {
                    "ledger": ledger_name,
                    "matched_terms": sorted(term for term in query_terms if term and term in txt)[:6],
                    "snippet": json.dumps(ln, ensure_ascii=False, sort_keys=True, default=str)[:180],
                    "ts": ln.get("ts"),
                }
            )
            if len(hits) >= max_hits:
                return hits
    return hits


def _previous_blink(state: Path) -> dict[str, Any]:
    return _latest(state / BLINK_LEDGER_NAME)


def _meaningful_delta(
    *,
    visual: Mapping[str, Any],
    face: Mapping[str, Any],
    previous: Mapping[str, Any],
    reason: str,
    config: BlinkConfig,
) -> tuple[bool, str]:
    if reason in ESCALATION_REASONS:
        return True, f"attention_escalation:{reason}"
    if not previous:
        return True, "first_blink"
    prior_visual = previous.get("visual") if isinstance(previous.get("visual"), dict) else {}
    prior_face = previous.get("face") if isinstance(previous.get("face"), dict) else {}
    if visual.get("sha8") and visual.get("sha8") != prior_visual.get("sha8"):
        return True, "sha8_changed"
    if abs(_coerce_float(visual.get("motion_mean"))) >= config.motion_threshold:
        return True, "motion_threshold"
    if abs(_coerce_float(visual.get("saliency_peak"))) >= config.saliency_threshold:
        return True, "saliency_threshold"
    if int(face.get("faces_detected") or 0) != int(prior_face.get("faces_detected") or 0):
        return True, "face_presence_changed"
    if str(face.get("audience") or "") != str(prior_face.get("audience") or ""):
        return True, "face_audience_changed"
    return False, "no_meaningful_delta"


def _should_decimate_idle(
    *,
    visual: Mapping[str, Any],
    face: Mapping[str, Any],
    previous: Mapping[str, Any],
    reason: str,
    config: BlinkConfig,
) -> bool:
    if reason in ESCALATION_REASONS or config.idle_decimate_beats <= 1:
        return False
    if not previous:
        return False
    if int(face.get("faces_detected") or 0) > 0:
        return False
    if abs(_coerce_float(visual.get("motion_mean"))) >= config.motion_threshold:
        return False
    try:
        beat_index = int(previous.get("beat_index") or 0) + 1
    except Exception:
        beat_index = 1
    return beat_index % config.idle_decimate_beats != 0


def _capture_world_eye_frame(state: Path) -> str | None:
    """Capture one frame from the world_eye (USB camera, identity-bound) for a
    co-watch description.

    Resolves the world_eye's current index by identity (vid:pid / unique_id),
    never a hardcoded index, then grabs a single frame via the iris. Returns the
    saved frame path, or ``None`` when the eye is not capturable (no cv2, no
    camera, permission denied). Never raises — the eye must degrade gracefully,
    and a ``None`` here makes the describer return an honest "unavailable" rather
    than describing the owner camera as the shared screen.
    """
    idx: int | None = None
    try:
        from System.swarm_eye_registry import eye_for_role

        rec = eye_for_role("world_eye", state_dir=state) or {}
        ci = rec.get("current_index")
        idx = int(ci) if ci is not None else None
    except Exception:
        idx = None
    if idx is None:
        try:
            from System.swarm_camera_target import index_for_name

            idx = index_for_name("usb camera vid:1133 pid:2081")
        except Exception:
            idx = None
    if idx is None:
        return None
    try:
        from System.swarm_iris import webcam_frame

        frame = webcam_frame(
            camera_index=int(idx),
            tag="world_eye_cowatch",
            save_to_disk=True,
            grab_timeout_s=1.5,
        )
    except Exception:
        return None
    if frame is None:
        return None
    path = getattr(frame, "file_path", "") or ""
    return path or None


def _world_eye_metadata_general_label(blink_context: Mapping[str, Any]) -> dict[str, Any] | None:
    """General co-watch label from receipt metadata only; never a title guess."""
    eye_role = str(blink_context.get("eye_role") or blink_context.get("eye_id") or "")
    if eye_role != "world_eye" or not blink_context.get("co_watch_active"):
        return None
    visual = blink_context.get("visual") if isinstance(blink_context.get("visual"), Mapping) else {}
    labels = blink_context.get("semantic_labels") if isinstance(blink_context.get("semantic_labels"), list) else []
    marker_text = " ".join(
        str(x or "")
        for x in (
            visual.get("source"),
            visual.get("stigmergic_label"),
            visual.get("truth"),
            *labels,
        )
    ).lower()
    media_marked = any(
        marker in marker_text
        for marker in ("observed_media", "co_watch", "cowatch", "youtube", "media")
    )
    if not media_marked:
        return None
    shape = ""
    if visual.get("w") and visual.get("h"):
        shape = f" frame_shape={visual.get('w')}x{visual.get('h')}"
    motion = _coerce_float(visual.get("motion_mean"))
    saliency = _coerce_float(visual.get("saliency_peak"))
    evidence = (
        f"source={visual.get('source') or 'unknown'} "
        f"label={visual.get('stigmergic_label') or 'unknown'}"
        f"{shape} motion={motion:.3f} saliency={saliency:.3f}"
    )
    return {
        "status": "ok",
        "source": "world_eye_metadata_general_label",
        "eye_role": "world_eye",
        "specificity": "general",
        "title_identified": False,
        "description": (
            "fresh world_eye co-watch visual receipt: a screen/video media surface is present; "
            "specific title, person, and plot are not identified by this receipt. "
            + evidence
        )[:800],
    }


def _default_description(blink_context: dict[str, Any]) -> dict[str, Any]:
    visual = blink_context.get("visual") or {}
    face = blink_context.get("face") or {}
    labels = blink_context.get("semantic_labels") or []
    if not blink_context.get("enable_local_vlm"):
        return {
            "status": "skipped",
            "source": "metadata_delta_default",
            "description": "; ".join(str(x) for x in labels[:6]),
        }
    eye_role = str(blink_context.get("eye_role") or blink_context.get("eye_id") or "owner_eye")
    state = _state_dir(blink_context.get("state_dir"))
    # Pacino guard (no false co-watch): the world_eye MUST describe a world_eye
    # frame. If no fresh world frame exists, return an honest "unavailable" — never
    # fall back to the owner camera's frame and mislabel the owner's room as the
    # thing we are watching together.
    if eye_role == "world_eye":
        wf = blink_context.get("world_frame_path")
        frame = Path(wf) if wf else None
        if frame is None or not frame.exists():
            general = _world_eye_metadata_general_label(blink_context)
            if general:
                return general
            return {
                "status": "unavailable",
                "source": "local_vlm:world_eye",
                "description": "no fresh world_eye frame; refusing to describe the owner frame as co-watch (Pacino guard)",
            }
    else:
        frame = state / "visual_stigmergy_last_frame.jpg"
        if not frame.exists():
            return {
                "status": "unavailable",
                "source": "local_vlm",
                "description": "no existing visual_stigmergy_last_frame.jpg; no frame written by blink organ",
            }
    try:
        from System.swarm_cosmos_reason1 import probe_and_infer

        row = probe_and_infer(
            image_path=frame,
            writer="saccadic_blink_vision",
            max_new_tokens=96,
            use_bridge=os.environ.get("SIFTA_BLINK_VLM_USE_BRIDGE", "1").strip().lower() not in {"0", "false", "no"},
        )
        return {
            "status": str(row.get("truth") or "unknown"),
            "source": "local_vlm:swarm_cosmos_reason1",
            "eye_role": eye_role,
            "description": str(row.get("response") or row.get("detail") or "")[:800],
            "vlm_receipt_truth": row.get("truth"),
        }
    except Exception as exc:
        if eye_role == "world_eye":
            general = _world_eye_metadata_general_label(blink_context)
            if general:
                general["vlm_error"] = f"{type(exc).__name__}: {exc}"[:240]
                return general
        return {
            "status": "error",
            "source": "local_vlm:swarm_cosmos_reason1",
            "eye_role": eye_role,
            "description": f"{type(exc).__name__}: {exc}",
        }


def _normalize_description(value: Mapping[str, Any] | str | None) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str):
        return {"status": "ok", "source": "injected_describer", "description": value}
    return {"status": "empty", "source": "describer", "description": ""}


def _feed_visual_cortex(
    *,
    state: Path,
    blink_row: Mapping[str, Any],
    labels: list[str],
) -> dict[str, Any]:
    try:
        from System.swarm_visual_cortex import process_blink_semantics

        return process_blink_semantics(dict(blink_row), labels, state_dir=state)
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _feed_latent_world_model(
    *,
    state: Path,
    previous: Mapping[str, Any],
    blink_row: Mapping[str, Any],
    labels: list[str],
) -> dict[str, Any]:
    try:
        from System.swarm_latent_world_model import LatentWorldModel

        model = LatentWorldModel(state_dir=state)
        prev_state = json.dumps(previous.get("visual") or {}, sort_keys=True, default=str)
        next_state = json.dumps(blink_row.get("visual") or {}, sort_keys=True, default=str)
        reward = 1.0 if blink_row.get("meaningful_delta") else 0.05
        model.observe_reality(prev_state, "heartbeat_blink", next_state, reward)
        model.save()
        row = {
            "ts": blink_row.get("ts") or time.time(),
            "truth_label": "LATENT_WORLD_MODEL_VISUAL_FEED_V1",
            "source": TRUTH_LABEL,
            "blink_id": blink_row.get("blink_id"),
            "semantic_labels": labels,
            "reward": reward,
            "transition_count": len(model.transitions),
        }
        _append_jsonl(state / WORLD_FEED_LEDGER_NAME, row)
        return {"ok": True, "ledger": WORLD_FEED_LEDGER_NAME, "transition_count": len(model.transitions)}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def probe_two_turn_receipt_gate(*, state_dir: Path | str | None = None, now: float | None = None) -> dict[str, Any]:
    state = _state_dir(state_dir)
    ts = float(now if now is not None else time.time())
    try:
        from System.swarm_two_turn_receipt_gate import LEDGER_NAME, TRUTH_LABEL as GATE_TRUTH, TwoTurnReceiptGate

        gate = TwoTurnReceiptGate("saccadic_blink_probe", state_dir=state)
        ledger = state / LEDGER_NAME
        rows = _read_jsonl_tail(ledger, 8)
        row = {
            "ts": ts,
            "truth_label": "TWO_TURN_RECEIPT_GATE_PROBE_V1",
            "gate_truth_label": GATE_TRUTH,
            "status": "ALIVE" if hasattr(gate, "require") and hasattr(gate, "record") else "BROKEN",
            "ledger": LEDGER_NAME,
            "ledger_exists": ledger.exists(),
            "recent_rows": len(rows),
            "latest_age_s": _age(ts, rows[-1]) if rows else None,
        }
    except Exception as exc:
        row = {
            "ts": ts,
            "truth_label": "TWO_TURN_RECEIPT_GATE_PROBE_V1",
            "status": "ERROR",
            "error": f"{type(exc).__name__}: {exc}",
        }
    _append_jsonl(state / TWO_TURN_PROBE_LEDGER_NAME, row)
    return row


def pulse_saccadic_blink(
    *,
    state_dir: Path | str | None = None,
    heart_row: Mapping[str, Any] | None = None,
    reason: str = "heartbeat",
    eye_id: str | None = None,
    eye_role: str | None = None,
    force: bool = False,
    config: BlinkConfig | None = None,
    describe_fn: DescribeFn | None = None,
    now_fn: Callable[[], float] | None = None,
    write: bool = True,
) -> dict[str, Any]:
    """Run one sparse visual blink over the existing eye ledgers (r1027 per-eye).

    eye_id: "owner_eye" (default, on every beat) or "world_eye" (on beat only during co-watch, decimated otherwise).
    The function never writes image files and strips frame/path fields before
    the blink row is persisted. Meaningful deltas can call a semantic describer;
    unchanged beats still refresh camera proof/staleness.
    Per-eye rows carry eye_id for co_watch_moment binding and registry health.
    """
    state = _state_dir(state_dir)
    cfg = config or BlinkConfig.from_env()
    now = float(now_fn() if now_fn is not None else time.time())
    visual_raw = _latest(state / "visual_stigmergy.jsonl")
    face_raw = _latest(state / "face_detection_events.jsonl")
    visual = _sanitize_visual(visual_raw, now=now)
    face = _sanitize_face(face_raw, now=now)
    previous = _previous_blink(state)
    explicit_eye = (eye_id or "").strip()
    role = (eye_role or "").strip() or (explicit_eye if explicit_eye in {"owner_eye", "world_eye"} else "owner_eye")
    try:
        from System.swarm_eye_registry import default_eye_id

        resolved_eye_id = (eye_id or "").strip() or default_eye_id(role=role, state_dir=state)
    except Exception:
        resolved_eye_id = (eye_id or "").strip() or role

    if force and reason not in ESCALATION_REASONS:
        reason = "manual"
    visual_age = visual.get("age_s")
    visual_fresh = visual_age is not None and float(visual_age) <= cfg.visual_fresh_s
    decimated = bool(_should_decimate_idle(visual=visual, face=face, previous=previous, reason=reason, config=cfg))
    meaningful_reason = "first_blink"

    # r1027+ George object-staring provenance reconstruction (2026-06-12 insight)
    # When attention lingers on one stable object (USB adaptor, pizza in oven), the mind auto-reconstructs
    # its history/provenance/details that would otherwise stay shallow. The object now "carries memory"
    # (the 4 frozen pizzas on sale, forgotten $8 discount, "I was pissed"). 
    # Alice's blink must do analogous: not just current facts on one heartbeat; deeper reconstruction
    # on prolonged stable gaze. 
    # "How long do I stare?": not fixed clock; iterative via heartbeat. Get facts -> other lanes process
    # (audio, interoception, latent) -> come back on next beat if still salient, deepen. Depth gated by
    # metabolism/attention budget (like world-eye decimation), not arbitrary time. This grounds reasoning,
    # reduces "LLM CoT off" by tying to real object provenance in the shared field.
    # Smallest cut: extend this existing blink organ (no new rival eye or ledger).

    # stare tracker for stable object (per eye, in-memory + small state for continuity across beats)
    stare_state_path = state / "blink_stare_state.json"
    stare_state = {}
    try:
        if stare_state_path.exists():
            stare_state = json.loads(stare_state_path.read_text(encoding="utf-8"))
    except Exception:
        pass

    # simple object key from current visual (label or sha for stability; extend later with better embedding)
    object_key = None
    try:
        labels = visual.get("semantic_labels") or []
        if labels:
            object_key = labels[0]  # e.g. "pizza_box", "usb_adaptor"
        elif visual.get("stigmergic_label"):
            object_key = str(visual.get("stigmergic_label"))
        elif visual.get("sha8"):
            object_key = "sha8:" + visual.get("sha8")[:8]
    except Exception:
        pass

    stare_beats = 0
    prev_object = stare_state.get(resolved_eye_id, {}).get("last_object")
    if object_key and prev_object == object_key and not decimated:
        stare_beats = stare_state.get(resolved_eye_id, {}).get("stare_beats", 0) + 1
    elif object_key:
        stare_beats = 1

    # provenance reconstruction on prolonged stare (escalate when stare_beats > threshold or reason escalates)
    object_provenance = []
    if stare_beats >= 3 or reason in ESCALATION_REASONS:  # "stare" depth trigger; iterate via heartbeats
        object_provenance = _collect_object_provenance(state, object_key)
        if object_provenance:
            meaningful_reason = f"provenance_depth_{len(object_provenance)}"

    # persist stare state (small, no raw pixels)
    try:
        stare_state[resolved_eye_id] = {"last_object": object_key, "stare_beats": stare_beats, "last_ts": now}
        stare_state_path.write_text(json.dumps(stare_state, default=str), encoding="utf-8")
    except Exception:
        pass

    # r1027 capture throttle (George order + metabolism gate)
    # World-eye ONLY during declared co-watch; even then decimated by N from metabolism (slow capture default).
    # N defaults 5, pulled from metabolic if available. Emit capture_budget row.
    co_watch_active = False
    try:
        yt = state / "youtube_watch_memory.jsonl"
        if yt.exists():
            last = _read_jsonl_tail(yt, 1)
            if last and ("co_watch" in str(last[0]).lower() or "media" in str(last[0]).lower()):
                co_watch_active = True
        if (state / "co_watch_active.flag").exists():
            co_watch_active = True
    except Exception:
        pass

    if resolved_eye_id == "world_eye":
        if not co_watch_active:
            decimated = True
            meaningful_reason = "world_eye_dark_no_co_watch"
        else:
            # metabolism-gated N
            n = 1
            try:
                from System.swarm_battery_metabolism_organ import sample
                m = sample(write=False) or {}
                if m.get("metabolic", {}).get("conserve"):
                    n = 10
            except Exception:
                pass
            try:
                beat_index = int(previous.get("beat_index") or 0) + 1
            except Exception:
                beat_index = 1
            if beat_index % n != 0:
                decimated = True
                meaningful_reason = f"world_eye_decimated_n={n}"
            # emit budget receipt
            try:
                budget_row = {
                    "ts": now,
                    "truth_label": "CAPTURE_BUDGET_V1",
                    "eye_id": eye_id,
                    "co_watch_active": co_watch_active,
                    "decimation_n": n,
                    "frames_this_session": 0,
                    "power_delta_estimate": 0.01,
                }
                _append_jsonl(state / "capture_budget.jsonl", budget_row)
            except Exception:
                pass

    if not decimated:
        meaningful, meaningful_reason = _meaningful_delta(
            visual=visual,
            face=face,
            previous=previous,
            reason=reason,
            config=cfg,
        )
        if (
            resolved_eye_id == "world_eye"
            and co_watch_active
            and int(face.get("faces_detected") or 0) == 0
            and abs(_coerce_float(visual.get("motion_mean"))) <= 0.0
            and reason not in ESCALATION_REASONS
        ):
            meaningful = False
            meaningful_reason = "no salient world_eye motion_or_face"
    else:
        meaningful = False
    if decimated:
        meaningful = False
        if not meaningful_reason or "decimated" not in str(meaningful_reason):
            meaningful_reason = "idle_decimated"

    labels = _semantic_labels(
        visual,
        face,
        meaningful_reason=meaningful_reason,
        eye_id=resolved_eye_id,
        eye_role=role,
    )
    try:
        beat_index = int(previous.get("beat_index") or 0) + 1
    except Exception:
        beat_index = 1
    blink_id = "blink_" + uuid.uuid4().hex[:12]
    description: dict[str, Any] = {"status": "not_run", "source": "delta_gate", "description": ""}
    visual_cortex: dict[str, Any] = {"ok": False, "skipped": True}
    latent_world: dict[str, Any] = {"ok": False, "skipped": True}
    if meaningful and visual_fresh:
        # World_eye describe path (r1027): when the owner has declared a co-watch,
        # capture the world_eye's OWN frame by identity and describe that. owner_eye
        # stays frugal — its describer is only on when the global flag is set, so we
        # never burn the local VLM on every owner-face twitch.
        world_frame_path: str | None = None
        effective_vlm = cfg.enable_local_vlm
        if resolved_eye_id == "world_eye" and co_watch_active:
            effective_vlm = True
            world_frame_path = _capture_world_eye_frame(state)
        ctx = {
            "blink_id": blink_id,
            "heart_receipt_id": (heart_row or {}).get("receipt_id") if heart_row else None,
            "eye_id": resolved_eye_id,
            "eye_role": role,
            "state_dir": str(state),
            "visual": visual,
            "face": face,
            "semantic_labels": labels,
            "enable_local_vlm": effective_vlm,
            "world_frame_path": world_frame_path,
            "co_watch_active": co_watch_active,
            "meaningful_reason": meaningful_reason,
        }
        description = _normalize_description((describe_fn or _default_description)(ctx))
        visual_cortex = _feed_visual_cortex(state=state, blink_row=ctx, labels=labels)
        latent_world = _feed_latent_world_model(state=state, previous=previous, blink_row=ctx, labels=labels)
        # Pixels die, information lives (r1026): the meaning row persists; drop the
        # captured world frame so no surveillance stream is archived.
        if world_frame_path:
            try:
                Path(world_frame_path).unlink(missing_ok=True)
            except Exception:
                pass

    row: dict[str, Any] = {
        "ts": now,
        "kind": "SACCADIC_BLINK",
        "truth_label": TRUTH_LABEL,
        "blink_id": blink_id,
        "eye_id": resolved_eye_id,
        "eye_role": role,
        "beat_index": beat_index,
        "reason": reason,
        "source": "hardware_heart" if heart_row else (reason if reason in ESCALATION_REASONS else "manual"),
        "heart_receipt_id": (heart_row or {}).get("receipt_id") if heart_row else None,
        "visual_fresh": visual_fresh,
        "visual_age_s": visual_age,
        "camera_staleness_budget_s": cfg.visual_fresh_s,
        "meaningful_delta": bool(meaningful and visual_fresh),
        "meaningful_reason": meaningful_reason,
        "idle_decimated": decimated,
        "privacy_policy": "pixels_die_information_lives_no_frame_archive",
        "frame_persistence": {
            "blink_wrote_frame_file": False,
            "raw_frame_archived": False,
            "persistent_payload": "metadata_and_semantic_labels_only",
        },
        "visual": visual,
        "face": face,
        "semantic_labels": labels,
        "semantic_description": description,
        "visual_cortex": visual_cortex,
        "latent_world_model": latent_world,
        "redacted_visual_hash": _redacted_row_hash(visual),
        "stare_beats": stare_beats,
        "object_key": object_key,
        "object_provenance": object_provenance,
        "provenance_depth": len(object_provenance),
    }
    for key in list(row):
        if key in FRAME_PATH_KEYS:
            row.pop(key, None)

    if write:
        _append_jsonl(state / BLINK_LEDGER_NAME, row)
        (state / SNAPSHOT_NAME).write_text(
            json.dumps(row, ensure_ascii=False, sort_keys=True, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        try:
            from System.swarm_camera_unified_field_proof import build_camera_unified_field_proof

            build_camera_unified_field_proof(state, now=now, stale_s=cfg.proof_stale_s, write_receipt=True)
        except Exception:
            pass
        if beat_index == 1 or beat_index % 60 == 0:
            probe_two_turn_receipt_gate(state_dir=state, now=now)
    return row


def _resolve_owner_frame_path(state: Path) -> tuple[Path | None, float | None]:
    """Best-effort owner camera frame for on-demand describe (no new capture)."""
    now = time.time()
    candidates = (
        state / "owner_body_vision_frames" / "active_eye_latest.png",
        state / "visual_stigmergy_last_frame.jpg",
    )
    best: Path | None = None
    best_age: float | None = None
    for path in candidates:
        try:
            if not path.exists():
                continue
            age = max(0.0, now - float(path.stat().st_mtime))
            if best is None or age < float(best_age or 1e9):
                best, best_age = path, age
        except Exception:
            continue
    return best, best_age


def _owner_describe_prompt(owner_text: str = "") -> str:
    _ = owner_text  # reserved for future owner-specific focus
    return (
        "Describe what the owner is wearing and the visible colors in this MacBook "
        "camera frame. Name shirt/top color, visible clothing, and the scene behind "
        "them. Be specific and brief. Only describe what is visible."
    )


def _run_owner_frame_vlm(frame: Path, *, owner_text: str = "") -> dict[str, Any]:
    """Run local VLM on an owner frame. Pacino guard does not apply to owner_eye."""
    prompt = _owner_describe_prompt(owner_text)
    try:
        from System.swarm_mlx_vlm_brain import describe_image

        text = str(
            describe_image(
                str(frame),
                prompt=prompt,
                max_tokens=220,
                timeout_s=int(os.environ.get("SIFTA_OWNER_DESCRIBE_TIMEOUT_S", "120") or "120"),
            )
            or ""
        ).strip()
        if text and not text.startswith("["):
            return {
                "status": "ok",
                "source": "local_vlm:mlx_vlm_brain",
                "eye_role": "owner_eye",
                "description": text[:800],
            }
        if text:
            return {
                "status": "unavailable",
                "source": "local_vlm:mlx_vlm_brain",
                "eye_role": "owner_eye",
                "description": text[:800],
            }
    except Exception as exc:
        mlx_err = f"{type(exc).__name__}: {exc}"
    else:
        mlx_err = ""

    try:
        from System.swarm_cosmos_reason1 import probe_and_infer

        row = probe_and_infer(
            frame,
            writer="owner_frame_on_demand",
            max_new_tokens=120,
            use_bridge=os.environ.get("SIFTA_BLINK_VLM_USE_BRIDGE", "1").strip().lower()
            not in {"0", "false", "no"},
        )
        response = str(row.get("response") or row.get("detail") or "").strip()
        truth = str(row.get("truth") or "").strip()
        if response and truth == "REAL_INFERENCE":
            return {
                "status": "ok",
                "source": "local_vlm:swarm_cosmos_reason1",
                "eye_role": "owner_eye",
                "description": response[:800],
                "vlm_receipt_truth": truth,
            }
        return {
            "status": "unavailable",
            "source": "local_vlm:swarm_cosmos_reason1",
            "eye_role": "owner_eye",
            "description": response[:800] or "owner-frame VLM route unavailable",
            "vlm_receipt_truth": truth,
            "mlx_error": mlx_err[:240] if mlx_err else None,
        }
    except Exception as exc:
        return {
            "status": "error",
            "source": "local_vlm:owner_frame_on_demand",
            "eye_role": "owner_eye",
            "description": f"{type(exc).__name__}: {exc}"[:800],
            "mlx_error": mlx_err[:240] if mlx_err else None,
        }


def describe_owner_frame_on_demand(
    *,
    state_dir: Path | str | None = None,
    reason: str = "owner_typed",
    owner_text: str = "",
    write: bool = True,
) -> dict[str, Any]:
    """CUR-V1: on-demand owner-frame VLM describe → blink ledger receipt.

    Runs only when George asks to describe clothes/colors/what Alice sees on him.
    Does not enable global heartbeat VLM; no raw frame is archived in the ledger.
    """
    state = _state_dir(state_dir)
    now = time.time()
    frame, frame_age_s = _resolve_owner_frame_path(state)
    blink_id = "blink_" + uuid.uuid4().hex[:12]
    visual_raw = _latest(state / "visual_stigmergy.jsonl")
    face_raw = _latest(state / "face_detection_events.jsonl")
    visual = _sanitize_visual(visual_raw, now=now)
    face = _sanitize_face(face_raw, now=now)

    if frame is None:
        description = {
            "status": "unavailable",
            "source": "owner_frame_on_demand",
            "eye_role": "owner_eye",
            "description": (
                "no owner camera frame on disk yet; open What Alice Sees / enable "
                "the MacBook camera and wait for a frame receipt"
            ),
        }
    else:
        description = _run_owner_frame_vlm(frame, owner_text=owner_text)

    row: dict[str, Any] = {
        "ts": now,
        "kind": "SACCADIC_BLINK",
        "truth_label": TRUTH_LABEL,
        "blink_id": blink_id,
        "eye_id": "owner_eye",
        "eye_role": "owner_eye",
        "reason": reason if reason in ESCALATION_REASONS else "owner_typed",
        "source": "owner_frame_on_demand",
        "on_demand": True,
        "owner_describe_turn": True,
        "visual_fresh": frame_age_s is not None and frame_age_s <= 120.0,
        "frame_age_s": frame_age_s,
        "privacy_policy": "pixels_die_information_lives_no_frame_archive",
        "frame_persistence": {
            "blink_wrote_frame_file": False,
            "raw_frame_archived": False,
            "persistent_payload": "semantic_description_only",
        },
        "visual": visual,
        "face": face,
        "semantic_description": description,
    }
    for key in list(row):
        if key in FRAME_PATH_KEYS:
            row.pop(key, None)

    if write:
        _append_jsonl(state / BLINK_LEDGER_NAME, row)
        (state / SNAPSHOT_NAME).write_text(
            json.dumps(row, ensure_ascii=False, sort_keys=True, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
    return row


def latest_owner_frame_description(
    *,
    state_dir: Path | str | None = None,
    max_age_s: float = 180.0,
) -> dict[str, Any] | None:
    """Return the newest on-demand owner describe receipt, if fresh enough."""
    state = _state_dir(state_dir)
    rows = _read_jsonl_tail(state / BLINK_LEDGER_NAME, 12)
    now = time.time()
    for row in reversed(rows):
        if not row.get("on_demand") and not row.get("owner_describe_turn"):
            continue
        desc = row.get("semantic_description")
        if not isinstance(desc, dict):
            continue
        age = _age(now, row)
        if age is not None and age > max_age_s:
            continue
        return {"row": row, "description": desc, "age_s": age}
    return None


def request_attention_blink(
    reason: str,
    *,
    state_dir: Path | str | None = None,
    now_fn: Callable[[], float] | None = None,
) -> dict[str, Any]:
    """Force one fresh blink for owner/effector attention events.

    This is the Talk/effector entrypoint for r1026 escalation. It stays on the
    same metadata-only bridge as heartbeat blinks, so a foreground owner turn
    can refresh visual meaning without creating a surveillance frame archive.
    """
    reason = (reason or "manual").strip() or "manual"
    if reason not in ESCALATION_REASONS:
        reason = "manual"
    return pulse_saccadic_blink(
        state_dir=state_dir,
        reason=reason,
        force=True,
        now_fn=now_fn,
    )


def format_blink_reply(row: Mapping[str, Any]) -> str:
    state = "GREEN" if row.get("visual_fresh") else "RED"
    reason = row.get("meaningful_reason") or row.get("reason")
    return (
        f"BLINK: {state} age={row.get('visual_age_s')}s "
        f"delta={str(row.get('meaningful_delta')).lower()} reason={reason} "
        f"archive={row.get('frame_persistence', {}).get('raw_frame_archived')}"
    )


if __name__ == "__main__":  # pragma: no cover
    print(format_blink_reply(pulse_saccadic_blink(reason="manual", force=True)))
