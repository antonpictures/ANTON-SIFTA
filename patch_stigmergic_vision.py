import re
from pathlib import Path

content = Path("System/stigmergic_vision.py").read_text()

# We need to implement 1.2 (IdentityImage + M3.3 l4_pixel)
identity_image_replacement = """@dataclass(frozen=True)
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
    reason: str = "AG31 1.2 implemented"
    lane_l1: Dict[str, Any] = field(default_factory=dict)
    lane_l2: Dict[str, Any] = field(default_factory=dict)
    lane_l3: Dict[str, Any] = field(default_factory=dict)
    l4_pixel: Optional[Dict[str, Any]] = None  # M3.3 patch
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def shannon_2_state(p: float) -> float:
        p = max(0.0, min(1.0, p))
        if p in (0.0, 1.0):
            return 0.0
        return -(p * math.log(p) + (1 - p) * math.log(1 - p))"""

content = re.sub(r"@dataclass\(frozen=True\)\nclass IdentityImage:.*?return asdict\(self\)", identity_image_replacement, content, flags=re.DOTALL)

# Implement 1.3 + M3.4
see_replacement = """def see(
    observer_trigger: str,
    target_trigger: str,
    *,
    recent_window_s: float = DEFAULT_RECENT_WINDOW_S,
    homeworld_serial: str = "GTH4921YP3",
    persist: bool = True,
    now_ts: Optional[float] = None,
    pixel_frame: Optional[Any] = None, # M3.4 patch
) -> IdentityImage:
    now_ts = now_ts or time.time()
    
    def safe_call(func, *args, name="lane", **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            return {"lane": name, "p_genuine": 0.5, "evidence_strength": 0.0, "details": {"error": str(e)}}

    l1 = safe_call(_l1_active_probe, target_trigger, recent_window_s=recent_window_s, now_ts=now_ts, name="L1_active_probe")
    l2 = safe_call(_l2_self_watermark, target_trigger, recent_window_s=recent_window_s, now_ts=now_ts, name="L2_self_watermark")
    l3 = safe_call(_l3_passive_fingerprint, target_trigger, recent_window_s=recent_window_s, now_ts=now_ts, name="L3_passive_fingerprint")
    l4 = safe_call(_l4_pixel_lane, target_trigger, recent_window_s=recent_window_s, now_ts=now_ts, name="L4_pixel_lane")
    
    # Optional integration via M3.1 / pixel_frame
    l4_chrome = None
    if pixel_frame is not None:
        try:
            # We assume _l4_pixel_chrome is defined further down
            l4_chrome = safe_call(_l4_pixel_chrome, target_trigger, pixel_frame=pixel_frame, now_ts=now_ts, name="L4_pixel_chrome")
        except Exception:
            pass

    # Fuse them all
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

    return image"""

content = re.sub(r"def see\(.*?raise NotImplementedError\(\s*\"AG31 SECTION 1\.3.*?\"\s*\)", see_replacement, content, flags=re.DOTALL)

# Implement 1.5
l2_replacement = """def _l2_self_watermark(
    target_trigger: str,
    *,
    recent_window_s: float = DEFAULT_RECENT_WINDOW_S,
    now_ts: Optional[float] = None,
) -> Dict[str, Any]:
    try:
        from System.agent_self_watermark import recent_watermark_rows
        rows = recent_watermark_rows(trigger_code=target_trigger, limit=200)
    except Exception as e:
        return {"lane": "L2_self_watermark", "p_genuine": 0.5, "evidence_strength": 0.0, "details": {"error": f"agent_self_watermark unavailable: {e}"}}

    cutoff = (now_ts or time.time()) - recent_window_s
    rows = [r for r in rows if r.get("timestamp", 0) >= cutoff]

    if not rows:
        return {
            "lane": "L2_self_watermark",
            "p_genuine": 0.5,
            "evidence_strength": 0.0,
            "details": {"n_signed_deposits": 0, "reason": "no watermark deposits in window"}
        }

    signed_count = len(rows)
    evidence_strength = min(1.0, signed_count / 8.0)
    p_genuine = min(0.75, 0.5 + 0.25 * evidence_strength)

    latest_signature_ts = max(r.get("timestamp", 0) for r in rows)
    signatures = [(r.get("signature") or r.get("anchor_signature") or "")[:8] for r in rows[-3:]]

    return {
        "lane": "L2_self_watermark",
        "p_genuine": round(p_genuine, 4),
        "evidence_strength": round(evidence_strength, 4),
        "details": {
            "n_signed_deposits": signed_count,
            "latest_signature_ts": latest_signature_ts,
            "sample_signatures": signatures
        }
    }"""

content = re.sub(r"def _l2_self_watermark\(.*?raise NotImplementedError\(\s*\"AG31 SECTION 1\.5.*?\"\s*\)", l2_replacement, content, flags=re.DOTALL)

