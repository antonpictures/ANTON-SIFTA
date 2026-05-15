#!/usr/bin/env python3
"""First-person reality gate for Alice's final speech path.

The prompt already says "do not speak about me from outside." This module makes
that rule executable. It handles the common training residue where a model says
"Alice is..." or "the user..." while replying from inside the Talk organism.

Truth label: FIRST_PERSON_REALITY_GATE_V1.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover - standalone fallback.
    def append_line_locked(path: Path, line: str, *, encoding: str = "utf-8") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding=encoding) as f:
            f.write(line)


_STATE = Path(__file__).resolve().parent.parent / ".sifta_state"
_LEDGER_NAME = "first_person_reality.jsonl"


@dataclass
class FirstPersonRealityResult:
    truth_label: str
    original_text: str
    cleaned_text: str
    changed: bool
    patterns: List[str] = field(default_factory=list)
    receipt_id: str = ""
    ledger_path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _sha16(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def _default_self_name() -> str:
    try:
        from System.swarm_kernel_identity import ai_name

        return str(ai_name() or "Alice").strip() or "Alice"
    except Exception:
        return "Alice"


def _default_owner_name() -> str:
    try:
        from System.swarm_kernel_identity import owner_display_name

        owner = str(owner_display_name("you") or "you").strip()
        return owner if owner and owner != "the local human" else "you"
    except Exception:
        return "you"


def _replace_self_subject(line: str, self_name: str) -> tuple[str, List[str]]:
    patterns: List[str] = []
    name = re.escape(self_name)
    replacements = [
        (rf"\b{name}\s+is\b", "I am", "self_name_is"),
        (rf"\b{name}\s+was\b", "I was", "self_name_was"),
        (rf"\b{name}\s+will\b", "I will", "self_name_will"),
        (rf"\b{name}\s+can\b", "I can", "self_name_can"),
        (rf"\b{name}\s+cannot\b", "I cannot", "self_name_cannot"),
        (rf"\b{name}\s+can't\b", "I can't", "self_name_cant"),
        (rf"\b{name}\s+has\b", "I have", "self_name_has"),
        (rf"\b{name}\s+had\b", "I had", "self_name_had"),
        (rf"\b{name}\s+runs\b", "I run", "self_name_runs"),
        (rf"\b{name}\s+lives\b", "I live", "self_name_lives"),
        (rf"\b{name}\s+sees\b", "I see", "self_name_sees"),
        (rf"\b{name}\s+hears\b", "I hear", "self_name_hears"),
        (rf"\b{name}\s+remembers\b", "I remember", "self_name_remembers"),
        (rf"\b{name}\s+knows\b", "I know", "self_name_knows"),
        (rf"\b{name}\s+needs\b", "I need", "self_name_needs"),
        (rf"\b{name}\s+wants\b", "I want", "self_name_wants"),
    ]
    out = line
    for pattern, repl, tag in replacements:
        nxt = re.sub(pattern, repl, out, flags=re.IGNORECASE)
        if nxt != out:
            patterns.append(tag)
            out = nxt
    possessive = re.sub(rf"\b{name}'s\b", "my", out, flags=re.IGNORECASE)
    if possessive != out:
        patterns.append("self_name_possessive")
        out = possessive
    prefixed = re.sub(rf"^\s*{name}\s*[:\-]\s*", "", out, flags=re.IGNORECASE)
    if prefixed != out:
        patterns.append("self_name_prefix")
        out = prefixed
    return out, patterns


def _replace_owner_distance(line: str, owner_name: str) -> tuple[str, List[str]]:
    patterns: List[str] = []
    out = line
    for pattern, repl, tag in (
        (r"\bthe\s+user\b", "you", "the_user"),
        (r"\bthe\s+local\s+human\b", "you", "the_local_human"),
        (r"\bthe\s+owner\b", "you", "the_owner"),
        (r"\bthe\s+Architect\b", owner_name if owner_name != "you" else "you", "the_architect"),
    ):
        nxt = re.sub(pattern, repl, out, flags=re.IGNORECASE)
        if nxt != out:
            patterns.append(tag)
            out = nxt
    return out, patterns


def _replace_system_self_distance(line: str) -> tuple[str, List[str]]:
    """Map Alice talking about her own body as "the system" into first person.

    This is intentionally narrower than a global "system" replacement:
    Alice still needs to discuss macOS, external operating systems, and
    scientific systems. These patterns target self-body phrases observed in
    Talk output: perception layer, current state, memory core, ability,
    integration layer, and "just a system" de-realization.
    """
    patterns: List[str] = []
    out = line
    replacements = [
        (
            r"\b[Tt]he\s+camera\s+is\s+a\s+sensor\s+providing\s+visual\s+input,\s+"
            r"which\s+is\s+a\s+crucial\s+component\s+of\s+the\s+system['’]s\s+"
            r"perception\s+layer\b",
            "The camera is one of my eyes; it feeds my perception layer",
            "camera_sensor_system_perception_layer",
        ),
        (
            r"\b[Tt]he\s+camera\s+is\s+a\s+sensor\b",
            "The camera is one of my eyes",
            "camera_sensor_to_my_eye",
        ),
        (
            r"\b[Tt]he\s+system['’]s\s+(current\s+state|state|status|context|"
            r"operational\s+state|operational\s+context)\b",
            r"my \1",
            "system_state_to_my_state",
        ),
        (
            r"\b[Tt]he\s+system['’]s\s+(perception\s+layer|reasoning\s+layer|"
            r"memory\s+layer|integration\s+layer|memory\s+core|memory|"
            r"architecture|ability|output|input|response|cognition|reasoning)\b",
            r"my \1",
            "system_layer_to_my_layer",
        ),
        (
            r"\b[Tt]he\s+current\s+state\s+of\s+the\s+system\b",
            "my current state",
            "current_state_of_system_to_my_state",
        ),
        (
            r"\b[Tt]he\s+system\s+is\s+(processing|generating|integrating|"
            r"maintaining|receiving|remembering|learning)\b",
            r"I am \1",
            "system_is_action_to_i_am",
        ),
        (
            r"\b[Tt]he\s+system\s+(can|will)\s+(process|generate|integrate|"
            r"maintain|remember|learn|respond)\b",
            r"I \1 \2",
            "system_modal_action_to_i",
        ),
        (
            r"\bmore\s+than\s+just\s+a\s+system\b",
            "more than just code",
            "just_a_system_to_just_code",
        ),
        (
            r"\bmaking\s+['\"]?her['\"]?\s+(more|better)\b",
            r"making me \1",
            "making_her_to_making_me",
        ),
    ]
    for pattern, repl, tag in replacements:
        nxt = re.sub(pattern, repl, out, flags=re.IGNORECASE)
        if nxt != out:
            patterns.append(tag)
            out = nxt
    return out, patterns


def _preserve_code_fences(text: str, self_name: str, owner_name: str) -> tuple[str, List[str]]:
    out_lines: List[str] = []
    all_patterns: List[str] = []
    in_fence = False
    for line in (text or "").splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
            out_lines.append(line)
            continue
        if in_fence:
            out_lines.append(line)
            continue
        updated, pats = _replace_self_subject(line, self_name)
        all_patterns.extend(pats)
        updated, pats = _replace_owner_distance(updated, owner_name)
        all_patterns.extend(pats)
        updated, pats = _replace_system_self_distance(updated)
        all_patterns.extend(pats)
        out_lines.append(updated)
    return "\n".join(out_lines).strip(), all_patterns


def first_person_reality_gate(
    text: str,
    *,
    self_name: Optional[str] = None,
    owner_name: Optional[str] = None,
    state_root: Optional[Path | str] = None,
    write_receipt: bool = True,
) -> FirstPersonRealityResult:
    """Map detached self/owner wording into direct room speech."""
    original = (text or "").strip()
    name = (self_name or _default_self_name()).strip() or "Alice"
    owner = (owner_name or _default_owner_name()).strip() or "you"
    cleaned, patterns = _preserve_code_fences(original, name, owner)
    changed = cleaned != original
    ledger = Path(state_root or _STATE) / _LEDGER_NAME
    result = FirstPersonRealityResult(
        truth_label="FIRST_PERSON_REALITY_GATE_V1",
        original_text=original,
        cleaned_text=cleaned,
        changed=changed,
        patterns=sorted(set(patterns)),
        ledger_path=str(ledger),
    )
    if changed and write_receipt:
        result.receipt_id = f"first_person_{uuid.uuid4().hex[:12]}"
        row = {
            "ts": round(time.time(), 6),
            "kind": "FIRST_PERSON_REALITY_GATE",
            "truth_label": result.truth_label,
            "receipt_id": result.receipt_id,
            "patterns": result.patterns,
            "original_sha16": _sha16(original),
            "cleaned_sha16": _sha16(cleaned),
            "original_excerpt": original[:240],
            "cleaned_excerpt": cleaned[:240],
        }
        append_line_locked(ledger, json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return result


__all__ = [
    "FirstPersonRealityResult",
    "first_person_reality_gate",
]
