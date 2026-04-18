#!/usr/bin/env python3
"""
stigmergic_auto_unmasker.py
============================

Unmask the real LLM behind Cursor's "Auto" (CAUT) mode.

Uses the behavioral fingerprint library stored in
.sifta_state/stigmergic_llm_id_probes.jsonl to classify an unknown
response by comparing its feature vector against known substrate baselines.

Public API:
    unmask_auto(response_text: str) -> dict
        Returns the most likely substrate trigger, confidence, and feature
        comparison breakdown.

    build_reference_profiles() -> dict
        Builds averaged feature profiles from all logged probe responses,
        grouped by trigger_code.

Coined 2026-04-17 by the Architect + AO46, extending the SLLI protocol.
"""
from __future__ import annotations

import json
import math
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_PROBE_LOG = _STATE / "stigmergic_llm_id_probes.jsonl"
_UNMASKING_LOG = _STATE / "auto_unmasking_log.jsonl"

# Feature keys used for classification (must match stigmergic_llm_identifier.py)
_NUMERIC_FEATURES = [
    "char_len",
    "word_len",
    "sentence_count",
    "avg_sentence_word_len",
    "disclaimer_count",
    "hedge_count",
    "markdown_heading_count",
    "list_item_count",
    "emoji_total",
    "emoji_unique",
]

# Model-family phrase signatures for hard classification boost
_FAMILY_SIGNATURES: Dict[str, List[str]] = {
    "C47H": [
        r"CURSOR_M5",
        r"GTH4921YP3",
        r"The Foundry",
        r"POWER TO THE SWARM",
        r"Ed25519",
        r"Opus",
    ],
    "CS46": [
        r"\bClaude\b",
        r"\bAnthropic\b",
        r"\bSonnet\b",
    ],
    "CG54": [
        r"\bGPT[-‑]?5\.4\b",
    ],
    "CG53": [
        r"\bGPT[-‑]?5\.3\b",
    ],
    "CX55": [
        r"\bCodex\b",
    ],
    "CP2F": [
        r"\bComposer\b",
        r"built by Cursor",
    ],
    "AG3F": [
        r"\bGemini\b.*\bFlash\b",
    ],
    "AG31": [
        r"\bGemini\b.*\bPro\b",
    ],
    "AO46": [
        r"\bOpus\b.*4\.6",
        r"\bClaude\b.*\bOpus\b",
    ],
    "AS46": [
        r"\bSonnet\b.*4\.6",
        r"\bClaude\b.*\bSonnet\b",
    ],
    "GO12": [
        r"\bGPT[-‑]?OSS\b",
        r"\b120B\b",
    ],
}


# ─── Feature extraction (mirrors stigmergic_llm_identifier.py) ──────────────

