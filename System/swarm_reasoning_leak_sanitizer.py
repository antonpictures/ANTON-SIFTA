#!/usr/bin/env python3
"""Strip model-internal reasoning scaffolds from Alice's visible speech.

This is not a style editor. It targets one failure class: a backend returns
draft/analysis text such as "1. Analyze the Context" as assistant content.
Those traces may be useful to a developer, but they are not Alice speaking.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, List


TRUTH_LABEL = "REASONING_LEAK_SANITIZER_EVENT_116"

_FINAL_MARKER_RE = re.compile(
    r"(?im)^\s*(?:final(?: answer)?|answer|response|reply)\s*:\s*"
)

_LEADING_STATUS_RE = re.compile(
    r"(?im)^\s*(?:thought|thinking|reasoning|analysis)\s+(?:for\s+)?\d+(?:\.\d+)?s\s*[:>]?.*$"
)

_INTERNAL_NUMBERED_RE = re.compile(
    r"(?im)^\s*(?:\d{1,2}[.)]\s*)?"
    r"(?:"
    r"analy[sz]e(?:\s+the)?\s+(?:context|input|request|statement)|"
    r"understand(?:ing)?\s+(?:the\s+)?(?:context|input|request|statement)|"
    r"identify(?:ing)?\s+(?:the\s+)?(?:intent|topic|user|request)|"
    r"determin(?:e|ing)\s+(?:the\s+)?(?:appropriate|best|response|answer|tone)|"
    r"assess(?:ing)?\s+(?:safety|policy|context|intent)|"
    r"formulat(?:e|ing)\s+(?:the\s+)?(?:response|answer|reply)|"
    r"draft(?:ing)?\s+(?:the\s+)?(?:response|answer|reply)|"
    r"construct(?:ing)?\s+(?:the\s+)?(?:response|answer|reply)|"
    r"generat(?:e|ing)\s+(?:the\s+)?(?:response|answer|reply)|"
    r"compos(?:e|ing)\s+(?:the\s+)?(?:response|answer|reply)"
    r")\b.*$"
)

_INTERNAL_PROSE_RE = re.compile(
    r"(?is)^\s*(?:"
    r"we\s+need\s+to\s+(?:answer|respond|analy[sz]e|determine)|"
    r"i\s+need\s+to\s+(?:answer|respond|analy[sz]e|determine)|"
    r"the\s+user\s+(?:is\s+asking|wants|provided)|"
    r"let'?s\s+(?:analy[sz]e|break\s+this\s+down|think\s+through)"
    r")\b"
)

_XML_THINK_RE = re.compile(
    r"(?is)<(?:thinking|thought|analysis|reasoning)\b[^>]*>.*?(?:</(?:thinking|thought|analysis|reasoning)>|$)"
)


@dataclass
class ReasoningLeakResult:
    text: str
    changed: bool
    rule_ids: List[str]
    original_chars: int
    final_chars: int
    truth_label: str = TRUTH_LABEL
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "truth_label": self.truth_label,
            "changed": self.changed,
            "rule_ids": list(self.rule_ids),
            "original_chars": self.original_chars,
            "final_chars": self.final_chars,
            "ts": self.ts,
        }


def _cut_to_final_marker(text: str) -> tuple[str, bool]:
    match = _FINAL_MARKER_RE.search(text)
    if not match:
        return text, False
    return text[match.end() :].strip(), True


def _leading_internal_line_count(text: str) -> int:
    count = 0
    for line in text.splitlines()[:8]:
        s = line.strip()
        if not s:
            continue
        if _INTERNAL_NUMBERED_RE.match(s):
            count += 1
            continue
        break
    return count


def is_probable_reasoning_stream_prefix(text: str) -> bool:
    """True while a stream prefix looks like internal reasoning, not speech."""
    s = (text or "").strip()
    if not s:
        return False
    if _FINAL_MARKER_RE.search(s):
        return False
    if _LEADING_STATUS_RE.match(s):
        return True
    if _INTERNAL_NUMBERED_RE.match(s):
        return True
    if _INTERNAL_PROSE_RE.match(s):
        return True
    return False


def sanitize_reasoning_leak(text: str) -> ReasoningLeakResult:
    original = text or ""
    out = original.strip()
    rules: List[str] = []
    if not out:
        return ReasoningLeakResult("", bool(original), ["empty"] if original else [], len(original), 0)

    stripped_xml = _XML_THINK_RE.sub("", out).strip()
    if stripped_xml != out:
        out = stripped_xml
        rules.append("reasoning_leak/xml_thinking_block")

    status_stripped = _LEADING_STATUS_RE.sub("", out).strip()
    if status_stripped != out:
        out = status_stripped
        rules.append("reasoning_leak/status_line")

    final_cut, cut = _cut_to_final_marker(out)
    if cut:
        out = final_cut
        rules.append("reasoning_leak/final_marker_cut")

    internal_lines = _leading_internal_line_count(out)
    if internal_lines >= 2 or (
        internal_lines == 1
        and len([ln for ln in out.splitlines() if ln.strip()]) <= 4
    ):
        out = ""
        rules.append("reasoning_leak/numbered_internal_scaffold")
    elif _INTERNAL_PROSE_RE.match(out):
        final_cut, cut = _cut_to_final_marker(out)
        out = final_cut if cut else ""
        rules.append("reasoning_leak/internal_prose")

    out = out.strip()
    return ReasoningLeakResult(
        text=out,
        changed=bool(rules) or out != original.strip(),
        rule_ids=rules,
        original_chars=len(original),
        final_chars=len(out),
    )


__all__ = [
    "TRUTH_LABEL",
    "ReasoningLeakResult",
    "is_probable_reasoning_stream_prefix",
    "sanitize_reasoning_leak",
]
