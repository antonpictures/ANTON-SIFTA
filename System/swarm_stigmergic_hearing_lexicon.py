#!/usr/bin/env python3
"""Local hearing lexicon for SIFTA-specific words.

This is not a ban list. It is a small receipt-backed repair lane for words the
owner uses that generic STT models tend to collapse into ordinary English.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_STATE = _REPO / ".sifta_state"
_LEDGER = "hearing_lexicon_corrections.jsonl"

TRUTH_LABEL = "STIGMERGIC_HEARING_LEXICON_V1"

_STIGMERGIC_PATTERN = re.compile(
    r"\b(?:stick|stigma|stigm|stig)\s+magic(?:al(?:ly)?|k)?\b",
    re.IGNORECASE,
)


def normalize_stigmergic_terms(text: str) -> tuple[str, list[dict[str, Any]]]:
    """Return text with high-confidence SIFTA vocabulary restored.

    The raw text remains available in the caller's receipt. This only repairs a
    known local homophone family: "stick magic" / "stigma magic" ->
    "STIGMERGIC".
    """
    original = str(text or "")
    corrections: list[dict[str, Any]] = []

    def _replace(match: re.Match[str]) -> str:
        heard = match.group(0)
        corrections.append(
            {
                "heard": heard,
                "canonical": "STIGMERGIC",
                "reason": "stigmergic_term_stt_homophone",
            }
        )
        return "STIGMERGIC"

    normalized = _STIGMERGIC_PATTERN.sub(_replace, original)
    return normalized, corrections


def apply_hearing_lexicon(
    text: str,
    *,
    state_dir: str | Path | None = None,
    source: str = "",
    stt_conf: float = 0.0,
    persist: bool = False,
) -> dict[str, Any]:
    """Normalize known local vocabulary and optionally write a receipt."""
    normalized, corrections = normalize_stigmergic_terms(text)
    out = {
        "truth_label": TRUTH_LABEL,
        "raw_text": str(text or ""),
        "normalized_text": normalized,
        "changed": normalized != str(text or ""),
        "corrections": corrections,
    }
    if persist and corrections:
        state = Path(state_dir) if state_dir is not None else _STATE
        row = {
            "ts": time.time(),
            "trace_id": uuid.uuid4().hex,
            "kind": "HEARING_LEXICON_CORRECTION",
            "truth_label": TRUTH_LABEL,
            "source": source or "unknown",
            "stt_confidence": round(float(stt_conf or 0.0), 3),
            **out,
        }
        try:
            state.mkdir(parents=True, exist_ok=True)
            with (state / _LEDGER).open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            out["receipt_ledger"] = str(state / _LEDGER)
            out["trace_id"] = row["trace_id"]
        except OSError:
            out["receipt_error"] = "write_failed"
    return out


__all__ = ["TRUTH_LABEL", "apply_hearing_lexicon", "normalize_stigmergic_terms"]
