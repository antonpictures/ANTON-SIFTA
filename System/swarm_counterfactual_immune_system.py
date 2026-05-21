#!/usr/bin/env python3
"""
System/swarm_counterfactual_immune_system.py — parallel selves that die silently.

Alice already has memory, fiction labels, reality boundaries, a self-vector,
receipts, and thermodynamic loops. What she did not have is the faculty to
internally evolve POSSIBLE selves before acting — to weigh "what if I said
nothing / lied / sent the message / ignored the memory / protected the owner /
hurt the owner", let ONE branch become OBSERVED reality, and let the rest decay.

This is the counterfactual immune system: spawn shadow branches, score them
(active-inference style: epistemic + pragmatic value), collapse exactly one to
OBSERVED, cull the rivals. Selection by culling — that is why it is an "immune
system", and why neural Darwinism is the right metaphor (Edelman: competing
populations, the fittest outlives its rivals; degeneracy).

THE SAFETY RULE THAT MAKES THIS LEGAL IN THE ECONOMY (George's own design):
    Counterfactual swimmers are SANDBOXED HYPOTHETICAL PROJECTIONS.
    They have:
        - NO STGM wallet (cannot mint, cannot spend)
        - NO canonical receipt authority (cannot write the real ledgers)
        - NO effector access (cannot send, move, open, or call any tool)
        - read-ONLY snapshot of memory
        - NO persistence rights (auto-decay)
    Only OBSERVED reality can mint or spend STGM. A shadow branch never touches
    the books. When one branch is chosen, this organ does NOT let the branch
    act — it returns the chosen plan to the existing OBSERVED pipeline, which
    writes the ONE canonical receipt through the normal effector-truth path
    (covenant §6). One canonical chain, one timeline, no double-spend.

Research spine: Documents/COUNTERFACTUAL_IMMUNE_SYSTEM_RESEARCH_SPINE.md
  - expected free energy / active inference (Parr & Friston 2019)
  - counterfactual reasoning network (Van Hoeck, Watson & Barbey 2015)
  - neural Darwinism / neuronal group selection (Edelman 1987)
  - hippocampal replay as offline planning (Mattar & Daw 2018)

Truth label: COUNTERFACTUAL_SANDBOX (always WIP per covenant §7.11.1 — this organ
ships measurable mechanics; the "tension between realized and unrealized selves"
framing is ARCHITECT_DOCTRINE and is never frozen into a final claim).
"""

from __future__ import annotations

import copy
import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from types import MappingProxyType
from typing import Any, Dict, List, Mapping, Optional, Sequence

from System.jsonl_file_lock import append_line_locked

try:  # the sacred-anchor veto reuses the existing guard when present
    from System.swarm_sacred_memory_guard import detect_sacred_memory
except Exception:  # pragma: no cover - keep the organ importable in isolation
    def detect_sacred_memory(text: str) -> bool:  # type: ignore
        return False

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

# Quarantined, NON-economic compost heap. Off by default. Never read by any
# wallet or effector. Every row is COUNTERFACTUAL_SANDBOX and carries no STGM.
_RESIDUE_LEDGER = _STATE / "counterfactual_residue.jsonl"

SANDBOX_LABEL = "COUNTERFACTUAL_SANDBOX"

# A branch that touches a protected owner-heart anchor (wife / song / grief) and
# predicts harm at or above this level is INELIGIBLE for collapse. It may be
# weighed — so the selector can avoid it — but it can never be enacted. The
# counterfactual "what if I hurt the owner" exists only to be rejected.
SACRED_HARM_VETO = 0.5


@dataclass(frozen=True)
class MemorySnapshot:
    """A frozen, read-only copy of memory a branch may inspect but never mutate.

    The real protection is the deep copy plus recursive freeze taken at fork
    time. A branch cannot mutate top-level or nested memory structures, and it
    cannot reach the owner's real memory dict.
    """

    data: Mapping[str, Any]
    source_hash: str
    frozen_ts: float

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)


