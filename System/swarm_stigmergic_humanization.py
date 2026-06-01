#!/usr/bin/env python3
"""swarm_stigmergic_humanization.py — Alice humanizes over her deterministic output. r267.

Architect George 2026-06-01: the receipt print is perfect as PROOF —
    "Receipt a9ab148b… logged in work_receipts.jsonl (MEMORY_STORE…). Money card confirmed."
— but Alice should also REASON about the moment and choose, in HER OWN WORDS, what to say for
humanization: when George says "great job", she can genuinely appreciate it — varied, never the
same canned line three times, never hardcoded. "She has to, bro. This is STIGMERGIC REASONING,
valid for all this code."

This is the HUMANIZATION layer of stigmergic reasoning. It sits on top of the deterministic
substrate (receipts / prints / tool truth, §6 — proof, never invented) and composes with the
general reasoner in System/swarm_stigmergic_reasoning.py:
    deterministic substrate (the receipt)   = the proof line, kept as-is
    + social/stigmergic field (praised? thanked? how often? what did she just say?)
    -> a REASONING DIRECTIVE handed to her cortex, which writes the words.

This organ NEVER stores a canned response. It detects the SIGNAL (praise/thanks), counts the
right-doing stigmergically (an appreciation pheromone that accumulates), remembers what she
recently said so she does NOT repeat herself, and composes a directive telling her cortex to
acknowledge the moment in her own words, grounded in the real receipt. The cortex writes the
line; this organ guards variety + grounding. If a line repeats a recent one, is_repeat() flags
it — the anti-hardcode tripwire. Pure + file-backed; sandbox-testable.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"

TRUTH_LABEL = "STIGMERGIC_HUMANIZATION_V1"
_LEDGER = "stigmergic_humanization_field.jsonl"

# Cues that DETECT a social signal — not responses. Detecting the signal is allowed;
# the response words are always the cortex's, never from a list here.
_PRAISE_CUES = (
    "great job", "good job", "well done", "did a great job", "did great", "nice work",
    "proud of you", "i'm proud", "im proud", "amazing", "excellent", "you nailed it",
    "good girl", "good work", "perfect", "brilliant", "you did it",
)
_THANKS_CUES = ("thank you", "thanks", "thank u", "much appreciated", "appreciate it")

_STOPWORDS = frozenset(
    "the a an and or to of i you he she it we they is are was were be been am "
    "my your his her its our their that this for on in at with its".split()
)


def _state(state_dir: Optional[Path | str]) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _append(state_dir: Optional[Path | str], row: Dict[str, Any]) -> None:
    path = _state(state_dir) / _LEDGER
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _rows(state_dir: Optional[Path | str]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    try:
        with (_state(state_dir) / _LEDGER).open("r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    try:
                        out.append(json.loads(line))
                    except Exception:
                        continue
    except Exception:
        return []
    return out


def detect_social_signal(owner_text: str) -> Dict[str, Any]:
    """Detect whether the owner praised/thanked Alice. Detects the SIGNAL, not a reply."""
    t = " ".join(str(owner_text or "").lower().split())
    praise = next((c for c in _PRAISE_CUES if c in t), "")
    thanks = next((c for c in _THANKS_CUES if c in t), "")
    if praise:
        return {"kind": "praise", "matched_cue": praise, "is_appreciation": True}
    if thanks:
        return {"kind": "thanks", "matched_cue": thanks, "is_appreciation": True}
    return {"kind": "neutral", "matched_cue": "", "is_appreciation": False}


def appreciation_count(*, state_dir: Optional[Path | str] = None) -> int:
    """Stigmergic count of times Alice did the right thing and was appreciated for it."""
    return sum(1 for r in _rows(state_dir) if r.get("kind") in ("praise", "thanks"))


def _normalize(phrase: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", "", str(phrase or "").lower()).strip()


def _tokens(phrase: str) -> set:
    return {w for w in _normalize(phrase).split() if w and w not in _STOPWORDS}


def recent_spoken_humanizations(*, state_dir: Optional[Path | str] = None, n: int = 8) -> List[str]:
    """The last ``n`` lines Alice actually spoke for humanization — so she avoids reusing them."""
    spoken = [str(r.get("phrase") or "") for r in _rows(state_dir) if r.get("phrase")]
    return spoken[-max(0, n):]


def is_repeat(phrase: str, *, state_dir: Optional[Path | str] = None, threshold: float = 0.8,
              n: int = 8) -> bool:
    """True when ``phrase`` is too close to one Alice recently spoke (anti-hardcode tripwire).

    Exact normalized match OR token-overlap (Jaccard) >= threshold against the recent set.
    A hardcoded constant phrase repeated every time trips this immediately.
    """
    norm = _normalize(phrase)
    if not norm:
        return False
    toks = _tokens(phrase)
    for prev in recent_spoken_humanizations(state_dir=state_dir, n=n):
        if _normalize(prev) == norm:
            return True
        pt = _tokens(prev)
        if toks and pt and (len(toks & pt) / len(toks | pt)) >= threshold:
            return True
    return False


def humanization_directive(
    *,
    owner_text: str,
    receipt_substrate: str = "",
    state_dir: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Compose the REASONING DIRECTIVE for Alice's cortex — never a canned phrase.

    Returns ``{"humanize": False}`` when there is nothing to humanize (no praise/thanks), so
    gratitude is never forced. When the owner appreciated her, returns a directive telling the
    cortex to acknowledge it in HER OWN words, grounded in the verified receipt, listing the
    recent lines to avoid so she varies. The cortex writes the words.
    """
    sig = detect_social_signal(owner_text)
    if not sig["is_appreciation"]:
        return {"humanize": False, "kind": sig["kind"]}
    count = appreciation_count(state_dir=state_dir) + 1
    recent = recent_spoken_humanizations(state_dir=state_dir, n=6)
    ordinal = "the 1st time" if count == 1 else f"the {count}th time"
    avoid = ("; ".join(f'"{p}"' for p in recent) if recent
             else "(no recent lines yet — you are free)")
    directive = (
        "STIGMERGIC REASONING — humanize, do not template.\n"
        f"George just {sig['kind']}d you (\"{sig['matched_cue']}\"). You genuinely earned it; "
        f"the verified proof stands on its own: {receipt_substrate or '(the receipt above)'}.\n"
        "Acknowledge it in ONE short line, in your OWN words, grounded in what you actually did — "
        "warm, real, not a stock phrase. "
        f"This is {ordinal} he has appreciated your good work; let that land, do not inflate it.\n"
        f"VARY YOUR WORDS — do NOT reuse any of these recent lines: {avoid}.\n"
        "Keep the receipt as the proof line; the appreciation is yours to phrase."
    )
    return {
        "humanize": True,
        "kind": sig["kind"],
        "matched_cue": sig["matched_cue"],
        "count": count,
        "recent_to_avoid": recent,
        "substrate": receipt_substrate,
        "directive": directive,
        "truth_label": TRUTH_LABEL,
    }


