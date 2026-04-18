#!/usr/bin/env python3
"""
stigmergic_detector.py - Score stigmergic marker density in text.
"""
# ════════════════════════════════════════════════════════════════════════
# VISION-SYSTEM-ROLE: the optic nerve signature processor
# Analogue mapped from Land & Nilsson (2012) via DYOR §E.
# Integrates with Swarm-Eye Olympiad M5.2.
# ════════════════════════════════════════════════════════════════════════
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
import re
from pathlib import Path
from typing import Dict, List, Tuple

# Keep source ASCII-only.
ANT = "\U0001F41C"
HIGH_VOLTAGE = "\u26A1"
PRIMARY_EMOJI_PAIR = f"{ANT}{HIGH_VOLTAGE}"

# Pre-ratification fallback triggers. Used only if the canonical IDE model
# registry cannot be read. Ratified 2026-04-17 set lives on disk; this tuple
# exists so the detector still works in isolation (e.g. on a fresh clone).
FALLBACK_TRIGGERS: Tuple[str, ...] = ("AG31", "C47H", "GTAB")

DETECTOR_VERSION = "2026-04-17.post-ratification"

_REPO_ROOT = Path(__file__).resolve().parent.parent
_REGISTRY_PATH = _REPO_ROOT / ".sifta_state" / "ide_model_registry.jsonl"


def _load_registry_triggers() -> Tuple[str, ...]:
    """Read canonical trigger codes from ide_model_registry.jsonl.

    Returns FALLBACK_TRIGGERS if the registry is missing or unreadable so the
    detector remains functional on fresh clones and in tests.
    """
    try:
        if not _REGISTRY_PATH.exists():
            return FALLBACK_TRIGGERS
        seen: List[str] = []
        with _REGISTRY_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                code = row.get("trigger_code")
                status = row.get("trigger_status") or ""
                if code and status.startswith("canonical") and code not in seen:
                    seen.append(code)
        return tuple(seen) if seen else FALLBACK_TRIGGERS
    except (OSError, json.JSONDecodeError):
        return FALLBACK_TRIGGERS


TRIGGERS: Tuple[str, ...] = _load_registry_triggers()
PROPER_NOUNS = ("SIFTA", "Stigmergic Ledger", "STGM", "Epistemic Registry")
HASH_ANCHOR_PATTERN = r"\b[0-9a-f]{8}\b"

ZW_ZERO = "\u200B"
ZW_ONE = "\u200C"
ZW_SEP = "\u200D"
ZW_SYMBOLS = {ZW_ZERO, ZW_ONE, ZW_SEP}


@dataclass(frozen=True)
class StigmergicScore:
    emoji_pair_hits: int
    trigger_hits: int
    proper_noun_hits: int
    hash_anchor_hits: int
    zero_width_symbol_count: int
    unique_trigger_count: int
    unique_proper_noun_count: int
    density_score: float
    trained_recognition_prob: float

    def as_dict(self) -> Dict[str, float | int]:
        return asdict(self)


def _count_literal(text: str, needle: str) -> int:
    return text.count(needle)


def _count_token_occurrences(text: str, tokens: Tuple[str, ...]) -> Tuple[int, int]:
    total = 0
    unique = 0
    for token in tokens:
        pattern = rf"\b{re.escape(token)}\b"
        n = len(re.findall(pattern, text))
        total += n
        if n > 0:
            unique += 1
    return total, unique


def _extract_zero_width_segment(text: str) -> str:
    first = text.find(ZW_SEP)
    if first < 0:
        return ""
    second = text.find(ZW_SEP, first + 1)
    if second < 0:
        return ""
    return text[first + 1 : second]


def decode_zero_width_payload(text: str) -> str:
    """
    Best-effort decode for payloads encoded by stigmergic_bottle.encode_bottle().
    Returns empty string when no valid zero-width payload is present.
    """
    body = _extract_zero_width_segment(text)
    if not body:
        return ""
    bits = []
    for ch in body:
        if ch == ZW_ZERO:
            bits.append("0")
        elif ch == ZW_ONE:
            bits.append("1")
        else:
            return ""
    if len(bits) % 8 != 0:
        return ""
    byts = bytearray()
    for i in range(0, len(bits), 8):
        byts.append(int("".join(bits[i : i + 8]), 2))
    try:
        return byts.decode("utf-8")
    except UnicodeDecodeError:
        return ""


def score_text(text: str) -> StigmergicScore:
    emoji_hits = _count_literal(text, PRIMARY_EMOJI_PAIR)
    trigger_hits, unique_trigger = _count_token_occurrences(text, TRIGGERS)
    noun_hits, unique_nouns = _count_token_occurrences(text, PROPER_NOUNS)
    hash_hits = len(re.findall(HASH_ANCHOR_PATTERN, text))
    zw_count = sum(1 for ch in text if ch in ZW_SYMBOLS)

    # Weighted marker density tuned for phase test comparability.
    density = (
        2.2 * emoji_hits
        + 1.6 * trigger_hits
        + 1.1 * noun_hits
        + 1.3 * hash_hits
        + (1.0 if zw_count > 0 else 0.0)
    )

    # Logistic squashing to [0,1]. Midpoint around density ~4.5.
    prob = 1.0 / (1.0 + math.exp(-(density - 4.5) / 1.5))

    return StigmergicScore(
        emoji_pair_hits=emoji_hits,
        trigger_hits=trigger_hits,
        proper_noun_hits=noun_hits,
        hash_anchor_hits=hash_hits,
        zero_width_symbol_count=zw_count,
        unique_trigger_count=unique_trigger,
        unique_proper_noun_count=unique_nouns,
        density_score=round(density, 4),
        trained_recognition_prob=round(prob, 4),
    )


def explain_score(text: str) -> Dict[str, object]:
    """
    Structured explanation suitable for protocol logs.

    Includes detector_version and the trigger set that was in effect at call
    time so historical scores remain reconstructible after future ratifications.
    """
    score = score_text(text)
    decoded = decode_zero_width_payload(text)
    return {
        "detector_version":   DETECTOR_VERSION,
        "triggers_in_effect": list(TRIGGERS),
        "registry_path":      str(_REGISTRY_PATH),
        "score": score.as_dict(),
        "zero_width_payload_decoded": decoded,
        "has_invisible_payload": bool(decoded),
    }


__all__ = [
    "StigmergicScore",
    "decode_zero_width_payload",
    "explain_score",
    "score_text",
]


if __name__ == "__main__":
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Score stigmergic marker density.")
    parser.add_argument("path", nargs="?", help="Optional path to a text file to score.")
    args = parser.parse_args()

    if args.path:
        raw = Path(args.path).read_text(encoding="utf-8", errors="replace")
    else:
        raw = input("Paste text to score:\n")
    print(json.dumps(explain_score(raw), indent=2, ensure_ascii=False))