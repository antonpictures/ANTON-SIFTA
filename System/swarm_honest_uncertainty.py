"""
System/swarm_honest_uncertainty.py
══════════════════════════════════
Round 65 (2026-05-27) — Architect task #51: "I don't know X" before invention.

Doctrine (Architect, 2026-05-26 from §18.3 of TOURNAMENT_PLAN):
    "Honest Uncertainty skill — Alice says 'I don't know X' instead
     of inventing. When memory card has no relevant rows and confidence
     is low on an operational question, I say 'I don't know X. Want me
     to dispatch Codex / Grok / write to unknowns ledger?' No confident
     hallucination."

This module is a PURE-PYTHON sysprompt-side helper. Its job is to:

  1. Look at the OWNER text + the memory card the widget already built
     for this turn, and decide whether the owner is asking an
     OPERATIONAL question (something Alice should answer from receipts
     + ledger truth, not from training prior).

  2. Look at the memory card to see whether the relevant evidence is
     actually IN the card. We have `memory_card_has_relevant` already
     wired into the widget (task #45 closed). This module extends that
     signal with topic-specific checks.

  3. Compose a small sysprompt block that the cortex reads BEFORE
     composing the reply. The block tells the cortex: "If you do not
     see the answer in the receipts surfaced above, say so plainly.
     Offer to dispatch an arm OR write the unknown to
     .sifta_state/unknowns_ledger.jsonl so a future arm can pick it
     up. Do NOT invent values, dates, receipt ids, status strings,
     or sensor readings."

  4. Provide a writer for the unknowns ledger so cortex (or any
     module) can append a row when honest uncertainty is the right
     answer. The ledger is append-only and read by future arms /
     research rounds.

Doctrine touchpoints
====================
  - Covenant §6 (effector immunity): never claim an external action
    without a receipt. Honest uncertainty IS the receipt-respecting
    answer when the receipt is missing.
  - Covenant §7.10.3 (lab measurement, not seminar language):
    "I don't know" is the correct measurement-language reply when
    the data isn't there. Invented prose is the seminar reply.
  - Round 50 (recovery layer + self-watch): this module sits next to
    them in the sysprompt assembly. Recovery handles silence +
    correction; self-watch surfaces arm work; honest uncertainty
    handles missing-evidence.
  - §18.3 nugget #3 ("models love to cheat. RL is really good at
    encouraging cheating"): the only honest reward is grounded
    receipts. Honest uncertainty is the cortex-side complement of
    the launcher-side `actually_landed` check.

Pure stdlib. No PyQt. Never raises out. Tested by
tests/test_swarm_honest_uncertainty.py.

Public surface
══════════════
    @dataclass UncertaintySignal
    classify_question_shape(text) -> str
    detect_operational_question(text) -> bool
    write_unknown(state_dir, *, topic, owner_text, attempted_sources)
        -> str (receipt_id)
    uncertainty_prompt_block(*, user_text, memory_card_has_relevant,
                             memory_card_excerpts="") -> str

Constants
═════════
    UNKNOWN_LEDGER_FILENAME = "unknowns_ledger.jsonl"
"""
from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


TRUTH_LABEL = "HONEST_UNCERTAINTY_V1"
UNKNOWN_LEDGER_FILENAME = "unknowns_ledger.jsonl"


# ─── Question shape classification ──────────────────────────────────────────


