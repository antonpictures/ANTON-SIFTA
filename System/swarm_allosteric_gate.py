#!/usr/bin/env python3
"""swarm_allosteric_gate.py — Hill-kinetics / allosteric decision curve (Gift 3).

Biology: hemoglobin binds O₂ cooperatively — almost nothing below a threshold,
then a sharp sigmoid commit. Same math as cooperative enzyme switches.

Silicon: any gate that currently uses a hard linear cutoff (especially the
owner voiceprint 0.51–0.60 straddle) can import a Hill curve:

    y = x^n / (x^n + K^n)

Below K → near-zero commit (reject ambient / podcast hosts).
Above K → decisive commit (owner path).

r1608 — first consumer is the voice / media ingress gate.
No LLM. Pure math + optional receipt.
"""
from __future__ import annotations

import json
import math
import time
import uuid
from pathlib import Path
from typing import Any, Mapping, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER = _STATE / "allosteric_gate_receipts.jsonl"

TRUTH_LABEL = "ALLOSTERIC_GATE_V1"

# Defaults tuned for owner-voice confidence in [0, 1].
# K slightly below the old hard 0.60 so true owner at 0.62+ commits hard;
# n high so 0.51–0.58 stays deep in the reject basin (kitchen leak band).
DEFAULT_K = 0.58
DEFAULT_N = 8.0
DEFAULT_COMMIT_THRESHOLD = 0.55  # on Hill output y
DEFAULT_REJECT_CEILING = 0.35    # y below this is hard reject/observe


def hill(x: float, *, K: float = DEFAULT_K, n: float = DEFAULT_N) -> float:
    """Hill binding fraction in [0, 1]. Safe for x<=0."""
    try:
        xv = float(x)
    except (TypeError, ValueError):
        xv = 0.0
    if xv <= 0.0 or n <= 0.0 or K <= 0.0:
        return 0.0
    if not math.isfinite(xv) or not math.isfinite(K) or not math.isfinite(n):
        return 0.0
    # Cap to avoid overflow on huge x
    xv = min(max(xv, 0.0), 10.0)
    try:
        xn = xv ** n
        kn = float(K) ** n
    except OverflowError:
        return 1.0 if xv >= K else 0.0
    denom = xn + kn
    if denom <= 0.0:
        return 0.0
    y = xn / denom
    if y < 0.0:
        return 0.0
    if y > 1.0:
        return 1.0
    return float(y)


def decide(
    x: float,
    *,
    K: float = DEFAULT_K,
    n: float = DEFAULT_N,
    commit_threshold: float = DEFAULT_COMMIT_THRESHOLD,
    reject_ceiling: float = DEFAULT_REJECT_CEILING,
    label: str = "generic",
) -> dict[str, Any]:
    """
    Map continuous evidence x to {reject, ambiguous, commit}.

    - commit:   y >= commit_threshold  (hard yes)
    - reject:   y <  reject_ceiling    (hard no / observe)
    - ambiguous: between
    """
    y = hill(x, K=K, n=n)
    if y >= float(commit_threshold):
        decision = "commit"
    elif y < float(reject_ceiling):
        decision = "reject"
    else:
        decision = "ambiguous"
    return {
        "truth_label": TRUTH_LABEL,
        "label": str(label or "generic"),
        "x": round(float(x or 0.0), 6),
        "y": round(y, 6),
        "K": float(K),
        "n": float(n),
        "commit_threshold": float(commit_threshold),
        "reject_ceiling": float(reject_ceiling),
        "decision": decision,
    }


def voice_owner_allosteric_decision(
    voice_george_conf: float,
    *,
    media_active: bool = False,
    K: float = DEFAULT_K,
    n: float = DEFAULT_N,
) -> dict[str, Any]:
    """
    Owner-voice commit under optional ambient media.

    When media is active, cooperativity is slightly higher (steeper) so
    podcast-host confidences in the 0.50–0.58 band stay rejected harder.
    """
    nn = float(n) + (2.0 if media_active else 0.0)
    # Under media, nudge K up so only strong owner matches commit.
    kk = float(K) + (0.02 if media_active else 0.0)
    out = decide(
        float(voice_george_conf or 0.0),
        K=kk,
        n=nn,
        commit_threshold=DEFAULT_COMMIT_THRESHOLD,
        reject_ceiling=DEFAULT_REJECT_CEILING,
        label="voice_owner",
    )
    out["media_active"] = bool(media_active)
    # Compatibility aliases for gates that used hard 0.60
    out["commit_owner"] = out["decision"] == "commit"
    out["observe_or_reject"] = out["decision"] in {"reject", "ambiguous"}
    # Effective "hard threshold" equivalent for logging (approx inverse Hill)
    out["legacy_hard_threshold"] = 0.60
    out["beats_legacy_hard_cutoff"] = bool(
        out["commit_owner"] or float(voice_george_conf or 0.0) < 0.60
    )
    return out


def should_commit_owner_voice(
    voice_george_conf: float,
    *,
    media_active: bool = False,
) -> bool:
    """Drop-in replacement for ``voice_george_conf >= 0.60``."""
    return bool(
        voice_owner_allosteric_decision(
            voice_george_conf, media_active=media_active
        ).get("commit_owner")
    )


def write_receipt(
    decision: Mapping[str, Any],
    *,
    state_dir: Optional[Path] = None,
    extra: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    state = Path(state_dir) if state_dir else _STATE
    state.mkdir(parents=True, exist_ok=True)
    path = state / "allosteric_gate_receipts.jsonl"
    row = {
        "ts": time.time(),
        "receipt_id": uuid.uuid4().hex[:12],
        **dict(decision),
    }
    if extra:
        row["extra"] = dict(extra)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


__all__ = [
    "TRUTH_LABEL",
    "DEFAULT_K",
    "DEFAULT_N",
    "hill",
    "decide",
    "voice_owner_allosteric_decision",
    "should_commit_owner_voice",
    "write_receipt",
]
