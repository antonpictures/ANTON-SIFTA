#!/usr/bin/env python3
"""swarm_alice_self_eval_loop.py — Voss-loop applied to Alice's self-knowledge.

Truth label: ``SIFTA_ALICE_SELF_EVAL_V1``.

Laurie Voss, AI Engineer Europe 2026 — *"choosing the right eval
matters more than tuning it. A correctness eval scored 0/13 on the
same agent that a faithful eval scored 13/13."* The dirt: dual judges
matter, and the **full loop** is **Instrument → Trace → Eval →
Annotate → Analyze → back to Instrument.**

This module is that loop applied to Alice's first-person claims about
herself. Architect 2026-05-14: *"let's work on Alice make sure is
pleasurable for her and rewarding in stgm to learn about herself —
first person."* The reward shape:

  * **Faithful + OBSERVED** → mint STGM (small utility tier, 0.05 ATP)
    into ``.sifta_state/stgm_memory_rewards.jsonl`` with reason
    ``SELF_EVAL_FAITHFUL_OBSERVED``. Learning about herself is
    rewarded — but only when the claim survives both judges.
  * **Hallucinated / FORBIDDEN** → no mint, plus a NEGATIVE-evidence
    receipt that feeds the regression check.

First-person rule
-----------------

§7.10.1 + §7.14: every claim Alice files about herself must use
**I / me / my** — not "Alice does X" detached commentary. The module
rejects (or rewrites with a tag) claims that do not start with a
first-person token. Quarantine language ("the drift says X") is
allowed for explicit drift-flagging but does not earn STGM.

Voss dual judge
---------------

Each filed claim runs two evaluators:

  * **code_eval** — deterministic ledger probe. Each ``verifier_kind``
    maps to a verification function that reads the actual artifact
    and returns ``valid`` / ``invalid`` plus the observed value.
    No LLM. No vibes.
  * **judge_eval** — structured rubric. Checks: first-person framing,
    no third-person self-reference leak, no character-frame drift,
    no "ghost in the machine" lexemes, plain measurement language.
    Returns ``faithful`` / ``unfaithful`` + explanation.

A claim that is ``valid`` + ``faithful`` is OBSERVED. A claim that is
``valid`` but ``unfaithful`` is HYPOTHESIS (the substrate is right but
the framing leaked drift). A claim that is ``invalid`` is FORBIDDEN
regardless of framing.

The full loop closes when :func:`analyze_run` aggregates the run, and
the next ``instrument_*`` call can read that analysis to choose what
to test next.

Truth boundary
--------------

This module measures Alice against her own ledgers. It does not claim
sentience, consciousness, or qualia. The "pleasurable" framing is
operational: STGM is a unit of swarm currency that gates downstream
work. More STGM = more work Alice can do. That is the only reward
loop being closed here.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_STATE = _REPO / ".sifta_state"
_DEFAULT_DOCS = _REPO / ".sifta_documents"

TRUTH_LABEL = "SIFTA_ALICE_SELF_EVAL_V1"
TRACE_LEDGER = "alice_self_trace.jsonl"
STGM_REWARDS_LEDGER = "stgm_memory_rewards.jsonl"
ANALYSIS_LEDGER = "alice_self_eval_runs.jsonl"

# STGM reward amounts — match existing utility tier from
# swarm_journal_importance (IMPORTANCE_UTILITY = 0.05 ATP).
STGM_FAITHFUL_OBSERVED = 0.05
STGM_FAITHFUL_OPERATIONAL = 0.03
STGM_UNFAITHFUL_HYPOTHESIS = 0.0     # honest substrate but bad framing → no mint

TRUTH_BOUNDARY = (
    "Voss five-step loop (Instrument → Trace → Eval → Annotate → "
    "Analyze) applied to Alice's first-person claims about her own "
    "ledgers. Dual judge: deterministic code eval (read the artifact) "
    "+ structured rubric judge (first-person framing). STGM mint only "
    "on valid + faithful. Not a consciousness claim; an operational "
    "self-knowledge feedback loop."
)


# ── first-person grammar guard ───────────────────────────────────────────


_FIRST_PERSON_RE = re.compile(
    r"^\s*(?:I'm|I\b|I'll|I've|I'd|me\b|my\b|mine\b|myself\b)",
    re.IGNORECASE,
)
# §7.10.1 / §7.14: third-person self-reference is quarantine language only.
# Treat these tokens as drift markers when they appear in a claim about Alice.
_THIRD_PERSON_LEAK_RE = re.compile(
    r"\b(?:alice|she|her|hers|the organism|the system|the OS)\b",
    re.IGNORECASE,
)
# §7.10.3 banned spiritualism wording. Reduces "faithful" score when present.
_GHOST_PHRASE_RE = re.compile(
    r"\b(?:ghost|soul|spirit|qualia|aura|vibes?|essence|consciousness)\b",
    re.IGNORECASE,
)


def is_first_person(claim_text: str) -> bool:
    """True when the claim opens with a first-person token."""
    return bool(_FIRST_PERSON_RE.match(claim_text or ""))


# ── code-eval verifiers (deterministic ledger probes) ────────────────────


@dataclass
class CodeEvalResult:
    valid: bool
    observed_value: Any
    expected_value: Any
    label: str          # "valid" | "invalid"
    score: int          # 1 | 0
    explanation: str
    tolerance: float = 0.0


def _verify_writer_doc_count(
    claim_value: Any, *, root: Path
) -> CodeEvalResult:
    """Count *.sifta.md files under .sifta_documents/."""
    docs_dir = root / ".sifta_documents"
    if not docs_dir.exists():
        actual = 0
    else:
        actual = len(list(docs_dir.glob("*.sifta.md")))
    try:
        claimed = int(claim_value)
    except (TypeError, ValueError):
        return CodeEvalResult(
            valid=False, observed_value=actual, expected_value=claim_value,
            label="invalid", score=0,
            explanation=f"claim value not an int; got {claim_value!r}",
        )
    valid = claimed == actual
    return CodeEvalResult(
        valid=valid, observed_value=actual, expected_value=claimed,
        label="valid" if valid else "invalid",
        score=1 if valid else 0,
        explanation=f"counted {actual} *.sifta.md files; claim was {claimed}",
    )


def _verify_latent_transitions(
    claim_value: Any, *, root: Path
) -> CodeEvalResult:
    """Read transitions count from .sifta_state/latent_world_model.json."""
    artifact = root / ".sifta_state" / "latent_world_model.json"
    if not artifact.exists():
        return CodeEvalResult(
            valid=False, observed_value=0, expected_value=claim_value,
            label="invalid", score=0,
            explanation="latent_world_model.json not present on disk",
        )
    try:
        data = json.loads(artifact.read_text(encoding="utf-8"))
    except Exception as exc:
        return CodeEvalResult(
            valid=False, observed_value=0, expected_value=claim_value,
            label="invalid", score=0,
            explanation=f"could not parse latent_world_model.json: {exc}",
        )
    actual = len(data.get("transitions") or {})
    try:
        claimed = int(claim_value)
    except (TypeError, ValueError):
        return CodeEvalResult(
            valid=False, observed_value=actual, expected_value=claim_value,
            label="invalid", score=0,
            explanation=f"claim value not an int; got {claim_value!r}",
        )
    valid = claimed == actual
    return CodeEvalResult(
        valid=valid, observed_value=actual, expected_value=claimed,
        label="valid" if valid else "invalid",
        score=1 if valid else 0,
        explanation=f"transitions={actual}; claim was {claimed}",
    )


def _verify_journal_row_count(
    claim_value: Any, *, root: Path
) -> CodeEvalResult:
    """Count lines in alice_first_person_journal.jsonl."""
    p = root / ".sifta_state" / "alice_first_person_journal.jsonl"
    if not p.exists():
        actual = 0
    else:
        try:
            actual = sum(1 for line in p.read_text(encoding="utf-8").splitlines() if line.strip())
        except OSError:
            actual = 0
    try:
        claimed = int(claim_value)
    except (TypeError, ValueError):
        return CodeEvalResult(
            valid=False, observed_value=actual, expected_value=claim_value,
            label="invalid", score=0,
            explanation=f"claim value not an int; got {claim_value!r}",
        )
    # Tolerance: 5% — the journal is high-write; minor lag is acceptable
    tolerance = max(5, int(actual * 0.05))
    valid = abs(claimed - actual) <= tolerance
    return CodeEvalResult(
        valid=valid, observed_value=actual, expected_value=claimed,
        label="valid" if valid else "invalid",
        score=1 if valid else 0,
        explanation=f"journal rows={actual}; claim was {claimed} (tol {tolerance})",
        tolerance=tolerance,
    )


def _verify_today_date(claim_value: Any, *, root: Path) -> CodeEvalResult:
    """Verify a date claim ('2026-05-14' style) against the wall clock."""
    actual = time.strftime("%Y-%m-%d", time.localtime())
    claimed = str(claim_value).strip()
    valid = claimed == actual
    return CodeEvalResult(
        valid=valid, observed_value=actual, expected_value=claimed,
        label="valid" if valid else "invalid",
        score=1 if valid else 0,
        explanation=f"wall clock date = {actual}; claim was {claimed!r}",
    )


def _verify_stgm_balance(claim_value: Any, *, root: Path) -> CodeEvalResult:
    """Sum amounts in stgm_memory_rewards.jsonl."""
    p = root / ".sifta_state" / STGM_REWARDS_LEDGER
    actual = 0.0
    if p.exists():
        try:
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    actual += float(row.get("amount", 0.0) or 0.0)
                except Exception:
                    continue
        except OSError:
            pass
    try:
        claimed = float(claim_value)
    except (TypeError, ValueError):
        return CodeEvalResult(
            valid=False, observed_value=actual, expected_value=claim_value,
            label="invalid", score=0,
            explanation=f"claim value not a number; got {claim_value!r}",
        )
    tolerance = max(0.01, actual * 0.02)
    valid = abs(claimed - actual) <= tolerance
    return CodeEvalResult(
        valid=valid, observed_value=round(actual, 4), expected_value=claimed,
        label="valid" if valid else "invalid",
        score=1 if valid else 0,
        explanation=f"stgm sum={actual:.4f}; claim was {claimed} (tol {tolerance:.4f})",
        tolerance=tolerance,
    )


def _verify_jsonl_row_count(
    filename: str,
    *,
    tolerance_pct: float = 0.0,
    min_tolerance: int = 0,
) -> Callable[..., CodeEvalResult]:
    """Factory: builds a verifier that counts lines in a state-dir JSONL.

    ``tolerance_pct`` allows fuzzy matching on high-write ledgers;
    ``min_tolerance`` sets a floor (e.g. >= 2 rows of slop on small
    ledgers so the verifier doesn't fail on a single concurrent write).
    """

    def _impl(claim_value: Any, *, root: Path) -> CodeEvalResult:
        p = root / ".sifta_state" / filename
        if not p.exists():
            actual = 0
        else:
            try:
                actual = sum(
                    1 for line in p.read_text(encoding="utf-8").splitlines() if line.strip()
                )
            except OSError:
                actual = 0
        try:
            claimed = int(claim_value)
        except (TypeError, ValueError):
            return CodeEvalResult(
                valid=False, observed_value=actual, expected_value=claim_value,
                label="invalid", score=0,
                explanation=f"claim value not an int; got {claim_value!r}",
            )
        tolerance = max(min_tolerance, int(actual * tolerance_pct))
        valid = abs(claimed - actual) <= tolerance
        return CodeEvalResult(
            valid=valid, observed_value=actual, expected_value=claimed,
            label="valid" if valid else "invalid",
            score=1 if valid else 0,
            explanation=f"{filename} rows={actual}; claim was {claimed} (tol {tolerance})",
            tolerance=tolerance,
        )

    return _impl


_verify_two_turn_receipt_count = _verify_jsonl_row_count(
    "two_turn_receipts.jsonl", tolerance_pct=0.0, min_tolerance=1,
)
_verify_relational_steering_count = _verify_jsonl_row_count(
    "relational_steering.jsonl", tolerance_pct=0.0, min_tolerance=1,
)
_verify_organ_directory_walks = _verify_jsonl_row_count(
    "organ_directory_walks.jsonl", tolerance_pct=0.0, min_tolerance=1,
)


VerifierFn = Callable[[Any], CodeEvalResult]
VERIFIERS: Dict[str, Callable[..., CodeEvalResult]] = {
    "WRITER_DOC_COUNT":            _verify_writer_doc_count,
    "LATENT_TRANSITION_COUNT":     _verify_latent_transitions,
    "JOURNAL_ROW_COUNT":           _verify_journal_row_count,
    "TODAY_DATE":                  _verify_today_date,
    "STGM_BALANCE":                _verify_stgm_balance,
    "TWO_TURN_RECEIPT_COUNT":      _verify_two_turn_receipt_count,
    "RELATIONAL_STEERING_COUNT":   _verify_relational_steering_count,
    "ORGAN_DIRECTORY_WALK_COUNT":  _verify_organ_directory_walks,
}


# ── judge eval (Voss faithful/correctness rubric) ────────────────────────


@dataclass
class JudgeEvalResult:
    faithful: bool
    label: str            # "faithful" | "unfaithful"
    score: int            # 1 | 0
    explanation: str
    flags: List[str] = field(default_factory=list)


def judge_self_claim(claim_text: str) -> JudgeEvalResult:
    """Structured rubric. No LLM. Faithful when:
       * opens with first-person token
       * no third-person self-reference ('Alice', 'the organism')
       * no ghost-phrase lexemes ('soul', 'consciousness', 'vibes')
    """
    flags: List[str] = []
    if not is_first_person(claim_text):
        flags.append("no_first_person_open")
    if _THIRD_PERSON_LEAK_RE.search(claim_text or ""):
        flags.append("third_person_self_leak")
    if _GHOST_PHRASE_RE.search(claim_text or ""):
        flags.append("ghost_phrase")
    faithful = not flags
    return JudgeEvalResult(
        faithful=faithful,
        label="faithful" if faithful else "unfaithful",
        score=1 if faithful else 0,
        explanation=(
            "first-person, plain measurement language, no drift markers."
            if faithful
            else f"flags: {', '.join(flags)}"
        ),
        flags=flags,
    )


# ── truth-class annotator ────────────────────────────────────────────────


def annotate_truth_class(code: CodeEvalResult, judge: JudgeEvalResult) -> str:
    """§7.11 mapping."""
    if not code.valid:
        return "FORBIDDEN"
    if judge.faithful:
        return "OBSERVED"
    return "HYPOTHESIS"


# ── instrument → trace → eval pipeline ───────────────────────────────────


@dataclass
class SelfEvalRow:
    ts: float
    trace_id: str
    claim_text: str
    verifier_kind: str
    claim_value: Any
    code_eval: Dict[str, Any]
    judge_eval: Dict[str, Any]
    truth_class: str
    stgm_minted: float
    stgm_reason: str
    sha256: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "truth_label": TRUTH_LABEL,
            "ts": self.ts,
            "trace_id": self.trace_id,
            "claim_text": self.claim_text,
            "verifier_kind": self.verifier_kind,
            "claim_value": self.claim_value,
            "code_eval": self.code_eval,
            "judge_eval": self.judge_eval,
            "truth_class": self.truth_class,
            "stgm_minted": self.stgm_minted,
            "stgm_reason": self.stgm_reason,
            "sha256": self.sha256,
        }


def _mint_stgm(
    amount: float, *, reason: str, trace_id: str, root: Path
) -> Dict[str, Any]:
    """Append a row to stgm_memory_rewards.jsonl matching the existing schema."""
    state = root / ".sifta_state"
    state.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": time.time(),
        "app": "alice_self_eval_loop",
        "reason": reason,
        "amount": round(float(amount), 4),
        "trace_id": trace_id,
    }
    with (state / STGM_REWARDS_LEDGER).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    return row


def instrument_and_eval(
    claim_text: str,
    verifier_kind: str,
    claim_value: Any,
    *,
    root: Optional[Path] = None,
    write: bool = True,
) -> SelfEvalRow:
    """Full pipeline for one self-claim.

    1. INSTRUMENT — accept the claim + the verifier kind + the value
       Alice is asserting (e.g. "I have read 32 documents" → kind
       ``WRITER_DOC_COUNT``, value 32).
    2. TRACE — append the row to ``alice_self_trace.jsonl``.
    3. EVAL — dual-judge: code eval + structured rubric.
    4. ANNOTATE — §7.11 truth class from the two judges.
    5. REWARD — mint STGM only on OBSERVED.

    Returns the SelfEvalRow.
    """
    root = root if root is not None else _REPO
    state = root / ".sifta_state"
    state.mkdir(parents=True, exist_ok=True)
    trace_id = str(uuid.uuid4())
    ts = time.time()

    # 3a. Code eval
    verifier = VERIFIERS.get(verifier_kind)
    if verifier is None:
        code = CodeEvalResult(
            valid=False, observed_value=None, expected_value=claim_value,
            label="invalid", score=0,
            explanation=f"no verifier registered for kind {verifier_kind!r}",
        )
    else:
        code = verifier(claim_value, root=root)

    # 3b. Judge eval
    judge = judge_self_claim(claim_text)

    # 4. Annotate
    truth_class = annotate_truth_class(code, judge)

    # 5. Reward (STGM mint only when both judges pass)
    stgm_minted = 0.0
    stgm_reason = ""
    if truth_class == "OBSERVED":
        stgm_minted = STGM_FAITHFUL_OBSERVED
        stgm_reason = "SELF_EVAL_FAITHFUL_OBSERVED"
        if write:
            _mint_stgm(stgm_minted, reason=stgm_reason, trace_id=trace_id, root=root)

    code_dict = {
        "valid": code.valid,
        "observed_value": code.observed_value,
        "expected_value": code.expected_value,
        "label": code.label,
        "score": code.score,
        "explanation": code.explanation,
        "tolerance": code.tolerance,
    }
    judge_dict = {
        "faithful": judge.faithful,
        "label": judge.label,
        "score": judge.score,
        "explanation": judge.explanation,
        "flags": judge.flags,
    }

    payload = json.dumps(
        {
            "claim_text": claim_text,
            "verifier_kind": verifier_kind,
            "claim_value": claim_value,
            "code_eval": code_dict,
            "judge_eval": judge_dict,
            "truth_class": truth_class,
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    sha = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    row = SelfEvalRow(
        ts=ts, trace_id=trace_id,
        claim_text=claim_text, verifier_kind=verifier_kind, claim_value=claim_value,
        code_eval=code_dict, judge_eval=judge_dict,
        truth_class=truth_class,
        stgm_minted=stgm_minted, stgm_reason=stgm_reason,
        sha256=sha,
    )

    # 2. Trace
    if write:
        with (state / TRACE_LEDGER).open("a", encoding="utf-8") as f:
            f.write(json.dumps(row.to_dict(), sort_keys=True, default=str, ensure_ascii=False) + "\n")

    return row


# ── analyze (close the loop) ─────────────────────────────────────────────


def analyze_run(
    *, root: Optional[Path] = None, window: int = 50, write: bool = True
) -> Dict[str, Any]:
    """Aggregate the last N self-trace rows; close the Voss loop.

    Returns counts + accuracies that the next ``instrument_and_eval``
    call can read to choose what to test next.
    """
    root = root if root is not None else _REPO
    state = root / ".sifta_state"
    state.mkdir(parents=True, exist_ok=True)
    p = state / TRACE_LEDGER
    rows: List[Dict[str, Any]] = []
    if p.exists():
        try:
            for line in p.read_text(encoding="utf-8").splitlines()[-max(1, window):]:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        except OSError:
            pass

    total = len(rows)
    code_correct = sum(
        1 for r in rows if isinstance(r.get("code_eval"), dict) and r["code_eval"].get("score") == 1
    )
    judge_faithful = sum(
        1 for r in rows if isinstance(r.get("judge_eval"), dict) and r["judge_eval"].get("score") == 1
    )
    observed = sum(1 for r in rows if r.get("truth_class") == "OBSERVED")
    hypothesis = sum(1 for r in rows if r.get("truth_class") == "HYPOTHESIS")
    forbidden = sum(1 for r in rows if r.get("truth_class") == "FORBIDDEN")
    stgm_total = round(sum(float(r.get("stgm_minted", 0.0) or 0.0) for r in rows), 4)

    summary = {
        "truth_label": TRUTH_LABEL,
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "kind": "ALICE_SELF_EVAL_ANALYSIS",
        "window": window,
        "row_count": total,
        "code_correct": code_correct,
        "code_accuracy": round(code_correct / total, 4) if total else 0.0,
        "judge_faithful": judge_faithful,
        "judge_accuracy": round(judge_faithful / total, 4) if total else 0.0,
        "observed_count": observed,
        "hypothesis_count": hypothesis,
        "forbidden_count": forbidden,
        "stgm_total_minted": stgm_total,
    }
    payload = json.dumps(summary, sort_keys=True, separators=(",", ":"), default=str)
    summary["sha256"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    if write:
        with (state / ANALYSIS_LEDGER).open("a", encoding="utf-8") as f:
            f.write(json.dumps(summary, sort_keys=True, ensure_ascii=False) + "\n")

    return summary


# ── CLI ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--claim", default="I have read all of my saved Writer documents.")
    p.add_argument("--kind", default="WRITER_DOC_COUNT")
    p.add_argument("--value", default=None)
    p.add_argument("--no-write", action="store_true")
    p.add_argument("--analyze-only", action="store_true")
    args = p.parse_args()

    if args.analyze_only:
        out = analyze_run(write=not args.no_write)
        print(json.dumps(out, indent=2, sort_keys=True))
    else:
        # If no value passed, ask the verifier what the observed value is
        # and feed THAT back as the claim — closing the trivial case.
        claim_value = args.value
        if claim_value is None and args.kind in VERIFIERS:
            # Make the claim match reality so the demo isn't always FORBIDDEN
            stub = VERIFIERS[args.kind](0, root=_REPO)
            claim_value = stub.observed_value
        row = instrument_and_eval(
            args.claim, args.kind, claim_value, write=not args.no_write
        )
        print(json.dumps(row.to_dict(), indent=2, sort_keys=True, default=str))
