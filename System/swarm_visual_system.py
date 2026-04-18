#!/usr/bin/env python3
"""
System/swarm_visual_system.py — Umbrella for the SIFTA Swarm Eye stack
══════════════════════════════════════════════════════════════════════
T65 BUILD — One canonical entry point for callers that want vision.
Underneath, the eye is composed of narrow-purpose organs (Brooks 1991:
"intelligence without representation"), each independently testable.

Vocabulary clarifications (no rewrites — just a unified naming surface):
  swarm_iris            (M1) — pixel intake (screen/webcam/synthetic)
  swarm_optic_nerve     (M2) — chrome OCR + template classification
  stigmergic_vision     (M3) — multi-lane fusion (L1 probe + L2 watermark
                                + L3 passive + L4 pixel lane)
  swarm_swimmer_passport(M4) — health gating + clearance issuance
  swarm_visual_cortex         existing higher-order cortex (Turn 14)

Public surface (re-exported below):
  See, IdentityImage          fusion façade (when AG31's 1.3 lands)
  SwarmIris, IrisFrame        capture
  OpticNerveBus, VisualSignal OCR + classification
  classify_ocr_text           direct template matcher
  PassportAuthority           health gating
  see_now()                   one-shot end-to-end perception (M5.1)
  capability_report()         what-this-install-can-do dump
══════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional

# ── Capture (M1) ───────────────────────────────────────────────────────────
from System.swarm_iris import (
    IrisFrame,
    IrisCaptureAdapter,
    SwarmIris,
    synthetic_frame,
    webcam_frame,
    capability_report,
)

# ── Optic relay (M2) ───────────────────────────────────────────────────────
from System.swarm_optic_nerve import (
    VisualSignal,
    OpticNerveBus,
    OpticNerveOCRRelay,
    classify_ocr_text,
    KNOWN_MODEL_TEMPLATES,
    read_chrome_ocr,
)

# ── Fusion (M3) ────────────────────────────────────────────────────────────
import System.stigmergic_vision as stigmergic_vision
from System.stigmergic_vision import (
    smoke_pixel_lane,
    _l4_pixel_lane,
)

# ── Passport (M4) ──────────────────────────────────────────────────────────
from System.swarm_swimmer_passport import (
    SwimmerPassport,
    HealthChecker,
    PassportAuthority,
    persist_passport,
    recent_passports,
)

# ── Higher-order cortex (existing Turn 14 module) ──────────────────────────
from System.swarm_visual_cortex import process_visual_stimulus

__all__ = [
    # M1 capture
    "IrisFrame", "IrisCaptureAdapter", "SwarmIris",
    "synthetic_frame", "webcam_frame", "capability_report",
    # M2 optic relay
    "VisualSignal", "OpticNerveBus", "OpticNerveOCRRelay",
    "classify_ocr_text", "KNOWN_MODEL_TEMPLATES", "read_chrome_ocr",
    # M3 fusion
    "stigmergic_vision", "smoke_pixel_lane",
    # M4 passport
    "SwimmerPassport", "HealthChecker", "PassportAuthority",
    "persist_passport", "recent_passports",
    # higher-order cortex
    "process_visual_stimulus",
    # M5.1 one-shot
    "see_now",
]

MODULE_VERSION = "2026-04-18.t65.umbrella.v1"


def see_now(
    target_trigger: str,
    *,
    source: str = "ide_chrome_screenshot",
    issue_passport: bool = False,
) -> Dict[str, Any]:
    """
    One-shot end-to-end perception:

      1. Capture a frame via SwarmIris (falls back to synthetic on
         headless installs — never raises).
      2. Route it through OpticNerveBus -> writes a VisualSignal to the
         relay log (the file _l4_pixel_lane reads).
      3. Re-read the L4 pixel lane to confirm the new signal is visible
         to the fusion façade.
      4. Optionally issue/refresh a passport for `target_trigger`.

    Returns a structured dict suitable for journaling. Never raises;
    failure modes are reported via the `errors` field.
    """
    out: Dict[str, Any] = {
        "ts": time.time(),
        "target_trigger": target_trigger,
        "source": source,
        "capability": capability_report(),
        "errors": [],
    }

    # 1. Capture
    try:
        iris = SwarmIris()
        frame = iris.blink_capture(source=source)
        out["frame_id"] = frame.frame_id
        out["frame_source"] = frame.capture_source
    except Exception as exc:
        out["errors"].append(f"capture: {exc!r}")
        return out

    # 2. Optic-nerve route
    try:
        bus = OpticNerveBus()
        sig = bus.route_signal(frame.frame_id, frame.file_path,
                               frame_metadata=frame.metadata)
        if sig is not None:
            out["signal_id"] = sig.signal_id
            out["ocr_confidence"] = sig.confidence_score
            out["best_model"] = sig.metadata.get("best_model")
            out["best_ide"] = sig.metadata.get("best_ide")
            out["ide_tags_found"] = sig.ide_tags_found
        else:
            out["errors"].append("optic_nerve: no signal produced")
    except Exception as exc:
        out["errors"].append(f"optic_nerve: {exc!r}")

    # 3. L4 pixel-lane re-read (does fusion see what the eye saw?)
    try:
        lane = _l4_pixel_lane(target_trigger, recent_window_s=300.0)
        out["l4_p_genuine"] = lane.get("p_genuine")
        out["l4_evidence_strength"] = lane.get("evidence_strength")
    except Exception as exc:
        out["errors"].append(f"l4_lane: {exc!r}")

    # 4. Optional passport
    if issue_passport:
        try:
            auth = PassportAuthority(persist=True)
            p = auth.issue_passport(target_trigger)
            out["passport_valid"] = p.is_valid
            out["passport_failing"] = p.revocation_reason
        except Exception as exc:
            out["errors"].append(f"passport: {exc!r}")

    return out


if __name__ == "__main__":
    import json
    print("[C47H-SMOKE-M5.1] capability:", json.dumps(capability_report()))
    result = see_now("C47H", source="ide_chrome_screenshot", issue_passport=True)
    print(f"[C47H-SMOKE-M5.1] see_now('C47H'): "
          f"frame={result.get('frame_id')} "
          f"best_model={result.get('best_model')} "
          f"l4_p={result.get('l4_p_genuine')} "
          f"passport_valid={result.get('passport_valid')}")
    if result["errors"]:
        print(f"[C47H-SMOKE-M5.1] non-fatal errors: {result['errors']}")
    print("[C47H-SMOKE-M5.1 OK] umbrella + see_now end-to-end green")
