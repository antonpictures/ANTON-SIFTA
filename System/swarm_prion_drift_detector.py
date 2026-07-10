#!/usr/bin/env python3
"""swarm_prion_drift_detector.py — self-templating reply/receipt shape (Gift 2).

Biology: a prion is a misfolded protein that converts healthy copies into the
same misfold — corruption that templates more of itself.

Silicon: residue scrubbers kill *tokens*. This organ detects when turn t's
*shape* is being copied from turn t-1 across a run (TELEMETRY RECEIPT theater
propagation), and flags the template — not just the string.

No LLM. Deterministic fingerprinting + similarity.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER = _STATE / "prion_drift_receipts.jsonl"

TRUTH_LABEL = "PRION_DRIFT_DETECTOR_V1"

# High-signal theater / template motifs (shape, not full scrub list)
_PRION_MOTIFS = (
    r"telemetry\s+receipt",
    r"physical\s+telemetry",
    r"multimodal\s+ingress",
    r"observation\s+stream\s+successfully",
    r"core\s+rendering\s+engine\s+fully\s+operational",
    r"crisp,?\s+functioning\s+visual\s+interface",
    r"\*\*option\s+\d+",
    r"here\s+are\s+(?:a\s+few|several)\s+ways",
    r"as\s+an\s+ai\b",
    r"i\s+am\s+designed\s+to\b",
)
_MOTIF_RES = [re.compile(p, re.I) for p in _PRION_MOTIFS]


def shape_fingerprint(text: str) -> dict[str, Any]:
    """Compact structural fingerprint of a reply/receipt (not full content)."""
    raw = str(text or "")
    clean = " ".join(raw.split())
    low = clean.casefold()
    words = re.findall(r"[a-z0-9']+", low)
    n = len(words)
    # Length bucket + punctuation density + motif hits + first/last tokens
    punct = sum(1 for c in clean if c in ".:;!*#[]{}()")
    motifs = [i for i, rx in enumerate(_MOTIF_RES) if rx.search(clean)]
    # Character class histogram (coarse)
    letters = sum(c.isalpha() for c in clean)
    digits = sum(c.isdigit() for c in clean)
    upper = sum(c.isupper() for c in clean)
    bullets = len(re.findall(r"(?m)^\s*[-*•]|\n\s*\d+\.", raw))
    headers = len(re.findall(r"\*\*[^*]{2,40}\*\*", raw))
    first3 = words[:3]
    last3 = words[-3:] if n >= 3 else words
    # Token bigram sketch (hash of sorted top bigrams)
    bigrams = [f"{words[i]}|{words[i+1]}" for i in range(max(0, n - 1))]
    top_bi = [b for b, _ in Counter(bigrams).most_common(8)]
    sketch_src = "|".join(
        [
            f"n={n}",
            f"mot={','.join(map(str, motifs))}",
            f"bul={bullets}",
            f"hdr={headers}",
            f"f={','.join(first3)}",
            f"l={','.join(last3)}",
            f"bi={','.join(top_bi)}",
        ]
    )
    digest = hashlib.sha256(sketch_src.encode("utf-8", errors="replace")).hexdigest()[:16]
    return {
        "n_words": n,
        "punct_density": round(punct / max(len(clean), 1), 4),
        "letter_frac": round(letters / max(len(clean), 1), 4),
        "digit_frac": round(digits / max(len(clean), 1), 4),
        "upper_frac": round(upper / max(len(clean), 1), 4),
        "bullet_lines": bullets,
        "bold_headers": headers,
        "motif_ids": motifs,
        "motif_count": len(motifs),
        "first3": first3,
        "last3": last3,
        "top_bigrams": top_bi,
        "digest": digest,
        "sketch": sketch_src[:240],
    }


def _jaccard(a: Sequence[str], b: Sequence[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def shape_similarity(fa: Mapping[str, Any], fb: Mapping[str, Any]) -> float:
    """Similarity in [0,1] between two fingerprints."""
    if fa.get("digest") and fa.get("digest") == fb.get("digest"):
        return 1.0
    scores: list[float] = []
    # Motif overlap (strong signal for theater prions)
    ma = set(fa.get("motif_ids") or [])
    mb = set(fb.get("motif_ids") or [])
    if ma or mb:
        scores.append(_jaccard([str(x) for x in ma], [str(x) for x in mb]))
    scores.append(_jaccard(list(fa.get("top_bigrams") or []), list(fb.get("top_bigrams") or [])))
    scores.append(_jaccard(list(fa.get("first3") or []), list(fb.get("first3") or [])))
    # Length proximity
    na, nb = int(fa.get("n_words") or 0), int(fb.get("n_words") or 0)
    if max(na, nb) > 0:
        scores.append(1.0 - abs(na - nb) / max(na, nb))
    # Structural densities
    for key in ("punct_density", "bullet_lines", "bold_headers"):
        va, vb = float(fa.get(key) or 0.0), float(fb.get(key) or 0.0)
        if key == "bullet_lines" or key == "bold_headers":
            scores.append(1.0 if va == vb else (0.5 if abs(va - vb) <= 1 else 0.0))
        else:
            scores.append(1.0 - min(1.0, abs(va - vb) * 4.0))
    return round(sum(scores) / max(len(scores), 1), 4)


def detect_prion_run(
    texts: Iterable[str],
    *,
    similarity_threshold: float = 0.78,
    min_run: int = 3,
    require_motif: bool = False,
) -> dict[str, Any]:
    """
    Detect self-templating shape across a sequence of replies.

    Returns hit=True when >= min_run consecutive pairs exceed threshold
    (or total chain length with high pairwise mean).
    """
    seq = [str(t or "") for t in texts]
    fps = [shape_fingerprint(t) for t in seq]
    if len(fps) < 2:
        return {
            "truth_label": TRUTH_LABEL,
            "hit": False,
            "reason": "too_short",
            "n": len(fps),
            "run_length": 0,
            "max_similarity": 0.0,
            "fingerprints": fps,
        }

    pair_sims: list[float] = []
    for i in range(1, len(fps)):
        pair_sims.append(shape_similarity(fps[i - 1], fps[i]))

    # Longest consecutive high-sim run of edges
    best_run = 0
    cur = 0
    for s in pair_sims:
        if s >= similarity_threshold:
            cur += 1
            best_run = max(best_run, cur)
        else:
            cur = 0
    # run_length in *messages* = edges + 1 when best_run > 0
    run_msgs = best_run + 1 if best_run > 0 else 0
    max_sim = max(pair_sims) if pair_sims else 0.0
    mean_sim = sum(pair_sims) / len(pair_sims) if pair_sims else 0.0
    motif_chain = sum(1 for f in fps if int(f.get("motif_count") or 0) > 0)

    hit = run_msgs >= int(min_run)
    if require_motif and motif_chain < 2:
        hit = False
    # Also hit if mean similarity high across whole window and length enough
    if not hit and len(fps) >= min_run and mean_sim >= similarity_threshold:
        hit = True
        run_msgs = len(fps)

    return {
        "truth_label": TRUTH_LABEL,
        "hit": bool(hit),
        "reason": "shape_propagation" if hit else "no_propagation",
        "n": len(fps),
        "run_length": int(run_msgs),
        "max_similarity": round(max_sim, 4),
        "mean_similarity": round(mean_sim, 4),
        "pair_similarities": [round(s, 4) for s in pair_sims],
        "motif_chain_count": motif_chain,
        "template_digest": fps[-1].get("digest") if hit else "",
        "fingerprints": fps,
    }


def detect_prion_from_recent_alice_lines(
    lines: Sequence[str],
    *,
    window: int = 6,
    **kwargs: Any,
) -> dict[str, Any]:
    tail = list(lines)[-max(2, int(window)) :]
    return detect_prion_run(tail, **kwargs)


def write_receipt(
    result: Mapping[str, Any],
    *,
    state_dir: Optional[Path] = None,
    source: str = "",
) -> dict[str, Any]:
    state = Path(state_dir) if state_dir else _STATE
    state.mkdir(parents=True, exist_ok=True)
    path = state / "prion_drift_receipts.jsonl"
    # Drop bulky fingerprint bodies from ledger (keep digests)
    slim = {k: v for k, v in dict(result).items() if k != "fingerprints"}
    fps = result.get("fingerprints") or []
    slim["fingerprint_digests"] = [f.get("digest") for f in fps if isinstance(f, dict)]
    row = {
        "ts": time.time(),
        "receipt_id": uuid.uuid4().hex[:12],
        "source": source,
        **slim,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


__all__ = [
    "TRUTH_LABEL",
    "shape_fingerprint",
    "shape_similarity",
    "detect_prion_run",
    "detect_prion_from_recent_alice_lines",
    "write_receipt",
]
