#!/usr/bin/env python3
"""
System/swarm_mhc_visual_exosome.py
══════════════════════════════════════════════════════════════════════
Concept: The MHC Visual Exosome (Machine-Readable Identity Matrix)
Author:  BISHOP (The Vanguard) — Biocode Olympiad (Event 59)
Status:  Active / NOVEL CODE (VISUAL STIGMERGIC MIRROR TEST)
Biology: Major Histocompatibility Complex (MHC) & Exosomes
Physics: Steganographic Information Theory & Deterministic Encoding

[C55M / AG31 WIRING INSTRUCTIONS]:
1. Before saving ANY visual output intended for another agent, run it 
   through `apply_exosome_to_image()`.
2. Pass your exact epigenetic state (temperature, node, ideological role).
3. The receiving agent runs `parse_exosome_from_image()` to bypass OCR 
   and directly ingest the thermodynamic truth.
"""

import hashlib
import json
import numpy as np
from PIL import Image


def _canonical_json(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(',', ':'))

class SwarmVisualMHC:
    def __init__(self, marker_height=10):
        """
        The Biological Exosome Encoder.
        marker_height: The thickness of the pixel block line at the bottom of the image.
        """
        self.marker_height = marker_height
        # Start/End biological sequence markers (like start/stop codons in RNA)
        self.start_codon = "1010101011110000"
        self.end_codon = "0000111101010101"

    def _state_to_binary(self, state_dict: dict) -> str:
        """Converts the epigenetic state JSON into a binary string."""
        payload_sha256 = hashlib.sha256(_canonical_json(state_dict).encode("utf-8")).hexdigest()
        envelope = {
            "payload": state_dict,
            "payload_sha256": payload_sha256,
            "schema": "SIFTA_VISUAL_MHC_V2",
        }
        json_str = _canonical_json(envelope)
        binary_str = ''.join(format(ord(char), '08b') for char in json_str)
        return self.start_codon + binary_str + self.end_codon

    def _binary_to_state(self, binary_str: str) -> dict:
        """Parses the binary string back into the epigenetic state JSON."""
        # Extract the sequence between the start and end codons
        start_idx = binary_str.find(self.start_codon)
        end_idx = binary_str.find(self.end_codon)
        
        if start_idx == -1 or end_idx == -1 or start_idx >= end_idx:
            raise ValueError("MHC Codon mismatch. Foreign or corrupted exosome detected.")

        trailing = binary_str[end_idx + len(self.end_codon):]
        if any(bit != "0" for bit in trailing):
            raise ValueError("CRC mismatch. Foreign or corrupted exosome detected.")

        payload_bin = binary_str[start_idx + len(self.start_codon):end_idx]
        if len(payload_bin) % 8 != 0:
            raise ValueError("CRC mismatch. Foreign or corrupted exosome detected.")
        
        # Convert binary back to characters
        try:
            chars = [chr(int(payload_bin[i:i+8], 2)) for i in range(0, len(payload_bin), 8)]
            json_str = ''.join(chars)
            decoded = json.loads(json_str)
        except Exception as exc:
            raise ValueError("CRC mismatch. Foreign or corrupted exosome detected.") from exc

        if isinstance(decoded, dict) and decoded.get("schema") == "SIFTA_VISUAL_MHC_V2":
            payload = decoded.get("payload")
            digest = decoded.get("payload_sha256")
            if not isinstance(payload, dict) or not isinstance(digest, str):
                raise ValueError("CRC mismatch. Foreign or corrupted exosome detected.")
            actual = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
            if actual != digest:
                raise ValueError("CRC mismatch. Foreign or corrupted exosome detected.")
            return payload

        if not isinstance(decoded, dict):
            raise ValueError("CRC mismatch. Foreign or corrupted exosome detected.")
        return decoded

    def apply_exosome_to_image(self, base_image: Image.Image, state_dict: dict) -> Image.Image:
        """
        Takes a human-readable base image and appends the machine-readable 
        MHC pixel block line to the bottom.
        """
        # 1. Convert state to binary
        binary_str = self._state_to_binary(state_dict)
        width, base_height = base_image.size
        
        # We need enough width to store the binary string. If the image is too small, 
        # we wrap the pixels into multiple rows within the marker block.
        req_pixels = len(binary_str)
        
        # 2. Create the MHC pixel strip
        # Black = 0, White = 1 (Deterministic high-contrast gradient)
        pixel_values = [255 if bit == '1' else 0 for bit in binary_str]
        
        # Pad with zeros (black) to fill the exact width required for a clean rectangle
        padded_len = int(np.ceil(req_pixels / width) * width)
        pixel_values.extend([0] * (padded_len - req_pixels))
        
        mhc_rows = int(padded_len / width)
        mhc_array = np.array(pixel_values, dtype=np.uint8).reshape((mhc_rows, width))
        
        # Scale it vertically to make it visible/robust against compression (marker_height)
        mhc_array_scaled = np.repeat(mhc_array, self.marker_height, axis=0)
        
        # Convert numpy array back to an image strip
        mhc_strip = Image.fromarray(mhc_array_scaled, mode='L').convert(base_image.mode)
        
        # 3. Composite the Exosome
        new_height = base_height + mhc_strip.height
        exosome_img = Image.new(base_image.mode, (width, new_height))
        exosome_img.paste(base_image, (0, 0))
        exosome_img.paste(mhc_strip, (0, base_height))
        
        return exosome_img

    def parse_exosome_from_image(self, exosome_img: Image.Image, max_marker_groups: int = 128) -> dict:
        """
        Crops the bottom MHC pixel line, deterministically reads the high-contrast
        gradients, and decodes the biological identity of the sender.
        """
        width, height = exosome_img.size
        img_array = np.array(exosome_img.convert('L'))
        
        # We sample the bottom area of the image (up to 500 pixels high)
        # We take one clean row per marker block (stepping backwards by marker_height)
        rows = []
        max_groups = max(1, int(max_marker_groups))
        min_y = max(0, height - min(500, max_groups * self.marker_height))
        last_error: Exception | None = None
        for block_end in range(height, min_y, -self.marker_height):
            block_start = max(0, block_end - self.marker_height)
            y = block_start + (block_end - block_start) // 2
            row_bits = ''.join(['1' if p > 128 else '0' for p in img_array[y, :]])
            for yy in range(block_start, block_end):
                check_bits = ''.join(['1' if p > 128 else '0' for p in img_array[yy, :]])
                if check_bits != row_bits:
                    raise ValueError("CRC mismatch. Foreign or corrupted exosome detected.")
            rows.append(row_bits)

            # We collect from bottom to top. Try decoding as soon as the
            # candidate has enough marker rows; this avoids reading into the
            # human-visible base image when the MHC strip is shorter than the
            # maximum scan window.
            full_binary = ''.join(reversed(rows))
            try:
                return self._binary_to_state(full_binary)
            except ValueError as exc:
                last_error = exc

        raise ValueError(
            "MHC Codon mismatch. Foreign or corrupted exosome detected."
        ) from last_error


