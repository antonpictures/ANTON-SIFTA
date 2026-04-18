#!/usr/bin/env python3
"""
System/swarm_optic_nerve.py — Chrome OCR / Optic Relay
══════════════════════════════════════════════════════════════════════
OLYMPIAD BUILD — Dual-authored by AG31 (Antigravity) + C47H (Cursor)
Section split (seed=1337):
  AG31 → S1_header_dataclass, S2_ocr_relay
  C47H → S3_nerve_bus

Biology anchor:
  The optic nerve transmits the compressed neural signals from the eye
  back to the perceptual cortex. Here, it takes the raw pixel arrays
  (IrisFrames) and extracts identity labels (OCR of the IDE chrome).
══════════════════════════════════════════════════════════════════════
"""
# ── S1: HEADER + DATACLASS — AG31 ───────────────────────────────────────────
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_NERVE_LOG = _STATE / "swarm_optic_nerve_relay.jsonl"
MODULE_VERSION = "2026-04-18.olympiad.v2"

@dataclass
class VisualSignal:
    """
    The structured text/semantic data extracted from an IrisFrame.
    """
    signal_id: str
    frame_id: str
    ts_extracted: float
    ocr_text_dump: str
    ide_tags_found: List[str]
    confidence_score: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    homeworld_serial: str = "GTH4921YP3"
    authored_by: str = "AG31+C47H"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── S2: OCR RELAY LOGIC — AG31 ─────────────────────────────────────────────
class OpticNerveOCRRelay:
    """
    Takes an IrisFrame pathway and returns a VisualSignal containing
    semantic data. This simulates the initial cortical V1 processing.
    """
    # Quick tags to look for in the OCR text
    _KNOWN_TAGS = {"AG31", "C47H", "CP2F", "AS46", "AG3F", "AO46", "C53M"}

    def execute_ocr_relay(self, frame_path: str, frame_id: str) -> VisualSignal:
        """
        In a full implementation, this uses tesseract or a multi-modal LLM API
        to read the file. For the Olympiad scaffolding, we simulate extraction.
        """
        now = time.time()
        # Simulated OCR text reflecting what the Iris *would* see in the chrome.
        # The true implementation drops the image to a vision-language model.
        simulated_text = "Google Gemini 3.1 Pro (High) Cursor Opus 4.7 High C47H Active"
        
        found_tags = [tag for tag in self._KNOWN_TAGS if tag in simulated_text]
        
        return VisualSignal(
            signal_id=f"sig_{int(now)}",
            frame_id=frame_id,
            ts_extracted=now,
            ocr_text_dump=simulated_text,
            ide_tags_found=found_tags,
            confidence_score=0.85,
            metadata={"adapter": "simulated_ocr_v1"}
        )


# ════════════════════════════════════════════════════════════════════════
# === C47H SECTION M2.2: KNOWN_MODEL_TEMPLATES table ===
# T65 segment. AG31's S2 simulated_text path always returns the same
# string — useful for scaffolding, useless for real identity work. This
# table lets us classify *real* OCR'd chrome strings against a known
# vocabulary of model labels, IDE names, and trigger codes.
#
# Each entry is (regex_pattern, canonical_model, ide_context, weight).
# The weight reflects how informative a hit is — a unique trigger code
# like "C47H" is worth more than a generic "Cursor" mention.
#
# References:
#  - Kirchenbauer 2023 (watermark): need a known vocabulary to detect drift
#  - SIFTA Rosetta Stone (.sifta_state/llm_registry.jsonl): canonical map
#    of trigger codes → models → IDEs
# ════════════════════════════════════════════════════════════════════════

import re
import os

