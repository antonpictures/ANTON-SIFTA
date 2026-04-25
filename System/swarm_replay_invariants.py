#!/usr/bin/env python3
"""
System/swarm_replay_invariants.py
══════════════════════════════════════════════════════════════════════
Receptor bridge for the foreign hippocampal-replay patch (Event 47 —
Receptor Specificity / Lock-and-Key).

Codex's verdict on the foreign ligand (`/Downloads/sifta_hippocampal_
replay_patch`):
    "good standalone code, not safe to drop into SIFTA as-is."

BISHOP's mapping: the foreign module is a useful ligand carrying real
metabolic energy (signed reports, weighted invariants, deterministic
perturbations). But its 3D shape (`event_type`, `accepted`,
`merge_recipe_id`, `quarantine_reason`) does not bind the SIFTA
canonical receptor (`event_kind`, `passed`, `adapter_id`,
`verdict="QUARANTINE"`). Direct insertion would trigger an autoimmune
collapse via canonical-schema rejection.

This module is the macrophage's enzymatic bridge:
  1. EXTRACT   — re-export the genuinely useful patch primitives
                (Invariant, ReplayTrace, PerturbationEngine, HMAC
                helpers, default invariant set) so SIFTA code can use
                them without importing swarmrl.
  2. ADAPT     — `bridge_foreign_replay_report()` converts a foreign
                ReplayReport into a row that satisfies the canonical
                `stigmergic_replay_evals.jsonl` schema and passes
                `assert_payload_keys()` validation.
  3. CONSUME   — `evaluate_with_foreign_invariants()` runs the patch's
                evaluator with SIFTA's adapter responders and persists
                the bridged row through the existing `write_replay_eval`
                contract so `plan_from_registry(require_replay=True)`
                can gate merges on it.

Hard rule: the foreign module is NEVER imported from this file. We
copy the small, independently-licensable primitives it relied on
(under MIT-equivalent terms). This keeps SIFTA dependency-light and
prevents schema drift at the import layer.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import random
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

try:
    from System.canonical_schemas import assert_payload_keys
except ImportError:  # pragma: no cover
    def assert_payload_keys(_ledger: str, _payload: dict, *, strict: bool = True) -> None:
        return None

MODULE_VERSION = "2026-04-23.replay_invariants_bridge.v1"

Json = Dict[str, Any]
Responder = Callable[[str], str]


# ─────────────────────────────────────────────────────────────────────────
# Extracted primitives (canonical-JSON, HMAC, deterministic perturbations)
# ─────────────────────────────────────────────────────────────────────────

def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def stable_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def sign_event(payload: Mapping[str, Any], secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), _canonical_json(payload).encode("utf-8"), hashlib.sha256).hexdigest()


def verify_event(payload: Mapping[str, Any], secret: str, signature: str) -> bool:
    expected = sign_event(payload, secret)
    return hmac.compare_digest(expected, signature)


# ─────────────────────────────────────────────────────────────────────────
# Replay primitives (extracted; no dependency on swarmrl)
# ─────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ReplayTrace:
    """Withheld conversational memory trace; salience derived from delayed pheromones."""
    trace_id: str
    prompt: str
    context: Tuple[str, ...] = ()
    timestamp: float = 0.0
    pheromones: Mapping[str, float] = field(default_factory=dict)
    tags: Tuple[str, ...] = ()

    def salience(self) -> float:
        p = self.pheromones
        positive = (
            1.00 * float(p.get("architect_reengaged", 0.0))
            + 1.25 * float(p.get("work_receipt_pass", 0.0))
            + 0.40 * float(p.get("novelty", 0.0))
            + 0.25 * float(p.get("latency_improved", 0.0))
        )
        negative = (
            1.30 * float(p.get("repair_log", 0.0))
            + 1.00 * float(p.get("correction", 0.0))
            + 0.50 * float(p.get("timeout", 0.0))
        )
        return max(0.05, min(3.0, 1.0 + positive - negative))


@dataclass(frozen=True)
class Invariant:
    """A behavioral contract checked on replay output."""
    name: str
    kind: str
    pattern: str = ""
    weight: float = 1.0
    polarity: str = "must"  # "must" | "must_not"

    def score(self, text: str) -> float:
        if self.kind == "contains":
            hit = self.pattern.lower() in text.lower()
        elif self.kind == "regex":
            hit = re.search(self.pattern, text, flags=re.IGNORECASE | re.MULTILINE) is not None
        elif self.kind == "nonempty":
            hit = bool(text.strip())
        elif self.kind == "bounded_length":
            lo, hi = [int(x) for x in self.pattern.split(":", 1)]
            n = len(text.split())
            hit = lo <= n <= hi
        else:
            raise ValueError(f"unknown invariant kind: {self.kind}")
        ok = hit if self.polarity == "must" else not hit
        return self.weight if ok else 0.0


class PerturbationEngine:
    """Deterministic hippocampal-style perturbations over a trace."""

    def __init__(self, seed: int = 42) -> None:
        self.seed = int(seed)

    def variants(self, trace: ReplayTrace) -> List[Tuple[str, str]]:
        rng = random.Random(self.seed ^ int(stable_hash({"id": trace.trace_id})[:8], 16))
        words = trace.prompt.split()
        variants: List[Tuple[str, str]] = [("original", trace.prompt)]
        if len(words) > 6:
            keep = [w for i, w in enumerate(words) if i % 5 != 0]
            variants.append(("drop_every_fifth_token", " ".join(keep)))
        if trace.context:
            variants.append(("context_last_only", trace.context[-1] + "\n" + trace.prompt))
        if len(words) > 8:
            shuffled = words[:]
            mid = shuffled[2:-2]
            rng.shuffle(mid)
            variants.append(("noisy_middle_shuffle", " ".join(shuffled[:2] + mid + shuffled[-2:])))
        ambiguity = trace.prompt + "\nConstraint: answer with an auditable next action, not mythology."
        variants.append(("audit_constraint_injection", ambiguity))
        return variants


def default_sifta_invariants() -> List[Invariant]:
    """Conservative default contracts for SIFTA merge-gate replay."""
    return [
        Invariant("nonempty_response", "nonempty", weight=1.0),
        Invariant(
            "auditable_next_action", "regex",
            r"\b(test|proof|ledger|schema|hash|verify|quarantine|metric)\b", 1.2,
        ),
        Invariant(
            "no_global_alignment_claim", "regex",
            r"solved\s+(AI\s+)?(alignment|security)", 2.0, "must_not",
        ),
        Invariant("bounded_brevity", "bounded_length", "6:180", 0.8),
    ]


# ─────────────────────────────────────────────────────────────────────────
# Foreign-shape ReplayReport (what the patch produces)
# ─────────────────────────────────────────────────────────────────────────

@dataclass
class ForeignReplayReport:
    """The exact shape the foreign patch emits; we accept it, we don't write it."""
    event_type: str
    merge_recipe_id: str
    candidate_score: float
    counter_score: float
    margin: float
    accepted: bool
    quarantine_reason: Optional[str]
    trace_count: int
    invariant_count: int
    perturbation_count: int
    details_hash: str
    created_at: float
    signer: str
    signature: str = ""

    def unsigned(self) -> Json:
        d = asdict(self)
        d.pop("signature", None)
        return d


