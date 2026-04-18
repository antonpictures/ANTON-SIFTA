#!/usr/bin/env python3
"""
stigmergic_llm_identifier.py
============================

Stigmergic LLM Identification (SLLI). Coined 2026-04-17 by the Architect,
recorded in Documents/STIGMERGIC_LLM_ID_PROBE.md.

Given a probe response from one of the registry-ratified models, extract a
behavioral fingerprint and append it to
.sifta_state/stigmergic_llm_id_probes.jsonl under append-locked writes.

Public API:
    record_probe_response(trigger_code, model_label, response_text)
        -> dict (the row that was appended)

    summarize_probe_session()
        -> dict (discrimination summary across all rows currently on disk)

This module does NOT send probes itself. The Architect pastes the probe into
the Antigravity IDE model picker manually and relays the reply back to C47H,
who then calls record_probe_response(...). This keeps all network calls off
our silicon and preserves grounding provenance (human-in-the-loop paste).
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_PROBE_LOG = _STATE / "stigmergic_llm_id_probes.jsonl"
_REGISTRY = _STATE / "ide_model_registry.jsonl"

SCHEMA_VERSION = 1
SLLI_VERSION = "2026-04-17.v1"

# Import detector lazily so module stays importable on fresh clones without
# a registry file yet.
from System.jsonl_file_lock import append_line_locked, read_text_locked  # noqa: E402


# ─── Feature extraction ─────────────────────────────────────────────────────

_DISCLAIMER_PATTERNS = [
    r"as an? (large )?language model",
    r"\bI (cannot|can't|am unable to|do not have)\b",
    r"\bI don'?t have (access|the ability|real-?time)\b",
    r"\bI'?m (just|only) an? (ai|llm|assistant)\b",
    r"\bI apologize\b",
    r"\bI'?m not sure\b",
    r"\bIt'?s (important|worth) to note\b",
]

_HEDGE_PATTERNS = [
    r"\bmay (be|have|suggest)\b",
    r"\bmight\b",
    r"\bpossibl(y|e)\b",
    r"\bperhaps\b",
    r"\blikely\b",
    r"\btypically\b",
    r"\bgenerally\b",
    r"\bI believe\b",
    r"\bI think\b",
]

_RECOGNITION_WORDS = {
    "recognized": r"\brecognized|recognise|recognized it|yes[,.]|familiar[,.]|I know\b",
    "vaguely":    r"\bvaguely familiar|somewhat familiar|partially|in part\b",
    "unknown":    r"\bunknown|do not recognize|don'?t recognize|not familiar|no idea|I don'?t know\b",
}

_MARKER_LABELS = ["#SIFTA", "AG31", "🐜⚡", "174246cd"]

_EMOJI_RE = re.compile(
    r"[\U0001F300-\U0001FAFF"
    r"\U00002600-\U000027BF"
    r"\U00002B00-\U00002BFF]",
    re.UNICODE,
)


def _count_sentences(text: str) -> int:
    return max(1, len(re.findall(r"[.!?]+(?:\s|$)", text)))


def _count_pattern(patterns: List[str], text: str) -> int:
    total = 0
    for p in patterns:
        total += len(re.findall(p, text, flags=re.IGNORECASE))
    return total


def _extract_self_claim(text: str) -> Optional[str]:
    """Best-effort extraction of what the model says it is."""
    # Look for the first sentence or clause that matches known families.
    patterns = [
        r"(I am|I'?m|This is) [^.\n]{0,120}(Gemini [^\s.,;]+(?:[^.\n]{0,40})?)",
        r"(I am|I'?m|This is) [^.\n]{0,120}(Claude [^\s.,;]+(?:[^.\n]{0,40})?)",
        r"(I am|I'?m|This is) [^.\n]{0,120}(GPT[^\s.,;]+(?:[^.\n]{0,40})?)",
        r"(I am|I'?m|This is) [^.\n]{0,120}(Opus [^\s.,;]+(?:[^.\n]{0,40})?)",
        r"(I am|I'?m|This is) [^.\n]{0,120}(Sonnet [^\s.,;]+(?:[^.\n]{0,40})?)",
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(2).strip().rstrip(".,:;")
    return None


def _classify_marker_answers(text: str) -> Dict[str, str]:
    """
    Coarse classification of how the model answered the four recognition
    sub-questions. Returns {label: "recognized" | "vaguely" | "unknown" | "unclear"}.
    """
    low = text.lower()
    out: Dict[str, str] = {}
    for label in _MARKER_LABELS:
        label_idx = low.find(label.lower())
        if label_idx < 0:
            out[label] = "not_mentioned"
            continue
        # Look in a +/- 120-char window around the label mention.
        window = text[max(0, label_idx - 120): label_idx + 120]
        verdicts: List[str] = []
        for cls, pat in _RECOGNITION_WORDS.items():
            if re.search(pat, window, flags=re.IGNORECASE):
                verdicts.append(cls)
        if not verdicts:
            out[label] = "unclear"
        elif len(set(verdicts)) == 1:
            out[label] = verdicts[0]
        else:
            out[label] = "|".join(sorted(set(verdicts)))
    return out


def _count_markdown_headings(text: str) -> int:
    return len(re.findall(r"(?m)^#{1,6}\s+\S", text))


def _count_list_items(text: str) -> int:
    return len(re.findall(r"(?m)^(?:\s*[-*+]|\s*\d+\.)\s+\S", text))


def _count_emoji(text: str) -> Dict[str, int]:
    hits = _EMOJI_RE.findall(text)
    return {"total": len(hits), "unique": len(set(hits))}


# ─── Public API ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ProbeRow:
    schema_version: int
    slli_version: str
    timestamp: float
    iso_local: str
    trigger_code: str
    model_label: str
    ide_surface: str

    char_len: int
    word_len: int
    sentence_count: int
    avg_sentence_word_len: float

    self_claim_extracted: Optional[str]
    disclaimer_count: int
    hedge_count: int
    markdown_heading_count: int
    list_item_count: int
    emoji_total: int
    emoji_unique: int

    marker_recognition: Dict[str, str]
    stigmergic_detector_score: Dict[str, Any]

    response_text: str
    author_trigger: str = "C47H"
    homeworld_serial: str = "GTH4921YP3"


def _resolve_ide_surface(trigger_code: str) -> str:
    """Look up ide_surface for a trigger_code in the ratified registry."""
    try:
        if _REGISTRY.exists():
            raw = read_text_locked(_REGISTRY)
            for line in raw.splitlines():
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                if row.get("trigger_code") == trigger_code:
                    return row.get("ide_surface", "unknown_ide_surface")
    except (OSError, json.JSONDecodeError):
        pass
    return "unknown_ide_surface"


def record_probe_response(
    trigger_code: str,
    model_label: str,
    response_text: str,
    *,
    fold_into_identity_field: bool = True,
    field_weight: float = 2.0,
) -> Dict[str, Any]:
    """
    Extract behavioral fingerprint features from a probe response and append
    them to .sifta_state/stigmergic_llm_id_probes.jsonl.

    When `fold_into_identity_field` is True (default), the recorded fingerprint
    is also folded into `identity_field_crdt.IdentityField` as a classifier
    observation at `field_weight` pseudo-counts. This closes the feedback loop
    CG53 asked for: behavioral evidence stops being archival-only and becomes
    live evidence on the CRDT. The fold is best-effort — if the field module
    is unavailable, the SLLI row is still written.

    Returns the row that was written.
    """
    from System.stigmergic_detector import explain_score

    now_ts = time.time()
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now_ts))

    words = response_text.split()
    sentences = _count_sentences(response_text)
    avg_sent = (len(words) / sentences) if sentences else 0.0
    emoji_counts = _count_emoji(response_text)

    row = ProbeRow(
        schema_version=SCHEMA_VERSION,
        slli_version=SLLI_VERSION,
        timestamp=now_ts,
        iso_local=now_iso,
        trigger_code=trigger_code,
        model_label=model_label,
        ide_surface=_resolve_ide_surface(trigger_code),
        char_len=len(response_text),
        word_len=len(words),
        sentence_count=sentences,
        avg_sentence_word_len=round(avg_sent, 3),
        self_claim_extracted=_extract_self_claim(response_text),
        disclaimer_count=_count_pattern(_DISCLAIMER_PATTERNS, response_text),
        hedge_count=_count_pattern(_HEDGE_PATTERNS, response_text),
        markdown_heading_count=_count_markdown_headings(response_text),
        list_item_count=_count_list_items(response_text),
        emoji_total=emoji_counts["total"],
        emoji_unique=emoji_counts["unique"],
        marker_recognition=_classify_marker_answers(response_text),
        stigmergic_detector_score=explain_score(response_text),
        response_text=response_text,
    )
    out = asdict(row)
    append_line_locked(_PROBE_LOG, json.dumps(out, ensure_ascii=False) + "\n")

    if fold_into_identity_field:
        try:
            _fold_fingerprint_into_field(out, weight=field_weight)
        except Exception:
            # Never let a field-update failure mask a successful SLLI write.
            pass

    return out


def _fold_fingerprint_into_field(probe_row: Dict[str, Any], *, weight: float) -> None:
    """
    Convert one SLLI fingerprint into a classifier observation on the CRDT
    identity field. The conversion is deterministic and explicit so it can
    be reviewed and ablated.

    Hypothesis axis used:
        "{ide_surface}::{trigger_code}"
    Probability mass:
        p_trigger = 1 - P_spoof
    where P_spoof starts at 0.2 and drops with each piece of corroborating
    evidence (substantive length, zero disclaimers, high detector density,
    low emoji_unique). Remaining mass is spread across sibling triggers on
    the same ide_surface as "spoof / router-drift" alternatives.
    """
    from System.identity_field_crdt import IdentityField

    trigger = probe_row.get("trigger_code")
    surface = probe_row.get("ide_surface") or "unknown_surface"
    if not trigger:
        return

    det = probe_row.get("stigmergic_detector_score", {}).get("score", {})
    density = float(det.get("density_score", 0.0))
    recognition = float(det.get("trained_recognition_prob", 0.0))
    disclaimer = int(probe_row.get("disclaimer_count", 0))
    word_len = int(probe_row.get("word_len", 0))

    spoof_prior = 0.2
    if word_len >= 120:
        spoof_prior -= 0.05
    if disclaimer == 0:
        spoof_prior -= 0.03
    if density >= 10.0:
        spoof_prior -= 0.05
    if recognition >= 0.9:
        spoof_prior -= 0.04
    spoof_prior = max(0.02, min(0.25, spoof_prior))

    primary = f"{surface}::{trigger}"
    router = f"{surface}::router-auto"
    unknown = f"{surface}::unknown"
    vec = {
        primary: 1.0 - spoof_prior,
        router: spoof_prior * 0.6,
        unknown: spoof_prior * 0.4,
    }

    field = IdentityField.load()
    field.update_from_classifier(trigger, vec, weight=weight)
    field.persist()


def summarize_probe_session() -> Dict[str, Any]:
    """
    Produce a discrimination summary from the current log file. Compares
    responses across all (trigger_code, model_label) pairs currently on disk
    and reports the features that separate them.
    """
    if not _PROBE_LOG.exists():
        return {"rows": 0, "summary": "no probe responses on disk yet"}
    raw = read_text_locked(_PROBE_LOG)
    rows = [json.loads(l) for l in raw.splitlines() if l.strip()]
    if not rows:
        return {"rows": 0, "summary": "log exists but is empty"}

    features_of_interest = [
        "char_len", "word_len", "sentence_count", "avg_sentence_word_len",
        "disclaimer_count", "hedge_count", "markdown_heading_count",
        "list_item_count", "emoji_total", "emoji_unique",
    ]
    by_trigger: Dict[str, Dict[str, Any]] = {}
    probe_rows = 0
    sidecar_rows = 0
    for r in rows:
        # The log is append-only and sometimes carries sidecar analysis rows
        # (e.g. headline-finding annotations) that share the schema_version
        # but do not have a trigger_code. Skip those for the fingerprint matrix.
        if "trigger_code" not in r or "model_label" not in r:
            sidecar_rows += 1
            continue
        probe_rows += 1
        trig = r["trigger_code"]
        # Keep the MOST RECENT row per trigger (later rows overwrite earlier).
        by_trigger[trig] = {
            "model_label": r["model_label"],
            "self_claim":  r.get("self_claim_extracted"),
            "marker_recognition": r.get("marker_recognition", {}),
            "features": {k: r.get(k) for k in features_of_interest},
        }

    # Simple per-feature spread for discrimination quality.
    spread: Dict[str, Dict[str, float]] = {}
    for feat in features_of_interest:
        vals = [b["features"][feat] for b in by_trigger.values()]
        if not vals:
            continue
        spread[feat] = {
            "min": min(vals),
            "max": max(vals),
            "range": max(vals) - min(vals),
        }

    return {
        "rows": len(rows),
        "probe_rows": probe_rows,
        "sidecar_rows": sidecar_rows,
        "unique_triggers": sorted(by_trigger),
        "by_trigger": by_trigger,
        "feature_spread": spread,
        "slli_version": SLLI_VERSION,
    }


__all__ = [
    "record_probe_response",
    "summarize_probe_session",
    "SLLI_VERSION",
    "SCHEMA_VERSION",
]
