#!/usr/bin/env python3
"""
Utilities/swarm_eye_smoke.py — End-to-end smoke for the SIFTA Swarm Eye
══════════════════════════════════════════════════════════════════════
T65 SEGMENT M5.3 — exercises every C47H-owned surface (M1.1, M1.4,
M1.5, M2.2, M2.3, M3.5, M4.4, M4.6, M4.10, M5.1) in one runnable script.

Usage:
    python3 -m Utilities.swarm_eye_smoke
    python3 -m Utilities.swarm_eye_smoke --verbose
    python3 -m Utilities.swarm_eye_smoke --no-passport-write   # dry run

Exit codes:
    0  — all green
    1  — at least one segment failed (details printed)
    2  — fatal import error (eye stack is structurally broken)

Designed for CI: never assumes a display, webcam, or pytesseract; uses
the synthetic_frame helper everywhere a real capture is unavailable.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from typing import Any, Callable, Dict, List, Tuple


def _step(name: str, fn: Callable[[], Any], *, verbose: bool) -> Tuple[bool, str, Any]:
    """Run a single smoke step. Returns (ok, message, value)."""
    t0 = time.time()
    try:
        result = fn()
        elapsed_ms = round((time.time() - t0) * 1000, 1)
        msg = f"PASS [{elapsed_ms:>6}ms] {name}"
        if verbose and result is not None:
            msg += f"  -> {result}"
        return True, msg, result
    except AssertionError as exc:
        elapsed_ms = round((time.time() - t0) * 1000, 1)
        return False, f"FAIL [{elapsed_ms:>6}ms] {name}: assertion failed: {exc}", None
    except Exception as exc:
        elapsed_ms = round((time.time() - t0) * 1000, 1)
        tb = traceback.format_exc(limit=3) if verbose else ""
        return False, f"FAIL [{elapsed_ms:>6}ms] {name}: {exc!r}\n{tb}", None


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="SIFTA Swarm Eye end-to-end smoke")
    parser.add_argument("--verbose", action="store_true", help="print full results + tracebacks")
    parser.add_argument("--no-passport-write", action="store_true",
                        help="skip the M4.10 persistence write to the ledger")
    args = parser.parse_args(argv)

    # Top-level imports — if these fail, the eye stack is broken structurally.
    try:
        from System.swarm_visual_system import (
            capability_report, synthetic_frame, webcam_frame,
            classify_ocr_text, OpticNerveBus,
            smoke_pixel_lane, see_now,
            HealthChecker, PassportAuthority, recent_passports,
        )
    except Exception as exc:
        print(f"[M5.3 FATAL] structural import failure: {exc!r}", file=sys.stderr)
        return 2

    print("=" * 72)
    print("SIFTA SWARM EYE — END-TO-END SMOKE (T65 / M5.3)")
    print("=" * 72)
    cap = capability_report()
    print(f"capability: pytesseract={('?' if 'pytesseract' not in cap else cap.get('pytesseract'))} "
          f"PIL={cap['pil']} cv2={cap['cv2']} "
          f"mac_screencapture={cap['mac_screencapture']} platform={cap['platform']}")
    print("-" * 72)

    results: List[Tuple[bool, str, Any]] = []

    # ── M1.1: capability_report shape ──────────────────────────────────────
    def _m1_1():
        r = capability_report()
        for k in ("mss", "cv2", "pil", "platform", "max_frame_bytes"):
            assert k in r, f"missing key {k}"
        return f"keys={list(r.keys())}"
    results.append(_step("M1.1 capability_report", _m1_1, verbose=args.verbose))

    # ── M1.5: synthetic_frame ──────────────────────────────────────────────
    def _m1_5():
        f = synthetic_frame("Cursor Opus 4.7 High C47H", save_to_disk=False)
        assert f.capture_source == "synthetic"
        assert f.byte_size > 0
        return f"frame={f.frame_id} {f.width}x{f.height} bytes={f.byte_size}"
    results.append(_step("M1.5 synthetic_frame", _m1_5, verbose=args.verbose))

    # ── M1.4: webcam_frame (None on CI is normal) ──────────────────────────
    def _m1_4():
        wf = webcam_frame(grab_timeout_s=0.05)
        # Either None or a valid frame — both are acceptable
        if wf is None:
            return "no webcam (expected in CI)"
        return f"frame={wf.frame_id} {wf.width}x{wf.height}"
    results.append(_step("M1.4 webcam_frame (optional)", _m1_4, verbose=args.verbose))

    # ── M2.2: classify_ocr_text ────────────────────────────────────────────
    def _m2_2():
        cases = [
            ("Cursor Opus 4.7 High C47H Active", "claude-opus-4-7", "cursor"),
            ("Antigravity IDE Gemini 3.1 Pro (High) AG31", "gemini-3.1-pro-high", "antigravity"),
            ("Codex 5.3 \u00b7 Medium",                   "gpt-5.3-codex",       "cursor"),
        ]
        for txt, want_model, want_ide in cases:
            r = classify_ocr_text(txt)
            assert r["best_model"] == want_model, f"{txt!r} -> {r['best_model']} != {want_model}"
            assert r["best_ide"]   == want_ide,   f"{txt!r} -> {r['best_ide']} != {want_ide}"
        return f"{len(cases)} chrome strings classified correctly"
    results.append(_step("M2.2 KNOWN_MODEL_TEMPLATES classifier", _m2_2, verbose=args.verbose))

    # ── M2.3: OCR pipeline (synthetic frame -> route_signal -> tags) ───────
    def _m2_3():
        sf = synthetic_frame("Cursor Opus 4.7 High C47H Active", save_to_disk=True)
        bus = OpticNerveBus()
        sig = bus.route_signal(sf.frame_id, sf.file_path, frame_metadata=sf.metadata)
        assert sig is not None, "route_signal returned None"
        assert "C47H" in sig.ide_tags_found, f"C47H tag missing from {sig.ide_tags_found}"
        return f"tags={sig.ide_tags_found} conf={sig.confidence_score} adapter={sig.metadata.get('adapter')}"
    results.append(_step("M2.3 read_chrome_ocr + route_signal", _m2_3, verbose=args.verbose))

    # ── M3.5: pixel-lane smoke ─────────────────────────────────────────────
    def _m3_5():
        ok = smoke_pixel_lane()
        assert ok, "smoke_pixel_lane returned False"
        return "L4 lane reads back fresh signal"
    results.append(_step("M3.5 stigmergic_vision._l4_pixel_lane", _m3_5, verbose=args.verbose))

    # ── M4.4: signature predicate ──────────────────────────────────────────
    def _m4_4():
        hc = HealthChecker()
        assert hasattr(hc, "check_signature_present"), "M4.4 not patched in"
        # We don't assert True/False — depends on whether C47H has fresh
        # watermark rows. We assert it returns a bool without raising.
        v = hc.check_signature_present("C47H")
        assert isinstance(v, bool), f"non-bool: {v!r}"
        return f"check_signature_present('C47H') = {v}"
    results.append(_step("M4.4 signature predicate", _m4_4, verbose=args.verbose))

    # ── M4.6: latency envelope predicate ───────────────────────────────────
    def _m4_6():
        hc = HealthChecker()
        assert hasattr(hc, "check_latency_envelope_ok"), "M4.6 not patched in"
        v = hc.check_latency_envelope_ok("C47H")
        assert isinstance(v, bool), f"non-bool: {v!r}"
        return f"check_latency_envelope_ok('C47H') = {v}"
    results.append(_step("M4.6 latency envelope predicate", _m4_6, verbose=args.verbose))

    # ── M4.10: persistence + recent_passports ──────────────────────────────
    def _m4_10():
        if args.no_passport_write:
            return "skipped (--no-passport-write)"
        auth = PassportAuthority(persist=True)
        p = auth.issue_passport("C47H")
        rows = recent_passports("C47H", limit=5)
        assert len(rows) >= 1, "no rows persisted"
        assert rows[-1]["swimmer_id"] == "C47H", "tail row swimmer mismatch"
        return f"is_valid={p.is_valid} ledger_tail={len(rows)} rows"
    results.append(_step("M4.10 passport persistence", _m4_10, verbose=args.verbose))

    # ── M5.1: see_now end-to-end ───────────────────────────────────────────
    def _m5_1():
        result = see_now("C47H", source="ide_chrome_screenshot",
                         issue_passport=not args.no_passport_write)
        # Tolerant assertions — capture might fail in CI, that's OK if we
        # at least got an L4 lane read from prior smoke runs.
        assert "frame_id" in result, f"no frame captured: {result.get('errors')}"
        assert "l4_p_genuine" in result, "L4 lane not exercised"
        return (f"frame={result['frame_id']} l4_p={result.get('l4_p_genuine')} "
                f"errors={len(result.get('errors', []))}")
    results.append(_step("M5.1 see_now() umbrella one-shot", _m5_1, verbose=args.verbose))

    # Print + tally
    print()
    for ok, msg, _ in results:
        print(msg)
    print("-" * 72)
    n_ok = sum(1 for ok, _, _ in results if ok)
    n_fail = sum(1 for ok, _, _ in results if not ok)
    summary = f"PASSED {n_ok}/{len(results)}"
    if n_fail:
        summary += f"   FAILED {n_fail}"
    print(summary)
    print("=" * 72)

    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
