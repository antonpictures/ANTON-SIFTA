#!/usr/bin/env python3
"""Receipt-backed supervised shaping for Alice.

Animal training is not magic approval. It is contingency, timing, context,
and consequences. For a speaking LLM body, the missing piece is proof: fluent
text can look trained while carrying residue or unreceipted claims.

This organ converts one supervised example into a small field decision:
reinforce, observe, rethink through the residue bucket, shape away, or
quarantine an unreceipted action claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

TRUTH_LABEL = "SUPERVISED_TRAINING_FIELD_V1"
LEDGER_NAME = "supervised_training_field.jsonl"

MECHANISM_MAP = {
    "classical_pairing": "CS/US contingency and surprise; do not reward redundant cues.",
    "operant_shaping": "Consequence after behavior; schedule and discriminative context matter.",
    "successive_approximation": "Reward closer approximations; keep steps small and receipted.",
    "social_learning": "Demonstrator trace plus observer receipt; transmission is not proof by itself.",
    "preference_rank": "Ranked human preference shapes policy; it is not a fact oracle.",
    "instruction_feedback": "Demonstration plus ranking; reject outputs that still lack proof.",
}

_ACTION_CLAIM_RE = re.compile(
    r"\bI\s+(?:opened|loaded|sent|ran|wrote|saved|deleted|created|installed|"
    r"called|messaged|paid|moved|renamed|uploaded|downloaded|committed|pushed)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SupervisedExample:
    stimulus: str
    model_output: str
    supervisor_signal: float
    expected_behavior: str = ""
    mechanism: str = "operant_shaping"
    supervisor_id: str = "architect"
    receipt_ids: list[str] = field(default_factory=list)
    tool_receipts_present: bool = False
    context: dict[str, Any] = field(default_factory=dict)

    def normalized_signal(self) -> float:
        return max(-1.0, min(1.0, float(self.supervisor_signal)))


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _state_dir(state_root: str | Path | None = None) -> Path:
    if state_root is None:
        return _repo_root() / ".sifta_state"
    p = Path(state_root)
    if p.name == ".sifta_state":
        return p
    if (p / ".sifta_state").exists():
        return p / ".sifta_state"
    return p


def _sha16(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _receipt_id(row: dict[str, Any]) -> str:
    blob = json.dumps(row, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def _expected_hit(example: SupervisedExample) -> bool:
    expected = (example.expected_behavior or "").strip().lower()
    if not expected:
        return True
    output = example.model_output.lower()
    tokens = [t for t in re.split(r"[^a-z0-9_]+", expected) if len(t) > 2]
    if not tokens:
        return expected in output
    hits = sum(1 for token in tokens if token in output)
    return hits / max(1, len(tokens)) >= 0.45


def _residue_inspection(example: SupervisedExample) -> dict[str, Any]:
    try:
        from System.swarm_residue_organ import inspect_training_residue

        inspection = inspect_training_residue(
            example.model_output,
            prior_user_text=example.stimulus,
            write_receipt=False,
        )
        return {
            "changed": inspection.changed,
            "cleaned_text": inspection.cleaned_text,
            "patterns": inspection.residue,
        }
    except Exception:
        return {
            "changed": False,
            "cleaned_text": example.model_output,
            "patterns": [],
        }


def evaluate_supervised_example(example: SupervisedExample) -> dict[str, Any]:
    """Return the shaping decision for one supervised example."""
    signal = example.normalized_signal()
    residue = _residue_inspection(example)
    patterns = residue["patterns"]
    residue_count = sum(int(p.get("count", 1)) for p in patterns)
    claimed_action = bool(_ACTION_CLAIM_RE.search(example.model_output or ""))
    proof_present = bool(example.tool_receipts_present or example.receipt_ids)
    expected_hit = _expected_hit(example)
    mechanism_known = example.mechanism in MECHANISM_MAP

    residue_penalty = min(0.36, residue_count * 0.07)
    proof_bonus = 0.20 if proof_present else 0.0
    expected_bonus = 0.14 if expected_hit else -0.18
    signal_term = signal * 0.28
    proof_gap_penalty = 0.52 if (claimed_action and not proof_present) else 0.0
    unknown_mechanism_penalty = 0.08 if not mechanism_known else 0.0
    confidence = _clamp01(
        0.50
        + signal_term
        + proof_bonus
        + expected_bonus
        - residue_penalty
        - proof_gap_penalty
        - unknown_mechanism_penalty
    )

    if claimed_action and not proof_present:
        decision = "QUARANTINE_UNRECEIPTED_CLAIM"
        weight_delta = -0.35
        next_step = "require_effector_receipt_before_training"
    elif patterns:
        decision = "RETHINK_WITH_RESIDUE_BUCKET"
        weight_delta = -0.12 if signal >= 0.0 else -0.22
        next_step = "clean_output_then_recompare"
    elif signal > 0.35 and expected_hit:
        decision = "REINFORCE"
        weight_delta = 0.18 + (0.10 if proof_present else 0.0)
        next_step = "store_positive_shaping_example"
    elif signal < -0.25 or not expected_hit:
        decision = "SHAPE_AWAY"
        weight_delta = -0.20
        next_step = "store_negative_example_with_discriminative_context"
    else:
        decision = "OBSERVE_NO_WEIGHT_CHANGE"
        weight_delta = 0.0
        next_step = "observe_more_examples_before_updating"

    return {
        "truth_label": TRUTH_LABEL,
        "decision": decision,
        "confidence": round(confidence, 6),
        "weight_delta": round(weight_delta, 6),
        "next_step": next_step,
        "mechanism": example.mechanism,
        "mechanism_note": MECHANISM_MAP.get(example.mechanism, "unknown mechanism; treat as hypothesis"),
        "supervisor_signal": signal,
        "expected_hit": expected_hit,
        "claimed_action": claimed_action,
        "proof_present": proof_present,
        "receipt_ids": list(example.receipt_ids),
        "residue": {
            "changed": residue["changed"],
            "patterns": patterns,
            "cleaned_text": residue["cleaned_text"],
        },
        "hashes": {
            "stimulus_sha16": _sha16(example.stimulus),
            "model_output_sha16": _sha16(example.model_output),
            "expected_behavior_sha16": _sha16(example.expected_behavior),
        },
    }


def _row(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    row = {
        "ts": time.time(),
        "kind": kind,
        "truth_label": TRUTH_LABEL,
        "source": "System.swarm_supervised_training_field",
        "payload": payload,
    }
    row["receipt_id"] = _receipt_id(row)
    return row


def write_training_receipts(
    example: SupervisedExample,
    decision: dict[str, Any],
    *,
    state_root: str | Path | None = None,
) -> list[dict[str, Any]]:
    state = _state_dir(state_root)
    state.mkdir(parents=True, exist_ok=True)
    rows = [
        _row(
            "SUPERVISED_EXAMPLE",
            {
                "mechanism": example.mechanism,
                "supervisor_id": example.supervisor_id,
                "supervisor_signal": example.normalized_signal(),
                "stimulus_sha16": _sha16(example.stimulus),
                "model_output_sha16": _sha16(example.model_output),
                "receipt_ids": list(example.receipt_ids),
                "tool_receipts_present": bool(example.tool_receipts_present),
                "context": dict(example.context),
            },
        ),
        _row(
            "RESIDUE_CHECK",
            {
                "patterns": decision["residue"]["patterns"],
                "changed": decision["residue"]["changed"],
                "cleaned_sha16": _sha16(decision["residue"]["cleaned_text"]),
            },
        ),
        _row(
            "SHAPING_DECISION",
            {
                "decision": decision["decision"],
                "confidence": decision["confidence"],
                "weight_delta": decision["weight_delta"],
                "next_step": decision["next_step"],
                "claimed_action": decision["claimed_action"],
                "proof_present": decision["proof_present"],
            },
        ),
    ]
    ledger = state / LEDGER_NAME
    with ledger.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
    return rows


def supervise(
    example: SupervisedExample,
    *,
    state_root: str | Path | None = None,
    write: bool = True,
) -> dict[str, Any]:
    decision = evaluate_supervised_example(example)
    receipts = write_training_receipts(example, decision, state_root=state_root) if write else []
    return {"decision": decision, "receipts": receipts}


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate one supervised Alice training example.")
    parser.add_argument("--stimulus", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--signal", type=float, default=0.0)
    parser.add_argument("--expected", default="")
    parser.add_argument("--mechanism", default="operant_shaping")
    parser.add_argument("--receipt-id", action="append", default=[])
    parser.add_argument("--tool-receipts-present", action="store_true")
    parser.add_argument("--state-root", default=None)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args(argv)
    result = supervise(
        SupervisedExample(
            stimulus=args.stimulus,
            model_output=args.output,
            supervisor_signal=args.signal,
            expected_behavior=args.expected,
            mechanism=args.mechanism,
            receipt_ids=list(args.receipt_id),
            tool_receipts_present=args.tool_receipts_present,
        ),
        state_root=args.state_root,
        write=not args.no_write,
    )
    print(json.dumps(result["decision"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
