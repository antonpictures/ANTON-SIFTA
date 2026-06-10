#!/usr/bin/env python3
"""
System/swarm_voice_stigma_repair.py
===================================
Voice Stigma Repair organ.

When STT mangles a command (especially "open <app>"), this organ repairs it using:
- Live apps_manifest.json
- Recent app_focus.jsonl (stigmergic context)
- Recent conversation context
- Fuzzy matching (Damerau-Levenshtein + token overlap)

It returns the best repair + confidence + short confirmation text for Alice to say.

This is the organ that makes natural language + bad voice-to-text actually usable in a real stigmergic OS.

All repairs are receipted.
"""

from __future__ import annotations

import json
import re
import time
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_MANIFEST = _REPO / "Applications" / "apps_manifest.json"
_APP_FOCUS = _STATE / "app_focus.jsonl"
_ALICE_CONVERSATION = _STATE / "alice_conversation.jsonl"

_RECEIPTS = _STATE / "voice_stigma_repair.jsonl"

def _append_receipt(row: Dict[str, Any]) -> None:
    _STATE.mkdir(parents=True, exist_ok=True)
    row["ts"] = time.time()
    with _RECEIPTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


# ── Alice/Ace STT vocative guard — Claude (Cowork CW47, cw47-0516-2347) ─
# Architect 2026-05-16: "very easy for her to confuse Alice with Ace —
# if I say Alice she starts the Ace game". STT collapses two-syllable
# "Alice" into one-syllable "Ace"; this organ's `nnorm in norm` substring
# pass then fuzz-matches the bare token "ace" against the manifest's
# "Ace" entry at 0.95 confidence, prompting Alice to ask "Should I open
# Ace?" which seeds the false launch. Abstain when the raw text is a
# misheard vocative — i.e. starts with bare "Ace" and contains no
# explicit Ace-app launch markers. Real "open Ace" / "play Ace" /
# "teach Ace to read" continue to repair correctly.

_BARE_ACE_VOCATIVE_RE = re.compile(
    r"^\s*(?:hey\s+|ok\s+|okay\s+|hi\s+|yo\s+)?ace\b",
    re.IGNORECASE,
)

_ACE_APP_INTENT_RES: Tuple[re.Pattern, ...] = (
    re.compile(
        r"\b(?:open|launch|start|run|play|do|teach|use|read\s+with|"
        r"practice\s+with|fire\s+up|bring\s+up|show\s+me|switch\s+to|"
        r"go\s+to)\s+(?:the\s+)?(?:reading\s+game\s+|word\s*ace\s+)?ace\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bace[,\s]+(?:app|game|lesson|reading|to\s+read|"
        r"please\s+(?:read|teach|start|open))\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:teach|tutor|help)\s+ace\s+(?:to\s+)?read\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bword\s*ace\b", re.IGNORECASE),
    re.compile(r"\bace\s+(?:reading|game|lesson)\b", re.IGNORECASE),
)

_TOOL_OR_EFFECTOR_CONTRACT_RE = re.compile(
    r"\[TOOL_CALL:|```tool_call|\bbrowser_close_tab\b|\beffector-only\b|"
    r"\b(?:close|shut|remove|kill)\b.{0,180}\b(?:tab|tabs)\b",
    re.IGNORECASE,
)


def is_misheard_ace_vocative(text: str) -> bool:
    """True when ``text`` is the STT mis-hearing of "Alice" as "Ace".

    Used by ``repair_voice_command`` to abstain from fuzz-matching the
    bare token "ace" to the Ace reading-game app. Conservative: any
    Ace-app launch marker disables the guard.
    """
    clean = (text or "").strip()
    if not clean:
        return False
    if not _BARE_ACE_VOCATIVE_RE.match(clean):
        return False
    for pat in _ACE_APP_INTENT_RES:
        if pat.search(clean):
            return False
    return True


def _load_manifest_names() -> List[str]:
    if not _MANIFEST.exists():
        return []
    try:
        data = json.loads(_MANIFEST.read_text(encoding="utf-8"))
        return list(data.keys())
    except Exception:
        return []


def _damerau_levenshtein(s1: str, s2: str) -> int:
    """Simple Damerau-Levenshtein distance."""
    if len(s1) < len(s2):
        return _damerau_levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def _recent_context(max_lines: int = 12) -> str:
    chunks = []
    for path in [_APP_FOCUS, _ALICE_CONVERSATION]:
        if not path.exists():
            continue
        try:
            lines = [l.strip() for l in path.read_text(encoding="utf-8", errors="ignore").splitlines() if l.strip()]
            for line in lines[-max_lines:]:
                chunks.append(line[:400])
        except Exception:
            continue
    return " ".join(chunks)


