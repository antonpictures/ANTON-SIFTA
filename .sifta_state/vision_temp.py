#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from System.swarm_vision_ocr import SwarmVisionOCR
    ocr = SwarmVisionOCR()
    text = ocr.read_image_text(".sifta_state/IMG_4314.jpg")
    print("OCR TEXT:", text)
except Exception as e:
    print("OCR error:", e)

