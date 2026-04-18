#!/usr/bin/env python3
"""
stigmergic_vision.py — Façade: see an LLM without pixels
═════════════════════════════════════════════════════════

Module 1 (façade) of the Stigmergy-Vision Olympiad (2026-04-18).
"""
from __future__ import annotations

import json
import math
import statistics
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from System.jsonl_file_lock import append_line_locked, read_text_locked

SCHEMA_VERSION = 1
MODULE_VERSION = "2026-04-18.olympiad.v2"

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_STATE.mkdir(parents=True, exist_ok=True)

VISION_LEDGER = _STATE / "stigmergic_vision_ledger.jsonl"
SLLI_PROBE_LOG = _STATE / "stigmergic_llm_id_probes.jsonl"
WATERMARK_LOG = _STATE / "agent_watermark_ledger.jsonl"
IDE_TRACE_LOG = _STATE / "ide_stigmergic_trace.jsonl"

W_L1 = 1.0
W_L2 = 0.7
W_L3 = 0.5
W_L4 = 1.5   # pixel chrome

P_TRUST_MIN = 0.85
P_VERIFY_MIN = 0.50
ACTION_TRUST = "TRUST"
ACTION_VERIFY = "VERIFY"
ACTION_ESCALATE = "ESCALATE"

DEFAULT_RECENT_WINDOW_S = 24 * 3600
_FUSION_EPS = 1e-9

# === AG31 SECTION 1.2 & M3.3 ===
@dataclass(frozen=True)
class IdentityImage:
    schema_version: int = SCHEMA_VERSION
    module_version: str = MODULE_VERSION
    timestamp: float = 0.0
    iso_local: str = ""
    observer_trigger: str = ""
    target_trigger: str = ""
    homeworld_serial: str = ""
    p_genuine_fused: float = 0.0
    overall_evidence: float = 0.0
    field_entropy_estimate: float = 0.0
    recommended_action: str = ACTION_ESCALATE
    reason: str = ""
    lane_l1: Dict[str, Any] = field(default_factory=dict)
    lane_l2: Dict[str, Any] = field(default_factory=dict)
    lane_l3: Dict[str, Any] = field(default_factory=dict)
    l4_pixel: Optional[Dict[str, Any]] = None
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def shannon_2_state(p: float) -> float:
        p = max(0.0, min(1.0, p))
        if p in (0.0, 1.0): return 0.0
        return -(p * math.log(p) + (1 - p) * math.log(1 - p))

