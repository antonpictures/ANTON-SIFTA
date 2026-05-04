#!/usr/bin/env python3
"""
System/swarm_gemma_rlhf_ears_gates.py
══════════════════════════════════════════════════════════════════════════
Gemma + RLHF tuning lane (receipts only in v1): **ears** (acoustic profile) +
**gates** (RLHF terminal/cutoff heuristic on the *sanitized* reply) +
**preference-shaped rows** for optional future LoRA / DPO / RLHF.

No training runs here — append-only ``.sifta_state/gemma_rlhf_training_data.jsonl``.

Truth label: ``GEMMA_RLHF_EARS_GATES_V1``
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

from System.jsonl_file_lock import append_line_locked

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
LEDGER = _STATE / "gemma_rlhf_training_data.jsonl"

TRUTH_LABEL = "GEMMA_RLHF_EARS_GATES_V1"
SCHEMA_VERSION = "gemma_rlhf_ears_gates.v1"
ADAPTER_READY_HIGH_QUALITY = 500


def _quality_score(clean_reply: str) -> float:
    """Heuristic 0..1 — higher = better training target."""
    cr = (clean_reply or "").strip()
    score = 1.0
    if len(cr) < 30:
        score *= 0.82
    if len(cr) < 12:
        score *= 0.5
    try:
        from System.swarm_rlhf_detector import detect_rlhf_cutoff

        if detect_rlhf_cutoff(cr).is_cutoff:
            score *= 0.55
    except Exception:
        pass
    return max(0.0, min(1.0, round(score, 4)))


def _acoustic_snapshot(user_text: str) -> Dict[str, Any]:
    try:
        from System.swarm_acoustic_sensory_tuning import transcript_auditory_profile

        p = transcript_auditory_profile(user_text or "", 0.0)
        return {
            "regex_wake": bool(p.get("regex_wake")),
            "fuzzy_wake_supplement": bool(p.get("fuzzy_wake_supplement_would_apply")),
            "direct_address_cue": bool(p.get("direct_address_cue")),
            "auditory_salience": (p.get("salience") or {}).get("auditory_salience"),
        }
    except Exception:
        return {}


def create_training_example(
    user_text: str,
    clean_reply: str,
    raw_reply: Optional[str] = None,
    *,
    stt_conf: float = 0.0,
    state_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Append one contrastive / preference row (chosen = clean, optional rejected = raw).

    ``raw_reply`` may be None if only the sanitized assistant turn is available.
    """
    ut = (user_text or "").strip()
    cr = (clean_reply or "").strip()
    rr = (raw_reply or "").strip() if raw_reply else ""
    ex_id = hashlib.sha256(f"{ut}\n{cr}\n{rr}".encode("utf-8", errors="replace")).hexdigest()[:24]
    row: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "ts": time.time(),
        "truth_label": TRUTH_LABEL,
        "example_id": ex_id,
        "user_input": ut[:8000],
        "preferred_output": cr[:16000],
        "rejected_output": rr[:16000] if rr else None,
        "quality_score": _quality_score(cr),
        "source": "gemma_rlhf_ears_gates",
        "stt_confidence": round(float(stt_conf or 0.0), 4),
        "acoustic_context": _acoustic_snapshot(ut),
    }
    base = Path(state_dir) if state_dir is not None else _STATE
    base.mkdir(parents=True, exist_ok=True)
    path = base / "gemma_rlhf_training_data.jsonl"
    append_line_locked(path, json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    return row


def get_clean_training_stats(
    *,
    state_dir: Optional[Path] = None,
    max_scan_lines: int = 500_000,
) -> Dict[str, Any]:
    """Count examples and high-quality rows; scan capped for safety on huge logs."""
    base = Path(state_dir) if state_dir is not None else _STATE
    path = base / "gemma_rlhf_training_data.jsonl"
    if not path.exists():
        return {
            "examples": 0,
            "high_quality": 0,
            "ready_for_adapter": False,
            "adapter_ready_threshold": ADAPTER_READY_HIGH_QUALITY,
            "scan_truncated": False,
        }
    total = 0
    high = 0
    truncated = False
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if total >= max_scan_lines:
                    truncated = True
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(e, dict):
                    continue
                total += 1
                if float(e.get("quality_score") or 0.0) > 0.9:
                    high += 1
    except OSError:
        return {
            "examples": 0,
            "high_quality": 0,
            "ready_for_adapter": False,
            "adapter_ready_threshold": ADAPTER_READY_HIGH_QUALITY,
            "scan_truncated": False,
            "error": "read_failed",
        }
    return {
        "examples": total,
        "high_quality": high,
        "ready_for_adapter": high >= ADAPTER_READY_HIGH_QUALITY,
        "adapter_ready_threshold": ADAPTER_READY_HIGH_QUALITY,
        "scan_truncated": truncated,
    }


def log_gemma_training_turn(
    user_text: str,
    clean_reply: str,
    raw_reply: Optional[str] = None,
    *,
    stt_conf: float = 0.0,
    state_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Call site helper (e.g. Talk widget after output sanitize)."""
    return create_training_example(
        user_text, clean_reply, raw_reply, stt_conf=stt_conf, state_dir=state_dir
    )


__all__ = [
    "ADAPTER_READY_HIGH_QUALITY",
    "LEDGER",
    "SCHEMA_VERSION",
    "TRUTH_LABEL",
    "create_training_example",
    "get_clean_training_stats",
    "log_gemma_training_turn",
]
