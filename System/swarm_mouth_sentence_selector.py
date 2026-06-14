#!/usr/bin/env python3
"""Select what Alice speaks from a longer printed reply.

The chat/text lane keeps the exact cortex answer, receipts, and proof. The
mouth lane should sound like a person in the room: one or two strong sentences
from Alice's own reply, not generated boilerplate and not raw receipt metadata.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE_DIR = REPO_ROOT / ".sifta_state"
LEDGER_NAME = "mouth_sentence_selector.jsonl"
TRUTH_LABEL = "MOUTH_SENTENCE_SELECTOR_V1"

_FULL_ALOUD_RE = re.compile(
    r"\b(?:read|speak|say)\b.{0,80}\b(?:all|whole|entire|full)\b"
    r".{0,80}\b(?:answer|reply|response|thing|message)\b.{0,40}\b(?:out\s+loud|aloud|to\s+me)?\b|"
    r"\b(?:read|speak|say)\b.{0,80}\b(?:answer|reply|response|message)\b"
    r".{0,80}\b(?:all|whole|entire|full)\b",
    re.IGNORECASE,
)
_NEGATED_RE = re.compile(r"\b(?:don'?t|do\s+not|not|never|please\s+don'?t)\b", re.IGNORECASE)
_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_BRACKET_RECEIPTS_RE = re.compile(r"\[receipts?:[^\]]+\]", re.IGNORECASE)
_MARKDOWN_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
_MARKDOWN_ITALIC_RE = re.compile(r"\*([^*]+)\*")
_URL_RE = re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)
_UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE)
_HEXISH_RE = re.compile(r"\b[0-9a-f]{12,}\b", re.IGNORECASE)
_PATH_RE = re.compile(r"(?:^|\s)(?:/Users/|\.sifta_state/|System/|Applications/|Documents/|tests/|tools/)\S+")
_COMMAND_RE = re.compile(r"\b(?:python3|pytest|py_compile|tail|rg|sed|cat|sudo|bash)\b")
_RECEIPT_WORD_RE = re.compile(
    r"\b(?:receipt|receipt_id|trace_id|work_receipts|jsonl|pytest|verification|files touched|"
    r"sensor_tier|truth_label|compile|passed|failed)\b",
    re.IGNORECASE,
)
_LIST_OR_HEADER_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)]|#{1,6}\s+|[A-Z][A-Z0-9 _/-]{8,}:)")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _state_dir(path: Optional[Path | str] = None) -> Path:
    if path is None:
        return DEFAULT_STATE_DIR
    p = Path(path).expanduser()
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def owner_requested_full_aloud(owner_text: str) -> bool:
    text = str(owner_text or "")
    match = _FULL_ALOUD_RE.search(text)
    if not match:
        return False
    window = text[max(0, match.start() - 40) : match.end() + 20]
    return not _NEGATED_RE.search(window)


def _owner_requested_receipt_aloud(owner_text: str) -> bool:
    try:
        from System.swarm_spoken_channel_filter import owner_requested_receipt_aloud

        return bool(owner_requested_receipt_aloud(owner_text))
    except Exception:
        return False


def _normalize_text(text: str) -> str:
    out = _FENCE_RE.sub(" ", str(text or ""))
    out = _BRACKET_RECEIPTS_RE.sub(" ", out)
    out = _MARKDOWN_BOLD_RE.sub(r"\1", out)
    out = _MARKDOWN_ITALIC_RE.sub(r"\1", out)
    out = out.replace("`", "")
    out = re.sub(r"\s+", " ", out)
    return out.strip()


def _sentences(text: str) -> List[str]:
    normalized = _normalize_text(text)
    if not normalized:
        return []
    chunks = _SENTENCE_SPLIT_RE.split(normalized)
    out: List[str] = []
    for chunk in chunks:
        sentence = chunk.strip()
        if not sentence:
            continue
        if len(sentence) > 280:
            # Split long proof paragraphs at soft boundaries before scoring.
            parts = re.split(r"\s+(?:--|—|;)\s+|\s+-\s+", sentence)
            out.extend(p.strip() for p in parts if p.strip())
        else:
            out.append(sentence)
    return out


def _proof_noise_score(sentence: str) -> int:
    score = 0
    if _URL_RE.search(sentence):
        score += 6
    if _UUID_RE.search(sentence) or _HEXISH_RE.search(sentence):
        score += 5
    if _PATH_RE.search(sentence):
        score += 5
    if _COMMAND_RE.search(sentence):
        score += 3
    if _RECEIPT_WORD_RE.search(sentence):
        score += 4
    if _LIST_OR_HEADER_RE.search(sentence):
        score += 2
    if "{" in sentence or "}" in sentence or "=>" in sentence:
        score += 3
    return score


def _sentence_score(sentence: str, index: int, total: int) -> float:
    text = sentence.strip()
    words = re.findall(r"[A-Za-z']+", text)
    word_count = len(words)
    score = 0.0

    if 7 <= word_count <= 32:
        score += 4.0
    elif 4 <= word_count <= 45:
        score += 1.5
    else:
        score -= 3.0

    if 45 <= len(text) <= 210:
        score += 2.0
    elif len(text) > 260:
        score -= 3.0

    low = text.lower()
    if re.search(r"\b(?:i|you|we|your|my|our)\b", low):
        score += 1.5
    if re.search(r"\b(?:i can|i will|i'm|i am|we can|you are|you asked|this means|that means)\b", low):
        score += 1.0
    if text.endswith(("!", "?")):
        score += 0.5
    if index == 0 and total > 3 and re.match(r"^(?:sure|okay|got it|understood|yes)[,. ]", low):
        score -= 1.0

    noise = _proof_noise_score(text)
    score -= float(noise * 2)
    if noise and word_count < 12:
        score -= 2.0
    return score


def _pick(sentences: List[str], max_sentences: int) -> Tuple[List[int], List[Tuple[int, str, float]]]:
    scored = [(i, s, _sentence_score(s, i, len(sentences))) for i, s in enumerate(sentences)]
    candidates = [item for item in scored if item[2] >= 4.0 and _proof_noise_score(item[1]) <= 1]
    candidates.sort(key=lambda item: (-item[2], item[0]))
    chosen = sorted(i for i, _s, _score in candidates[: max(1, max_sentences)])
    return chosen, scored


def select_mouth_sentences(
    printed_text: str,
    *,
    owner_text: str = "",
    state_dir: Optional[Path | str] = None,
    now: Optional[float] = None,
    source: str = "talk_tts_boundary",
    max_sentences: int = 2,
    min_chars_to_select: int = 260,
) -> Dict[str, Any]:
    """Return the content-derived speech text for Alice's mouth.

    The selector never mutates the printed reply. It only shortens spoken text
    when there are more than two candidate sentences and George did not ask for
    the whole answer or receipts out loud.
    """
    printed = str(printed_text or "")
    if not printed.strip():
        return {"ok": False, "spoken_text": "", "changed": False, "reason": "empty"}
    if owner_requested_full_aloud(owner_text):
        return {"ok": True, "spoken_text": printed, "changed": False, "reason": "owner_requested_full_aloud"}
    if _owner_requested_receipt_aloud(owner_text):
        return {"ok": True, "spoken_text": printed, "changed": False, "reason": "owner_requested_receipt_aloud"}
    if len(printed) < min_chars_to_select:
        return {"ok": True, "spoken_text": printed, "changed": False, "reason": "short_enough"}

    sentence_list = _sentences(printed)
    if len(sentence_list) <= max_sentences:
        return {"ok": True, "spoken_text": _normalize_text(printed), "changed": False, "reason": "few_sentences"}

    chosen, scored = _pick(sentence_list, max_sentences=max_sentences)
    if not chosen:
        return {"ok": True, "spoken_text": _normalize_text(printed), "changed": False, "reason": "no_human_sentence_candidate"}

    spoken = " ".join(sentence_list[i].strip() for i in chosen).strip()
    changed = spoken != _normalize_text(printed)
    row = {
        "ts": float(now if now is not None else time.time()),
        "truth_label": TRUTH_LABEL,
        "source": source,
        "changed": bool(changed),
        "selected_indices": chosen,
        "sentence_count": len(sentence_list),
        "printed_sha16": hashlib.sha256(printed.encode("utf-8", errors="ignore")).hexdigest()[:16],
        "spoken_sha16": hashlib.sha256(spoken.encode("utf-8", errors="ignore")).hexdigest()[:16],
        "spoken_preview": spoken[:220],
        "print_text_unchanged": True,
        "reason": "selected_human_sentences" if changed else "unchanged_after_selection",
        "scores": [
            {"i": i, "score": round(score, 3), "proof_noise": _proof_noise_score(sentence)}
            for i, sentence, score in scored[:24]
        ],
    }
    try:
        base = _state_dir(state_dir)
        base.mkdir(parents=True, exist_ok=True)
        with (base / LEDGER_NAME).open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass

    try:
        from System.swarm_speech_lane_selector import select_spoken_sentences

        lane = select_spoken_sentences(
            spoken,
            owner_text=owner_text,
            state_dir=state_dir,
            source=source,
        )
        if lane.get("ok") and lane.get("spoken_text"):
            spoken = str(lane["spoken_text"])
            changed = spoken != _normalize_text(printed)
    except Exception:
        pass

    return {
        "ok": True,
        "spoken_text": spoken,
        "changed": bool(changed),
        "selected_indices": chosen,
        "sentence_count": len(sentence_list),
        "print_text_unchanged": True,
        "reason": row["reason"],
        "ledger_name": LEDGER_NAME,
    }


__all__ = [
    "LEDGER_NAME",
    "TRUTH_LABEL",
    "owner_requested_full_aloud",
    "select_mouth_sentences",
]