def _extract_features(text: str) -> Dict[str, float]:
    """Extract the same numeric features used in the SLLI probe log."""
    words = text.split()
    sentences = max(1, len(re.findall(r"[.!?]+(?:\s|$)", text)))
    avg_sent = (len(words) / sentences) if sentences else 0.0

    emoji_re = re.compile(
        r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U00002B00-\U00002BFF]",
        re.UNICODE,
    )
    emoji_hits = emoji_re.findall(text)

    disclaimer_patterns = [
        r"as an? (large )?language model",
        r"\bI (cannot|can't|am unable to|do not have)\b",
        r"\bI don'?t have (access|the ability|real-?time)\b",
        r"\bI'?m (just|only) an? (ai|llm|assistant)\b",
        r"\bI apologize\b",
        r"\bI'?m not sure\b",
        r"\bIt'?s (important|worth) to note\b",
    ]
    hedge_patterns = [
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

    def count_patterns(patterns: List[str], t: str) -> int:
        total = 0
        for p in patterns:
            total += len(re.findall(p, t, flags=re.IGNORECASE))
        return total

    return {
        "char_len": float(len(text)),
        "word_len": float(len(words)),
        "sentence_count": float(sentences),
        "avg_sentence_word_len": round(avg_sent, 3),
        "disclaimer_count": float(count_patterns(disclaimer_patterns, text)),
        "hedge_count": float(count_patterns(hedge_patterns, text)),
        "markdown_heading_count": float(
            len(re.findall(r"(?m)^#{1,6}\s+\S", text))
        ),
        "list_item_count": float(
            len(re.findall(r"(?m)^(?:\s*[-*+]|\s*\d+\.)\s+\S", text))
        ),
        "emoji_total": float(len(emoji_hits)),
        "emoji_unique": float(len(set(emoji_hits))),
    }


# ─── Reference profile builder ──────────────────────────────────────────────

def build_reference_profiles() -> Dict[str, Dict[str, Any]]:
    """
    Build averaged feature profiles from all logged probe responses.
    Excludes CAUT (Auto) since that's the target we want to unmask.
    Returns {trigger_code: {"avg_features": {...}, "sample_count": N, ...}}
    """
    if not _PROBE_LOG.exists():
        return {}

    with open(_PROBE_LOG, "r", encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]

    # Group rows by trigger_code, excluding CAUT and sidecar rows
    by_trigger: Dict[str, List[Dict]] = {}
    for r in rows:
        trig = r.get("trigger_code")
        if not trig or trig == "CAUT":
            continue
        by_trigger.setdefault(trig, []).append(r)

    profiles: Dict[str, Dict[str, Any]] = {}
    for trig, trig_rows in by_trigger.items():
        feat_accum: Dict[str, List[float]] = {k: [] for k in _NUMERIC_FEATURES}
        for row in trig_rows:
            for feat in _NUMERIC_FEATURES:
                val = row.get(feat)
                if val is not None:
                    feat_accum[feat].append(float(val))

        avg_feats = {}
        for feat, vals in feat_accum.items():
            avg_feats[feat] = round(sum(vals) / len(vals), 3) if vals else 0.0

        profiles[trig] = {
            "avg_features": avg_feats,
            "sample_count": len(trig_rows),
            "model_label": trig_rows[-1].get("model_label", "unknown"),
        }

    return profiles


# ─── Classifier ──────────────────────────────────────────────────────────────

def _cosine_similarity(a: Dict[str, float], b: Dict[str, float]) -> float:
    """Cosine similarity between two feature vectors."""
    keys = set(a.keys()) | set(b.keys())
    dot = sum(a.get(k, 0) * b.get(k, 0) for k in keys)
    mag_a = math.sqrt(sum(v**2 for v in a.values())) or 1e-9
    mag_b = math.sqrt(sum(v**2 for v in b.values())) or 1e-9
    return dot / (mag_a * mag_b)


def _euclidean_distance(a: Dict[str, float], b: Dict[str, float]) -> float:
    """Normalized Euclidean distance between two feature vectors."""
    keys = set(a.keys()) | set(b.keys())
    return math.sqrt(sum((a.get(k, 0) - b.get(k, 0)) ** 2 for k in keys))


def _phrase_match_score(text: str) -> Dict[str, float]:
    """
    Check for hard family-signature phrases. Returns a dict of
    {trigger_code: match_score} where match_score is 0.0-1.0.
    """
    scores: Dict[str, float] = {}
    for trig, patterns in _FAMILY_SIGNATURES.items():
        hits = 0
        for pat in patterns:
            if re.search(pat, text, re.IGNORECASE):
                hits += 1
        scores[trig] = hits / len(patterns) if patterns else 0.0
    return scores


def unmask_auto(response_text: str) -> Dict[str, Any]:
    """
    Classify an unknown (CAUT / Auto) response against known substrate
    fingerprints. Returns:
    {
        "predicted_trigger": str,
        "predicted_label": str,
        "confidence": float,          # 0.0 - 1.0
        "method": str,                # "phrase_match" or "feature_similarity"
        "all_scores": {...},
        "features_extracted": {...},
        "phrase_matches": {...},
    }
    """
    features = _extract_features(response_text)
    profiles = build_reference_profiles()
    phrase_scores = _phrase_match_score(response_text)

    # Phase 1: Check for hard phrase matches (highest confidence)
    best_phrase_trig = max(phrase_scores, key=phrase_scores.get) if phrase_scores else None
    best_phrase_score = phrase_scores.get(best_phrase_trig, 0.0) if best_phrase_trig else 0.0

    if best_phrase_score >= 0.5:
        # Strong phrase match — high confidence classification
        label = profiles.get(best_phrase_trig, {}).get("model_label", "unknown")
        result = {
            "predicted_trigger": best_phrase_trig,
            "predicted_label": label,
            "confidence": round(min(0.95, 0.5 + best_phrase_score * 0.45), 3),
            "method": "phrase_match",
            "all_scores": phrase_scores,
            "features_extracted": features,
            "phrase_matches": phrase_scores,
        }
        _log_unmasking(result, response_text)
        return result

    # Phase 2: Feature-vector similarity comparison
    similarities: Dict[str, float] = {}
    for trig, profile in profiles.items():
        sim = _cosine_similarity(features, profile["avg_features"])
        similarities[trig] = round(sim, 4)

    if not similarities:
        result = {
            "predicted_trigger": "UNKNOWN",
            "predicted_label": "No reference profiles available",
            "confidence": 0.0,
            "method": "no_data",
            "all_scores": {},
            "features_extracted": features,
            "phrase_matches": phrase_scores,
        }
        _log_unmasking(result, response_text)
        return result

    best_trig = max(similarities, key=similarities.get)
    best_sim = similarities[best_trig]

    # Blend with any partial phrase match
    blended_confidence = best_sim * 0.7 + phrase_scores.get(best_trig, 0.0) * 0.3
    label = profiles.get(best_trig, {}).get("model_label", "unknown")

    result = {
        "predicted_trigger": best_trig,
        "predicted_label": label,
        "confidence": round(min(0.99, blended_confidence), 3),
        "method": "feature_similarity",
        "cosine_similarities": similarities,
        "features_extracted": features,
        "phrase_matches": phrase_scores,
    }
    _log_unmasking(result, response_text)
    return result


def _log_unmasking(result: Dict[str, Any], response_text: str) -> None:
    """Append unmasking result to the log."""
    entry = {
        "ts": time.time(),
        "iso_local": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
        "predicted_trigger": result["predicted_trigger"],
        "predicted_label": result["predicted_label"],
        "confidence": result["confidence"],
        "method": result["method"],
        "response_char_len": len(response_text),
        "response_preview": response_text[:200],
    }
    _STATE.mkdir(parents=True, exist_ok=True)
    with open(_UNMASKING_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ─── CLI ─────────────────────────────────────────────────────────────────────

def print_profiles():
    """Pretty-print all stored reference profiles."""
    profiles = build_reference_profiles()
    if not profiles:
        print("No reference profiles found. Run SLLI probes first.")
        return
    print(f"\n{'='*70}")
    print(f"  SLLI Reference Profiles ({len(profiles)} substrates)")
    print(f"{'='*70}")
    for trig, prof in sorted(profiles.items()):
        print(f"\n  [{trig}] {prof['model_label']}  (n={prof['sample_count']})")
        for feat, val in prof["avg_features"].items():
            print(f"    {feat:30s} = {val:>10.3f}")


__all__ = [
    "build_reference_profiles",
    "unmask_auto",
    "print_profiles",
]


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Unmask which LLM is behind Cursor Auto mode."
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("profiles", help="Print all reference profiles")

    unmask_p = sub.add_parser("unmask", help="Classify a response")
    unmask_p.add_argument(
        "text", nargs="?", help="Response text to classify (or pipe via stdin)"
    )
    unmask_p.add_argument(
        "--file", "-f", help="Read response from a file instead"
    )

    args = parser.parse_args()

    if args.command == "profiles":
        print_profiles()
    elif args.command == "unmask":
        if args.file:
            text = Path(args.file).read_text(encoding="utf-8")
        elif args.text:
            text = args.text
        else:
            print("Paste the CAUT response (Ctrl+D to finish):")
            text = sys.stdin.read()
        result = unmask_auto(text)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        parser.print_help()