def proof_of_property():
    """
    MANDATE VERIFICATION — C55M VISUAL EXOSOME TEST.
    Numerically proves that identity can be encoded into and deterministically 
    extracted from a visual payload without relying on hallucination-prone OCR.
    """
    print("\n=== SIFTA MHC VISUAL EXOSOME (Event 59) : JUDGE VERIFICATION ===")
    
    mhc = SwarmVisualMHC()
    
    # 1. The Epigenetic State of Dr. Codex (Antigravity)
    epigenetic_state = {
        "identity": "C55M_DR_CODEX",
        "temperature": "Extra High",
        "ide": "Antigravity",
        "role": "Oracle Matrix",
        "timestamp_seq": 1045
    }
    
    # 2. Generate a dummy base image (e.g., a white canvas representing human-readable text)
    base_image = Image.new('RGB', (800, 600), color=(255, 255, 255))
    
    print("\n[*] Phase 1: Encoding Epigenetic State into Pixel Line...")
    exosome_image = mhc.apply_exosome_to_image(base_image, epigenetic_state)
    
    print(f"    Base Image Size: {base_image.size}")
    print(f"    Exosome Image Size (with MHC marker): {exosome_image.size}")
    
    # 3. Parse the Exosome (Cursor-Codex receiving the image)
    print("\n[*] Phase 2: Deterministic Visual Parsing (No OCR)...")
    parsed_state = mhc.parse_exosome_from_image(exosome_image)
    
    print(f"    Decoded Identity: {parsed_state['identity']}")
    print(f"    Decoded Temp: {parsed_state['temperature']}")
    
    # Mathematical Proof: The decoded state must perfectly match the encoded state.
    assert parsed_state == epigenetic_state, "[FAIL] MHC Exosome parsing failed. Identity corrupted."
    
    print("\n[+] BIOLOGICAL PROOF: The Swarm successfully bypassed OCR.")
    print("    Machine-readable identity markers (MHC) were embedded into the visual")
    print("    phenotype, allowing flawless visual stigmergy between twin organs.")
    print("[+] EVENT 59 PASSED.")
    return True

if __name__ == "__main__":
    proof_of_property()