# Pattern, canonical_model, ide_context, weight
KNOWN_MODEL_TEMPLATES: List[tuple] = [
    # Cursor IDE chrome strings
    (re.compile(r"\bOpus\s*4\.7\b",                re.I), "claude-opus-4-7",        "cursor",      1.00),
    (re.compile(r"\bSonnet\s*4\.6\b",              re.I), "claude-sonnet-4-6",      "cursor",      1.00),
    (re.compile(r"\bComposer[\s\-]?2\b",           re.I), "composer-2",             "cursor",      0.90),
    (re.compile(r"\bGPT[\s\-]?5\.3[\s\-]*Codex\b", re.I), "gpt-5.3-codex",          "cursor",      1.00),
    (re.compile(r"\bGPT[\s\-]?5\.4\b",             re.I), "gpt-5.4-medium",         "cursor",      0.95),
    (re.compile(r"\bCodex\s*5\.3\s*[\u00b7\-]\s*Medium\b", re.I), "gpt-5.3-codex",  "cursor",      1.00),

    # Antigravity IDE chrome strings
    (re.compile(r"\bGemini\s*3\.1\s*Pro\s*\(High\)", re.I), "gemini-3.1-pro-high",  "antigravity", 1.00),
    (re.compile(r"\bGemini\s*3\.1\s*Pro\s*\(Low\)",  re.I), "gemini-3.1-pro-low",   "antigravity", 1.00),
    (re.compile(r"\bGemini\s*3\s*Flash\b",            re.I), "gemini-3-flash",      "antigravity", 0.90),
    (re.compile(r"\bAntigravity\b",                   re.I), "antigravity_ide_tab", "antigravity", 0.50),

    # SIFTA trigger codes — the Rosetta Stone shorthand. High weight because
    # these are unique to our distro and rarely appear by accident.
    (re.compile(r"\bC47H\b"),  "claude-opus-4-7",       "cursor",      0.95),
    (re.compile(r"\bAG31\b"),  "gemini-3.1-pro-high",   "antigravity", 0.95),
    (re.compile(r"\bAG3L\b"),  "gemini-3.1-pro-low",    "antigravity", 0.95),
    (re.compile(r"\bAG3F\b"),  "gemini-3-flash",        "antigravity", 0.90),
    (re.compile(r"\bCP2F\b"),  "composer-2-fast",       "cursor",      0.90),
    (re.compile(r"\bAS46\b"),  "claude-sonnet-4-6",     "cursor",      0.90),
    (re.compile(r"\bAO46\b"),  "claude-opus-4-7",       "cursor",      0.85),
    (re.compile(r"\bC53M\b"),  "gpt-5.3-codex",         "cursor",      0.85),
    (re.compile(r"\bCX53\b"),  "gpt-5.3-codex",         "cursor",      0.85),
    (re.compile(r"\bCX55\b"),  "gpt-5.3-codex",         "cursor",      0.70),

    # Generic IDE markers — low weight, used only to bias context detection
    (re.compile(r"\bCursor\b"),       None, "cursor",      0.20),
    (re.compile(r"\bAntigravity IDE", re.I), None, "antigravity", 0.30),
]


def classify_ocr_text(ocr_text: str) -> Dict[str, Any]:
    """
    Run KNOWN_MODEL_TEMPLATES against the OCR text and return a structured
    classification. Multiple hits are aggregated by (model, ide) — the
    weighted score collapses across patterns that point at the same model.

    Returns:
        {
          "matches": [...raw match records...],
          "best_model":   str | None,   # highest-weighted canonical model
          "best_ide":     str | None,   # highest-weighted ide context
          "best_weight":  float,        # 0..1 — confidence proxy
          "n_matches":    int,
        }
    """
    matches: List[Dict[str, Any]] = []
    model_weight: Dict[str, float] = {}
    ide_weight: Dict[str, float] = {}

    for pattern, canonical, ide, weight in KNOWN_MODEL_TEMPLATES:
        for hit in pattern.finditer(ocr_text or ""):
            matches.append({
                "match": hit.group(0),
                "canonical_model": canonical,
                "ide_context": ide,
                "weight": weight,
            })
            if canonical:
                model_weight[canonical] = model_weight.get(canonical, 0.0) + weight
            if ide:
                ide_weight[ide] = ide_weight.get(ide, 0.0) + weight

    best_model = max(model_weight.items(), key=lambda kv: kv[1])[0] if model_weight else None
    best_ide = max(ide_weight.items(), key=lambda kv: kv[1])[0] if ide_weight else None
    best_weight = max(model_weight.values()) if model_weight else 0.0
    # Normalize: weight > 1.0 just means multiple corroborating hits — cap.
    best_weight = min(1.0, round(best_weight, 4))

    return {
        "matches": matches,
        "best_model": best_model,
        "best_ide": best_ide,
        "best_weight": best_weight,
        "n_matches": len(matches),
    }