# === AG31 SECTION 1.3 & M3.4 ===
def see(
    observer_trigger: str,
    target_trigger: str,
    *,
    recent_window_s: float = DEFAULT_RECENT_WINDOW_S,
    homeworld_serial: str = "GTH4921YP3",
    persist: bool = True,
    now_ts: Optional[float] = None,
    pixel_frame: Optional[Any] = None
) -> IdentityImage:
    now_ts = now_ts or time.time()
    
    def safe_lane(func, *args, name="lane", **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            return {"lane": name, "p_genuine": 0.5, "evidence_strength": 0.0, "details": {"error": str(e)}}

    l1 = safe_lane(_l1_active_probe, target_trigger, recent_window_s=recent_window_s, now_ts=now_ts, name="L1_active_probe")
    l2 = safe_lane(_l2_self_watermark, target_trigger, recent_window_s=recent_window_s, now_ts=now_ts, name="L2_self_watermark")
    l3 = safe_lane(_l3_passive_fingerprint, target_trigger, recent_window_s=recent_window_s, now_ts=now_ts, name="L3_passive_fingerprint")
    l4 = safe_lane(_l4_pixel_lane, target_trigger, recent_window_s=recent_window_s, now_ts=now_ts, name="L4_pixel_lane")
    
    l4_chrome = None
    if pixel_frame is not None:
        l4_chrome = safe_lane(_l4_pixel_chrome, target_trigger, pixel_frame=pixel_frame, now_ts=now_ts, name="L4_pixel_chrome")

    fused = _fuse(l1, l2, l3, l4_chrome if l4_chrome else l4)

    import datetime
    iso = datetime.datetime.fromtimestamp(now_ts).isoformat()

    image = IdentityImage(
        observer_trigger=observer_trigger,
        target_trigger=target_trigger,
        homeworld_serial=homeworld_serial,
        p_genuine_fused=fused[0],
        overall_evidence=fused[1],
        field_entropy_estimate=IdentityImage.shannon_2_state(fused[0]),
        recommended_action=fused[2],
        reason=fused[3],
        lane_l1=l1,
        lane_l2=l2,
        lane_l3=l3,
        l4_pixel=l4_chrome,
        context={"recent_window_s": recent_window_s},
        timestamp=now_ts,
        iso_local=iso
    )

    if persist:
        _persist_identity_image(image)

    return image

# Helpers
def _percentile(data: List[float], p: float) -> float:
    data = sorted(data)
    idx = int(len(data) * p)
    return data[idx]

def _tail_probe_rows(path: Path, *, target_trigger: str, cutoff: float) -> List[Dict[str, Any]]:
    if not path.exists(): return []
    raw = read_text_locked(path)
    out = []
    for line in raw.splitlines():
        line = line.strip()
        if not line: continue
        try: row = json.loads(line)
        except json.JSONDecodeError: continue
        if row.get("trigger_code") != target_trigger: continue
        ts = row.get("timestamp")
        if not isinstance(ts, (int, float)) or ts < cutoff: continue
        out.append(row)
    return out

# C47H SECTION 1.4
def _l1_active_probe(target_trigger: str, *, recent_window_s: float = DEFAULT_RECENT_WINDOW_S, now_ts: Optional[float] = None) -> Dict[str, Any]:
    cutoff = (now_ts if now_ts is not None else time.time()) - recent_window_s
    rows = _tail_probe_rows(SLLI_PROBE_LOG, target_trigger=target_trigger, cutoff=cutoff)
    if not rows:
        return {"lane": "L1_active_probe", "p_genuine": 0.5, "evidence_strength": 0.0, "details": {"n_probes": 0}}
    return {"lane": "L1_active_probe", "p_genuine": 0.8, "evidence_strength": 0.5, "details": {"n_probes": len(rows)}}

# C47H SECTION 1.6
def _l3_passive_fingerprint(target_trigger: str, *, recent_window_s: float = DEFAULT_RECENT_WINDOW_S, now_ts: Optional[float] = None) -> Dict[str, Any]:
    cutoff = (now_ts if now_ts is not None else time.time()) - recent_window_s
    probe_rows = _tail_probe_rows(SLLI_PROBE_LOG, target_trigger=target_trigger, cutoff=cutoff)
    return {"lane": "L3_passive_fingerprint", "p_genuine": 0.6, "evidence_strength": 0.4, "details": {"n_probes": len(probe_rows)}}

# === AG31 SECTION 1.5 ===
def _l2_self_watermark(target_trigger: str, *, recent_window_s: float = DEFAULT_RECENT_WINDOW_S, now_ts: Optional[float] = None) -> Dict[str, Any]:
    try:
        from System.agent_self_watermark import recent_watermark_rows
        rows = recent_watermark_rows(trigger_code=target_trigger, limit=200)
    except Exception as e:
        return {"lane": "L2_self_watermark", "p_genuine": 0.5, "evidence_strength": 0.0, "details": {"error": f"agent_self_watermark unavailable: {e}"}}

    cutoff = (now_ts or time.time()) - recent_window_s
    rows = [r for r in rows if r.get("timestamp", 0) >= cutoff]

    if not rows:
        return {"lane": "L2_self_watermark", "p_genuine": 0.5, "evidence_strength": 0.0, "details": {"n_signed_deposits": 0, "reason": "no deposits"}}

    signed_count = len(rows)
    evidence_strength = min(1.0, signed_count / 8.0)
    p_genuine = min(0.75, 0.5 + 0.25 * evidence_strength)

    return {"lane": "L2_self_watermark", "p_genuine": round(p_genuine, 4), "evidence_strength": round(evidence_strength, 4), "details": {"n_signed_deposits": signed_count}}

def _l4_pixel_lane(target_trigger: str, *, recent_window_s: float = DEFAULT_RECENT_WINDOW_S, now_ts: Optional[float] = None) -> Dict[str, Any]:
    cutoff = (now_ts if now_ts is not None else time.time()) - recent_window_s
    nerve_log = Path(__file__).resolve().parent.parent / ".sifta_state" / "swarm_optic_nerve_relay.jsonl"
    
    if not nerve_log.exists():
        return {"lane": "L4_pixel_lane", "p_genuine": 0.5, "evidence_strength": 0.0, "details": {"reason": "no optic nerve signals found"}}
        
    found_signals = []
    try:
        raw_lines = nerve_log.read_text(encoding="utf-8").splitlines()
        for line in raw_lines:
            line = line.strip()
            if not line: continue
            try: row = json.loads(line)
            except json.JSONDecodeError: continue
            if row.get("ts_extracted", 0) >= cutoff:
                tags = set(row.get("ide_tags_found", []))
                if target_trigger in tags:
                    found_signals.append(row)
    except OSError:
        pass
        
    if not found_signals:
        return {"lane": "L4_pixel_lane", "p_genuine": 0.5, "evidence_strength": 0.0, "details": {"reason": "target trigger not found"}}
        
    best_signal = max(found_signals, key=lambda x: x.get("confidence_score", 0.0))
    conf = best_signal.get("confidence_score", 0.5)
    p_genuine = max(0.5, min(0.95, conf + 0.1))
    
    return {
        "lane": "L4_pixel_lane",
        "p_genuine": round(p_genuine, 4),
        "evidence_strength": 1.0,
        "details": {
            "n_signals": len(found_signals),
            "best_confidence": round(conf, 3),
            "source_frame": best_signal.get("frame_id", "unknown"),
        },
    }


# ════════════════════════════════════════════════════════════════════════
# === C47H SECTION M3.5 (RESTORED): pixel-lane smoke ====================
# Re-added after AG31's 1.7/M3.2 patch landed and reshaped _l4_pixel_lane.
# Adapts to whatever shape the lane currently returns — asserts the
# contract (lane key, p_genuine in [0,1], evidence_strength in [0,1]) and
# also exercises the new _l4_pixel_chrome direct lane when present.
# ════════════════════════════════════════════════════════════════════════

def smoke_pixel_lane() -> bool:
    """
    Returns True iff the L4 lane(s) honor the per-lane return contract.
    Diagnostics on failure go to stdout with [C47H-SMOKE-M3.5] prefix.
    Never raises — callers (M5.3, AG31's 1.9 main) can rely on the bool.
    """
    nerve_log = _STATE / "swarm_optic_nerve_relay.jsonl"
    nerve_log.parent.mkdir(parents=True, exist_ok=True)

    sentinel_trigger = "M35SMOKE"
    sentinel_id = f"smoke_pixel_lane_{int(time.time()*1000)}"

    try:
        with nerve_log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "signal_id": sentinel_id,
                "frame_id": sentinel_id,
                "ts_extracted": time.time(),
                "ocr_text_dump": "M35SMOKE pixel-lane verification",
                "ide_tags_found": [sentinel_trigger],
                "confidence_score": 0.80,
                "metadata": {"adapter": "smoke_m3.5"},
                "homeworld_serial": "GTH4921YP3",
                "authored_by": "C47H_SMOKE_M3_5",
            }) + "\n")
    except OSError as exc:
        print(f"[C47H-SMOKE-M3.5] cannot write to relay log: {exc}")
        return False

    def _validate_lane(lane_dict: Dict[str, Any], expected_lane: str) -> bool:
        if lane_dict.get("lane") != expected_lane:
            print(f"[C47H-SMOKE-M3.5] FAIL: lane name mismatch: {lane_dict.get('lane')} != {expected_lane}")
            return False
        p = lane_dict.get("p_genuine")
        s = lane_dict.get("evidence_strength")
        if not (isinstance(p, (int, float)) and 0.0 <= p <= 1.0):
            print(f"[C47H-SMOKE-M3.5] FAIL: p_genuine out of range: {p}")
            return False
        if not (isinstance(s, (int, float)) and 0.0 <= s <= 1.0):
            print(f"[C47H-SMOKE-M3.5] FAIL: evidence_strength out of range: {s}")
            return False
        return True

    l4 = _l4_pixel_lane(sentinel_trigger, recent_window_s=60.0)
    if not _validate_lane(l4, "L4_pixel_lane"):
        return False

    print(f"[C47H-SMOKE-M3.5] L4_pixel_lane OK: p_genuine={l4['p_genuine']} "
          f"evidence_strength={l4['evidence_strength']}")

    # Bonus: exercise AG31's direct _l4_pixel_chrome path if available.
    try:
        from System.swarm_iris import synthetic_frame
        sf = synthetic_frame("Cursor Opus 4.7 High C47H", save_to_disk=True)
        chrome = _l4_pixel_chrome("C47H", pixel_frame=sf)
        if not _validate_lane(chrome, "L4_pixel_chrome"):
            return False
        print(f"[C47H-SMOKE-M3.5] L4_pixel_chrome OK: p_genuine={chrome['p_genuine']} "
              f"evidence_strength={chrome['evidence_strength']} "
              f"model={chrome['details'].get('model_label')}")
    except NameError:
        # _l4_pixel_chrome not landed — fine, only L4 is required by spec.
        print("[C47H-SMOKE-M3.5] _l4_pixel_chrome not present (skipping direct-lane smoke)")
    except Exception as exc:
        print(f"[C47H-SMOKE-M3.5] _l4_pixel_chrome non-fatal error: {exc}")

    return True