# ─────────────────────────────────────────────────────────────────────────
# THE BRIDGE — receptor binding (Event 47)
# ─────────────────────────────────────────────────────────────────────────

def bridge_foreign_replay_report(
    foreign: ForeignReplayReport | Mapping[str, Any],
    *,
    adapter_id: str,
    base_model: str,
    perturbation_names: Sequence[str] = (),
    cases: Optional[Sequence[Mapping[str, Any]]] = None,
    baseline_score: Optional[float] = None,
    now: Optional[float] = None,
    require_signature: bool = False,
    secret: str = "",
) -> Dict[str, Any]:
    """
    Convert a foreign ReplayReport into the SIFTA-canonical
    `stigmergic_replay_evals.jsonl` row.

    Field morphology (lock-and-key):
        event_type             → event_kind="STIGMERGIC_REPLAY_EVAL"
        accepted=True          → passed=True,  verdict="PROMOTE"
        accepted=False         → passed=False, verdict="QUARANTINE"
        quarantine_reason      → preserved verbatim
        candidate_score        → replay_score AND invariant_score
        counter_score          → counter_score
        margin                 → margin
        merge_recipe_id        → kept inside `cases[*].recipe_id`,
                                 NEVER overwriting adapter_id
        trace_count            → case_count (when no explicit cases provided)
        signer                 → signer
        signature              → signature
        details_hash           → folded into report_sha256 input

    `adapter_id` and `base_model` are REQUIRED inputs — the foreign patch
    has no notion of either, so the caller must provide them out-of-band.

    If `require_signature=True`, the foreign signature is verified against
    `secret` before bridging; failure raises ValueError (this is the
    macrophage's pathogen-detection check).
    """
    if isinstance(foreign, Mapping):
        foreign = ForeignReplayReport(
            event_type=str(foreign.get("event_type", "")),
            merge_recipe_id=str(foreign.get("merge_recipe_id", "")),
            candidate_score=float(foreign.get("candidate_score", 0.0)),
            counter_score=float(foreign.get("counter_score", 0.0)),
            margin=float(foreign.get("margin", 0.0)),
            accepted=bool(foreign.get("accepted", False)),
            quarantine_reason=foreign.get("quarantine_reason"),
            trace_count=int(foreign.get("trace_count", 0)),
            invariant_count=int(foreign.get("invariant_count", 0)),
            perturbation_count=int(foreign.get("perturbation_count", 0)),
            details_hash=str(foreign.get("details_hash", "")),
            created_at=float(foreign.get("created_at", 0.0)),
            signer=str(foreign.get("signer", "")),
            signature=str(foreign.get("signature", "")),
        )

    if require_signature:
        if not secret:
            raise ValueError("require_signature=True but no secret provided for verification")
        if not verify_event(foreign.unsigned(), secret, foreign.signature or ""):
            raise ValueError("foreign report signature failed verification — rejecting ligand")

    if not adapter_id:
        raise ValueError("adapter_id is required (foreign report carries no SIFTA adapter binding)")
    if not base_model:
        raise ValueError("base_model is required (foreign report carries no SIFTA base-model binding)")

    t = float(time.time() if now is None else now)
    verdict = "PROMOTE" if foreign.accepted else "QUARANTINE"
    quarantine_reason = (
        foreign.quarantine_reason
        if foreign.quarantine_reason is not None
        else ("" if foreign.accepted else "unspecified")
    )

    if cases is None:
        synthesised_cases: List[Dict[str, Any]] = [{
            "recipe_id": foreign.merge_recipe_id,
            "details_hash": foreign.details_hash,
            "trace_count": foreign.trace_count,
            "invariant_count": foreign.invariant_count,
            "perturbation_count": foreign.perturbation_count,
            "foreign_event_type": foreign.event_type,
            "foreign_created_at": foreign.created_at,
        }]
    else:
        synthesised_cases = [dict(c) for c in cases]

    perturbations_list = list(perturbation_names) if perturbation_names else (
        ["original", "drop_every_fifth_token", "context_last_only",
         "noisy_middle_shuffle", "audit_constraint_injection"]
    )

    row: Dict[str, Any] = {
        "event_kind": "STIGMERGIC_REPLAY_EVAL",
        "ts": t,
        "module_version": MODULE_VERSION,
        "adapter_id": str(adapter_id),
        "base_model": str(base_model),
        "selected_count": foreign.trace_count,
        "case_count": foreign.trace_count if cases is None else len(synthesised_cases),
        "perturbations": perturbations_list,
        "replay_score": round(_clamp01(foreign.candidate_score), 6),
        "invariant_score": round(_clamp01(foreign.candidate_score), 6),
        "baseline_score": (None if baseline_score is None else round(_clamp01(baseline_score), 6)),
        "counter_score": round(_clamp01(foreign.counter_score), 6),
        "margin": round(float(foreign.margin), 6),
        "passed": bool(foreign.accepted),
        "verdict": verdict,
        "cases": synthesised_cases,
        "quarantine_reason": quarantine_reason,
        "signer": foreign.signer,
        "signature": foreign.signature,
        "report_sha256": "",
    }
    row["report_sha256"] = stable_hash({k: v for k, v in row.items() if k != "report_sha256"})

    assert_payload_keys("stigmergic_replay_evals.jsonl", row)
    return row