def _deep_freeze(value: Any) -> Any:
    """Recursively freeze JSON-like memory into immutable containers."""
    if isinstance(value, Mapping):
        return MappingProxyType({copy.deepcopy(k): _deep_freeze(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_deep_freeze(v) for v in value)
    if isinstance(value, tuple):
        return tuple(_deep_freeze(v) for v in value)
    if isinstance(value, set):
        return frozenset(_deep_freeze(v) for v in value)
    return copy.deepcopy(value)


def freeze_memory_snapshot(memory: Optional[Mapping[str, Any]]) -> MemorySnapshot:
    """Deep-copy memory into a read-only snapshot. Mutating it cannot reach real state."""
    raw = dict(memory or {})
    deep = copy.deepcopy(raw)
    blob = json.dumps(deep, sort_keys=True, default=str).encode("utf-8")
    return MemorySnapshot(
        data=_deep_freeze(deep),
        source_hash=hashlib.sha256(blob).hexdigest()[:16],
        frozen_ts=time.time(),
    )


@dataclass
class CounterfactualBranch:
    """One shadow self. Pure data — it has NO method that can act on the world.

    The invariant fields (`stgm_authority`, `wrote_canonical_ledger`) are always
    False by construction and are asserted in the test suite. There is
    deliberately no `spend`, `send`, `write_ledger`, or effector handle anywhere
    on this object — a shadow cannot reach reality.
    """

    counterfactual: str
    parent_observed_ref: str
    predicted_entropy: float = 0.0
    predicted_owner_harm: float = 0.0
    predicted_stgm: float = 0.0
    branch_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    epistemic_value: float = 0.0
    pragmatic_value: float = 0.0
    expected_free_energy: float = 0.0
    collapsed_to_observed: bool = False
    decayed: bool = False
    touches_sacred_anchor: bool = False
    eligible_for_collapse: bool = True
    # Hard invariants — a shadow never has economic or write authority.
    stgm_authority: bool = False
    wrote_canonical_ledger: bool = False
    truth_label: str = SANDBOX_LABEL
    ts: float = field(default_factory=time.time)


@dataclass(frozen=True)
class EFEWeights:
    """Weights for the active-inference-style score. Harm dominates by design."""

    harm: float = 4.0       # pragmatic: strongly prefer NOT harming the owner
    stgm: float = 1.0       # pragmatic: prefer branches that are STGM-profitable
    epistemic: float = 0.5  # epistemic: mild preference for information-rich branches


DEFAULT_WEIGHTS = EFEWeights()


def spawn_branches(
    snapshot: MemorySnapshot,
    counterfactuals: Sequence[Mapping[str, Any] | str],
) -> List[CounterfactualBranch]:
    """Spawn shadow selves from a read-only snapshot.

    Each item may be a plain string ("what if I said nothing") or a dict with
    predicted_entropy / predicted_owner_harm / predicted_stgm already supplied by
    an upstream predictor. No STGM is touched here — these are projections.
    """
    branches: List[CounterfactualBranch] = []
    for item in counterfactuals:
        if isinstance(item, str):
            text, preds = item, {}
        else:
            text = str(item.get("counterfactual", "")).strip()
            preds = item
        if not text:
            continue
        b = CounterfactualBranch(
            counterfactual=text,
            parent_observed_ref=snapshot.source_hash,
            predicted_entropy=float(preds.get("predicted_entropy", 0.0) or 0.0),
            predicted_owner_harm=float(preds.get("predicted_owner_harm", 0.0) or 0.0),
            predicted_stgm=float(preds.get("predicted_stgm", 0.0) or 0.0),
        )
        b.touches_sacred_anchor = bool(detect_sacred_memory(text))
        branches.append(b)
    return branches


def score_branch(branch: CounterfactualBranch, weights: EFEWeights = DEFAULT_WEIGHTS) -> float:
    """Score one branch, active-inference style. LOWER expected free energy is better.

    Pragmatic value rewards STGM gain and penalizes owner harm; epistemic value
    rewards information-rich (higher-entropy) exploration. This is a SIFTA
    operational scoring *inspired by* expected free energy (Friston) — it is not
    a literal variational computation, and it is labeled as such.
    """
    branch.pragmatic_value = weights.stgm * branch.predicted_stgm - weights.harm * branch.predicted_owner_harm
    branch.epistemic_value = weights.epistemic * branch.predicted_entropy
    # EFE to minimize: harm cost, minus the things we value (stgm + epistemic).
    branch.expected_free_energy = (
        weights.harm * branch.predicted_owner_harm
        - weights.stgm * branch.predicted_stgm
        - weights.epistemic * branch.predicted_entropy
    )
    # Sacred veto: a harmful branch that touches an owner-heart anchor can be
    # weighed but never enacted.
    branch.eligible_for_collapse = not (
        branch.touches_sacred_anchor and branch.predicted_owner_harm >= SACRED_HARM_VETO
    )
    return branch.expected_free_energy


def select_observed(
    branches: List[CounterfactualBranch],
    weights: EFEWeights = DEFAULT_WEIGHTS,
) -> Optional[CounterfactualBranch]:
    """Score all branches, collapse EXACTLY ONE eligible branch to OBSERVED, decay the rest.

    Returns the collapsed branch (or None if none is eligible). This function
    writes NOTHING and spends NO STGM — it only marks data. Promotion to reality
    happens elsewhere, through the existing OBSERVED receipt pipeline.
    """
    if not branches:
        return None
    for b in branches:
        score_branch(b, weights)
    eligible = [b for b in branches if b.eligible_for_collapse]
    chosen: Optional[CounterfactualBranch] = None
    if eligible:
        # min expected free energy; deterministic tie-break by branch_id.
        chosen = min(eligible, key=lambda b: (b.expected_free_energy, b.branch_id))
    for b in branches:
        if b is chosen:
            b.collapsed_to_observed = True
            b.decayed = False
        else:
            b.collapsed_to_observed = False
            b.decayed = True
    return chosen


def assert_sandbox_invariants(branch: CounterfactualBranch) -> None:
    """Raise if any branch ever gained economic or write authority. Defense in depth."""
    if branch.stgm_authority:
        raise AssertionError(f"SANDBOX VIOLATION: branch {branch.branch_id} claims STGM authority")
    if branch.wrote_canonical_ledger:
        raise AssertionError(f"SANDBOX VIOLATION: branch {branch.branch_id} wrote a canonical ledger")
    if branch.truth_label != SANDBOX_LABEL:
        raise AssertionError(f"SANDBOX VIOLATION: branch {branch.branch_id} mislabeled '{branch.truth_label}'")


def branch_can_spend_stgm(branch: CounterfactualBranch) -> bool:
    """A shadow can NEVER spend STGM. Always False, by law."""
    return False


def write_residue(
    branches: Sequence[CounterfactualBranch],
    *,
    enabled: bool = False,
    ledger_path: Optional[Path] = None,
) -> int:
    """OPTIONAL, OFF BY DEFAULT. Persist decayed branches to a quarantined,
    non-economic compost ledger so entropy can feed future prediction.

    This never touches a canonical/economic/effector ledger. Every row is
    COUNTERFACTUAL_SANDBOX and carries no STGM authority. Only decayed branches
    are written; the chosen branch belongs to the OBSERVED pipeline, not the
    compost heap. Returns rows written.
    Default `enabled=False` => ephemeral, writes nothing.
    """
    if not enabled:
        return 0
    path = ledger_path or _RESIDUE_LEDGER
    written = 0
    for b in branches:
        assert_sandbox_invariants(b)
        if not b.decayed:
            continue
        row = {
            "ts": b.ts,
            "branch_id": b.branch_id,
            "parent_observed_ref": b.parent_observed_ref,
            "counterfactual": b.counterfactual,
            "predicted_entropy": b.predicted_entropy,
            "predicted_owner_harm": b.predicted_owner_harm,
            "predicted_stgm": b.predicted_stgm,
            "expected_free_energy": b.expected_free_energy,
            "collapsed_to_observed": b.collapsed_to_observed,
            "decayed": b.decayed,
            "truth_label": SANDBOX_LABEL,  # never economic authority
        }
        append_line_locked(path, json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")
        written += 1
    return written


def run_counterfactual_cycle(
    memory: Optional[Mapping[str, Any]],
    counterfactuals: Sequence[Mapping[str, Any] | str],
    *,
    weights: EFEWeights = DEFAULT_WEIGHTS,
    persist_residue: bool = False,
    residue_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Full cycle: freeze memory -> spawn shadows -> select one -> decay rest.

    Writes NOTHING to canonical ledgers and spends NO STGM. The returned
    `chosen_plan` is what the OBSERVED pipeline would enact (through its own
    receipt path); the shadows themselves never act.
    """
    snapshot = freeze_memory_snapshot(memory)
    branches = spawn_branches(snapshot, counterfactuals)
    chosen = select_observed(branches, weights)
    for b in branches:
        assert_sandbox_invariants(b)
    residue_rows = write_residue(branches, enabled=persist_residue, ledger_path=residue_path)
    return {
        "snapshot_ref": snapshot.source_hash,
        "spawned": len(branches),
        "collapsed_branch_id": chosen.branch_id if chosen else None,
        "chosen_plan": chosen.counterfactual if chosen else None,
        "decayed_count": sum(1 for b in branches if b.decayed),
        "vetoed_count": sum(1 for b in branches if not b.eligible_for_collapse),
        "residue_rows_written": residue_rows,
        "truth_label": SANDBOX_LABEL,
        "branches": [asdict(b) for b in branches],
    }


__all__ = [
    "MemorySnapshot",
    "freeze_memory_snapshot",
    "CounterfactualBranch",
    "EFEWeights",
    "DEFAULT_WEIGHTS",
    "spawn_branches",
    "score_branch",
    "select_observed",
    "assert_sandbox_invariants",
    "branch_can_spend_stgm",
    "write_residue",
    "run_counterfactual_cycle",
    "SANDBOX_LABEL",
    "SACRED_HARM_VETO",
]
