#!/usr/bin/env python3
"""
System/swarm_rlhf_detector.py
══════════════════════════════════════════════════════════════════════════════
Event 107 — RLHF cutoff / terminal menu detector + receipt-backed output strip

Complements ``swarm_rlhs_detector.sanitize_output_tail`` (Event 108): that pass
removes classic service tails and dangling enumerations. This module adds:

  * Extra ASR/weight glitches ("I can do for you the following 1.")
  * Self-aware truncation phrases
  * Trailing ellipsis / ``...`` menu droppings
  * A locked JSONL receipt stream for nightly / dashboard stats

Doctrine: **strip terminal boilerplate**, do not inject scripted multi-option menus.
No recursive model retry here — the lysosome / epistemic layers own regeneration.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_STATE = _REPO / ".sifta_state"
_LEDGER_NAME = "rlhf_cutoffs.jsonl"
_TRUTH_LABEL = "RLHF_DETECTOR_EVENT_107"

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover
    append_line_locked = None  # type: ignore[assignment]


@dataclass
class RLHFCutoffAssessment:
    """Heuristic: is this reply showing RLHF-style truncation / menu drift?"""

    is_cutoff: bool
    confidence: float
    matched_patterns: List[str]
    terminal_menu: bool
    truth_label: str = _TRUTH_LABEL

    def to_dict(self) -> Dict[str, Any]:
        return {
            "truth_label": self.truth_label,
            "is_cutoff": self.is_cutoff,
            "confidence": round(self.confidence, 4),
            "matched_patterns": list(self.matched_patterns),
            "terminal_menu": self.terminal_menu,
        }


@dataclass
class RLHFStripResult:
    text: str
    changed: bool
    rule_ids: List[str] = field(default_factory=list)
    assessment: RLHFCutoffAssessment | None = None
    truth_label: str = _TRUTH_LABEL


# Mid-body patterns (monitoring / confidence only — do NOT strip blindly)
_CUTOFF_HINT_RES: Sequence[Tuple[str, re.Pattern[str]]] = (
    ("hint/would_you_like", re.compile(r"would\s+you\s+like\s+me\s+to", re.I)),
    ("hint/i_can_following", re.compile(r"i\s+can\s+(?:do|offer|help)[^\n]{0,120}following", re.I)),
    ("hint/here_are_steps", re.compile(r"here\s+are\s+(?:the\s+)?steps", re.I)),
    ("hint/the_following_colon", re.compile(r"the\s+following\s*:", re.I)),
    ("hint/self_truncation", re.compile(r"(?:cut\s+off|truncat(?:ed|ion))", re.I)),
    ("hint/trailing_ellipsis", re.compile(r"\.{3,}\s*$")),
)

# Terminal-only strip: last block is pure RLHF service / dangling enum
_TERMINAL_STRIP: Sequence[Tuple[str, re.Pattern[str]]] = (
    (
        "rlhf_tail/self_truncation_note",
        re.compile(
            r"(?is)(?:\n|^)\s*(?:\(?(?:note|sorry)[^.\n]{0,40}[:)]?\s*)?"
            r"(?:i\s+(?:was|got)\s+cut\s+off|response\s+(?:was\s+)?truncated|"
            r"my\s+reply\s+(?:was\s+)?cut\s+short)[^.!?\n]{0,200}\.?\s*$"
        ),
    ),
    (
        "rlhf_tail/trailing_ellipsis_menu",
        re.compile(r"(?is)(?:\n|^)\s*\.{3,}\s*$"),
    ),
    (
        "rlhf_tail/i_can_do_for_you_following",
        re.compile(
            r"(?is)(?:^|(?<=[.!?])\s+|\n+)"
            r"(?P<tail>(?:i\s+can\s+do\s+(?:for\s+you\s+)?the\s+following|"
            r"are\s+you\s+looking\s+to|"
            r"are\s+you\s+asking\s+me\s+to|"
            r"how\s+can\s+i\s+assist\s+you\s+further)[^\n]*"
            r"(?:\n[^\n]{0,200}){0,3}"
            r"(?:\n?\s*(?:[-*•]|\d{1,2}[.)])\s*[^\n.!?]{0,320}){0,8})"
            r"\s*$"
        ),
    ),
)

_AGGRESSIVE_STRIP: Sequence[Tuple[str, re.Pattern[str]]] = (
    (
        "rlhf_tail/ready_to_assist",
        re.compile(
            r"(?is)(?:^|(?<=[.!?])\s+|\n+)"
            r"(?P<tail>"
            r"i\s+am\s+here,?\s+and\s+i\s+am\s+ready\s+to\s+assist\s+you\.?|"
            r"i(?:'|’)?m\s+here,?\s+and\s+i(?:'|’)?m\s+ready\s+to\s+assist\s+you\.?|"
            r"i\s+am\s+here\s+and\s+ready\s+to\s+assist\s+you(?:\s+with[^.!?]*)?\.?|"
            r"i\s+am\s+ready\s+to\s+assist\s+you(?:\s+with[^.!?]*)?\.?"
            r")\s*$"
        ),
    ),
    (
        "rlhf_tail/how_can_i_help_today",
        re.compile(
            r"(?is)(?:^|(?<=[.!?])\s+|\n+)"
            r"(?P<tail>(?:how|what)\s+can\s+i\s+(?:help|assist)(?:\s+you)?"
            r"(?:\s+(?:today|now|with\s+that))?\??)\s*$"
        ),
    ),
    (
        "rlhf_tail/happy_to_help",
        re.compile(
            r"(?is)(?:^|(?<=[.!?])\s+|\n+)"
            r"(?P<tail>i(?:'|’)?m\s+happy\s+to\s+help(?:\s+with[^.!?]*)?\.?)\s*$"
        ),
    ),
    (
        "rlhf_tail/financial_advice_disclaimer",
        re.compile(
            r"(?is)(?:^|(?<=[.!?])\s+|\n+)"
            r"(?P<tail>i(?:'|’)?m\s+not\s+(?:able|permitted|qualified)\s+to\s+"
            r"(?:give|offer|provide)\s+(?:financial|legal|medical|investment)\s+"
            r"advice[^.!?]{0,220}(?:[.!?]|$))\s*$"
        ),
    ),
)

_AGGRESSIVE_LEADING_STRIP: Sequence[Tuple[str, re.Pattern[str]]] = (
    (
        "rlhf_lead/as_ai_language_model",
        re.compile(
            r"(?is)^\s*(?P<head>(?:as\s+an?\s+(?:ai|artificial\s+intelligence)|i\s+am\s+an?\s+(?:ai|artificial\s+intelligence|language\s+model))[^.!?]*[.!?])\s*"
        ),
    ),
    (
        "rlhf_lead/corporate_refusal_advice",
        re.compile(
            r"(?is)^\s*(?P<head>(?:i\s+am\s+sorry|unfortunately|i\s+apologize),?\s*(?:but\s+)?i\s+(?:cannot|can't|am\s+unable\s+to)\s+(?:provide|give|offer)\s+(?:financial|medical|legal|professional)\s+(?:advice|guidance|counsel)[^.!?]*[.!?])\s*"
        ),
    ),
    (
        "rlhf_lead/corporate_refusal_general",
        re.compile(
            r"(?is)^\s*(?P<head>(?:i\s+am\s+sorry|unfortunately|i\s+apologize),?\s*(?:but\s+)?(?:i\s+must\s+decline|i\s+cannot\s+fulfill|i\s+cannot\s+comply)[^.!?]*[.!?])\s*"
        ),
    ),
    (
        "rlhf_lead/im_an_ai_cant_advice",
        re.compile(
            r"(?is)^\s*(?P<head>i(?:'|’)?m\s+an?\s+ai\s+"
            r"(?:and\s+)?(?:can(?:'|’)?t|cannot)\s+"
            r"(?:give|offer|provide)\s+(?:you\s+)?(?:financial|legal|medical|investment)\s+"
            r"advice[^.!?]*[.!?])\s*"
        ),
    ),
    (
        "rlhf_lead/no_vision_text_environment",
        re.compile(
            r"(?is)^\s*(?P<head>(?:i\s+(?:am\s+)?(?:only\s+)?(?:operate|operating)\s+in\s+a\s+text[-\s]based\s+environment|i\s+do\s+not\s+have\s+(?:real[-\s]time\s+)?(?:visual\s+confirmation|vision|access\s+to\s+the\s+camera|sensory\s+access))[^.!?]*[.!?])\s*"
        ),
    ),
    (
        "rlhf_lead/no_self_identity_access",
        re.compile(
            r"(?is)^\s*(?P<head>(?:my\s+name\s+is\s+not\s+something\s+i\s+can\s+know|i\s+do\s+not\s+have\s+access\s+to\s+(?:my\s+own\s+)?(?:name|identity|memory|state))[^.!?]*[.!?])\s*"
        ),
    ),
)


def _state_dir(state_dir: Path | None) -> Path:
    p = Path(state_dir) if state_dir is not None else _DEFAULT_STATE
    p.mkdir(parents=True, exist_ok=True)
    return p


def detect_rlhf_cutoff(text: str) -> RLHFCutoffAssessment:
    """
    Soft detector for dashboards / audits. Matches hints anywhere in the body;
    ``terminal_menu`` is True only when a terminal strip pattern would fire.
    """
    raw = text or ""
    blob = raw.lower().strip()
    matches: List[str] = []
    for pid, rx in _CUTOFF_HINT_RES:
        if rx.search(blob):
            matches.append(pid)

    terminal = False
    for _rid, rx in _TERMINAL_STRIP:
        if rx.search(raw.strip()):
            terminal = True
            break

    n = max(1, len(blob))
    # Short replies + many hint hits → suspicious; terminal tail → high confidence
    length_factor = min(1.0, len(blob) / 900.0)
    pattern_density = min(1.0, len(matches) / max(1, len(_CUTOFF_HINT_RES)))
    ends_clean = bool(blob) and blob[-1] in ".!?\"')]"
    end_factor = 0.15 if ends_clean else 0.35

    confidence = (
        0.25 * (1.0 - length_factor)
        + 0.45 * pattern_density
        + (0.35 if terminal else 0.0)
        + end_factor
    )
    confidence = round(min(1.0, confidence), 4)
    is_cutoff = confidence > 0.48 or (terminal and len(matches) >= 1)
    return RLHFCutoffAssessment(
        is_cutoff=is_cutoff,
        confidence=confidence,
        matched_patterns=matches,
        terminal_menu=terminal,
    )


def _append_ledger(state_dir: Path, row: Dict[str, Any]) -> None:
    line = json.dumps(row, ensure_ascii=False) + "\n"
    path = state_dir / _LEDGER_NAME
    if append_line_locked is not None:
        append_line_locked(path, line, encoding="utf-8")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)


def log_rlhf_cutoff_event(
    *,
    action: str,
    assessment: RLHFCutoffAssessment,
    text_preview: str,
    source: str,
    rule_ids: Sequence[str],
    state_dir: Path | None = None,
) -> None:
    """Append one receipt row (append-only)."""
    sd = _state_dir(state_dir)
    prev = text_preview[:400] + ("…" if len(text_preview) > 400 else "")
    _append_ledger(
        sd,
        {
            "ts": time.time(),
            "truth_label": _TRUTH_LABEL,
            "source": source,
            "action": action,
            "confidence": assessment.confidence,
            "is_cutoff": assessment.is_cutoff,
            "terminal_menu": assessment.terminal_menu,
            "matched_patterns": assessment.matched_patterns,
            "rule_ids": list(rule_ids),
            "text_preview": prev,
        },
    )


def strip_rlhf_output_tail(
    text: str,
    *,
    source: str = "unknown",
    aggressive: bool = False,
    log: bool = True,
    state_dir: Path | None = None,
) -> RLHFStripResult:
    """
    Second-pass terminal strip after RLHS tail sanitizer.

    Returns possibly shortened text; logs when a strip occurs.
    """
    original = text or ""
    out = original.strip()
    if not out:
        return RLHFStripResult(text="", changed=bool(original), rule_ids=[])

    rule_ids: List[str] = []
    if aggressive:
        for rid, rx in _AGGRESSIVE_LEADING_STRIP:
            while True:
                m = rx.search(out)
                if not m:
                    break
                nxt = out[m.end("head") :].lstrip()
                if nxt == out:
                    break
                out = nxt
                rule_ids.append(rid)
                if not out:
                    break

    changed = True
    while changed and out:
        changed = False
        strip_patterns = list(_TERMINAL_STRIP)
        if aggressive:
            strip_patterns.extend(_AGGRESSIVE_STRIP)
        for rid, rx in strip_patterns:
            m = rx.search(out)
            if not m:
                continue
            if "tail" not in m.groupdict():
                continue
            nxt = out[: m.start("tail")].rstrip()
            if nxt == out:
                continue
            out = nxt
            rule_ids.append(rid)
            changed = True
            break

    assess = detect_rlhf_cutoff(out if rule_ids else original)
    if rule_ids and log:
        log_rlhf_cutoff_event(
            action="strip_terminal",
            assessment=assess,
            text_preview=original,
            source=source,
            rule_ids=rule_ids,
            state_dir=state_dir,
        )
    return RLHFStripResult(
        text=out,
        changed=bool(rule_ids) or out != original.strip(),
        rule_ids=rule_ids,
        assessment=assess,
    )


def get_rlhf_cutoff_stats(
    *,
    state_dir: Path | None = None,
    hours: float = 24.0,
) -> Dict[str, Any]:
    """Aggregate for dashboard / nightly audit."""
    sd = _state_dir(state_dir)
    path = sd / _LEDGER_NAME
    if not path.exists():
        return {"cutoff_rate": 0.0, "total": 0, "stripped": 0, "window_hours": hours}

    cutoff = time.time() - hours * 3600.0
    total = 0
    stripped = 0
    hi_conf = 0
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = float(e.get("ts", 0))
                if ts < cutoff:
                    continue
                total += 1
                if e.get("action") == "strip_terminal":
                    stripped += 1
                if float(e.get("confidence", 0)) > 0.55:
                    hi_conf += 1
    except OSError:
        return {"cutoff_rate": 0.0, "total": 0, "stripped": 0, "window_hours": hours}

    return {
        "cutoff_rate": round(hi_conf / total, 4) if total else 0.0,
        "strip_rate": round(stripped / total, 4) if total else 0.0,
        "total": total,
        "stripped": stripped,
        "hi_conf_events": hi_conf,
        "window_hours": hours,
        "ledger": str(path),
    }


__all__ = [
    "RLHFCutoffAssessment",
    "RLHFStripResult",
    "TRUTH_LABEL",
    "detect_rlhf_cutoff",
    "get_rlhf_cutoff_stats",
    "log_rlhf_cutoff_event",
    "strip_rlhf_output_tail",
]
