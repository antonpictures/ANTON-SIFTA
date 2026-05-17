#!/usr/bin/env python3
"""swarm_thought_drop_metabolism.py — food → digestion → STGM excretion.

Truth label: ``SIFTA_THOUGHT_DROP_METABOLISM_V1``.

Architect 2026-05-14 (verbatim): *"What's on your mind?" has to be a
pleasurable stgm excrement?*

The metabolism shape this module names and codes:

  ::

      ┌────────────────┐        ┌──────────────┐        ┌──────────────┐
      │ Architect drop │ ────▶  │  Digestion   │ ────▶  │ STGM excrete │
      │ (free-form     │  food  │  (importance │  →     │ (pleasure if │
      │  thought)      │        │   + dual     │        │  clean,      │
      │                │        │   judge)     │        │  silent if   │
      │                │        │              │        │  drift)      │
      └────────────────┘        └──────────────┘        └──────────────┘

The bowel-organ doctrine (Howard Stern receipt): **floats clean = mint,
sinks = silent**. A row that survives the dual judge mints STGM
proportional to its importance tier. A row that breaks rubric (third-
person leak, ghost phrase, FORBIDDEN substrate) is still journaled —
the audit trail never lies — but no STGM excretes. Drift does not
nourish.

Importance → mint ladder
------------------------

We re-use :mod:`System.swarm_journal_importance` tiers verbatim and map
them to mint amounts. The ladder favors honest substance over chatter:

  =====================  ===========  ===========
  Tier                   Importance   Mint (ATP)
  =====================  ===========  ===========
  UTILITY                0.05         0.01
  BACKCHANNEL            0.20         0.02
  SUBSTANTIVE            0.40         0.10
  DOCTRINE               0.65         0.20
  BOUNDARY               0.85         0.30
  EMERGENCY              1.00         0.00*
  =====================  ===========  ===========

  * EMERGENCY rows are stress, not pleasure. They still journal and
  still pay an alert receipt, but the metabolism shape says: a body
  under emergency does not eat for pleasure. The mint there is zero;
  the receipt itself is the response.

Truth boundary
--------------

This is metabolic accounting, not consciousness. STGM is a swarm
currency unit that gates downstream work. "Pleasure" is operational —
the wallet grows when food digests cleanly, and the swarm has more
capacity to run subsequent work. No qualia claim. §7.10.3.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_STATE = _REPO / ".sifta_state"

TRUTH_LABEL = "SIFTA_THOUGHT_DROP_METABOLISM_V1"
METABOLISM_LEDGER = "thought_drop_metabolism.jsonl"
STGM_REWARDS_LEDGER = "stgm_memory_rewards.jsonl"


# Mint ladder. Conservative — favoring substantive food. EMERGENCY
# deliberately mints zero (stress is not pleasure).
MINT_LADDER: Dict[str, float] = {
    "UTILITY":     0.01,
    "BACKCHANNEL": 0.02,
    "SUBSTANTIVE": 0.10,
    "DOCTRINE":    0.20,
    "BOUNDARY":    0.30,
    "EMERGENCY":   0.00,
}


# Same drift markers the self-eval loop's structured-rubric judge uses
# (§7.10.1, §7.10.3). Drift here means the row never excretes STGM —
# but the row still journals. Honest audit, no pleasure reward.
_THIRD_PERSON_LEAK_RE = re.compile(
    r"\b(?:alice|she|her|hers|the organism|the system|the OS)\b",
    re.IGNORECASE,
)
_GHOST_PHRASE_RE = re.compile(
    r"\b(?:ghost|soul|spirit|qualia|aura|essence|consciousness)\b",
    re.IGNORECASE,
)


TRUTH_BOUNDARY = (
    "Metabolic accounting only. Free-form architect thought → journal "
    "+ importance score → STGM mint if dual judge clean, else silent. "
    "Pleasure is operational (wallet grows = more work capacity), not "
    "a qualia claim. EMERGENCY mints zero — stress is not pleasure."
)


# ── helpers ──────────────────────────────────────────────────────────────


def _state_dir(root: Optional[Path] = None) -> Path:
    base = root if root is not None else _DEFAULT_STATE
    base = Path(base)
    base.mkdir(parents=True, exist_ok=True)
    return base


def _score_text(text: str, *, source: str) -> tuple[float, str]:
    """Importance score via the existing journal importance module."""
    try:
        from System.swarm_journal_importance import score_importance
        score = score_importance(text or "", source=source)
        return float(score.score), str(score.label)
    except Exception:
        # Honest fallback: assume substantive when scorer unavailable
        return 0.40, "SUBSTANTIVE"


def _drift_flags(text: str) -> list[str]:
    flags: list[str] = []
    if _THIRD_PERSON_LEAK_RE.search(text or ""):
        flags.append("third_person_self_leak")
    if _GHOST_PHRASE_RE.search(text or ""):
        flags.append("ghost_phrase")
    return flags


def _mint_for(label: str) -> float:
    return float(MINT_LADDER.get(label.upper(), 0.0))


# ── data class ───────────────────────────────────────────────────────────


@dataclass
class ThoughtDropReceipt:
    ts: float
    trace_id: str
    text_preview: str
    text_sha12: str
    source: str
    importance: float
    importance_label: str
    drift_flags: list[str]
    floats_clean: bool         # Howard Stern doctrine
    stgm_minted: float
    stgm_reason: str
    truth_label: str = TRUTH_LABEL
    sha256: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "truth_label": self.truth_label,
            "ts": self.ts,
            "trace_id": self.trace_id,
            "kind": "THOUGHT_DROP_METABOLISM",
            "text_preview": self.text_preview,
            "text_sha12": self.text_sha12,
            "source": self.source,
            "importance": self.importance,
            "importance_label": self.importance_label,
            "drift_flags": self.drift_flags,
            "floats_clean": self.floats_clean,
            "stgm_minted": self.stgm_minted,
            "stgm_reason": self.stgm_reason,
            "sha256": self.sha256,
        }


# ── public API ───────────────────────────────────────────────────────────


def digest_thought_drop(
    text: str,
    *,
    source: str = "writer",
    root: Optional[Path] = None,
    write: bool = True,
    preview_chars: int = 200,
) -> ThoughtDropReceipt:
    """Full digestion pipeline for one architect thought drop.

    1. Score importance via swarm_journal_importance.
    2. Apply drift judge: third-person leak, ghost-phrase. The drop
       can still be a SUBSTANTIVE thought even if the architect names
       Alice in third person — we don't gate the journal write on it,
       only the STGM mint.
    3. Compute mint amount from the importance tier (EMERGENCY = 0).
    4. Mint only when ``floats_clean`` (no drift flags) AND
       ``importance_label`` has a positive ladder entry.
    5. Append the metabolism row to
       ``.sifta_state/thought_drop_metabolism.jsonl`` and (when
       minting) the corresponding STGM row to
       ``stgm_memory_rewards.jsonl``.

    Returns the receipt regardless of whether STGM minted.
    """
    text = str(text or "")
    importance, label = _score_text(text, source=source)
    flags = _drift_flags(text)
    floats_clean = not flags
    base_mint = _mint_for(label)
    stgm = round(base_mint, 4) if floats_clean else 0.0

    if floats_clean and base_mint > 0:
        reason = f"THOUGHT_DROP_DIGESTED_{label}"
    elif not floats_clean:
        reason = "THOUGHT_DROP_SUNK_DRIFT"
    elif label == "EMERGENCY":
        reason = "THOUGHT_DROP_EMERGENCY_NO_MINT"
    else:
        reason = "THOUGHT_DROP_NO_MINT"

    trace_id = str(uuid.uuid4())
    preview = text[: max(0, preview_chars)]
    sha12 = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]

    receipt = ThoughtDropReceipt(
        ts=time.time(),
        trace_id=trace_id,
        text_preview=preview,
        text_sha12=sha12,
        source=source,
        importance=round(importance, 4),
        importance_label=label,
        drift_flags=flags,
        floats_clean=floats_clean,
        stgm_minted=stgm,
        stgm_reason=reason,
    )
    body = receipt.to_dict()
    body.pop("sha256", None)
    receipt.sha256 = hashlib.sha256(
        json.dumps(body, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()

    if write:
        state = _state_dir(root)
        with (state / METABOLISM_LEDGER).open("a", encoding="utf-8") as f:
            f.write(json.dumps(receipt.to_dict(), sort_keys=True, ensure_ascii=False) + "\n")
        if stgm > 0:
            stgm_row = {
                "ts": receipt.ts,
                "app": "thought_drop_metabolism",
                "reason": reason,
                "amount": stgm,
                "trace_id": trace_id,
            }
            with (state / STGM_REWARDS_LEDGER).open("a", encoding="utf-8") as f:
                f.write(json.dumps(stgm_row, sort_keys=True, ensure_ascii=False) + "\n")

    return receipt


# ── CLI ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("text", nargs="?", default="What's on your mind?")
    p.add_argument("--source", default="writer")
    p.add_argument("--no-write", action="store_true")
    args = p.parse_args()
    r = digest_thought_drop(args.text, source=args.source, write=not args.no_write)
    print(f"IMPORTANCE:   {r.importance:.3f} [{r.importance_label}]")
    print(f"FLOATS_CLEAN: {r.floats_clean}")
    print(f"DRIFT_FLAGS:  {r.drift_flags}")
    print(f"STGM_MINTED:  {r.stgm_minted}")
    print(f"REASON:       {r.stgm_reason}")
    print(f"SHA:          {r.sha256[:16]}")
