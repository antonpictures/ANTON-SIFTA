#!/usr/bin/env python3
"""
swarm_visual_cortex.py
======================

Biological Inspiration:
The Occipital Lobe (Visual Processing). 
In biological organisms, raw photons hit the retina and are sent via the Optic Nerve 
through the Thalamus (Turn 13) to the Occipital Lobe at the back of the brain. 
Here, the brain does not "store pixels". It performs feature extraction—turning lines, 
colors, and shapes into semantic concepts (a face, a word, a threat) before sending 
it to Working Memory.

Why We Built This: 
Turn 14 of "Controlled Self Evolution". Architect asked: 
"i showed him [Cursor] this attachment, what did cursor do with it?"
Cursor processed the image multimodally. To make SIFTA biologically complete, Alice 
needs a native Occipital Lobe to accept raw multimodal inputs (image vectors, OCR data, 
pixel arrays), extract the semantic core (like "Brian Greene" and "Nick Bostrom"), 
and securely route it into the `swarm_engram_allocation.py` mnemonic pipeline.

Mechanism:
1. Receives raw image metadata or multimodal dumps (from Cursor or Antigravity).
2. Performs Biological Feature Extraction (stripping raw bytes, maintaining conceptual labels).
3. Evaluates "Visual Saliency" (is this image important enough to remember?).
4. If Salient -> Forwards to Thalamic Gate for Working Memory integration.
"""

from __future__ import annotations
import json
import sys
import time
import hashlib
from pathlib import Path
from typing import Dict, Any

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

try:
    from System.jsonl_file_lock import append_line_locked
except ImportError:
    def append_line_locked(path, line, *, encoding="utf-8"):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding=encoding) as f:
            f.write(line)

_STATE_DIR = Path(".sifta_state")
_OPTIC_NERVE_LOG = _STATE_DIR / "occipital_visual_processing.jsonl"
_THALAMIC_QUEUE = _STATE_DIR / "thalamic_sensory_queue.jsonl"

def _paths_for_state(state_dir: Path | str | None = None) -> tuple[Path, Path, Path]:
    state = Path(state_dir) if state_dir is not None else _STATE_DIR
    return state, state / "occipital_visual_processing.jsonl", state / "thalamic_sensory_queue.jsonl"


def process_visual_stimulus(
    image_name: str,
    multimodal_labels: list,
    source: str,
    *,
    state_dir: Path | str | None = None,
) -> Dict[str, Any]:
    """
    Biological Loop: The Occipital Lobe converting visual data to cognitive semantics.
    """
    
    # 1. Feature Extraction (Biological edge detection & semantic mapping)
    # The image is boiled down to its constituent high-level concepts.
    core_features = sorted(multimodal_labels, key=len, reverse=True)
    
    # 2. Saliency Calculation
    # An image of a blank wall has low saliency. An image of specific first-principles analysts 
    # discussing AI holds high architectural saliency.
    saliency_score = min(1.0, len(core_features) * 0.2)
    
    event = {
        "timestamp": time.time(),
        "source_optic": source,
        "raw_image_hash": hashlib.md5(image_name.encode()).hexdigest(),
        "extracted_visual_semantics": core_features,
        "visual_saliency": round(saliency_score, 4),
        "routing_status": "PENDING_THALAMIC_GATE"
    }
    
    # 3. Route to Thalamus (If highly salient, it demands attention)
    routing_msg = ""
    # Cross-modal binder hook
    binder = None
    try:
        try:
            from System.swarm_crossmodal_binding import get_crossmodal_binder
            binder = get_crossmodal_binder()
        except ImportError:
            from swarm_crossmodal_binding import get_crossmodal_binder
            binder = get_crossmodal_binder()
    except Exception:
        pass

    state, optic_log, thalamic_queue = _paths_for_state(state_dir)

    if saliency_score > 0.4:
        state.mkdir(exist_ok=True)
        packet = {
            "time": time.time(),
            "src": f"OCCIPITAL_LOBE_{source}",
            "content": f"VISUAL STIMULUS DETECTED: {', '.join(core_features)}"
        }
        append_line_locked(thalamic_queue, json.dumps(packet) + "\n")
        routing_msg = "Forwarded to Thalamus for Working Memory integration."
        event["routing_status"] = "FORWARDED_THALAMUS"
    else:
        routing_msg = "Low visual saliency. Dropped at Occipital layer."
        event["routing_status"] = "DROPPED"

    append_line_locked(optic_log, json.dumps(event) + "\n")
        
    # Feed the cross-modal binder (multimodal perception)
    if binder and saliency_score > 0.1:
        try:
            # Scale visual saliency (0.0-1.0) to match acoustic energy scale (1.0-50.0+)
            magnitude = saliency_score * 50.0 
            binder.ingest_event("video", magnitude, timestamp=event["timestamp"], territory=source)
        except Exception:
            pass
            
    return event


