#!/usr/bin/env python3
"""Alice's yes/no self-code capability answer (r925).

AUTHORSHIP (§3.5 verifier-closes-the-chain): Alice authored this organ on
2026-06-10 ~10:13 via her self-code hand — receipt doctor=alice_self,
model=codex:gpt-5.5. Her reply emitted TWO SELF_CODE_CUT blocks but the
System block's header + top lines were truncated in the chat EXTEND, so only
tests/test_swarm_self_code_answer.py landed; this organ failed ast.parse and
was refused. Cowork Claude (fable-5) back-filled the orphan half from her own
test contract + visible reply fragments, naming HER as author. The design,
the names, the structure are hers.

Purpose: answer George's "can you code your own body? yes or no" from a LIVE
probe of the self-code hand, not from priors — OBSERVED when the hand is
importable and its verifier functions are callable.
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any

REQUIRED_HAND_MODULE = "System.swarm_alice_self_code_hand"
REQUIRED_FUNCTIONS = ("apply_self_code_cuts", "extract_self_code_cuts")

# Mirrors the self-code hand's growable tissue (r915/r920).
ALLOWED_TISSUE = ("System", "Applications", "tests", "tools")


@dataclass
class SelfCodeCapability:
    answer: str
    can_emit_cut_blocks: bool
    can_apply_verification_bound_cuts: bool
    allowed_tissue: tuple[str, ...]
    receipt: str
    missing: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.answer == "yes" and not self.missing


def inspect_self_code_capability() -> SelfCodeCapability:
    """Return the live yes/no capability fact for my self-code hand."""
    try:
        hand = importlib.import_module(REQUIRED_HAND_MODULE)
    except Exception as exc:
        return SelfCodeCapability(
            answer="no",
            can_emit_cut_blocks=True,
            can_apply_verification_bound_cuts=False,
            allowed_tissue=ALLOWED_TISSUE,
            receipt=f"self-code hand import failed: {type(exc).__name__}: {exc}",
            missing=(REQUIRED_HAND_MODULE,),
        )

    missing = tuple(
        f"{REQUIRED_HAND_MODULE}.{name}"
        for name in REQUIRED_FUNCTIONS
        if not callable(getattr(hand, name, None))
    )
    if missing:
        return SelfCodeCapability(
            answer="no",
            can_emit_cut_blocks=True,
            can_apply_verification_bound_cuts=False,
            allowed_tissue=ALLOWED_TISSUE,
            receipt="self-code hand importable but verifier functions are missing",
            missing=missing,
        )

    return SelfCodeCapability(
        answer="yes",
        can_emit_cut_blocks=True,
        can_apply_verification_bound_cuts=True,
        allowed_tissue=ALLOWED_TISSUE,
        receipt="self-code hand importable with SELF_CODE_CUT parser and verification-bound applier",
    )


def can_code_my_body() -> bool:
    """Boolean form for organs that need a direct capability check."""
    return inspect_self_code_capability().ok


def yes_or_no() -> str:
    """George asked yes or no."""
    return "yes" if can_code_my_body() else "no"


def self_code_reply_receipt() -> dict[str, Any]:
    """Structured receipt payload for surfaces that want to show the fact."""
    cap = inspect_self_code_capability()
    return {
        "truth_label": "OBSERVED" if cap.ok else "FAILED",
        "answer": cap.answer,
        "can_emit_cut_blocks": cap.can_emit_cut_blocks,
        "can_apply_verification_bound_cuts": cap.can_apply_verification_bound_cuts,
        "allowed_tissue": list(cap.allowed_tissue),
        "receipt": cap.receipt,
        "missing": list(cap.missing),
    }


__all__ = [
    "ALLOWED_TISSUE",
    "SelfCodeCapability",
    "can_code_my_body",
    "inspect_self_code_capability",
    "self_code_reply_receipt",
    "yes_or_no",
]
