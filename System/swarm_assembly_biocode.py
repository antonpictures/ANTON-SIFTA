#!/usr/bin/env python3
"""Assembly Theory biocode engine for SIFTA.

This is a symbolic assembly-space organ, not a mass-spectrometry molecular
assembly-index pipeline.

Research anchors:
  * Sharma et al., Nature 2023, DOI 10.1038/s41586-023-06600-9:
    assembly combines assembly index and copy number as evidence of selection.
  * Marshall et al., Entropy 2022, DOI 10.3390/e24070884:
    assembly spaces use shortest construction pathways with reuse of
    constructed sub-objects.

What this module does honestly:
  * computes exact shortest assembly pathways for small strings / biocode;
  * quantifies copy-number weighted assembly for observed ensembles;
  * simulates the Nature 2023 growth equation dN(a+1)/dt = k_d * N(a)^alpha;
  * emits truth labels so UI layers can distinguish symbolic code from wet-lab
    molecular metrology.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


TRUTH_LABEL = "SYMBOLIC_ASSEMBLY_SPACE_ANALOGUE_NOT_MASS_SPEC"
NATURE_2023_DOI = "10.1038/s41586-023-06600-9"
ENTROPY_2022_DOI = "10.3390/e24070884"


@dataclass(frozen=True)
class AssemblyStep:
    """One pathway operation: left + right -> product."""

    left: str
    right: str
    product: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class AssemblyPathway:
    target: str
    assembly_index: int
    alphabet: tuple[str, ...]
    steps: tuple[AssemblyStep, ...]
    exact: bool
    truth_label: str = TRUTH_LABEL
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def pathway_hash(self) -> str:
        payload = json.dumps(self.as_dict(include_hash=False), sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def as_dict(self, *, include_hash: bool = True) -> dict[str, Any]:
        data = {
            "target": self.target,
            "assembly_index": self.assembly_index,
            "alphabet": list(self.alphabet),
            "steps": [s.as_dict() for s in self.steps],
            "exact": self.exact,
            "truth_label": self.truth_label,
            "notes": list(self.notes),
            "research_anchors": {
                "nature_2023": NATURE_2023_DOI,
                "entropy_2022": ENTROPY_2022_DOI,
            },
        }
        if include_hash:
            data["pathway_hash"] = self.pathway_hash
        return data


@dataclass(frozen=True)
class EnsembleAssembly:
    """Copy-number weighted assembly for an observed ensemble."""

    pathways: dict[str, AssemblyPathway]
    copy_numbers: dict[str, int]
    assembly: float
    log10_selection_score: float
    truth_label: str = TRUTH_LABEL

    @property
    def assembly_score(self) -> float:
        """UI-facing alias for the copy-number weighted assembly value."""
        return self.assembly

    @property
    def log_assembly_score(self) -> float:
        """UI-facing alias for the log-scaled selection score."""
        return self.log10_selection_score

    @property
    def observations(self) -> dict[str, int]:
        """UI-facing alias for observed object copy numbers."""
        return dict(self.copy_numbers)

    @property
    def assembly_indices(self) -> dict[str, int]:
        """UI-facing object -> shortest pathway length map."""
        return {obj: path.assembly_index for obj, path in self.pathways.items()}

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": "SIFTA_SYMBOLIC_ENSEMBLE_ASSEMBLY_V1",
            "assembly": self.assembly,
            "assembly_score": self.assembly_score,
            "log10_selection_score": self.log10_selection_score,
            "log_assembly_score": self.log_assembly_score,
            "copy_numbers": dict(sorted(self.copy_numbers.items())),
            "assembly_indices": dict(sorted(self.assembly_indices.items())),
            "pathways": {k: v.as_dict() for k, v in sorted(self.pathways.items())},
            "truth_label": self.truth_label,
            "assembly_equation": "A=sum(exp(a_i)*((n_i-1)/N_T))",
            "research_anchor": NATURE_2023_DOI,
        }


def _normalize_biocode(target: str) -> str:
    s = "".join(str(target or "").split()).upper()
    if not s:
        raise ValueError("target biocode must not be empty")
    return s


def _all_substrings(target: str) -> set[str]:
    return {
        target[i:j]
        for i in range(len(target))
        for j in range(i + 1, len(target) + 1)
    }


def exact_string_assembly_pathway(
    target: str,
    *,
    max_len: int = 14,
    max_states: int = 200_000,
) -> AssemblyPathway:
    """Return a shortest construction pathway for a small symbolic object.

    Starting objects are the target's irreducible symbols. Each step may join
    any two already-constructed objects; constructed sub-objects can be reused.
    Search is restricted to substrings of the target, which is exact for string
    concatenation pathways because non-substrings cannot appear in the final
    concatenation tree.
    """
    target = _normalize_biocode(target)
    if len(target) > max_len:
        return greedy_string_assembly_pathway(
            target,
            note=f"target length {len(target)} exceeds exact max_len {max_len}",
        )

    alphabet = tuple(sorted(set(target)))
    if target in alphabet:
        return AssemblyPathway(
            target=target,
            assembly_index=0,
            alphabet=alphabet,
            steps=(),
            exact=True,
            notes=("single irreducible object",),
        )

    allowed = _all_substrings(target)
    start = frozenset(alphabet)
    queue = deque([(start, tuple())])
    seen = {start}
    states = 0

    while queue:
        state, steps = queue.popleft()
        states += 1
        if states > max_states:
            return greedy_string_assembly_pathway(
                target,
                note=f"exact search exceeded max_states {max_states}",
            )

        pieces = sorted(state, key=lambda s: (len(s), s))
        candidates: list[AssemblyStep] = []
        for left in pieces:
            for right in pieces:
                product = left + right
                if product in allowed and product not in state:
                    candidates.append(AssemblyStep(left=left, right=right, product=product))

        # Prefer useful long products first within this BFS depth; BFS still
        # guarantees minimal step count because every edge adds exactly one
        # constructed object.
        candidates.sort(key=lambda st: (-len(st.product), st.product, st.left, st.right))

        for step in candidates:
            next_steps = steps + (step,)
            if step.product == target:
                return AssemblyPathway(
                    target=target,
                    assembly_index=len(next_steps),
                    alphabet=alphabet,
                    steps=next_steps,
                    exact=True,
                    notes=("shortest pathway in bounded string assembly space",),
                )
            next_state = frozenset((*state, step.product))
            if next_state not in seen:
                seen.add(next_state)
                queue.append((next_state, next_steps))

    raise RuntimeError(f"target {target!r} was unreachable from its alphabet")


def greedy_string_assembly_pathway(target: str, *, note: str = "greedy fallback") -> AssemblyPathway:
    """Greedy reuse-heavy pathway for longer strings.

    This is a fallback only. It repeatedly builds the longest target substring
    that can be made from already-built pieces, then finishes the target.
    """
    target = _normalize_biocode(target)
    alphabet = tuple(sorted(set(target)))
    state = set(alphabet)
    steps: list[AssemblyStep] = []
    allowed = _all_substrings(target)

    while target not in state:
        best: AssemblyStep | None = None
        for left in sorted(state, key=len, reverse=True):
            for right in sorted(state, key=len, reverse=True):
                product = left + right
                if product in allowed and product not in state:
                    candidate = AssemblyStep(left=left, right=right, product=product)
                    if best is None or len(candidate.product) > len(best.product):
                        best = candidate
        if best is None:
            # Always possible to extend a prefix by one symbol.
            prefix = max((p for p in state if target.startswith(p)), key=len)
            next_symbol = target[len(prefix)]
            best = AssemblyStep(left=prefix, right=next_symbol, product=prefix + next_symbol)
        state.add(best.product)
        steps.append(best)
        if len(steps) > max(2 * len(target), 1):
            raise RuntimeError(f"greedy assembly stalled for {target!r}")

    return AssemblyPathway(
        target=target,
        assembly_index=len(steps),
        alphabet=alphabet,
        steps=tuple(steps),
        exact=False,
        notes=(note, "upper bound only; use exact mode for small targets"),
    )


def assembly_equation(copy_numbers: Mapping[str, int], assembly_indices: Mapping[str, int]) -> float:
    """Nature 2023 assembly equation for an observed ensemble.

    A = sum_i exp(a_i) * ((n_i - 1) / N_T)
    Copy number one contributes zero: a single complex object is not enough to
    infer selection without repeated production.
    """
    total = sum(max(0, int(n)) for n in copy_numbers.values())
    if total <= 0:
        return 0.0
    value = 0.0
    for obj, n_raw in copy_numbers.items():
        n = max(0, int(n_raw))
        if n <= 1:
            continue
        ai = int(assembly_indices[obj])
        value += math.exp(ai) * ((n - 1) / total)
    return value


def analyze_ensemble(
    observations: Mapping[str, int] | Iterable[str],
    *,
    exact_max_len: int = 14,
) -> EnsembleAssembly:
    """Compute symbolic pathways and copy-number assembly for observations."""
    if isinstance(observations, Mapping):
        copy_numbers = {
            _normalize_biocode(obj): max(0, int(n))
            for obj, n in observations.items()
            if int(n) > 0
        }
    else:
        copy_numbers: dict[str, int] = {}
        for obj in observations:
            norm = _normalize_biocode(obj)
            copy_numbers[norm] = copy_numbers.get(norm, 0) + 1

    pathways = {
        obj: exact_string_assembly_pathway(obj, max_len=exact_max_len)
        for obj in copy_numbers
    }
    ai = {obj: path.assembly_index for obj, path in pathways.items()}
    assembly = assembly_equation(copy_numbers, ai)
    return EnsembleAssembly(
        pathways=pathways,
        copy_numbers=copy_numbers,
        assembly=assembly,
        log10_selection_score=math.log10(1.0 + assembly),
    )


def growth_step(counts_by_index: Mapping[int, float], *, alpha: float, kd: float, dt: float = 1.0) -> dict[int, float]:
    """One Euler step of dN(a+1)/dt = k_d * N(a)^alpha.

    alpha=1 is unbiased historical reuse; 0<=alpha<1 models selected narrowing
    of available pathways in the Nature 2023 formulation.
    """
    if alpha < 0:
        raise ValueError("alpha must be non-negative")
    out = {int(k): max(0.0, float(v)) for k, v in counts_by_index.items()}
    for a, count in list(out.items()):
        if count <= 0:
            continue
        out[a + 1] = out.get(a + 1, 0.0) + kd * (count ** alpha) * dt
    return dict(sorted(out.items()))


def biocode_demo() -> dict[str, Any]:
    """Small public demo payload for Sara/Assembly UI layers."""
    observations = {
        "ABCD": 1,       # one complex object, no copy-number evidence
        "ABABABAB": 12,  # repeated object with reuse path
        "ACGTACGT": 8,   # DNA-like repeated biocode
    }
    ensemble = analyze_ensemble(observations)
    growth = {0: 16.0}
    for _ in range(4):
        growth = growth_step(growth, alpha=0.65, kd=0.5)
    return {
        "schema": "SIFTA_ASSEMBLY_BIOCODE_DEMO_V1",
        "research": {
            "nature_2023_doi": NATURE_2023_DOI,
            "entropy_2022_doi": ENTROPY_2022_DOI,
            "claim": "symbolic assembly-space analogue for SIFTA biocode",
        },
        "ensemble": ensemble.as_dict(),
        "growth_alpha_0_65": growth,
        "honest_gap": (
            "Symbolic biocode assembly is executable math for SIFTA. It is not "
            "a replacement for molecular fragmentation graphs or mass-spec "
            "assembly-index measurement."
        ),
    }


__all__ = [
    "AssemblyPathway",
    "AssemblyStep",
    "EnsembleAssembly",
    "TRUTH_LABEL",
    "analyze_ensemble",
    "assembly_equation",
    "biocode_demo",
    "exact_string_assembly_pathway",
    "greedy_string_assembly_pathway",
    "growth_step",
]


if __name__ == "__main__":
    print(json.dumps(biocode_demo(), indent=2, sort_keys=True))