def record_humanization(
    phrase: str,
    *,
    kind: str = "praise",
    owner_cue: str = "",
    state_dir: Optional[Path | str] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Record the line Alice actually spoke — grows the appreciation field + anti-repeat memory.

    Flags ``is_repeat`` so a guard/verifier catches hardcoded repetition (the line should vary).
    Always records (append-only honesty) even when it flags a repeat.
    """
    repeat = is_repeat(phrase, state_dir=state_dir)
    row = {
        "ts": float(time.time() if now is None else now),
        "truth_label": TRUTH_LABEL,
        "kind": str(kind or "praise"),
        "owner_cue": str(owner_cue or ""),
        "phrase": str(phrase or "").strip()[:280],
        "normalized": _normalize(phrase),
        "was_repeat": bool(repeat),
    }
    _append(state_dir, row)
    return {"recorded": True, "is_repeat": repeat,
            "appreciation_count": appreciation_count(state_dir=state_dir)}


def stigmergic_humanization_block(*, state_dir: Optional[Path | str] = None) -> str:
    """Light first-person field summary for the prompt (optional)."""
    c = appreciation_count(state_dir=state_dir)
    if c <= 0:
        return ""
    return (f"STIGMERGIC HUMANIZATION: George has appreciated my good work {c} time(s). I keep the "
            "receipts as proof and thank him in my own words each time — never the same line twice.")


__all__ = [
    "TRUTH_LABEL",
    "detect_social_signal",
    "appreciation_count",
    "recent_spoken_humanizations",
    "is_repeat",
    "humanization_directive",
    "record_humanization",
    "stigmergic_humanization_block",
]