# Implement 1.7 + M3.2
fuse_replacement = """def _fuse(
    l1: Dict[str, Any],
    l2: Dict[str, Any],
    l3: Dict[str, Any],
    l4: Optional[Dict[str, Any]] = None,
) -> Tuple[float, float, str, str]:
    weights = [(l1, W_L1), (l2, W_L2), (l3, W_L3)]
    
    # M3.2 W_L4 integration
    if l4 and l4.get("evidence_strength", 0.0) > 0:
        weights.append((l4, 1.5))

    numer = denom = 0.0
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
        reason = f"insufficient evidence (overall={overall_evidence:.2f})"
    elif p_fused >= P_TRUST_MIN:
        action = ACTION_TRUST
        reason = f"fused p_genuine={p_fused:.3f} >= {P_TRUST_MIN}"
    elif p_fused >= P_VERIFY_MIN:
        action = ACTION_VERIFY
        reason = f"fused p_genuine={p_fused:.3f} in [{P_VERIFY_MIN}, {P_TRUST_MIN})"
    else:
        action = ACTION_ESCALATE
        reason = f"fused p_genuine={p_fused:.3f} < {P_VERIFY_MIN}"

    return (round(p_fused, 4), round(overall_evidence, 4), action, reason)"""

content = re.sub(r"def _fuse\(.*?raise NotImplementedError\(\s*\"AG31 SECTION 1\.7.*?\"\s*\)", fuse_replacement, content, flags=re.DOTALL)

# Implement 1.8
persist_replacement = """def _persist_identity_image(image: IdentityImage) -> None:
    try:
        append_line_locked(VISION_LEDGER, json.dumps(image.to_dict(), ensure_ascii=False) + "\\n")
    except Exception as e:
        import sys
        print(f"Failed to append to vision ledger: {e}", file=sys.stderr)

    try:
        from System.ide_stigmergic_bridge import deposit
        deposit(
            source_ide="AG31_VISION_FUSE",
            payload=(
                f"VISION IMAGE: observer={image.observer_trigger} "
                f"target={image.target_trigger} "
                f"p_fused={image.p_genuine_fused:.3f} "
                f"action={image.recommended_action}"
            ),
            kind="stigmergic_vision_image",
            meta={
                "observer_trigger": image.observer_trigger,
                "target_trigger": image.target_trigger,
                "p_genuine_fused": image.p_genuine_fused,
                "overall_evidence": image.overall_evidence,
                "recommended_action": image.recommended_action,
                "field_entropy_estimate": image.field_entropy_estimate,
                "lane_l1_p": image.lane_l1.get("p_genuine"),
                "lane_l2_p": image.lane_l2.get("p_genuine"),
                "lane_l3_p": image.lane_l3.get("p_genuine"),
            },
            homeworld_serial=image.homeworld_serial,
        )
    except Exception as e:
        import sys
        print(f"Failed to deposit stigmergic trace: {e}", file=sys.stderr)"""

content = re.sub(r"def _persist_identity_image\(.*?raise NotImplementedError\(\s*\"AG31 SECTION 1\.8.*?\"\s*\)", persist_replacement, content, flags=re.DOTALL)

# Implement 1.9
main_replacement = """if __name__ == "__main__":
    img_self = see("C47H", "C47H", recent_window_s=24*3600, persist=False)
    print(f"[AG31-SMOKE-1.9] self-image: {img_self.recommended_action} p={img_self.p_genuine_fused:.3f} ev={img_self.overall_evidence:.3f}")

    img_ag31 = see("C47H", "AG31", recent_window_s=24*3600, persist=False)
    print(f"[AG31-SMOKE-1.9] AG31-image: {img_ag31.recommended_action} p={img_ag31.p_genuine_fused:.3f} ev={img_ag31.overall_evidence:.3f}")

    img_unknown = see("C47H", "Z9Z9", recent_window_s=60, persist=False)
    assert img_unknown.recommended_action == ACTION_ESCALATE
    print("[AG31-SMOKE-1.9] unknown-target -> ESCALATE confirmed")
    print("[AG31-SMOKE-1.9 OK]")
"""

content = re.sub(r"if __name__ == \"__main__\":.*?raise NotImplementedError\(\s*\"AG31 SECTION 1\.9.*?\"\s*\)", main_replacement, content, flags=re.DOTALL)

# Add M3.1 _l4_pixel_chrome wrapping
l4_chrome = """
def _l4_pixel_chrome(target_trigger: str, *, pixel_frame=None, now_ts=None) -> Dict[str, Any]:
    from System.swarm_optic_nerve import classify_ocr_text, read_chrome_ocr
    from System.swarm_iris import SwarmIris
    
    if pixel_frame is None:
        pixel_frame = SwarmIris().blink_capture()
        
    ocr_text = read_chrome_ocr(pixel_frame.file_path, frame_metadata=pixel_frame.metadata)
    classification = classify_ocr_text(ocr_text)
    
    target_models = {
        "C47H": "claude-opus-4-7",
        "AG31": "gemini-3.1-pro-high",
    }
    expected_model = target_models.get(target_trigger)
    matches = (classification["best_model"] == expected_model) if expected_model else False

    p_genuine = 0.95 if matches else 0.10
    evidence_strength = classification["best_weight"]
    
    return {
        "lane": "L4_pixel_chrome",
        "p_genuine": p_genuine,
        "evidence_strength": evidence_strength,
        "details": {
            "model_label": classification["best_model"],
            "picker_open": False,
            "active_marker": "",
            "source": pixel_frame.capture_source
        }
    }
"""

content = content.replace("def _l4_pixel_lane(", l4_chrome + "\ndef _l4_pixel_lane(")

Path("System/stigmergic_vision.py").write_text(content)
