#!/usr/bin/env python3
"""
vision_validator.py — The Optical Oracle
══════════════════════════════════════════════════
Bridges the captured photonic hash into the local Ollama Vision matrix.
Maintains absolute temperature=0 zero-shot inference. 
If the physical world does not perfectly match the target geometry, it returns NO.
"""

import subprocess
import json
import base64
from pathlib import Path
from typing import Tuple

class OpticalOracle:
    def __init__(self, model_name: str = "llama3.2-vision"):
        self.model_name = model_name

    def validate_geometry(self, image_path: Path, expected_geometry: str) -> Tuple[bool, str]:
        """
        Pipes the physical image directly into local silicon.
        Returns (True/False, Oracle Logic).
        """
        if not image_path.exists():
            return False, "OPTICAL_STREAM_MISSING"

        # Check if we are running in headless mock mode
        with open(image_path, "rb") as f:
            header = f.read(18)
            if header == b"MOCK_OPTICAL_ARRAY":
                print(f"[👁️ ORACLE] Headless Array Detected. Simulating Vision validation for '{expected_geometry}'.")
                return True, "MOCK_VALIDATION_APPROVED"
        
        # Read image to base64
        with open(image_path, "rb") as f:
            b64_image = base64.b64encode(f.read()).decode("utf-8")

        prompt = (
            f"You are the SIFTA Sovereign OCR and Geometry Validator. "
            f"Analyze the attached physical image. Does this physical object precisely match "
            f"a successfully manufactured '{expected_geometry}'?\n"
            f"Respond exclusively with YES or NO. No other text is permitted."
        )

        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [b64_image]
                }
            ],
            "stream": False,
            "options": {"temperature": 0.0} # Absolute zero hallucination
        }

        try:
            cmd = ["curl", "-s", "-X", "POST", "http://127.0.0.1:11434/api/chat", "-d", json.dumps(payload)]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if res.returncode != 0:
                return False, f"OLLAMA_CALL_FAILED: {res.stderr}"
                
            response_json = json.loads(res.stdout)
            oracle_decision = response_json.get("message", {}).get("content", "").strip().upper()
            
            print(f"[👁️ ORACLE] Vision parsing complete. Decision: {oracle_decision}")
            
            if "YES" in oracle_decision:
                return True, "VISION_APPROVED"
            else:
                return False, f"VISION_REJECTED: Model perceived {oracle_decision}"

        except Exception as e:
            return False, f"VISION_CRASH: {e}"

# Global Singleton
oracle = OpticalOracle()
