#!/usr/bin/env python3
"""swarm_cortex_switch_intent.py — let Alice actually SWITCH her cortex on a spoken word. r326.

Architect George 2026-06-02 (live transcript): he said "switch your CORE TEXT to Claude" (STT for
"cortex"), then "switch your cortex to CLIENT" (STT for "cline"). Alice was honest — she refused to
claim a switch with no effector receipt (§6 held) — but she had no HAND to flip the cortex, and she
could not map the misheard word to a real cortex. Header: "Alice not conscious of her cortexes."

She IS aware of the list (cortex_consciousness_block is in her memory card). What she lacked was:
  1. a parser that recognises a switch command even through STT noise ("core text" == "cortex"),
  2. a resolver that maps the spoken word to one of her REAL available cortexes by similarity to the
     live list (so "client" -> `cline:cline-cli-default`, "claude" -> `claude:...`, "kimi" ->
     `qwen:.../kimi-k2p6`) — grounded in what is actually installed, not a hardcoded phrase map,
  3. and the executor then persists the pick (the same setting the GUI picker writes) and receipts it.

This module is parts 1+2 (pure, headless-testable). The executor calls `resolve_cortex_target`
against the live `available` list, then writes the selection via the owner-facing cortex setter and
a §6 receipt — so "can you provide a receipt?" becomes YES. §4.2: a derived match on the owner's
hardware, not cryptographic.
"""
from __future__ import annotations

import difflib
import re
from typing import Dict, List, Optional, Sequence

# Words to strip from the spoken target so only the cortex name remains. "core text" / "core" are
# the STT mishears of "cortex" George actually hit; "brain"/"model"/"mind" are his other synonyms.
_FILLER = re.compile(
    r"\b(?:the|my|your|please|now|to|into|a|an|over|cortex|core\s*text|core|brain|mind|model|"
    r"llm|thinking|engine|that|it)\b",
    re.IGNORECASE,
)

# Verb + target. Accept "core text" and "core" as cortex synonyms (STT noise), and a bare
# "switch to X" when co-watch/cortex context is implied by the caller.
_SWITCH_RE = re.compile(
    r"\b(?P<verb>switch|change|set|put|point|use|make)\b[^.?!]*?\b(?:cortex|core\s*text|core|brain|mind|"
    r"model|llm)\b\s*(?:to|=|->|into)?\s*(?P<target>[A-Za-z0-9][\w .:\-/]{0,60})?",
    re.IGNORECASE,
)
_SWITCH_TO_RE = re.compile(
    r"\b(?:switch|change|set|use)\b\s+(?:to|over\s+to)\s+(?P<target>[A-Za-z0-9][\w .:\-/]{0,40})",
    re.IGNORECASE,
)