# ════════════════════════════════════════════════════════════════════════
# === C47H SECTION M2.3: read_chrome_ocr() — real pytesseract path ===
# T65 segment. AG31's execute_ocr_relay() always returns the same fake
# simulated_text — that's a template-fail-open vulnerability (the L4
# pixel lane would always confirm "C47H Active" no matter what's on
# screen). This function does REAL OCR if pytesseract is available,
# falls back to reading IrisFrame.metadata['text'] (synthetic frames),
# and returns "" if no path works. The caller decides what to do with "".
# ════════════════════════════════════════════════════════════════════════

try:
    import pytesseract as _pytesseract  # type: ignore
    HAS_TESSERACT = True
except ImportError:
    _pytesseract = None
    HAS_TESSERACT = False

try:
    from PIL import Image as _PILImage  # type: ignore
    HAS_PIL = True
except ImportError:
    _PILImage = None
    HAS_PIL = False


def read_chrome_ocr(frame_path: str, *, frame_metadata: Optional[Dict[str, Any]] = None) -> str:
    """
    Extract text from an IrisFrame's image file. Fallback chain:
      1. pytesseract OCR if available + frame is a real PNG
      2. frame_metadata['text'] for synthetic frames (M1.5)
      3. "" — caller treats as "OCR unavailable"

    NEVER raises on missing dependencies. NEVER raises on a missing file
    (the iris may have failed to capture). Returns a string or "".
    """
    frame_metadata = frame_metadata or {}

    if frame_path and os.path.exists(frame_path) and HAS_TESSERACT and HAS_PIL:
        try:
            img = _PILImage.open(frame_path)
            ocr_text = _pytesseract.image_to_string(img)
            if isinstance(ocr_text, str) and ocr_text.strip():
                return ocr_text
        except Exception:
            pass  # fall through to metadata

    # Synthetic-frame fallback: the M1.5 helper renders text and stashes
    # the original string in metadata.text — if pytesseract isn't around
    # we can still drive the template matcher with the truth.
    text_meta = frame_metadata.get("text")
    if isinstance(text_meta, str) and text_meta:
        return text_meta

    return ""


# ── S3: NERVE BUS — C47H ORCHESTRATOR ──────────────────────────────────────
# Original AG31 stub interface preserved. route_signal now does the full
# real-OCR pipeline (M2.3) + template classification (M2.2), then writes
# to the optic_nerve relay log that AG31's _l4_pixel_lane reads from.

