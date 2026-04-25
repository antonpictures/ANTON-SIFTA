#!/usr/bin/env python3
"""
Machine-readable visual identity markers for SIFTA images.

Event 59: MHC Visual Exosome.

The human-readable image remains visible to the Architect. A deterministic
black/white marker strip is appended to the bottom so peer IDEs can parse the
sender's identity without OCR. This is not steganographic secrecy; it is a
robust, machine-readable MHC surface tag.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np
from PIL import Image

START_CODON = "1010101011110000"
END_CODON = "0000111101010101"
MODULE_VERSION = "swarm_visual_mhc_exosome.v1"


@dataclass(frozen=True)
class DecodedExosome:
    state: Dict[str, Any]
    payload_sha256: str
    payload_bits: int
    marker_height: int
    start_bit: int


class SwarmVisualMHC:
    """Encode/decode a deterministic MHC pixel strip at the image bottom."""

    def __init__(self, marker_height: int = 10) -> None:
        if marker_height <= 0:
            raise ValueError("marker_height must be positive")
        self.marker_height = marker_height

    def state_to_bits(self, state_dict: Dict[str, Any]) -> str:
        payload = json.dumps(
            state_dict,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        payload_bits = _bytes_to_bits(payload)
        payload_len = f"{len(payload):032b}"
        digest_bits = _bytes_to_bits(hashlib.sha256(payload).digest())
        return START_CODON + payload_len + payload_bits + digest_bits + END_CODON

    def apply_exosome_to_image(
        self,
        base_image: Image.Image,
        state_dict: Dict[str, Any],
    ) -> Image.Image:
        """Append a deterministic MHC strip to a human-readable image."""
        if base_image.width <= 0 or base_image.height <= 0:
            raise ValueError("base image must have positive dimensions")

        bits = self.state_to_bits(state_dict)
        width = base_image.width
        padded_len = int(math.ceil(len(bits) / width) * width)
        bits = bits + ("0" * (padded_len - len(bits)))

        pixels = np.array([255 if bit == "1" else 0 for bit in bits], dtype=np.uint8)
        logical_rows = pixels.reshape((padded_len // width, width))
        marker_rows = np.repeat(logical_rows, self.marker_height, axis=0)
        strip = Image.fromarray(marker_rows).convert(base_image.mode)

        out = Image.new(base_image.mode, (width, base_image.height + strip.height))
        out.paste(base_image, (0, 0))
        out.paste(strip, (0, base_image.height))
        return out

    def parse_exosome_from_image(self, exosome_img: Image.Image) -> Dict[str, Any]:
        """Return only the decoded state dict, matching Bishop's public API."""
        return self.decode_exosome(exosome_img).state

    def decode_exosome(self, exosome_img: Image.Image) -> DecodedExosome:
        """Decode and validate the bottom MHC strip from an image."""
        if exosome_img.width <= 0 or exosome_img.height < self.marker_height:
            raise ValueError("image is too small to contain an MHC exosome")

        bits = self._collapse_candidate_rows(exosome_img)
        decoded: List[DecodedExosome] = []
        start = bits.find(START_CODON)
        while start != -1:
            try:
                decoded.append(self._decode_at(bits, start))
            except ValueError:
                pass
            start = bits.find(START_CODON, start + 1)
        if not decoded:
            raise ValueError("MHC codon mismatch or corrupted exosome detected")
        # The true marker strip is appended at the bottom, so prefer the last
        # valid occurrence after scanning the entire image.
        return decoded[-1]

    def _collapse_candidate_rows(self, img: Image.Image) -> str:
        arr = np.array(img.convert("L"))
        height, width = arr.shape
        bits_by_group: List[str] = []

        # Walk bottom-up in exact marker-height groups. This aligns with strips
        # created by apply_exosome_to_image() while tolerating any base height.
        for group_start in range(height - self.marker_height, -1, -self.marker_height):
            sample_row = group_start + (self.marker_height // 2)
            row = arr[sample_row, :width]
            bits_by_group.append("".join("1" if p > 128 else "0" for p in row))

        return "".join(reversed(bits_by_group))

    def _decode_at(self, bits: str, start: int) -> DecodedExosome:
        pos = start + len(START_CODON)
        if pos + 32 > len(bits):
            raise ValueError("MHC length header truncated")
        payload_len = int(bits[pos : pos + 32], 2)
        pos += 32

        payload_bit_len = payload_len * 8
        payload_bits = bits[pos : pos + payload_bit_len]
        if len(payload_bits) != payload_bit_len:
            raise ValueError("MHC payload truncated")
        pos += payload_bit_len

        digest_bits = bits[pos : pos + 256]
        if len(digest_bits) != 256:
            raise ValueError("MHC digest truncated")
        pos += 256

        if bits[pos : pos + len(END_CODON)] != END_CODON:
            raise ValueError("MHC end codon mismatch")

        payload = _bits_to_bytes(payload_bits)
        digest = _bits_to_bytes(digest_bits).hex()
        actual = hashlib.sha256(payload).hexdigest()
        if digest != actual:
            raise ValueError("MHC payload digest mismatch")

        state = json.loads(payload.decode("utf-8"))
        if not isinstance(state, dict):
            raise ValueError("MHC payload did not decode to an object")
        return DecodedExosome(
            state=state,
            payload_sha256=actual,
            payload_bits=payload_bit_len,
            marker_height=self.marker_height,
            start_bit=start,
        )


def _bytes_to_bits(payload: bytes) -> str:
    return "".join(f"{byte:08b}" for byte in payload)


def _bits_to_bytes(bits: str) -> bytes:
    if len(bits) % 8 != 0:
        raise ValueError("bit string length must be divisible by 8")
    return bytes(int(bits[i : i + 8], 2) for i in range(0, len(bits), 8))


def proof_of_property() -> bool:
    """Numerically prove encode/decode identity round-trip without OCR."""
    mhc = SwarmVisualMHC(marker_height=10)
    state = {
        "identity": "C55M_DR_CODEX",
        "ide": "codex",
        "model": "GPT-5.5 Extra High",
        "role": "oracle_matrix",
        "schema": "SIFTA_VISUAL_MHC_EXOSOME_V1",
    }
    image = Image.new("RGB", (128, 64), color=(255, 255, 255))
    exosome = mhc.apply_exosome_to_image(image, state)
    decoded = mhc.parse_exosome_from_image(exosome)
    assert decoded == state
    return True


if __name__ == "__main__":
    print("EVENT 59 MHC VISUAL EXOSOME:", "PASS" if proof_of_property() else "FAIL")
