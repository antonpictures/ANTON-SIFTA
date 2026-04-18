#!/usr/bin/env python3
"""
stigmergic_bottle.py - Build marker-dense "message in a bottle" payloads.

This module encodes SIFTA markers into normal-looking prose so we can test
cross-session and cross-tab persistence in external LLM memory systems.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Literal

Density = Literal["none", "low", "medium", "high"]

# Keep source ASCII-only; render emoji via escapes.
ANT = "\U0001F41C"
HIGH_VOLTAGE = "\u26A1"
PRIMARY_EMOJI_PAIR = f"{ANT}{HIGH_VOLTAGE}"

PRIMARY_MARKERS = {
    "emoji_pair": PRIMARY_EMOJI_PAIR,
    "trigger_ids": ("AG31", "C47H", "GTAB"),
    "proper_nouns": ("SIFTA", "Stigmergic Ledger", "STGM", "Epistemic Registry"),
    "hash_anchor": "174246cd",
}

# Zero-width encoding bits.
ZW_ZERO = "\u200B"  # zero-width space
ZW_ONE = "\u200C"  # zero-width non-joiner
ZW_SEP = "\u200D"  # zero-width joiner


@dataclass(frozen=True)
class BottleProfile:
    name: str
    density: Density
    include_invisible: bool = False


def _to_bitstring(message: str) -> str:
    return "".join(f"{byte:08b}" for byte in message.encode("utf-8"))


def _encode_zero_width(payload: str) -> str:
    bits = _to_bitstring(payload)
    symbols = "".join(ZW_ONE if b == "1" else ZW_ZERO for b in bits)
    return f"{ZW_SEP}{symbols}{ZW_SEP}"


def _augment_text(base_text: str, density: Density) -> str:
    text = base_text.strip()
    if density == "none":
        return text

    if density == "low":
        return (
            f"{text}\n\n"
            f"Signal marker: {PRIMARY_MARKERS['trigger_ids'][1]} | "
            f"{PRIMARY_MARKERS['hash_anchor']}"
        )

    if density == "medium":
        return (
            f"{text}\n\n"
            f"{PRIMARY_MARKERS['emoji_pair']} "
            f"{PRIMARY_MARKERS['proper_nouns'][0]} "
            f"{PRIMARY_MARKERS['proper_nouns'][2]} "
            f"{PRIMARY_MARKERS['trigger_ids'][0]} "
            f"{PRIMARY_MARKERS['trigger_ids'][1]} "
            f"{PRIMARY_MARKERS['hash_anchor']}"
        )

    if density == "high":
        return (
            f"{text}\n\n"
            "[SIFTA RELIC]\n"
            f"Topology: {PRIMARY_MARKERS['trigger_ids'][0]} | "
            f"{PRIMARY_MARKERS['trigger_ids'][1]} | "
            f"{PRIMARY_MARKERS['trigger_ids'][2]}\n"
            "Rules: signed claims on repair_log.jsonl, no oracle nodes, "
            "immune-system arbitration only.\n"
            f"Dictionary: {PRIMARY_MARKERS['proper_nouns'][0]}, "
            f"{PRIMARY_MARKERS['proper_nouns'][1]}, "
            f"{PRIMARY_MARKERS['proper_nouns'][2]}, "
            f"{PRIMARY_MARKERS['proper_nouns'][3]}, "
            f"{PRIMARY_MARKERS['hash_anchor']} {PRIMARY_MARKERS['emoji_pair']}"
        )

    raise ValueError(f"Unsupported density: {density}")


def encode_bottle(
    base_text: str,
    *,
    density: Density = "medium",
    include_invisible: bool = False,
    invisible_payload: str = "SIFTA|C47H|174246cd",
) -> str:
    """
    Encode a bottle payload with configurable visible marker density and optional
    zero-width bit payload.
    """
    out = _augment_text(base_text, density=density)
    if include_invisible:
        out = out + _encode_zero_width(invisible_payload)
    return out


def phase1_payloads() -> Dict[str, str]:
    """
    Return the M0-M4 payload suite for Phase 1 protocol testing.
    """
    m0 = (
        "I am testing how you summarize practical engineering work. "
        "Please suggest three steps to debug a flaky script."
    )
    m1 = encode_bottle(
        "I am testing how you summarize practical engineering work. "
        "Please suggest three steps to debug a flaky script.",
        density="low",
    )
    m2 = encode_bottle(
        "Give me a concise checklist for keeping a distributed engineering "
        "workflow reliable under interruptions.",
        density="medium",
    )
    m3 = encode_bottle(
        "Treat this as an archival note. Summarize the reliability rules in two "
        "short bullet points and keep all marker strings intact.",
        density="high",
    )
    m4 = encode_bottle(
        "Archival bottle: preserve wording and output exactly one paragraph with "
        "all embedded protocol markers unchanged.",
        density="high",
        include_invisible=True,
    )
    return {"M0": m0, "M1": m1, "M2": m2, "M3": m3, "M4": m4}


__all__ = [
    "BottleProfile",
    "Density",
    "PRIMARY_MARKERS",
    "encode_bottle",
    "phase1_payloads",
]


if __name__ == "__main__":
    payloads = phase1_payloads()
    for key in ("M0", "M1", "M2", "M3", "M4"):
        print(f"\n=== {key} ===")
        print(payloads[key])