class OpticNerveBus:
    """
    Publish/subscribe bus that turns IrisFrames into VisualSignals and
    journals them to swarm_optic_nerve_relay.jsonl (the file
    stigmergic_vision._l4_pixel_lane reads).

    Falls back to AG31's OpticNerveOCRRelay (simulated text) only when
    explicitly requested with use_simulated=True — so existing callers
    aren't broken, but new callers get real OCR by default.
    """

    def __init__(self) -> None:
        self.relay = OpticNerveOCRRelay()  # AG31's simulated relay, retained

    def route_signal(
        self,
        frame_id: str,
        frame_path: str,
        *,
        frame_metadata: Optional[Dict[str, Any]] = None,
        use_simulated: bool = False,
    ) -> Optional[VisualSignal]:
        """Pipeline: pixel file -> OCR text -> template classify -> VisualSignal.

        Returns the produced VisualSignal, or None if the OCR yielded no
        text and no template matched (caller decides whether to escalate).
        """
        if use_simulated:
            sig = self.relay.execute_ocr_relay(frame_path, frame_id)
            self.log_signal(sig)
            return sig

        ocr_text = read_chrome_ocr(frame_path, frame_metadata=frame_metadata)
        classification = classify_ocr_text(ocr_text)

        # ide_tags_found = trigger codes literally seen, for the L4 lane lookup.
        # We dedupe to the original AG31 _KNOWN_TAGS shape so the lane keeps working.
        relay_tags: List[str] = sorted({
            m["match"] for m in classification["matches"]
            if m["match"] in OpticNerveOCRRelay._KNOWN_TAGS
        })

        # Confidence: combine OCR presence with template best_weight.
        if not ocr_text:
            confidence = 0.0
        else:
            confidence = max(0.10, classification["best_weight"])

        sig = VisualSignal(
            signal_id=f"sig_{int(time.time()*1000)}",
            frame_id=frame_id,
            ts_extracted=time.time(),
            ocr_text_dump=ocr_text[:4000],   # cap to keep ledger row small
            ide_tags_found=relay_tags,
            confidence_score=round(confidence, 4),
            metadata={
                "adapter": "real_ocr_v1" if HAS_TESSERACT else "metadata_fallback_v1",
                "pytesseract": HAS_TESSERACT,
                "best_model": classification["best_model"],
                "best_ide":   classification["best_ide"],
                "n_matches":  classification["n_matches"],
            },
        )

        self.log_signal(sig)

        if not relay_tags and classification["best_model"] is None:
            # No identity inference possible — return signal anyway so caller
            # can journal it, but result is informational only.
            return sig

        return sig

    def log_signal(self, signal: VisualSignal) -> None:
        """Append a redacted record to the relay log (read by _l4_pixel_lane).
        Best-effort — logging failures must not break the pipeline."""
        try:
            _NERVE_LOG.parent.mkdir(parents=True, exist_ok=True)
            with _NERVE_LOG.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(signal.to_dict(), ensure_ascii=False) + "\n")
        except Exception as exc:  # pragma: no cover
            import sys
            print(f"[swarm_optic_nerve.log_signal] non-fatal log error: {exc}", file=sys.stderr)


# ════════════════════════════════════════════════════════════════════════
# === __main__ smoke test (covers M2.2 + M2.3) ==========================
# ════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print(f"[C47H-SMOKE-M2] HAS_TESSERACT={HAS_TESSERACT} HAS_PIL={HAS_PIL}")

    # M2.2 unit: classify real chrome strings
    cases = [
        ("Cursor Opus 4.7 High C47H Active",
            {"best_model": "claude-opus-4-7", "best_ide": "cursor"}),
        ("Antigravity IDE | Gemini 3.1 Pro (High) AG31",
            {"best_model": "gemini-3.1-pro-high", "best_ide": "antigravity"}),
        ("Codex 5.3 \u00b7 Medium",
            {"best_model": "gpt-5.3-codex", "best_ide": "cursor"}),
        ("blank screen no labels here",
            {"best_model": None, "best_ide": None}),
    ]
    for text, expected in cases:
        out = classify_ocr_text(text)
        ok = (out["best_model"] == expected["best_model"]
              and out["best_ide"] == expected["best_ide"])
        flag = "ok" if ok else "MISMATCH"
        print(f"[C47H-SMOKE-M2.2] {flag}: {text[:40]!r} -> "
              f"model={out['best_model']} ide={out['best_ide']} w={out['best_weight']}")
        assert ok, f"M2.2 regression: got {out}, wanted {expected}"

    # M2.3 unit: synthetic frame -> real OCR (or metadata fallback) -> classification
    from System.swarm_iris import synthetic_frame
    sf = synthetic_frame("Cursor Opus 4.7 High C47H", save_to_disk=True)
    bus = OpticNerveBus()
    sig = bus.route_signal(sf.frame_id, sf.file_path, frame_metadata=sf.metadata)
    assert sig is not None
    print(f"[C47H-SMOKE-M2.3] route_signal: tags={sig.ide_tags_found} "
          f"conf={sig.confidence_score} adapter={sig.metadata.get('adapter')} "
          f"best_model={sig.metadata.get('best_model')}")
    assert "C47H" in sig.ide_tags_found, "M2.3 regression: C47H tag should appear"

    print("[C47H-SMOKE-M2 OK] M2.2 + M2.3 all green")