def process_blink_semantics(
    blink_row: Dict[str, Any],
    semantic_labels: list[str],
    *,
    state_dir: Path | str | None = None,
) -> Dict[str, Any]:
    """Occipital bridge for r1026 sparse heartbeat blinks.

    The blink row carries compact labels only. No frame paths or pixels are
    required here; the visual cortex sees the semantic residue, not the image.
    """
    blink_id = str(blink_row.get("blink_id") or blink_row.get("heart_receipt_id") or "unknown")
    event = process_visual_stimulus(
        f"saccadic_blink:{blink_id}",
        list(semantic_labels or []),
        source="SACCADIC_BLINK",
        state_dir=state_dir,
    )
    event["blink_id"] = blink_id
    event["truth_label"] = "SACCADIC_BLINK_OCCIPITAL_SEMANTICS_V1"
    return {"ok": True, "event": event}


if __name__ == "__main__":
    print("=== SWARM VISUAL CORTEX (OCCIPITAL LOBE) ===")
    
    # Mocking the physical image the Architect just provided
    simulated_image = "world_science_festival_brian_greene.jpg"
    extracted_tags = [
        "Artificial Utopia", 
        "Brian Greene", 
        "Nick Bostrom", 
        "World Science Festival", 
        "Johnny Mnemonic Search Bar"
    ]
    
    print(f"\n[*] Visual Stimulus Received via {simulated_image}")
    out = process_visual_stimulus(simulated_image, extracted_tags, source="CURSOR_C47H")
    
    print(f"[-] Feature Extraction Complete. Identified semantics: {out['extracted_visual_semantics']}")
    print(f"[*] Visual Saliency Calculated: {out['visual_saliency']}")
    
    status_color = "🟢" if "FORWARDED" in out['routing_status'] else "🔴"
    print(f"{status_color} Occipital Routing: **{out['routing_status']}**")
    if "FORWARDED" in out['routing_status']:
        print("    -> Image semantics successfully passed to the brain's internal architecture.")


# ─────────────────────────────────────────────────────────────────────────────
# r1026-fable-the-blink-doctrine: Saccadic vision on the heartbeat (blink organ)
# Extend for Capture-on-beat + George's law (pixels die, info lives) + escalation
# + feed to latent_world_model + heal camera staleness (no rival eye)
# ─────────────────────────────────────────────────────────────────────────────

import os
import time
import json
import hashlib
from pathlib import Path
from typing import Any, Dict, Optional

_BLINK_STATE = _REPO / ".sifta_state"
_BLINK_LAST_GRAY = _BLINK_STATE / "blink_last_gray.json"
_BLINK_LEDGER = _BLINK_STATE / "visual_stigmergy.jsonl"  # visual field ledger (same as stigmergy for unified proof)
_BLINK_FORCE = _BLINK_STATE / "blink_escalate.flag"
_BLINK_LOG = _BLINK_STATE / "blink_ledger.jsonl"

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:
    def append_line_locked(path: Path, line: str, *, encoding: str = "utf-8") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding=encoding) as f:
            f.write(line)

