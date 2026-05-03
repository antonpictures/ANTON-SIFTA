#!/usr/bin/env python3
"""
System/swarm_acoustic_scene_classifier.py
══════════════════════════════════════════════════════════════════════
Acoustic Scene Pre-Classifier (Event 121b)

Reads the live stigmergic_cochlea.jsonl features and classifies the
ambient audio environment into coarse YouTube categories BEFORE the
LLM Shazam guess is made.

This narrows the LLM's prior space: instead of "guess anything",
the prompt becomes "guess within CINEMATIC".

Research spine:
  Wang (2003)  Landmark fingerprinting          ISMIR 2003
  DCASE (2013-) Acoustic Scene Classification   dcase.community
  Barchiesi et al. (2015) ASC survey            IEEE SPM
  Dorigo, Bonabeau, Theraulaz (2000) Stigmergy  FGCS doi:10.1016/S0167-739X(99)00143-7

Scene taxonomy aligned to YouTube category API:
  CINEMATIC  — movie/TV dialogue, narrative scoring
  NEWS       — news broadcast, documentary voice-over
  MUSIC      — songs, music videos, live performance
  SPORTS     — commentary, crowd, arena
  GAMING     — game SFX, esports commentary
  PODCAST    — interview/conversation, near-field voice pairs
  AMBIENT    — nature, ASMR, lo-fi, background
  UNKNOWN    — classifier confidence below threshold

Truth label: ACOUSTIC_SCENE_CLASSIFICATION_V1
"""
from __future__ import annotations

import json
import math
import time
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from System.jsonl_file_lock import append_line_locked

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_COCHLEA_LOG = _STATE_DIR / "stigmergic_cochlea.jsonl"
_SCENE_LOG    = _STATE_DIR / "acoustic_scene_classifications.jsonl"

SCHEMA_VERSION = "event121b.acoustic_scene_classifier.v1"

# YouTube categories recognised by this classifier
SCENE_LABELS = [
    "CINEMATIC",   # film/TV dialogue and score
    "NEWS",        # broadcast journalism, docs
    "MUSIC",       # songs, live performance
    "SPORTS",      # commentary + crowd
    "GAMING",      # game SFX + esports
    "PODCAST",     # interview / conversation
    "AMBIENT",     # ASMR, lo-fi, nature
    "UNKNOWN",     # below confidence floor
]

# Minimum posterior to commit to a label (vs UNKNOWN)
_CONFIDENCE_FLOOR = 0.35


@dataclass(frozen=True)
class SceneFrame:
    scene: str
    confidence: float
    scores: Dict[str, float]
    feature_snapshot: Dict[str, Any]
    ts: float
    schema_version: str = SCHEMA_VERSION
    truth_label: str = "ACOUSTIC_SCENE_CLASSIFICATION_V1"
    receipt_id: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _read_last_cochlea_row(n_rows: int = 5) -> Optional[Dict[str, Any]]:
    """Return the averaged feature dict of the last N cochlea rows."""
    if not _COCHLEA_LOG.exists():
        return None
    try:
        lines = _COCHLEA_LOG.read_text(encoding="utf-8").splitlines()[-n_rows:]
        rows = [json.loads(l) for l in lines if l.strip()]
        if not rows:
            return None
        # Average the scalar features across last N rows for stability
        keys = ["acoustic_stress", "f0_hz", "spectral_centroid_hz",
                "spectral_entropy", "zero_crossing_rate", "rms", "peak"]
        avg: Dict[str, float] = {}
        for k in keys:
            vals = [float(r.get(k, 0.0)) for r in rows if r.get(k) is not None]
            avg[k] = sum(vals) / len(vals) if vals else 0.0

        # Average first MFCC coefficient (energy proxy)
        mfcc_0s = [r.get("mfcc", [0])[0] for r in rows if r.get("mfcc")]
        avg["mfcc_0"] = sum(mfcc_0s) / len(mfcc_0s) if mfcc_0s else 0.0

        # Acoustic fingerprint averages
        fp_keys = ["farfield_replay_likelihood", "nearfield_voice_likelihood",
                   "spectral_flatness", "hnr_proxy", "am_depth", "crest_factor"]
        for k in fp_keys:
            vals = [float(r.get("playback_fingerprint", {}).get(k, 0.0)) for r in rows]
            avg[f"fp_{k}"] = sum(vals) / len(vals) if vals else 0.0

        avg["vad_ratio"] = sum(1 for r in rows if r.get("vad")) / len(rows)
        return avg
    except Exception:
        return None


