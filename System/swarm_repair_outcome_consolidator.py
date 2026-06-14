#!/usr/bin/env python3
"""swarm_repair_outcome_consolidator.py — close the body-code memory loop write-side (r988).

r983 landed the READ side: compose_body_code_card reads prior repair_outcome
engrams before a self-code cut, and suggest_next_cut changes the next choice
when one exists. But nothing WROTE those engrams — the loop read from a well
nobody filled. This organ is the well-filler.

After Alice's self-code hand lands (or refuses) a cut, this consolidator turns
that outcome into the exact repair_outcome engram shape the read side expects
(swarm_code_knowledge_graph §559):

    {"engram_id", kind="repair_outcome", "files":[...], "why", "result",
     "next_risk", "truth_label"}

written to long_term_engrams.jsonl. THE GATE (r983 doctrine, §6 no-double-spend):
only a landing whose receipt carries real test names in tests_green becomes a
weight CANDIDATE in engram_weight_candidates.jsonl. A failed, untested, or
hallucinated repair is recorded as an engram for memory, but NEVER promoted
toward training. That gate is what lets us say "continuous self-improvement"
without lying.

Pure stdlib. Never raises. Author: cowork_claude (claude-fable-5), 2026-06-11.
Doctrine: §0 (open-ended self-improvement), §6 (effector truth), §7.12 (probe),
r983 (body-code memory loop).
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

TRUTH_LABEL = "REPAIR_OUTCOME_CONSOLIDATOR_V1"
ENGRAMS_LEDGER = "long_term_engrams.jsonl"
CANDIDATES_LEDGER = "engram_weight_candidates.jsonl"

# A tests_green line is "real" only if it names tests/results, not prose like
# "no_test_block_in_this_cut" or an error string. This is the promotion gate.
_NO_TEST_MARKERS = (
    "no_test_block", "no-test", "no test", "error", "failed", "exception",
    "unknown", "honest failure",
)


def _state_root() -> Path:
    return Path(__file__).resolve().parents[1] / ".sifta_state"


def _tests_are_real(tests_green: str) -> bool:
    """True when tests_green names actual passing tests, not absence/failure."""
    t = (tests_green or "").strip().lower()
    if not t:
        return False
    if any(m in t for m in _NO_TEST_MARKERS):
        return False
    # must look like a real pytest tail: "N passed" or a test id
    return ("passed" in t) or ("::" in t) or ("test_" in t)


def consolidate_repair_outcome(
    summary: Dict[str, Any],
    *,
    model: str = "",
    state_dir: Optional[Path | str] = None,
    why: str = "",
    next_risk: str = "",
) -> Dict[str, Any]:
    """Turn a self-code-hand summary into a repair_outcome engram (+ candidate if gated).

    `summary` is the dict apply_self_code_cuts returns. Returns
    {engram_id, engram_written, candidate_written, promotion_gated, reason}.
    Never raises.
    """
    try:
        sd = Path(state_dir) if state_dir is not None else _state_root()
        results = summary.get("results") or []
        landed = [r.get("path") for r in results if r.get("landed")]
        refused = [r.get("path") for r in results if not r.get("landed")]
        any_landed = bool(summary.get("any_landed"))
        py = summary.get("pytest") or {}
        tests_green = " ".join(py.get("tail") or []) if py else ""
        if not tests_green:
            # the hand's receipt may carry it instead
            rec = summary.get("receipt") or {}
            tests_green = str(rec.get("tests_green") or "")

        result = "landed" if any_landed else "nothing_landed"
        engram_id = f"repair-{int(time.time())}-{uuid.uuid4().hex[:6]}"
        auto_risk = next_risk
        if not auto_risk:
            if refused and not any_landed:
                auto_risk = f"cut refused on {refused}; the path/validation rejected it — re-read before retrying"
            elif refused:
                auto_risk = f"partial: {refused} did not land while {landed} did — reconcile the siblings"
            elif not _tests_are_real(tests_green):
                auto_risk = "landed without a real test block — add a proof file before trusting this organ"
            else:
                auto_risk = ""

        engram = {
            "ts": time.time(),
            "engram_id": engram_id,
            "kind": "repair_outcome",
            "files": landed or refused,
            "why": why or f"self-code cut by {model or 'live cortex'}",
            "result": result,
            "tests_green": tests_green,
            "next_risk": auto_risk,
            "model": model,
            "truth_label": "REPAIR_OUTCOME_ENGRAM",
            "source_ledger": "self_code_hand",
        }
        sd.mkdir(parents=True, exist_ok=True)
        with (sd / ENGRAMS_LEDGER).open("a", encoding="utf-8") as f:
            f.write(json.dumps(engram) + "\n")

        # PROMOTION GATE — only a verified landing becomes a weight candidate.
        promote = bool(any_landed and _tests_are_real(tests_green))
        candidate_written = False
        gate_reason = ""
        if promote:
            candidate = {
                "ts": time.time(),
                "engram_id": engram_id,
                "kind": "repair_outcome_candidate",
                "files": landed,
                "why": engram["why"],
                "tests_green": tests_green,
                # match the ARM_OUTCOME label the existing miner already accepts (r983)
                "truth_label": "ARM_OUTCOME_LEARNING_V1",
                "source": "repair_outcome_consolidator",
                "owner_gate": "PENDING",  # George's GO still required before any training (r983)
            }
            with (sd / CANDIDATES_LEDGER).open("a", encoding="utf-8") as f:
                f.write(json.dumps(candidate) + "\n")
            candidate_written = True
            gate_reason = "verified landing with real tests → candidate (owner GO still required to train)"
        else:
            if not any_landed:
                gate_reason = "no landing — engram kept for memory, never promoted"
            else:
                gate_reason = "landed but no real test block — engram kept, promotion withheld (§6)"

        return {
            "engram_id": engram_id,
            "engram_written": True,
            "candidate_written": candidate_written,
            "promotion_gated": not promote,
            "reason": gate_reason,
            "next_risk": auto_risk,
        }
    except Exception as exc:
        return {
            "engram_written": False,
            "candidate_written": False,
            "promotion_gated": True,
            "reason": f"consolidator failed: {type(exc).__name__}: {exc}",
        }


__all__ = ["TRUTH_LABEL", "consolidate_repair_outcome"]