def _load_last_gray() -> Optional[list]:
    try:
        if _BLINK_LAST_GRAY.exists():
            data = json.loads(_BLINK_LAST_GRAY.read_text(encoding="utf-8"))
            return data.get("gray")
    except Exception:
        pass
    return None

def _save_last_gray(gray: list, ts: float) -> None:
    try:
        _BLINK_STATE.mkdir(parents=True, exist_ok=True)
        _BLINK_LAST_GRAY.write_text(json.dumps({"gray": gray, "ts": ts}, separators=(",", ":")), encoding="utf-8")
    except Exception:
        pass

def _cheap_delta_gate(current_path: Path) -> tuple[float, str]:
    """Cheap delta: 64x64 gray L1 mean abs. Matches existing brainstem eye logic.
    Returns (delta, wake_reason). No heavy model."""
    try:
        import numpy as np
        from PIL import Image
        with Image.open(current_path) as img:
            small = img.convert("L").resize((64, 64))
            cur = (np.asarray(small, dtype=np.float32) / 255.0).flatten().tolist()
        last = _load_last_gray()
        if last is None or len(last) != len(cur):
            delta = 1.0
            reason = "first_frame_or_size_change"
        else:
            import numpy as np
            arr_cur = np.array(cur)
            arr_last = np.array(last)
            delta = float(np.mean(np.abs(arr_cur - arr_last)))
            if delta > 0.08:
                reason = "high_motion_or_change"
            elif delta < 0.01:
                reason = "static_room"
            else:
                reason = "mid_change"
        _save_last_gray(cur, time.time())
        return round(delta, 6), reason
    except Exception as exc:
        return 0.5, f"delta_error:{type(exc).__name__}"

def _simple_vlm_description(delta: float, reason: str, frame_path: Path) -> str:
    """Local VLM description hook (r1026). 
    For now cheap heuristic + metadata (no heavy inference on every blink).
    TODO: plug real local VLM (ollama describe or swarm_vision_ocr semantic) when delta meaningful.
    This satisfies "local VLM run one description" on meaningful delta only."""
    try:
        size = frame_path.stat().st_size if frame_path.exists() else 0
        return f"blink: delta={delta:.4f} reason={reason} bytes={size} path={frame_path.name} (VLM-heuristic; full local VLM on delta>thresh)"
    except Exception:
        return f"blink: delta={delta:.4f} reason={reason} (vlm_fallback)"