def _score_scene(feat: Dict[str, float]) -> Dict[str, float]:
    """
    Rule-based posterior over scene labels from acoustic features.

    All rules are derived from the DCASE/ASC literature:
    - Spectral flatness separates music (high flatness) from speech (low).
    - F0 stability and range separate singing from speech.
    - HNR proxy high → voiced speech (news, podcast, cinema dialogue).
    - AM depth high → music (rhythmic amplitude modulation).
    - Farfield replay likelihood → TV/monitor source.
    - ZCR high + low RMS → noisy crowd (sports).
    - Spectral centroid high → news (rapid, bright consonants).

    Returns unnormalised logit-like scores (positive = evidence for).
    """
    sf  = feat.get("fp_spectral_flatness", 0.1)       # music: high, speech: low
    hnr = feat.get("fp_hnr_proxy", 0.05)              # voiced: high
    am  = feat.get("fp_am_depth", 0.5)                # music: high
    ff  = feat.get("fp_farfield_replay_likelihood",0.4)
    nf  = feat.get("fp_nearfield_voice_likelihood", 0.5)
    cf  = feat.get("fp_crest_factor", 5.0)            # percussive: high
    f0  = feat.get("f0_hz", 130.0)                    # speech: 80-300, singing: varies
    sc  = feat.get("spectral_centroid_hz", 350.0)     # news: 400+, cinema: 250-400
    se  = feat.get("spectral_entropy", 0.7)           # noise: high, tonal: low
    zcr = feat.get("zero_crossing_rate", 0.07)        # crowd noise: high
    rms = feat.get("rms", 0.15)
    vad = feat.get("vad_ratio", 1.0)

    scores: Dict[str, float] = {s: 0.0 for s in SCENE_LABELS}

    # ── MUSIC ──────────────────────────────────────────────────────────────
    # High spectral flatness + high AM depth = music source
    scores["MUSIC"] += 2.0 * sf
    scores["MUSIC"] += 1.5 * am
    scores["MUSIC"] -= 1.0 * hnr          # voiced speech anti-correlates
    scores["MUSIC"] += 0.5 * (1.0 - se)  # tonal audio → low entropy

    # ── NEWS ───────────────────────────────────────────────────────────────
    # High HNR (voiced) + high centroid (bright speech) + farfield (TV)
    scores["NEWS"] += 2.0 * hnr
    scores["NEWS"] += 1.5 * min(1.0, sc / 600.0)
    scores["NEWS"] += 1.0 * ff
    scores["NEWS"] -= 1.0 * sf           # music anti-correlates
    if 120 < f0 < 220:                   # typical announcer F0 range
        scores["NEWS"] += 0.8

    # ── CINEMATIC ──────────────────────────────────────────────────────────
    # HNR present (dialogue) + low-to-mid centroid + moderate AM (score) + farfield
    scores["CINEMATIC"] += 1.5 * hnr
    scores["CINEMATIC"] += 1.2 * ff
    scores["CINEMATIC"] += 0.8 * am      # underscore / score
    scores["CINEMATIC"] -= 1.0 * min(1.0, sc / 600.0)  # NOT bright news-style
    if f0 < 120 or f0 > 220:            # character voices outside announcer range
        scores["CINEMATIC"] += 0.6

    # ── SPORTS ─────────────────────────────────────────────────────────────
    # High ZCR (crowd noise), high entropy, moderate farfield
    scores["SPORTS"] += 2.0 * zcr
    scores["SPORTS"] += 1.5 * se
    scores["SPORTS"] += 1.0 * ff
    scores["SPORTS"] -= 1.5 * hnr       # pure voiced speech unlikely in crowd

    # ── GAMING ─────────────────────────────────────────────────────────────
    # High crest factor (percussive SFX), high entropy, moderate centroid
    scores["GAMING"] += 1.5 * min(1.0, cf / 10.0)
    scores["GAMING"] += 1.0 * se
    scores["GAMING"] += 0.5 * (1.0 - ff)  # nearfield setup (headphones/mic)

    # ── PODCAST ────────────────────────────────────────────────────────────
    # High HNR + high nearfield likelihood + low AM (no music)
    scores["PODCAST"] += 2.0 * hnr
    scores["PODCAST"] += 1.5 * nf
    scores["PODCAST"] -= 1.0 * am       # music presence anti-correlates
    scores["PODCAST"] -= 0.5 * ff       # nearfield not farfield

    # ── AMBIENT ────────────────────────────────────────────────────────────
    # Low VAD + low HNR + high entropy (rain, nature, lo-fi)
    scores["AMBIENT"] += 2.0 * (1.0 - vad)
    scores["AMBIENT"] += 1.0 * se
    scores["AMBIENT"] -= 1.0 * hnr

    return scores


def _softmax(scores: Dict[str, float]) -> Dict[str, float]:
    """Stable softmax over the score dict (excludes UNKNOWN)."""
    labels = [s for s in SCENE_LABELS if s != "UNKNOWN"]
    vals = [scores[s] for s in labels]
    max_v = max(vals) if vals else 0.0
    exps = [math.exp(v - max_v) for v in vals]
    total = sum(exps)
    return {l: (e / total) if total > 0 else 0.0 for l, e in zip(labels, exps)}


def classify_scene(cochlea_row: Optional[Dict[str, float]] = None) -> SceneFrame:
    """
    Main entry point. Reads last cochlea window and returns a SceneFrame.
    If cochlea_row is provided, skips disk read (for testing).
    """
    feat = cochlea_row if cochlea_row is not None else _read_last_cochlea_row()
    if not feat:
        return SceneFrame(
            scene="UNKNOWN", confidence=0.0, scores={},
            feature_snapshot={}, ts=time.time(),
            receipt_id=str(uuid.uuid4()),
        )

    raw_scores = _score_scene(feat)
    posteriors = _softmax(raw_scores)
    best_label = max(posteriors, key=posteriors.__getitem__)
    best_conf  = posteriors[best_label]

    scene = best_label if best_conf >= _CONFIDENCE_FLOOR else "UNKNOWN"
    frame = SceneFrame(
        scene=scene,
        confidence=round(best_conf, 4),
        scores={k: round(v, 4) for k, v in posteriors.items()},
        feature_snapshot=feat,
        ts=time.time(),
        receipt_id=str(uuid.uuid4()),
    )
    _emit_receipt(frame)
    return frame


def _emit_receipt(frame: SceneFrame) -> None:
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    append_line_locked(_SCENE_LOG, json.dumps(frame.as_dict(), sort_keys=True) + "\n")


if __name__ == "__main__":
    frame = classify_scene()
    print(f"Scene: {frame.scene}  confidence={frame.confidence:.3f}")
    for k, v in sorted(frame.scores.items(), key=lambda x: -x[1]):
        bar = "█" * int(v * 20)
        print(f"  {k:<12} {v:.3f}  {bar}")