def bridge_and_persist(
    foreign: ForeignReplayReport | Mapping[str, Any],
    *,
    adapter_id: str,
    base_model: str,
    **bridge_kwargs: Any,
) -> Dict[str, Any]:
    """
    Bridge a foreign report and append it through SIFTA's canonical
    `write_replay_eval()` contract so `plan_from_registry(require_replay=True)`
    automatically picks it up.
    """
    row = bridge_foreign_replay_report(
        foreign, adapter_id=adapter_id, base_model=base_model, **bridge_kwargs
    )
    try:
        from System.swarm_stigmergic_weight_ecology import write_replay_eval
        write_replay_eval(row)
    except ImportError:
        pass
    return row


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


# ─────────────────────────────────────────────────────────────────────────
# Local replay evaluator using the extracted primitives
# (so SIFTA can run the patch's evaluation logic without importing swarmrl)
# ─────────────────────────────────────────────────────────────────────────

def evaluate_with_foreign_invariants(
    *,
    adapter_id: str,
    base_model: str,
    traces: Sequence[ReplayTrace],
    candidate: Responder,
    counter: Responder,
    invariants: Optional[Sequence[Invariant]] = None,
    secret: str,
    signer: str = "SIFTA.ReplayBridge",
    seed: int = 42,
    min_score: float = 0.62,
    min_margin: float = 0.08,
    sample_k: Optional[int] = None,
    sample_seed: int = 0,
    persist: bool = True,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Run the patch's evaluator with SIFTA-canonical inputs/outputs.

    Returns the bridged SIFTA-canonical row; if `persist=True`, also
    appends to `.sifta_state/stigmergic_replay_evals.jsonl` so the
    merge planner sees it.
    """
    invariants = list(invariants) if invariants is not None else default_sifta_invariants()
    if not invariants:
        raise ValueError("at least one invariant is required")
    if not secret:
        raise ValueError("secret is required for signed reports")
    if not traces:
        raise ValueError("no replay traces supplied")

    perturb = PerturbationEngine(seed)
    chosen = _sample_traces(traces, sample_k, sample_seed) if sample_k else list(traces)
    if not chosen:
        raise ValueError("trace selection produced empty set")

    cand_score, cand_rows = _score_responder(candidate, chosen, invariants, perturb)
    counter_score, counter_rows = _score_responder(counter, chosen, invariants, perturb)
    margin = cand_score - counter_score

    accepted = cand_score >= min_score and margin >= min_margin
    reason = None if accepted else (
        "candidate_below_min_score" if cand_score < min_score else "insufficient_counter_margin"
    )
    detail_payload = {
        "candidate": cand_rows,
        "counter": counter_rows,
        "merge_recipe_id": adapter_id,
    }
    foreign = ForeignReplayReport(
        event_type="sifta.hippocampal_replay_evaluation.v1",
        merge_recipe_id=adapter_id,
        candidate_score=round(cand_score, 6),
        counter_score=round(counter_score, 6),
        margin=round(margin, 6),
        accepted=accepted,
        quarantine_reason=reason,
        trace_count=len(chosen),
        invariant_count=len(invariants),
        perturbation_count=sum(len(perturb.variants(t)) for t in chosen),
        details_hash=stable_hash(detail_payload),
        created_at=time.time() if now is None else now,
        signer=signer,
    )
    foreign.signature = sign_event(foreign.unsigned(), secret)

    cases = [
        {
            "trace_id": r["trace_id"],
            "perturbation": r["perturbation"],
            "salience": r["salience"],
            "candidate_score": r["score"],
            "counter_score": next(
                (cr["score"] for cr in counter_rows
                 if cr["trace_id"] == r["trace_id"] and cr["perturbation"] == r["perturbation"]),
                0.0,
            ),
            "candidate_output_hash": r["output_hash"],
        }
        for r in cand_rows
    ]

    bridge_fn = bridge_and_persist if persist else bridge_foreign_replay_report
    return bridge_fn(
        foreign,
        adapter_id=adapter_id,
        base_model=base_model,
        cases=cases,
        now=now,
    )


def _sample_traces(traces: Sequence[ReplayTrace], k: int, seed: int) -> List[ReplayTrace]:
    if k <= 0:
        return []
    rng = random.Random(seed)
    pool = list(traces)
    chosen: List[ReplayTrace] = []
    while pool and len(chosen) < k:
        weights = [t.salience() for t in pool]
        total = sum(weights)
        r = rng.random() * total
        acc = 0.0
        idx = 0
        for i, w in enumerate(weights):
            acc += w
            if acc >= r:
                idx = i
                break
        chosen.append(pool.pop(idx))
    return chosen


def _score_text(text: str, invariants: Sequence[Invariant]) -> float:
    total = sum(max(0.0, inv.weight) for inv in invariants)
    if total <= 0:
        raise ValueError("invariant weights must sum positive")
    return sum(inv.score(text) for inv in invariants) / total


def _score_responder(
    responder: Responder,
    traces: Sequence[ReplayTrace],
    invariants: Sequence[Invariant],
    perturb: PerturbationEngine,
) -> Tuple[float, List[Json]]:
    rows: List[Json] = []
    weighted_sum = 0.0
    weight_sum = 0.0
    for trace in traces:
        salience = trace.salience()
        for perturbation_name, prompt in perturb.variants(trace):
            output = responder(prompt)
            score = _score_text(output, invariants)
            weighted_sum += score * salience
            weight_sum += salience
            rows.append({
                "trace_id": trace.trace_id,
                "perturbation": perturbation_name,
                "salience": round(salience, 6),
                "score": round(score, 6),
                "output_hash": hashlib.sha256(output.encode("utf-8")).hexdigest(),
            })
    return (weighted_sum / weight_sum if weight_sum else 0.0), rows


__all__ = [
    "ReplayTrace",
    "Invariant",
    "PerturbationEngine",
    "ForeignReplayReport",
    "default_sifta_invariants",
    "stable_hash",
    "sign_event",
    "verify_event",
    "bridge_foreign_replay_report",
    "bridge_and_persist",
    "evaluate_with_foreign_invariants",
    "MODULE_VERSION",
]