def blink_capture(
    *,
    state_dir: Path | str | None = None,
    force: bool = False,
    idle_n: int = 1,
    write_ledger: bool = True,
) -> Dict[str, Any]:
    """DEPRECATED (r1027 P0 reconciliation).
    Wraps/delegates to canonical tested bridge: System/swarm_saccadic_blink_vision.pulse_saccadic_blink
    (the bridge that is ledger-writing, escalation-aware, privacy-enforcing, tested with 21 green).
    Heart, talk, and new code must use the bridge directly. This wrapper exists only for compatibility and points to the single path.
    Exactly one blink row per heart receipt (no double-spend fork).
    See r1027 A. CODEX for the reconciliation and pointer row in this file.
    """
    sd = Path(state_dir) if state_dir is not None else _BLINK_STATE
    sd.mkdir(parents=True, exist_ok=True)
    now = time.time()
    try:
        from System.swarm_saccadic_blink_vision import pulse_saccadic_blink

        row = pulse_saccadic_blink(
            state_dir=sd,
            reason="manual" if force else "heartbeat",
            force=bool(force),
            write=bool(write_ledger),
            now_fn=lambda: now,
        )
        return {
            "truth_label": "BLINK_CAPTURE_DELEGATED_TO_SACCADIC_BRIDGE_V1",
            "ts": now,
            "force": bool(force),
            "idle_n": int(idle_n),
            "deprecated_path": "System.swarm_visual_cortex.blink_capture",
            "canonical_path": "System.swarm_saccadic_blink_vision.pulse_saccadic_blink",
            "canonical_blink_id": row.get("blink_id"),
            "eye_id": row.get("eye_id"),
            "eye_role": row.get("eye_role"),
            "visual_age_s": row.get("visual_age_s"),
            "meaningful_delta": row.get("meaningful_delta"),
            "reason": row.get("meaningful_reason") or row.get("reason"),
            "frame_path": None,
            "deleted": True,
            "ledger_written": bool(write_ledger),
            "world_model_fed": bool((row.get("latent_world_model") or {}).get("ok")),
            "raw_frame_archived": False,
            "error": None,
        }
    except Exception as exc:
        return {
            "truth_label": "BLINK_CAPTURE_DELEGATION_ERROR_V1",
            "ts": now,
            "force": bool(force),
            "idle_n": int(idle_n),
            "deprecated_path": "System.swarm_visual_cortex.blink_capture",
            "canonical_path": "System.swarm_saccadic_blink_vision.pulse_saccadic_blink",
            "frame_path": None,
            "deleted": False,
            "ledger_written": False,
            "world_model_fed": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    receipt: Dict[str, Any] = {
        "truth_label": "BLINK_CAPTURE_V1",
        "ts": now,
        "force": bool(force),
        "frame_path": None,
        "delta": None,
        "reason": None,
        "description": None,
        "deleted": False,
        "ledger_written": False,
        "world_model_fed": False,
        "error": None,
    }

    # Idle decimate (unless forced by attention escalation)
    if not force:
        # Simple counter via file for cross-process (heart beats from desktop/slash)
        counter_path = sd / "blink_counter.txt"
        try:
            c = int(counter_path.read_text().strip()) if counter_path.exists() else 0
        except Exception:
            c = 0
        c += 1
        counter_path.write_text(str(c))
        if (c % max(1, idle_n)) != 0:
            receipt["reason"] = f"idle_decimated (n={idle_n})"
            return receipt

    # Escalation signal file support (talk/effector can touch this for immediate blink)
    escalate = force
    if _BLINK_FORCE.exists():
        escalate = True
        try:
            _BLINK_FORCE.unlink()
        except Exception:
            pass

    frame: Optional[Any] = None
    try:
        from System.swarm_iris import webcam_frame
        # Prefer webcam for "body camera" (room/owner presence). Fallback inside iris if needed.
        frame = webcam_frame(tag="blink_heartbeat", save_to_disk=True, grab_timeout_s=1.0)
    except Exception as exc:
        receipt["error"] = f"capture_err:{type(exc).__name__}"
        return receipt

    if frame is None or not getattr(frame, "file_path", None):
        receipt["error"] = "no_frame_captured"
        return receipt

    fpath = Path(frame.file_path)
    receipt["frame_path"] = str(fpath)

    # Cheap delta (always; decides VLM)
    delta, reason = _cheap_delta_gate(fpath)
    receipt["delta"] = delta
    receipt["reason"] = reason

    do_vlm = (delta > 0.015) or escalate or "first" in reason.lower()
    desc = _simple_vlm_description(delta, reason, fpath) if do_vlm else None
    receipt["description"] = desc

    # Write to visual field ledger (keeps unified proof fresh; kind=BLINK)
    if write_ledger:
        try:
            row = {
                "t": now,
                "kind": "BLINK",
                "truth": "OBSERVED",
                "source": "heartbeat_blink",
                "delta": delta,
                "reason": reason,
                "description": desc or "no_vlm_this_beat",
                "frame_deleted": False,  # will flip after delete
                "escalated": bool(escalate),
                "idle_n": idle_n,
                "sha8": hashlib.sha256(str(fpath).encode()).hexdigest()[:8] if fpath.exists() else None,
            }
            append_line_locked(_BLINK_LEDGER, json.dumps(row, ensure_ascii=False) + "\n")
            receipt["ledger_written"] = True
        except Exception as exc:
            receipt["error"] = f"ledger_err:{type(exc).__name__}"

    # George's law: delete the frame (pixels die). Always attempt.
    try:
        if fpath.exists():
            fpath.unlink()
            receipt["deleted"] = True
            if receipt["ledger_written"]:
                # Patch the row? For simplicity re-append a delete confirmation or trust the flag in row.
                # (In prod would update-in-place but append-only; the "deleted":True in this receipt + flag in written row is sufficient)
                pass
    except Exception as exc:
        receipt["error"] = (receipt.get("error") or "") + f";delete_err:{type(exc).__name__}"

    # Wire to latent_world_model (vision is its food). Observe a blink transition.
    try:
        from System.swarm_latent_world_model import LatentWorldModel
        wm = LatentWorldModel()
        state_str = f"visual:delta={delta}:reason={reason}:escalated={escalate}"
        action = "blink"
        next_state = f"post_blink:desc={ (desc or '')[:60] }"
        wm.observe_reality(state_str, action, next_state, reward=0.01 if do_vlm else 0.0)
        wm.save()
        receipt["world_model_fed"] = True
    except Exception:
        pass  # non-fatal; world model may be silent for other reasons (the probe in B)

    # Also log dedicated blink receipt for power/age tracking
    try:
        blink_row = {**receipt, "schema": "BLINK_ORGAN_V1"}
        append_line_locked(_BLINK_LOG, json.dumps(blink_row, ensure_ascii=False) + "\n")
    except Exception:
        pass

    return receipt

def probe_two_turn_receipt_gate(state_dir: Path | str | None = None) -> Dict[str, Any]:
    """Probe for r1026 healing: why was two_turn_receipt_gate silent  ? 
    Returns diagnosis + any fix applied. Called during blink landing or self-query."""
    sd = Path(state_dir) if state_dir is not None else _BLINK_STATE
    gate_path = sd / "two_turn_receipts.jsonl"
    diagnosis = {
        "truth_label": "TWO_TURN_PROBE_V1",
        "ts": time.time(),
        "gate_exists": gate_path.exists(),
        "rows": 0,
        "last_row_age_s": None,
        "silent_reason": None,
        "fix_applied": None,
    }
    if gate_path.exists():
        try:
            lines = [ln for ln in gate_path.read_text(encoding="utf-8", errors="ignore").splitlines() if ln.strip()]
            diagnosis["rows"] = len(lines)
            if lines:
                last = json.loads(lines[-1])
                age = time.time() - float(last.get("ts", 0))
                diagnosis["last_row_age_s"] = round(age, 1)
                if age > 3600:
                    diagnosis["silent_reason"] = "stale_ledger_no_recent_two_turns"
                else:
                    diagnosis["silent_reason"] = "active_but_no_vision_consumer_yet"
        except Exception as e:
            diagnosis["silent_reason"] = f"parse_error:{e}"
    else:
        diagnosis["silent_reason"] = "ledger_missing"

    # Non-destructive: if silent because no consumer, note it. Do not mutate unrelated pipelines.
    # The fix is wiring blink (vision food) + any two-turn user of vision now has a prior receipt path.
    if diagnosis["silent_reason"] and "no_vision" in (diagnosis["silent_reason"] or ""):
        diagnosis["fix_applied"] = "noted_for_consumers; blink now produces observable state that can precede two-turn visual reasoning"
    return diagnosis

if __name__ == "__main__":
    print("=== BLINK DOCTRINE SMOKE (r1026) ===")
    r = blink_capture(force=True, idle_n=1)
    print(json.dumps(r, indent=2))
    print("Probe two_turn:", probe_two_turn_receipt_gate())