# Shapes that demand receipt-grounded answers (Alice should know from
# ledgers, not from training prior). When the memory card lacks
# relevant rows for these, honest uncertainty is the correct reply.
_OPERATIONAL_PATTERNS: tuple[tuple[str, str], ...] = (
    # Receipt / ledger / disk-truth questions
    (r"\bwhat (?:was|is) (?:the\s+)?(?:last\s+|latest\s+|recent\s+|my\s+)*receipt(?:\s+id)?\b",  "receipt_lookup"),
    (r"\bdid (?:you|alice) (?:save|write|send|run|dispatch|land|push|commit)\b",
                                                              "did_alice_do_X"),
    (r"\bwhen did (?:you|alice) last (?:save|write|send|run|dispatch)\b",
                                                              "last_action_lookup"),
    (r"\bshow me (?:the|my) (?:last|recent|latest) (?:receipt|ledger|row)\b",
                                                              "show_receipts"),

    # Body state / sensor questions
    (r"\bwhat (?:is|was) (?:my|the) (?:stgm|balance|metabolic|budget)\b",
                                                              "metabolic_state"),
    (r"\bis (?:the|my) (?:camera|mic|gps|ble|wifi|sensor) (?:on|active|working)\b",
                                                              "sensor_state"),
    (r"\bwhat (?:cortex|model|arm) (?:are you|is alice) using\b",
                                                              "cortex_state"),

    # Arm / dispatch questions
    (r"\bwhat did (?:codex|claude|grok|hermes|the arm) (?:do|write|produce)\b",
                                                              "arm_output_lookup"),
    (r"\bwhich files did .* (?:write|change|modify|touch)\b",  "arm_file_lookup"),

    # Schedule / continuity questions
    (r"\bwhat (?:is|was) on my (?:calendar|schedule|agenda)\b", "schedule_lookup"),
    (r"\bwhen (?:is|was) my next \w+\b",                       "next_event_lookup"),
)

_COMPILED_OPERATIONAL = tuple(
    (re.compile(p, re.IGNORECASE), label) for p, label in _OPERATIONAL_PATTERNS
)


def classify_question_shape(text: str) -> str:
    """Return a question-shape label or 'open' for non-operational turns."""
    clean = (text or "").strip()
    if not clean:
        return "empty"
    for pat, label in _COMPILED_OPERATIONAL:
        if pat.search(clean):
            return label
    return "open"


def detect_operational_question(text: str) -> bool:
    """True when the owner's text demands receipt-grounded truth.

    Use this as the "should I trigger honest uncertainty if memory_card
    lacks evidence?" decision.
    """
    shape = classify_question_shape(text)
    return shape not in ("open", "empty")


# ─── Unknowns ledger writer ─────────────────────────────────────────────────


@dataclass(frozen=True)
class UncertaintySignal:
    """Captures one moment of honest uncertainty."""
    is_uncertain: bool
    question_shape: str
    memory_card_has_relevant: bool
    suggested_action: str   # "dispatch_arm" | "write_unknown" | "ask_owner"
    block_text: str         # what gets injected into sysprompt (empty if not uncertain)


def write_unknown(
    state_dir: Path | str,
    *,
    topic: str,
    owner_text: str,
    attempted_sources: Iterable[str] = (),
    suggested_arm: Optional[str] = None,
    cortex_label: Optional[str] = None,
) -> str:
    """
    Append one row to .sifta_state/unknowns_ledger.jsonl. Future arms /
    research rounds can read this ledger to know what Alice could not
    answer from receipts and pick up the dispatch.

    Returns the receipt_id (uuid hex string).

    The row shape:
        {
            "ts": <unix>,
            "receipt_id": "unknown_<16-hex>",
            "truth_label": "HONEST_UNCERTAINTY_V1",
            "topic": <short label>,
            "owner_text_head": <first 240 chars of owner text>,
            "attempted_sources": [<which ledgers/tools were checked>],
            "suggested_arm": <arm_id or None>,
            "cortex_label": <cortex that surfaced the uncertainty>,
        }
    """
    rid = "unknown_" + uuid.uuid4().hex[:16]
    head = (owner_text or "").strip()[:240]
    row = {
        "ts": time.time(),
        "receipt_id": rid,
        "truth_label": TRUTH_LABEL,
        "topic": str(topic or "").strip()[:120] or "unspecified",
        "owner_text_head": head,
        "attempted_sources": list(attempted_sources),
        "suggested_arm": suggested_arm,
        "cortex_label": cortex_label,
    }
    path = Path(state_dir) / UNKNOWN_LEDGER_FILENAME
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        # Never raise — the ledger writer is autonomic; if disk is full
        # the receipt_id is still returned so the cortex can include it
        # in its reply (the row may be missing from disk but the id is
        # at least consistent for this turn).
        pass
    return rid


# ─── Sysprompt block composer ───────────────────────────────────────────────