def repair_voice_command(raw_text: str, intent: str = "open_app") -> Dict[str, Any]:
    """
    Main entry point.
    Returns:
        {
            "original": raw_text,
            "repaired": best_guess or None,
            "confidence": 0.0-1.0,
            "candidates": [...],
            "confirmation_text": short sentence Alice can say,
            "receipt": ...
        }
    """
    original = raw_text
    norm = _normalize(raw_text)

    # Preserve explicit tool/effector contracts. A long owner paste that starts
    # with "Alice" must not be repaired to the app name "Alice" before the
    # cortex/tool router can read the real command.
    if _TOOL_OR_EFFECTOR_CONTRACT_RE.search(raw_text or ""):
        receipt = {
            "original": original,
            "repaired": None,
            "confidence": 0.0,
            "method": "abstain_tool_or_effector_contract",
            "note": "Explicit tool/effector contract preserved verbatim; no app-name repair.",
        }
        _append_receipt(receipt)
        return {
            "original": original,
            "repaired": None,
            "confidence": 0.0,
            "candidates": [],
            "confirmation_text": "",
            "receipt": receipt,
        }

    # ── Alice/Ace STT vocative abstain (cw47-0516-2347) ───────────────────
    # If the raw text is the canonical misheard-vocative "Ace ..." (no Ace
    # launch markers), do NOT fuzz-match it to the Ace app. Return
    # untouched with confidence 0.0 and a method tag so the caller can
    # route to the brain as conversation.
    if is_misheard_ace_vocative(raw_text):
        receipt = {
            "original": original,
            "repaired": None,
            "confidence": 0.0,
            "method": "abstain_alice_ace_vocative",
            "note": "STT mis-hearing guard: bare 'Ace' vocative without "
                    "Ace-app launch marker — preserved as conversation.",
        }
        _append_receipt(receipt)
        return {
            "original": original,
            "repaired": None,
            "confidence": 0.0,
            "candidates": [],
            "confirmation_text": "",
            "receipt": receipt,
        }

    manifest_names = _load_manifest_names()
    if not manifest_names:
        return {"original": original, "repaired": None, "confidence": 0.0, "error": "no manifest"}

    # 1. Exact / substring / alias match (fast path)
    for name in manifest_names:
        nnorm = _normalize(name)
        if nnorm == norm or nnorm in norm or norm in nnorm:
            receipt = {"original": original, "repaired": name, "confidence": 0.95, "method": "exact"}
            _append_receipt(receipt)
            return {"original": original, "repaired": name, "confidence": 0.95, "method": "exact", "receipt": receipt}

    # 2. Recent context boost (stigmergic)
    context = _recent_context()
    context_boost = {}
    for name in manifest_names:
        if _normalize(name) in context:
            context_boost[name] = 0.3

    # 3. Fuzzy (Damerau-Levenshtein)
    scored: List[Tuple[float, str]] = []
    for name in manifest_names:
        nnorm = _normalize(name)
        dist = _damerau_levenshtein(norm, nnorm)
        max_dist = max(1, min(3, len(nnorm) // 4))
        if dist <= max_dist:
            base_score = 1.0 - (dist / max(1, len(nnorm)))
            boost = context_boost.get(name, 0.0)
            score = base_score + boost
            scored.append((score, name))

    scored.sort(reverse=True)

    if not scored:
        receipt = {"original": original, "repaired": None, "confidence": 0.0, "method": "no_match"}
        _append_receipt(receipt)
        return {
            "original": original,
            "repaired": None,
            "confidence": 0.0,
            "candidates": [],
            "confirmation_text": f"I didn't catch that clearly. Did you want to open something specific?",
            "receipt": receipt,
        }

    best_score, best_name = scored[0]
    candidates = [name for score, name in scored[:3]]

    confidence = min(0.98, best_score)
    if confidence < 0.65:
        confirmation_text = f"I heard something like “{original}”. Did you mean “{best_name}”?"
    else:
        confirmation_text = f"I think you said “{best_name}”. Should I open that?"

    receipt = {
        "original": original,
        "repaired": best_name,
        "confidence": round(confidence, 3),
        "method": "fuzzy+context",
        "candidates": candidates,
    }
    _append_receipt(receipt)

    return {
        "original": original,
        "repaired": best_name,
        "confidence": round(confidence, 3),
        "candidates": candidates,
        "confirmation_text": confirmation_text,
        "receipt": receipt,
    }


# Tool wrapper for the router if we want Alice to be able to call repair explicitly
def repair_voice_command_tool(params: Dict[str, str]) -> Dict[str, Any]:
    return repair_voice_command(
        raw_text=params.get("raw_text", ""),
        intent=params.get("intent", "general")
    )