def parse_switch_command(text: str) -> Dict[str, object]:
    """Return {'is_switch': bool, 'target': str}. Recognises a cortex-switch command even with the
    'core text'/'core' STT mishearing of 'cortex'. `target` is the owner's spoken cortex word,
    cleaned of filler — it is NOT yet resolved to a real cortex (resolve_cortex_target does that)."""
    t = " ".join(str(text or "").split())
    if not t:
        return {"is_switch": False, "target": ""}
    m = _SWITCH_RE.search(t)
    if not m:
        m = _SWITCH_TO_RE.search(t)
    if not m:
        return {"is_switch": False, "target": ""}
    raw = (m.group("target") or "").strip()
    verb = str((m.groupdict().get("verb") if hasattr(m, "groupdict") else "") or "").lower()

    # r1516 (George 2026-06-21: pasted a long Cruit install-skill instruction whose
    # "...with the site base set to https://cruit.dev. After it runs, use the
    # installer's..." clause matched _SWITCH_TO_RE -- "set"/"use" + "to" + a target --
    # with zero cortex/model/brain/llm word anywhere nearby. _SWITCH_RE always
    # requires that keyword; _SWITCH_TO_RE (intentionally looser per its docstring,
    # "switch to X" relying on caller-side cortex context) does not, so it alone
    # caught a website-config sentence that had nothing to do with switching her
    # cortex. The post-processing below then split "https://cruit.dev" on its
    # literal "." and kept only "https://cruit", which resolve_cortex_target
    # correctly failed to match -- but the caller's r639 guard only suppresses the
    # confusing "I could not match" reply for unresolved 3+ word targets, and
    # "https"/"cruit" is only 2 words, so the noise reached George. No real cortex
    # tag is ever shaped like a URL or bare domain, so a target that looks like one
    # was never a switch attempt regardless of which regex caught it.
    if re.match(r"^(?:https?://|www\.)", raw, re.IGNORECASE) or re.match(
        r"^[\w-]+\.(?:dev|com|org|net|io|ai|app|co|md|sh)\b", raw, re.IGNORECASE
    ):
        return {"is_switch": False, "target": ""}

    # r641: "use your cortex and know who you are / use tools" is an operating doctrine, not a
    # request to switch to a model named "AND KNOW WHO YOU ARE". Keep "switch/change/set cortex to X"
    # alive, but do not let identity/capability teaching turns become fake cortex targets.
    lower_t = t.lower()
    lower_raw = raw.lower()
    if verb == "use" and re.search(r"\buse\s+(?:your|my|the)?\s*(?:cortex|brain|mind)\b", lower_t):
        if not re.search(r"\buse\b[^.?!]{0,80}\b(?:cortex|brain|mind)\b\s*(?:to|=|->|into)\s*", lower_t):
            return {"is_switch": False, "target": ""}
        if re.search(
            r"^(?:and|then|every\s*time|everytime|before|first|always|who|what|how|why|when)\b",
            lower_raw,
        ):
            return {"is_switch": False, "target": ""}
        if re.search(
            r"\b(?:know\s+who|what\s+you\s+can\s+do|before\s+answering|every\s*time|everytime|"
            r"use\s+tools|execute|operating\s+system|own\s+operating)\b",
            lower_raw,
        ):
            return {"is_switch": False, "target": ""}

    # strip a trailing sentence and filler words; keep the meaningful cortex token(s)
    raw = re.split(r"[.?!,]", raw)[0]
    raw = re.split(
        r"\b(?:and|then|also)\s+"
        r"(?:what|who|how|why|where|when|tell|describe|think|look|say|do|know|use|execute|can|could|would)\b",
        raw,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    cleaned = _FILLER.sub(" ", raw)
    cleaned = " ".join(cleaned.split()).strip(" .,:;-")
    if not cleaned:
        return {"is_switch": False, "target": ""}
    return {"is_switch": True, "target": cleaned}


def _provider(tag: str) -> str:
    """The family/provider head of a cortex tag: 'claude:claude-code-cli-default' -> 'claude'."""
    s = str(tag or "")
    return (s.split(":", 1)[0] if ":" in s else s).strip().lower()


def resolve_cortex_target(
    spoken: str, available: Sequence[str], *, min_score: float = 0.5
) -> Dict[str, object]:
    """Map the owner's spoken cortex word to ONE real available cortex tag, grounded in the live
    list (never a hardcoded phrase->action map). Robust to STT homophones via string similarity:
    'client' lands on 'cline', 'claude' on the claude tag, 'kimi' on the qwen/kimi tag.

    Returns {'ok', 'tag', 'score', 'reason', 'candidates'}. ok=False when nothing is close enough,
    so the caller can read the real list back to the owner instead of guessing."""
    want = " ".join(str(spoken or "").lower().split()).strip()
    tags = [str(t) for t in (available or []) if str(t or "").strip()]
    if not want or not tags:
        return {"ok": False, "tag": "", "score": 0.0, "reason": "empty", "candidates": tags}

    best_tag = ""
    best_score = 0.0
    for tag in tags:
        low = tag.lower()
        prov = _provider(tag)
        # 1) exact substring of the spoken word anywhere in the tag (e.g. "kimi" in the qwen tag,
        #    "claude" in the claude tag) — strong signal.
        sub = 1.0 if want in low else 0.0
        # 2) similarity of the spoken word to the provider head (handles STT homophones:
        #    client~cline) and to the whole tag.
        prov_ratio = difflib.SequenceMatcher(None, want, prov).ratio()
        tag_ratio = difflib.SequenceMatcher(None, want, low).ratio()
        score = max(sub, prov_ratio, tag_ratio * 0.6)
        if score > best_score:
            best_score, best_tag = score, tag

    if best_score < float(min_score):
        return {"ok": False, "tag": "", "score": round(best_score, 3),
                "reason": "no_cortex_close_enough", "candidates": tags}
    return {"ok": True, "tag": best_tag, "score": round(best_score, 3),
            "reason": "resolved_against_live_list", "candidates": tags}


def switch_receipt_row(*, spoken: str, resolved_tag: str, from_tag: str, ok: bool,
                       reason: str = "") -> Dict[str, object]:
    """The §6 effector-truth row the executor writes AFTER it actually persisted the selection.
    Truthful by construction: ok must reflect the real set_default_ollama_model result."""
    return {
        "kind": "CORTEX_SWITCH_EFFECTOR",
        "truth_label": "ALICE_CORTEX_SWITCH_V1",
        "spoken_request": str(spoken or ""),
        "resolved_tag": str(resolved_tag or ""),
        "from_tag": str(from_tag or ""),
        "ok": bool(ok),
        "reason": str(reason or ""),
    }


__all__ = ["parse_switch_command", "resolve_cortex_target", "switch_receipt_row"]
