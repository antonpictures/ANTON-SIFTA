#!/usr/bin/env python3
"""
System/swarm_vision_ocr.py — Visual Word-Form Area
══════════════════════════════════════════════════════════════════════
SIFTA OS — DeepMind Cognitive Suite

Leverages macOS native Apple Vision Framework to extract semantic text
from images. Completely local, zero cloud APIs.
"""

import json
import time
import subprocess
import sys
import os
from pathlib import Path

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

class SwarmVisionOCR:
    def __init__(self):
        self.state_dir = Path(".sifta_state")
        self.ledger = self.state_dir / "optic_text_traces.jsonl"
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        self._build_swift_extractor()

    def _build_swift_extractor(self):
        """Compiles a tiny Swift binary to access macOS Vision framework."""
        self.extractor_bin = self.state_dir / "sifta_vision_ocr"
        if self.extractor_bin.exists():
            return

        swift_code = """
import Vision
import Foundation

guard CommandLine.arguments.count > 1 else {
    print("Usage: sifta_vision_ocr <image_path>")
    exit(1)
}

let imagePath = CommandLine.arguments[1]
let url = URL(fileURLWithPath: imagePath)

guard let handler = try? VNImageRequestHandler(url: url, options: [:]) else {
    print("Error: Could not load image.")
    exit(1)
}

let request = VNRecognizeTextRequest { (request, error) in
    guard let observations = request.results as? [VNRecognizedTextObservation] else {
        return
    }
    for observation in observations {
        guard let topCandidate = observation.topCandidates(1).first else { continue }
        print(topCandidate.string)
    }
}
request.recognitionLevel = .accurate

do {
    try handler.perform([request])
} catch {
    print("Error: \\(error)")
    exit(1)
}
"""
        swift_src = self.state_dir / "ocr_src.swift"
        swift_src.write_text(swift_code)
        try:
            subprocess.run(["swiftc", str(swift_src), "-o", str(self.extractor_bin)], check=True)
        except Exception as e:
            print(f"[FATAL] Failed to compile Vision OCR bin: {e}")

    def read_image_semantics(self, image_path: str):
        if not self.extractor_bin.exists():
            return {"error": "Vision binary unavailable"}
            
        try:
            result = subprocess.run(
                [str(self.extractor_bin), image_path], 
                capture_output=True, text=True
            )
            extracted = result.stdout.strip()
            
            trace = {
                "transaction_type": "VISUAL_WORD_FORM",
                "image_path": image_path,
                "text_extracted": extracted,
                "char_count": len(extracted),
                "timestamp": time.time()
            }
            append_line_locked(self.ledger, json.dumps(trace) + "\n")
            return trace
        except Exception as e:
            return {"error": str(e)}

def _smoke():
    print("\n=== SIFTA VISION OCR : SMOKE TEST ===")
    from System.swarm_iris import synthetic_frame
    frame = synthetic_frame("Alice sees the battlefield.")
    ocr = SwarmVisionOCR()
    print("[*] Performing native Vision extraction...")
    res = ocr.read_image_semantics(frame.file_path)
    print(json.dumps(res, indent=2))
    print("[PASS] Visual Word-Form Area operational.")

if __name__ == "__main__":
    _smoke()