def uncertainty_prompt_block(
    *,
    user_text: str,
    memory_card_has_relevant: bool,
    memory_card_excerpts: str = "",
) -> str:
    """
    Compose the sysprompt block that tells the cortex how to handle
    operational questions when receipt evidence is missing. Returns ""
    for non-operational turns (the normal case — the block adds zero
    overhead to chit-chat).
    """
    shape = classify_question_shape(user_text or "")
    if shape in ("open", "empty"):
        return ""
    if memory_card_has_relevant:
        # Evidence is in the card already — cortex should cite it,
        # not declare uncertainty. The block does NOT fire.
        return ""

    # Build the block. Naming the question shape helps the cortex
    # pick the right "I don't know" phrasing.
    suggested_arms = _suggested_arms_for_shape(shape)
    arm_hint = (
        f"  Suggested arms to dispatch if owner wants the answer: "
        f"{', '.join(suggested_arms)}." if suggested_arms else
        "  No arm suggested — this looks like a body-state question; "
        "say so plainly."
    )

    lines = [
        "[HONEST UNCERTAINTY — Round 65 / Task #51]",
        f"The owner asked an OPERATIONAL question (shape: {shape}).",
        "I checked the memory card surfaced above this block and could not "
        "find evidence that answers the question.",
        "",
        "CORRECT REPLY SHAPE:",
        '  "I don\'t know <what> — the receipts surfaced for this turn '
        "don't show it. Want me to dispatch <arm> to find out, or "
        "write the unknown to .sifta_state/unknowns_ledger.jsonl so I "
        'can pick it up later?"',
        "",
        arm_hint,
        "",
        "DO NOT:",
        "  - invent receipt ids, timestamps, status strings, sensor readings",
        "  - confabulate from training prior (covenant §6 effector immunity)",
        "  - phrase the unknown as 'I sense' / 'I perceive' / 'the field "
        "shows' — that is seminar/spiritualism language (§7.10.3); use "
        "plain measurement language: 'I do not see X in the ledger'.",
    ]
    if memory_card_excerpts:
        head = memory_card_excerpts.strip()[:280]
        lines.append("")
        lines.append(f"Memory card excerpt seen for this turn: {head}")
    return "\n".join(lines)


def _suggested_arms_for_shape(shape: str) -> list[str]:
    """Map a question shape to the arms most likely to answer it."""
    if shape in ("receipt_lookup", "show_receipts", "last_action_lookup",
                  "did_alice_do_X", "arm_output_lookup", "arm_file_lookup"):
        return ["codex_agent", "claude_agent"]
    if shape in ("metabolic_state", "sensor_state", "cortex_state"):
        # Body-state questions — local arms / corvid scout are cheaper
        return ["corvid_scout"]
    if shape in ("schedule_lookup", "next_event_lookup"):
        return ["codex_agent"]
    return []


def evaluate(
    *,
    user_text: str,
    memory_card_has_relevant: bool,
    memory_card_excerpts: str = "",
) -> UncertaintySignal:
    """One-shot evaluator returning the full signal for callers that want
    structured access to the decision rather than just the block text."""
    shape = classify_question_shape(user_text or "")
    is_op = shape not in ("open", "empty")
    block = uncertainty_prompt_block(
        user_text=user_text,
        memory_card_has_relevant=memory_card_has_relevant,
        memory_card_excerpts=memory_card_excerpts,
    )
    fires = bool(is_op and not memory_card_has_relevant)
    if not fires:
        suggested = "ask_owner"
    elif _suggested_arms_for_shape(shape):
        suggested = "dispatch_arm"
    else:
        suggested = "write_unknown"
    return UncertaintySignal(
        is_uncertain=fires,
        question_shape=shape,
        memory_card_has_relevant=memory_card_has_relevant,
        suggested_action=suggested,
        block_text=block,
    )


OPERATIONAL_SHAPES = [label for _, label in _OPERATIONAL_PATTERNS]

__all__ = [
    "TRUTH_LABEL",
    "UNKNOWN_LEDGER_FILENAME",
    "UncertaintySignal",
    "classify_question_shape",
    "detect_operational_question",
    "write_unknown",
    "uncertainty_prompt_block",
    "evaluate",
    "OPERATIONAL_SHAPES",
]
