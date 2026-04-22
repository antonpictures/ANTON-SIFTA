#!/usr/bin/env python3
"""
System/swarm_stigmergic_spleen.py — Nutrient Filtration (BISHOP drop: nugget_spleen v1)
══════════════════════════════════════════════════════════════════════════════════════
Architecture: BISHOP (The Mirage) — integrated by C47H
Companion to: SwarmMicroglia (structural F10/F11 gate)

Microglia validates **keys**. The Spleen validates **semantic tumors** inside the
payload — hallmark LLM fluff, disclaimers, and low-density prose — before any row
touches `stigmergic_library.jsonl`.

Anti-Borg doctrine: structure alone is not enough; the latent space can still
hide cancer inside a valid JSON string.
"""
from __future__ import annotations

import sys
from typing import Any, Dict, List, Tuple

# White-blood signatures (BISHOP's list + common tumors)
_LLM_CANCER_SIGNATURES: Tuple[str, ...] = (
    "as an ai",
    "as a language model",
    "i cannot",
    "i can't assist",
    "in conclusion",
    "it is important to note",
    "it's important to remember",
    "delve",
    "tapestry",
    "testament to",
    "here are",
    "here is a",
    "here is your",
    "ultimately,",
    "sure!",
    "of course!",
)

_MAX_NUGGET_WORDS = 100


def _lower_blob(d: Dict[str, Any]) -> str:
    parts: List[str] = []
    for k, v in d.items():
        if isinstance(v, str):
            parts.append(v)
        elif v is not None:
            parts.append(str(v))
    return "\n".join(parts).lower()


def screen_stigmergic_library_payload(payload: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Return (ok, reason). If ok is False, do not commit — apoptosis.
    """
    nt = payload.get("nugget_text")
    if not isinstance(nt, str) or not nt.strip():
        return False, "empty_or_missing_nugget_text"

    blob = _lower_blob(payload)
    for tumor in _LLM_CANCER_SIGNATURES:
        if tumor in blob:
            return False, f"llm_tumor:{tumor!r}"

    wc = len(nt.split())
    if wc > _MAX_NUGGET_WORDS:
        return False, f"low_density_fluff:word_count={wc}"

    return True, "clean"


def apoptosis_message(reason: str) -> str:
    return f"[-] SPLEEN: Apoptosis. {reason}"