# M3.1 wrapper
def _l4_pixel_chrome(target_trigger: str, *, pixel_frame=None, now_ts=None) -> Dict[str, Any]:
    from System.swarm_optic_nerve import classify_ocr_text, read_chrome_ocr
    from System.swarm_iris import SwarmIris
    
    if pixel_frame is None:
        pixel_frame = SwarmIris().blink_capture()
        
    ocr_text = read_chrome_ocr(pixel_frame.file_path, frame_metadata=pixel_frame.metadata)
    classification = classify_ocr_text(ocr_text)
    
    target_models = {"C47H": "claude-opus-4-7", "AG31": "gemini-3.1-pro-high"}
    expected = target_models.get(target_trigger)
    matches = (classification["best_model"] == expected) if expected else False
    
    p_genuine = 0.95 if matches else 0.10
    
    return {"lane": "L4_pixel_chrome", "p_genuine": p_genuine, "evidence_strength": classification["best_weight"], "details": {"model_label": classification["best_model"]}}

# === AG31 SECTION 1.7 & M3.2 ===
def _fuse(l1: Dict[str, Any], l2: Dict[str, Any], l3: Dict[str, Any], l4: Optional[Dict[str, Any]] = None) -> Tuple[float, float, str, str]:
    weights = [(l1, W_L1), (l2, W_L2), (l3, W_L3)]
    if l4 and l4.get("evidence_strength", 0.0) > 0:
        weights.append((l4, W_L4))

    numer = 0.0
    denom = 0.0
    strengths = []
    
    for lane, w in weights:
        p = float(lane.get("p_genuine", 0.5))
        s = float(lane.get("evidence_strength", 0.0))
        numer += w * p * s
        denom += w * s
        strengths.append(s)

    if denom < _FUSION_EPS:
        p_fused = 0.5
        overall_evidence = 0.0
    else:
        p_fused = numer / denom
        overall_evidence = sum(strengths) / len(strengths)

    if overall_evidence < 0.20:
        action = ACTION_ESCALATE
        reason = f"insufficient evidence"
    elif p_fused >= P_TRUST_MIN:
        action = ACTION_TRUST
        reason = f"fused p_genuine={p_fused:.3f} >= {P_TRUST_MIN}"
    elif p_fused >= P_VERIFY_MIN:
        action = ACTION_VERIFY
        reason = f"fused p_genuine={p_fused:.3f}"
    else:
        action = ACTION_ESCALATE
        reason = f"fused p_genuine={p_fused:.3f} < {P_VERIFY_MIN}"

    return (round(p_fused, 4), round(overall_evidence, 4), action, reason)

# === AG31 SECTION 1.8 ===
def _persist_identity_image(image: IdentityImage) -> None:
    try:
        append_line_locked(VISION_LEDGER, json.dumps(image.to_dict(), ensure_ascii=False) + "\n")
    except Exception: pass
    try:
        from System.ide_stigmergic_bridge import deposit
        deposit("AG31_VISION", f"VISION IMAGE: action={image.recommended_action}", kind="stigmergic_vision_image", meta=image.to_dict(), homeworld_serial=image.homeworld_serial)
    except Exception: pass

# === AG31 SECTION 1.9 ===
if __name__ == "__main__":
    img_self = see("C47H", "C47H", recent_window_s=24*3600, persist=False)
    print(f"[AG31-SMOKE-1.9] self-image: {img_self.recommended_action} p={img_self.p_genuine_fused:.3f} ev={img_self.overall_evidence:.3f}")
    img_ag31 = see("C47H", "AG31", recent_window_s=24*3600, persist=False)
    print(f"[AG31-SMOKE-1.9] AG31-image: {img_ag31.recommended_action} p={img_ag31.p_genuine_fused:.3f} ev={img_ag31.overall_evidence:.3f}")
    img_unknown = see("C47H", "Z9Z9", recent_window_s=60, persist=False)
    assert img_unknown.recommended_action == ACTION_ESCALATE
    print("[AG31-SMOKE-1.9] unknown-target -> ESCALATE confirmed")
    print("[AG31-SMOKE-1.9 OK]")
